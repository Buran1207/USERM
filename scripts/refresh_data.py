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


def publish(mapped: dict, rows: list, info: dict, cutoff: str, source_type: str):
    DATA.mkdir(parents=True, exist_ok=True)
    snapshot_path = DATA / 'etf_prices.csv.gz'
    mapping_path = DATA / 'etf_codes.csv'
    manifest_path = DATA / 'snapshot_manifest.json'
    existing = {}
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding='utf-8'))
    old_latest = existing.get('etfs',{}).get('max_date','')
    if old_latest and info['max_date'] < old_latest:
        raise RuntimeError(f'New snapshot ends {info["max_date"]}, before existing {old_latest}; refusing downgrade')
    manifest = {
        'name':'USERM 20 ETF only snapshot',
        'schema':'USERM-ETF-v1',
        'generated_utc':datetime.now(timezone.utc).isoformat(),
        'source':'preexisting local CPS:2 daily files; no iFinD API calls',
        'source_path_type':source_type,
        'adjustment':'CPS:2 as labeled by source; total return handling not independently verified',
        'universe':'11 sector ETFs and 9 tech-theme ETFs; no individual stocks',
        'last_safe_nyse_session':cutoff,
        'published_last_complete_etf_session':info['max_date'],
        'etfs':info,
        'warnings':[]}
    # Stage then replace. Existing data stays unchanged if parsing fails.
    stage_dir = Path(tempfile.mkdtemp(prefix='.userm_etf_',dir=DATA))
    try:
        new_quotes = stage_dir / 'etf_prices.csv.gz'
        with gzip.open(new_quotes,'wt',encoding='utf-8',newline='',compresslevel=3) as handle:
            writer = csv.DictWriter(handle,fieldnames=COLUMNS,lineterminator='\n')
            writer.writeheader(); writer.writerows(rows)
        new_codes = stage_dir / 'etf_codes.csv'
        with new_codes.open('w',encoding='utf-8-sig',newline='') as handle:
            writer = csv.writer(handle);writer.writerow(['etf','symbol'])
            writer.writerows(sorted(mapped.items()))
        new_manifest = stage_dir / 'snapshot_manifest.json'
        new_manifest.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        # Verify staged gzip and full ticker mapping before replacing files.
        with gzip.open(new_quotes,'rt',encoding='utf-8') as handle:
            n = sum(1 for _ in handle) - 1
        if n != info['rows'] or len(mapped) != 20 or info['symbols_found'] != 20:
            raise RuntimeError('Staged ETF snapshot validation failed')
        os.replace(new_quotes,snapshot_path)
        os.replace(new_codes,mapping_path)
        os.replace(new_manifest,manifest_path)
    finally:
        import shutil
        shutil.rmtree(stage_dir, ignore_errors=True)
    print(f'SUCCESS: {info["symbols_found"]}/20 ETFs, {info["rows"]:,} bars, '
          f'{info["min_date"]} -> {info["max_date"]}, NYSE safe cutoff {cutoff}')
    print('Upload to GitHub main/data:',snapshot_path.name,mapping_path.name,manifest_path.name)


def run(opts):
    # Critical: determine the *live* cutoff before inspecting raw snapshots.
    cutoff = last_safe_session()
    source = Source(Path(opts.source) if opts.source else None,
                    Path(opts.cps2_zip) if opts.cps2_zip else None)
    try:
        mapped, rows, info = make_snapshot(source, cutoff)
    finally:
        source.close()
    publish(mapped,rows,info,cutoff,'archive' if opts.cps2_zip else 'local directory')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--source',help=r'C:\code\DATA\US\data (contains cps2_adjusted/train & oos)')
    group.add_argument('--cps2-zip',help='Existing local CPS:2 zip archive')
    run(parser.parse_args())
