"""USERM public-source EOD updater; full-history, single-vendor adjusted snapshot.
Yahoo access is experimental and subject to data rights. Never mix CPS2 and Yahoo.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import exchange_calendars as xcals
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.refresh_data import last_safe_session

DATA = ROOT / 'data'
SOURCE = 'Yahoo Finance via yfinance'
BUFFER = 20
START = '2020-01-01'
COLS = ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'partition']
FILES = ['etf_prices.csv.gz', 'spy_prices.csv.gz', 'snapshot_manifest.json', 'spy_snapshot_manifest.json']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sessions(start, end):
    idx = xcals.get_calendar('XNYS').sessions_in_range(pd.Timestamp(start), pd.Timestamp(end))
    return pd.DatetimeIndex(idx).tz_localize(None).normalize()


def normalize(raw, symbol, cutoff, old_dates):
    """Use Adj Close / Close for all OHLC, anchored at last eligible session.
    Yahoo close is already split-adjusted; volume remains as delivered.
    """
    if raw is None or raw.empty:
        raise ValueError(f'{symbol}: empty Yahoo response')
    names = ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
    if set(names) - set(raw.columns):
        raise ValueError(f'{symbol}: missing Yahoo fields {set(names)-set(raw.columns)}')
    raw = raw[names].copy()
    idx = pd.DatetimeIndex(raw.index)
    # yfinance ticker.history uses exchange-local timezone for daily bars.
    raw.index = idx.tz_localize(None).normalize()
    target = pd.Timestamp(cutoff)
    raw = raw.loc[(raw.index >= pd.Timestamp(START)) & (raw.index <= target)].sort_index()
    if raw.empty or raw.index[-1] != target or raw.index.has_duplicates:
        raise ValueError(f'{symbol}: missing target {cutoff} or duplicate bars')
    raw = raw.apply(pd.to_numeric, errors='coerce')
    if not np.isfinite(raw.to_numpy()).all():
        raise ValueError(f'{symbol}: nonfinite/missing OHLCV or Adj Close')
    if (raw[names[:5]] <= 0).any().any() or (raw.Volume < 0).any() or raw.Volume.iloc[-1] <= 0:
        raise ValueError(f'{symbol}: invalid prices/volume')
    if ((raw.High+1e-8 < raw[['Open','Close','Low']].max(axis=1)) | (raw.Low-1e-8 > raw[['Open','Close','High']].min(axis=1))).any():
        raise ValueError(f'{symbol}: inconsistent OHLC')
    missing = pd.DatetimeIndex(old_dates).difference(raw.index)
    if len(missing):
        raise ValueError(f'{symbol}: would lose {len(missing)} original dates, e.g. {missing[:3].tolist()}')
    expected = sessions(raw.index[0], target)
    if not raw.index.equals(expected):
        raise ValueError(f'{symbol}: calendar gap or unexpected session; missing={expected.difference(raw.index)[:5].tolist()} extra={raw.index.difference(expected)[:5].tolist()}')
    ratio = raw['Adj Close'] / raw.Close
    factor = ratio / ratio.iloc[-1]
    out = raw[['Open','High','Low','Close']].mul(factor, axis=0).rename(columns=str.lower)
    out['volume'] = raw.Volume
    out['date'] = out.index.strftime('%Y-%m-%d')
    out['symbol'] = symbol
    out['partition'] = np.where(out.index.year < 2026, 'TRAIN', 'OOS')
    return out[COLS].reset_index(drop=True)


def download(ticker, cutoff):
    import yfinance as yf
    end = (pd.Timestamp(cutoff) + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
    return yf.Ticker(ticker).history(start=START, end=end, interval='1d',
        auto_adjust=False, back_adjust=False, actions=False, prepost=False,
        repair=True, keepna=True, timeout=30, raise_errors=True)


def fetch_one(ticker, symbol, cutoff, old_dates, fetch=download):
    error = None
    for attempt in range(2):
        try:
            return normalize(fetch(ticker, cutoff), symbol, cutoff, old_dates)
        except Exception as exc:
            error = exc
            print(f'[RETRY] {ticker} attempt {attempt+1}: {exc}', flush=True)
            if attempt == 0:
                time.sleep(3)
    raise RuntimeError(f'{ticker}: failed; previous snapshot retained') from error


def overlap_audit(old, new):
    a = old.set_index('date').close.astype(float).sort_index()
    b = new.set_index('date').close.astype(float).sort_index()
    common = a.index.intersection(b.index)
    if len(common) < 2:
        return {'common_rows': len(common)}
    delta = (a.loc[common].pct_change() - b.loc[common].pct_change()).abs().dropna()*10000
    return {'common_rows': len(common), 'median_abs_daily_return_diff_bp': round(float(delta.median()), 4),
            'max_abs_daily_return_diff_bp': round(float(delta.max()), 4)}


def refresh(data=DATA, now=None, fetch=download, force=False):
    cutoff = last_safe_session(now, buffer_minutes=BUFFER)
    old_etf = pd.read_csv(data/'etf_prices.csv.gz', dtype={'date':str, 'symbol':str})
    old_spy = pd.read_csv(data/'spy_prices.csv.gz', dtype={'date':str})
    old_meta = json.loads((data/'snapshot_manifest.json').read_text(encoding='utf-8'))
    if cutoff < max(old_etf.date.max(), old_spy.date.max()):
        print('[SKIP] latest safe session precedes existing snapshot; no downgrade')
        return False
    mapping = pd.read_csv(data/'etf_codes.csv', encoding='utf-8-sig')
    master = pd.read_csv(data/'etfs.csv', encoding='utf-8-sig')
    if len(mapping) != 20 or mapping.etf.nunique()!=20 or mapping.symbol.nunique()!=20 or set(mapping.etf)!=set(master.etf) or 'SPY' in set(mapping.etf):
        raise ValueError('invalid 20 ETF mapping; SPY must remain independent')
    if any(s.split('.')[0] != e for e,s in zip(mapping.etf,mapping.symbol)):
        raise ValueError('ticker mapping mismatch')
    if set(old_etf.symbol) != set(mapping.symbol):
        raise ValueError('original snapshot and universe mismatch')
    if not force and old_meta.get('source') == SOURCE and old_meta.get('published_last_complete_21_session')==cutoff:
        checks = old_meta.get('sha256',{})
        if (data/FILES[3]).exists() and all(checks.get(f)==sha(data/f) for f in FILES[:2]):
            print(f'[SKIP] already published complete Yahoo EOD {cutoff}')
            return False
    print(f'[PLAN] {cutoff} | 20 ETFs + SPY | full history; no CPS2 splice', flush=True)
    frames, audit = [], {}
    for ticker, symbol in zip(mapping.etf,mapping.symbol):
        old = old_etf.loc[old_etf.symbol==symbol]
        frame = fetch_one(ticker, symbol, cutoff, pd.to_datetime(old.date), fetch)
        frames.append(frame)
        audit[ticker] = overlap_audit(old, frame)
        print(f'[PASS] {ticker}: {len(frame)} bars {frame.date.min()}..{frame.date.max()}', flush=True)
    spy = fetch_one('SPY', 'SPY.P', cutoff, pd.to_datetime(old_spy.date), fetch)[['date','close']]
    audit['SPY'] = overlap_audit(old_spy, spy)
    etf = pd.concat(frames, ignore_index=True).sort_values(['symbol','date'])
    if len(etf.symbol.unique()) != 20 or etf.groupby('symbol').date.max().ne(cutoff).any() or spy.date.max()!=cutoff:
        raise RuntimeError('21-way latest-session check failed')
    meta = {'name':'USERM 20 ETF + SPY benchmark EOD snapshot','schema':'USERM-ETF-SPY-v1',
        'source': SOURCE, 'source_path_type':'public network', 'generated_utc':datetime.now(timezone.utc).isoformat(),
        'adjustment':'Yahoo split-adjusted OHLC multiplied by (Adj Close / Close) normalized to most recent eligible session; dividends included; volume as reported',
        'rrg_benchmark':'SPY','universe':'20 target ETFs; SPY benchmark only', 'eod_buffer_minutes':BUFFER,
        'last_safe_nyse_session':cutoff,'published_last_complete_21_session':cutoff,
        'etfs':{'rows':len(etf),'symbols_found':20,'symbols_requested':20,'invalid_rows':0,
            'partition_rows':{k:int(v) for k,v in etf.partition.value_counts().items()},
            'min_date':etf.date.min(),'max_date':cutoff,'latest_by_symbol':etf.groupby('symbol').date.max().to_dict()},
        'spy':{'symbol':'SPY.P','rows':len(spy),'invalid_rows':0,'min_date':spy.date.min(),'max_date':cutoff},
        'overlap_audit_previous_snapshot':audit,'previous_source':old_meta.get('source'),
        'warnings':['Vendor adjustment/volume and past signals can differ from CPS2; research use and redistribution subject to data rights.']}
    with tempfile.TemporaryDirectory(prefix='.public_',dir=data) as temp:
        stage = Path(temp)
        for name, frame in zip(FILES[:2], (etf,spy)):
            frame.to_csv(stage/name,index=False,compression={'method':'gzip','compresslevel':3,'mtime':0})
            check = pd.read_csv(stage/name)
            if len(check)!=len(frame) or check.isna().any().any():
                raise RuntimeError(f'Staged {name} verification failed')
        meta['sha256'] = {f:sha(stage/f) for f in FILES[:2]}
        (stage/FILES[2]).write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        spy_meta = {'schema':'USERM-SPY-ETF-BENCHMARK-v1', 'ticker':'SPY', 'source':SOURCE,
            'adjustment':meta['adjustment'], 'last_safe_session':cutoff, 'generated_utc':meta['generated_utc'],
            **meta['spy'], 'sha256':meta['sha256'][FILES[1]]}
        (stage/FILES[3]).write_text(json.dumps(spy_meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        backup = stage/'old'; backup.mkdir()
        for name in FILES:
            if (data/name).exists(): shutil.copy2(data/name,backup/name)
        replaced=[]
        try:
            for name in FILES:
                os.replace(stage/name,data/name); replaced.append(name)
        except Exception:
            for name in reversed(replaced):
                if (backup/name).exists(): os.replace(backup/name,data/name)
                else: (data/name).unlink(missing_ok=True)
            raise
    print(f'[SUCCESS] {cutoff}: {len(etf)} ETF + {len(spy)} SPY bars; all 21 valid')
    return True


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--force',action='store_true',help='Recheck even if latest snapshot already published')
    args=p.parse_args()
    # Prevent accidental public redistribution through automated deployment.
    if os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('USERM_DATA_AUTHORIZED')!='yes':
        sys.exit('Data rights gate: set USERM_DATA_AUTHORIZED=yes only after confirming use and redistribution rights.')
    refresh(force=args.force)
