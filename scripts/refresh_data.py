r"""ETF-only offline snapshot refresh from locally downloaded CPS:2 daily bars.

  py -3.12 scripts\refresh_data.py --source "C:\code\DATA\US\data"
  python scripts/refresh_data.py --cps2-zip /path/to/cps2_adjusted.zip

Never calls iFinD or fetches network data. Excludes any session which has not
closed at NYSE, plus a 90-minute EOD buffer. Requires complete 20-ETF coverage
on the latest published session and rejects stale snapshot overwrites.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import os
import re
import tempfile
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import exchange_calendars as xcals
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
COLUMNS = ['date','symbol','open','high','low','close','volume','partition']


def last_safe_session(now_utc: datetime | None = None, buffer_minutes: int = 90) -> str:
    """Last NYSE session whose *actual scheduled* close is over 90 min ago.

    NYSE includes normal holiday, early-close and DST schedules; therefore
    do not infer a US close from a fixed clock time or weekday arithmetic.
    """
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('now_utc must be timezone-aware')
    now = now.astimezone(timezone.utc)
    cal = xcals.get_calendar('XNYS')
    end = pd.Timestamp(now.date())
    start = end - pd.Timedelta(days=35)
    sessions = cal.sessions_in_range(start, end)
    for session in reversed(sessions):
        close = cal.session_close(session).to_pydatetime().astimezone(timezone.utc)
        if now >= close + timedelta(minutes=buffer_minutes):
            return session.date().isoformat()
    raise RuntimeError('No safely completed NYSE session in the past 35 days')


class Source:
    def __init__(self, source: Path | None, archive_path: Path | None):
        self.archive = zipfile.ZipFile(archive_path) if archive_path else None
        if self.archive is not None:
            filenames = [n for n in self.archive.namelist() if n.lower().endswith('.csv.gz')]
        else:
            if source is None or not source.is_dir():
                raise FileNotFoundError(f'Local CPS2 directory does not exist: {source}')
            filenames = list(source.rglob('*.csv.gz'))
        self.by_file = {}
        self.by_base = defaultdict(set)
        for path in filenames:
            name = str(path).replace('\\','/')
            match = re.search(r'/(train|oos)/(20\d\d)/([^/]+\.csv\.gz)$',name,re.I)
            if not match:
                continue
            partition, year, basename = match.groups()
            symbol = basename[:-7].upper()
            self.by_file[(symbol, int(year), partition.lower())] = path
            self.by_base[symbol.rsplit('.',1)[0]].add(symbol)
        print('Indexed CPS2 symbol-year files:', len(self.by_file))

    def resolve(self, symbol: str) -> str:
        symbol = str(symbol).upper().strip()
        choices = self.by_base.get(symbol, set())
        if symbol in choices:
            return symbol
        # Avoid arbitrary selection if exchange suffix is ambiguous.
        return next(iter(choices)) if len(choices) == 1 else ''

    def iter_bars(self, symbol: str):
        filenames = sorted((k for k in self.by_file if k[0] == symbol),key=lambda k:(k[1],k[2]))
        for _, year, partition in filenames:
            if (year < 2026 and partition != 'train') or (year >= 2026 and partition != 'oos'):
                continue
            path = self.by_file[(symbol,year,partition)]
            raw = self.archive.read(path) if self.archive else Path(path).read_bytes()
            with io.StringIO(gzip.decompress(raw).decode('utf-8-sig', errors='replace')) as handle:
                for row in csv.DictReader(handle):
                    yield row, partition.upper()

    def close(self):
        if self.archive:
            self.archive.close()


def read_csv(path: Path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def make_snapshot(source: Source, cutoff: str):
    universe = read_csv(DATA / 'etfs.csv')
    if len(universe) != 20 or len({r['etf'] for r in universe}) != 20:
        raise ValueError('etfs.csv must contain exactly 20 distinct ETF tickers')
    mapped = {r['etf']: source.resolve(r['etf']) for r in universe}
    missing = [etf for etf, symbol in mapped.items() if not symbol]
    if missing:
        raise ValueError(f'ETF source files missing or ambiguous: {missing}')
    all_rows = []
    invalid = 0
    seen_dates = defaultdict(set)
    for etf, symbol in sorted(mapped.items()):
        keyed = {}
        for raw, partition in source.iter_bars(symbol):
            try:
                dt = str(raw['date']).strip()[:10]
                parsed = datetime.strptime(dt,'%Y-%m-%d')
                if parsed.year < 2020 or dt > cutoff:
                    continue
                close = float(raw['close'])
                if not (close > 0):
                    raise ValueError('Nonpositive close')
                keyed[dt] = dict(date=dt,symbol=symbol,
                                 open=raw.get('open',''),high=raw.get('high',''),
                                 low=raw.get('low',''),close=raw['close'],
                                 volume=raw.get('volume',''),partition=partition)
            except (KeyError,TypeError,ValueError,OverflowError):
                invalid += 1
        for dt, item in keyed.items():
            seen_dates[dt].add(etf)
            all_rows.append(item)
    # Do not publish an incompletely collected latest session. First find the
    # most recent session on which *all* 20 ETF prices are available.
    complete = [date for date, etfs in seen_dates.items() if len(etfs) == 20]
    if not complete:
        raise RuntimeError('No single session with 20/20 ETF records; refusing overwrite')
    latest = max(complete)
    all_rows = sorted((r for r in all_rows if r['date'] <= latest),
                      key=lambda r:(r['symbol'],r['date']))
    if not all_rows:
        raise RuntimeError('No valid ETF historical data at cutoff')
    seen = defaultdict(list)
    bypart = {'TRAIN':0, 'OOS':0}
    for r in all_rows:
        seen[r['symbol']].append(r['date'])
        bypart[r['partition']] += 1
    info = {'rows':len(all_rows),'symbols_found':len(seen),
            'symbols_requested':len(mapped),'invalid_rows':invalid,
            'partition_rows':bypart,'min_date':min(r['date'] for r in all_rows),
            'max_date':latest,'latest_by_symbol':{s:max(dates) for s,dates in seen.items()}}
    return mapped, all_rows, info


def make_spy_snapshot(source: Source, cutoff: str, etf_latest: str,
                      explicit_symbol: str | None = None):
    """Read genuine SPY ETF prices from the same CPS2 directory as the 20 ETFs.

    The latest SPY bar MUST match the last complete 20/20 ETF session.  A
    stale/missing benchmark is an error, not permission to silently switch
    to an ETF20 benchmark or publish misaligned RRG coordinates.
    """
    symbol = (explicit_symbol or source.resolve('SPY')).strip().upper()
    if not symbol or symbol.rsplit('.', 1)[0] != 'SPY':
        raise ValueError('SPY source missing/ambiguous: ensure SPY.P or another SPY exchange '
                         'code exists under cps2_adjusted, or use --spy-symbol SPY.P')
    if isinstance(source, Source) and not any(k[0] == symbol for k in source.by_file):
        raise FileNotFoundError(f'SPY source ticker {symbol} not present in CPS2')
    keyed = {}
    invalid = 0
    for raw, partition in source.iter_bars(symbol):
        try:
            dt = str(raw['date']).strip()[:10]
            parsed = datetime.strptime(dt, '%Y-%m-%d')
            if parsed.year < 2020 or dt > cutoff or dt > etf_latest:
                continue
            close = float(raw['close'])
            if not (0 < close < float('inf')):
                raise ValueError('Invalid SPY close')
            keyed[dt] = {
                'date': dt, 'close': close, 'symbol': symbol,
                'partition': partition,
            }
        except (KeyError, TypeError, ValueError, OverflowError):
            invalid += 1
    rows = [keyed[d] for d in sorted(keyed)]
    if len(rows) < 50:
        raise RuntimeError(f'SPY only has {len(rows)} valid historical bars; at least 50 required')
    latest = rows[-1]['date']
    if latest != etf_latest:
        raise RuntimeError(f'SPY latest {latest} != latest complete 20-ETF session '
                           f'{etf_latest}; refusing to publish misaligned snapshots')
    return rows, {
        'symbol': symbol, 'rows': len(rows), 'invalid_rows': invalid,
        'min_date': rows[0]['date'], 'max_date': latest,
    }


def publish(mapped: dict, rows: list, info: dict, cutoff: str, source_type: str,
            spy_rows: list, spy_info: dict):
    """Stage and verify all four data files; restore backups if publishing fails."""
    DATA.mkdir(parents=True, exist_ok=True)
    if spy_info['max_date'] != info['max_date']:
        raise RuntimeError('SPY and ETF end dates must agree')
    paths = {name: DATA/name for name in
             ('etf_prices.csv.gz','spy_prices.csv.gz','etf_codes.csv','snapshot_manifest.json')}
    existing = {}
    if paths['snapshot_manifest.json'].exists():
        existing = json.loads(paths['snapshot_manifest.json'].read_text(encoding='utf-8'))
    old_dates = [existing.get('etfs',{}).get('max_date',''),
                 existing.get('spy',{}).get('max_date','')]
    # Check existing SPY file as well; legacy manifest may not record it.
    if paths['spy_prices.csv.gz'].exists():
        old = pd.read_csv(paths['spy_prices.csv.gz'], usecols=['date'])
        old_dates.append(str(old.date.max()))
    for old_last in old_dates:
        if old_last and info['max_date'] < old_last:
            raise RuntimeError(f'New snapshot ends {info["max_date"]}, before existing '
                               f'{old_last}; refusing downgrade')
    manifest = {
        'name': 'USERM 20 ETF + SPY benchmark EOD snapshot',
        'schema': 'USERM-ETF-SPY-v1',
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'source': 'preexisting local CPS:2 adjusted daily files; no iFinD API calls',
        'source_path_type': source_type,
        'adjustment': 'CPS:2 per source; dividend / total-return comparability not independently verified',
        'universe': '20 target ETFs; SPY is ONLY RRG benchmark, excluded from ranks',
        'rrg_benchmark': 'SPY',
        'last_safe_nyse_session': cutoff,
        'published_last_complete_21_session': info['max_date'],
        'etfs': info,
        'spy': spy_info,
        'warnings': [],
    }
    stage_dir = Path(tempfile.mkdtemp(prefix='.userm_etf_spy_', dir=DATA))
    try:
        etf_stage = stage_dir / 'etf_prices.csv.gz'
        with gzip.open(etf_stage,'wt',encoding='utf-8',newline='',compresslevel=3) as handle:
            writer=csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator='\n')
            writer.writeheader(); writer.writerows(rows)
        spy_stage = stage_dir / 'spy_prices.csv.gz'
        with gzip.open(spy_stage,'wt',encoding='utf-8',newline='',compresslevel=3) as handle:
            writer=csv.DictWriter(handle,fieldnames=['date','close'],lineterminator='\n')
            writer.writeheader(); writer.writerows([{'date':r['date'],'close':r['close']} for r in spy_rows])
        code_stage=stage_dir/'etf_codes.csv'
        with code_stage.open('w',encoding='utf-8-sig',newline='') as handle:
            writer=csv.writer(handle); writer.writerow(['etf','symbol']); writer.writerows(sorted(mapped.items()))
        manifest_stage=stage_dir/'snapshot_manifest.json'
        manifest_stage.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        with gzip.open(etf_stage,'rt',encoding='utf-8') as handle:
            etf_n=sum(1 for _ in handle)-1
        check_spy=pd.read_csv(spy_stage)
        if (etf_n != info['rows'] or len(mapped)!=20 or info['symbols_found'] != 20
                or len(check_spy) != spy_info['rows']
                or str(check_spy.date.iloc[-1]) != info['max_date']):
            raise RuntimeError('ETF/SPY staged snapshot verification failed')
        # Replace all as a group. If one rename fails, restore the prior set.
        backup = stage_dir / 'previous'
        backup.mkdir()
        replaced = []
        for name, dest in paths.items():
            if dest.exists():
                import shutil
                shutil.copy2(dest, backup/name)
        try:
            for name, dest in paths.items():
                os.replace(stage_dir/name, dest)
                replaced.append(name)
        except Exception:
            for name in reversed(replaced):
                restore = backup/name
                if restore.exists():
                    os.replace(restore, paths[name])
                else:
                    paths[name].unlink(missing_ok=True)
            raise
    finally:
        import shutil
        shutil.rmtree(stage_dir, ignore_errors=True)
    print(f'SUCCESS: 20 ETF + SPY; ETF bars {info["rows"]:,}; '
          f'SPY bars {spy_info["rows"]:,}; latest COMPLETE {info["max_date"]}; '
          f'safe NYSE cutoff {cutoff}')
    print('Upload all to GitHub main/data: etf_prices.csv.gz, spy_prices.csv.gz, '
          'etf_codes.csv, snapshot_manifest.json')


def run(opts):
    cutoff = last_safe_session()
    source = Source(Path(opts.source) if opts.source else None,
                    Path(opts.cps2_zip) if opts.cps2_zip else None)
    try:
        mapped, rows, info = make_snapshot(source, cutoff)
        spy_rows, spy_info = make_spy_snapshot(source, cutoff, info['max_date'],
                                               getattr(opts,'spy_symbol',None))
    finally:
        source.close()
    publish(mapped, rows, info, cutoff, 'archive' if opts.cps2_zip else 'local directory',
            spy_rows, spy_info)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--source',help=r'C:\code\DATA\US\data (contains cps2_adjusted/train & oos)')
    group.add_argument('--cps2-zip',help='Existing local CPS:2 zip archive')
    parser.add_argument('--spy-symbol',help='Exact ticker if multiple SPY exchange suffixes (e.g. SPY.P)')
    run(parser.parse_args())
