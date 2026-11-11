"""Transparent RRG-style approximations (NOT the proprietary JdK calculation).

Important contractual properties:
- all ETFs use ONE common benchmark for the map;
- 10/30/9 SMA is a reproducible public approximation;
- a 4-day tail affects DISPLAY ONLY, not calculation;
- raw history before the selected end date is retained for warm-up;
- no forward-filled missing ETF/index bars, no future information.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

RRG_SMA = 'SMA10_30_9'
RRG_LEGACY = 'EMA14_36_5'
METHOD_LABELS = {RRG_SMA: '公开RRG近似 · SMA(10/30/9)',
                 RRG_LEGACY: 'USERM旧公式 · EMA(14/36)+5日'}


def classify_quadrant(x: pd.Series, y: pd.Series) -> pd.Series:
    out = pd.Series('NA', index=x.index, dtype='object')
    valid = x.notna() & y.notna()
    out.loc[valid & (x >= 100) & (y >= 100)] = 'LEADING'
    out.loc[valid & (x >= 100) & (y < 100)] = 'WEAKENING'
    out.loc[valid & (x < 100) & (y >= 100)] = 'IMPROVING'
    out.loc[valid & (x < 100) & (y < 100)] = 'LAGGING'
    return out


def rrg_series(close: pd.Series, benchmark: pd.Series, method: str = RRG_SMA) -> pd.DataFrame:
    """Use matching trading dates; no filling a missing observation.

    SMA approximation:
      RS = close / benchmark
      X  = 100 * SMA10(RS) / SMA30(RS)
      Y  = 100 * X / SMA9(X)
    Note: no known public implementation guarantees StockCharts JdK identity.
    """
    close = pd.to_numeric(close, errors='coerce').astype(float)
    benchmark = pd.to_numeric(benchmark.reindex(close.index), errors='coerce').astype(float)
    relative = close.where(close > 0) / benchmark.where(benchmark > 0)
    relative = relative.replace([np.inf, -np.inf], np.nan)
    if method == RRG_SMA:
        short = relative.rolling(10, min_periods=10).mean()
        long = relative.rolling(30, min_periods=30).mean()
        x = 100 * short / long.where(long > 0)
        y = 100 * x / x.rolling(9, min_periods=9).mean()
    elif method == RRG_LEGACY:
        log_rel = np.log(relative.where(relative > 0))
        short = log_rel.ewm(span=14, adjust=False, min_periods=14).mean()
        long = log_rel.ewm(span=36, adjust=False, min_periods=36).mean()
        x = 100 * np.exp(short - long)
        y = 100 * x / x.shift(5)
    else:
        raise ValueError(f'Unknown RRG method: {method}')
    return pd.DataFrame({'rs_ratio': x, 'rs_momentum': y,
                         'quadrant': classify_quadrant(x, y), 'raw_relative': relative})


def attach_common_rrg(signals: pd.DataFrame, quotes: pd.DataFrame,
                      etf_mapping: pd.DataFrame, benchmark: pd.Series,
                      method: str = RRG_SMA) -> pd.DataFrame:
    """Replace plot-only RRG columns; retain old peer scores for audit.

    The chosen observation-period return/rank remains peer-relative and does not
    depend on the common map benchmark.
    """
    result = signals.copy()
    result['peer_rs_ratio_legacy'] = result['rs_ratio']
    result['peer_rs_momentum_legacy'] = result['rs_momentum']
    mapframe = quotes.merge(etf_mapping[['etf', 'symbol']], on='symbol', validate='many_to_one')
    benchmark = benchmark.copy()
    benchmark.index = pd.to_datetime(benchmark.index)
    benchmark = benchmark.sort_index()
    observations = []
    full_sessions = pd.DatetimeIndex(sorted(pd.to_datetime(quotes['date']).unique()))
    for etf, group in mapframe.groupby('etf', sort=True):
        group = group.sort_values('date').drop_duplicates('date', keep='last')
        close = group.set_index('date')['close'].astype(float).reindex(full_sessions)
        # compute over full historical ETF calendar, not clipped to 3 mo/Tail4
        r = rrg_series(close, benchmark, method)
        r = r[['rs_ratio', 'rs_momentum', 'quadrant', 'raw_relative']].reset_index()
        r.rename(columns={r.columns[0]: 'date'}, inplace=True)
        r['etf'] = etf
        observations.append(r)
    joined = pd.concat(observations, ignore_index=True)
    result = result.drop(columns=['rs_ratio','rs_momentum','quadrant']).merge(
        joined, on=['etf','date'], how='left', validate='many_to_one')
    result['quadrant'] = result['quadrant'].fillna('NA')
    return result
