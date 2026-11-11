"""Verify GitHub-ready USERM files contain 20 ETF histories plus independent SPY EOD.

Run after REFRESH_ETF_AND_SPY.bat, before uploading data to GitHub.
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.refresh_data import last_safe_session
from userm.data import load_quotes, table, manifest
from userm.benchmarks import load_spy


def verify() -> None:
    mapping=table('etf_codes.csv')
    etfs=table('etfs.csv')
    if len(mapping)!=20 or mapping.etf.nunique()!=20 or len(etfs)!=20:
        raise RuntimeError('ETF mapping/universe must be 20 (SPY excluded)')
    if mapping.symbol.astype(str).str.upper().str.startswith('SPY.').any():
        raise RuntimeError('SPY incorrectly included among 20 tradable ETFs')
    prices=load_quotes()
    spy=load_spy()
    if spy is None:
        raise RuntimeError('Missing SPY benchmark: data/spy_prices.csv.gz')
    latest=prices.date.max()
    all_latest=prices.sort_values('date').groupby('symbol').date.max()
    if len(all_latest)!=20 or (all_latest!=latest).any():
        raise RuntimeError('Some of 20 ETF tickers have older latest bars')
    if spy.index.max()!=latest:
        raise RuntimeError(f'SPY latest {spy.index.max().date()} != ETFs {latest.date()}')
    safe=pd.Timestamp(last_safe_session())
    if latest>safe:
        raise RuntimeError(f'Unsafe intraday bar {latest.date()} beyond safe close {safe.date()}')
    meta=manifest()
    if meta.get('rrg_benchmark')!='SPY':
        raise RuntimeError('Manifest RRG benchmark not SPY; did you run the new refresh?')
    if str(meta.get('published_last_complete_21_session'))!=str(latest.date()):
        raise RuntimeError('Manifest date mismatches data date')
    print(f'PASS: 20 ETF tickers, {len(prices):,} ETF bars, '
          f'SPY {len(spy):,} bars, aligned EOD {latest.date()}')
    print('Upload four files: data/etf_prices.csv.gz, data/spy_prices.csv.gz, '
          'data/etf_codes.csv, data/snapshot_manifest.json')


if __name__=='__main__':
    verify()
