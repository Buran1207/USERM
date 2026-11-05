"""USERM ETF relative strength, RRG coordinates and chosen-horizon performance.

All inputs are completed historical bars already present in the offline snapshot.
No forward-fills, no ML and no L1–L4 trading triggers. RRG is an independent
transparent approximation, not licensed JdK RS-Ratio/RS-Momentum.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from .config import RotationConfig, CONFIG


def _quadrant(x: pd.Series, y: pd.Series) -> pd.Series:
    out = pd.Series('NA', index=x.index, dtype=object)
    ok = x.notna() & y.notna()
    out.loc[ok & (x >= 100) & (y >= 100)] = 'LEADING'
    out.loc[ok & (x >= 100) & (y < 100)] = 'WEAKENING'
    out.loc[ok & (x < 100) & (y >= 100)] = 'IMPROVING'
    out.loc[ok & (x < 100) & (y < 100)] = 'LAGGING'
    return out


def _one_etf(bars: pd.DataFrame, peer_index: pd.Series, cfg: RotationConfig) -> pd.DataFrame:
    d = bars.sort_index().copy()
    px = d['close']
    peer = peer_index.reindex(d.index)
    log_rs = np.log(px.where(px > 0)) - np.log(peer.where(peer > 0))
    fast = log_rs.ewm(span=cfg.rs_fast_ema, adjust=False, min_periods=cfg.rs_fast_ema).mean()
    slow = log_rs.ewm(span=cfg.rs_slow_ema, adjust=False, min_periods=cfg.rs_slow_ema).mean()
    d['rs_ratio'] = 100 * np.exp(fast - slow)
    d['rs_momentum'] = 100 * d['rs_ratio'] / d['rs_ratio'].shift(cfg.rs_momentum_lag)
    d['quadrant'] = _quadrant(d['rs_ratio'], d['rs_momentum'])
    for h in (1, 5, 10, 20, 60):
        # Backward-looking reference columns; selectable period is calculated separately.
        d[f'ret_{h}'] = px / px.shift(h) - 1
        d[f'peer_ret_{h}'] = peer / peer.shift(h) - 1
        d[f'rel_{h}'] = d[f'ret_{h}'] - d[f'peer_ret_{h}']
    for h in (20, 50):
        d[f'ma_{h}'] = px.rolling(h, min_periods=h).mean()
    d['rvol_20'] = d['volume'] / d['volume'].rolling(cfg.rvol_window, min_periods=cfg.rvol_window).mean().shift(1).replace(0, np.nan)
    d['benchmark_close'] = peer
    return d


def calculate_etf_signals(quotes: pd.DataFrame, master: pd.DataFrame, cfg: RotationConfig = CONFIG) -> pd.DataFrame:
    """Build a historical, fixed peer-group benchmark for each of 20 ETFs."""
    from .data import table
    mapping = table('etf_codes.csv').dropna(subset=['symbol'])
    q = quotes.merge(mapping, on='symbol', how='inner', validate='many_to_one')
    q = q.merge(master[['etf', 'group', 'name_zh']], on='etf', how='inner', validate='many_to_one')
    if q.empty:
        raise ValueError('20只ETF无可用行情 / No ETF daily bars matched the universe')
    names = master.set_index('etf')
    results = []
    for family, group in q.groupby('group', sort=False):
        close = group.pivot(index='date', columns='etf', values='close').sort_index()
        peer_returns = close.pct_change(fill_method=None)
        for code, bars in group.groupby('etf'):
            peers = peer_returns.drop(columns=[code])
            pr = peers.mean(axis=1)
            pr.loc[peers.count(axis=1) < cfg.min_peer_returns] = np.nan
            # Missing day is *not* carried as valid. The cumulative index merely
            # holds its internal level through gaps; observations stay missing.
            benchmark = 100 * (1 + pr.fillna(0)).cumprod()
            benchmark.loc[pr.isna()] = np.nan
            result = _one_etf(bars.set_index('date'), benchmark, cfg).reset_index()
            result['etf'] = code
            result['group'] = family
            result['name_zh'] = names.loc[code, 'name_zh']
            result['peer_count'] = peers.count(axis=1).reindex(result.date).to_numpy()
            results.append(result)
    return pd.concat(results, ignore_index=True).sort_values(['date', 'group', 'etf']).reset_index(drop=True)


def _reference_dates(dates: pd.Series, calendar: pd.DatetimeIndex, n: int) -> list:
    """Exactly n market sessions ago; never use n-th available ETF quote instead."""
    positions = calendar.get_indexer(pd.to_datetime(dates))
    return [calendar[i - n] if i >= n else pd.NaT for i in positions]


def latest_table(signals: pd.DataFrame, asof, calendar: pd.DatetimeIndex,
                 observation_days: int = 20, max_stale_sessions: int = 2) -> pd.DataFrame:
    """EOD snapshot; chosen slider controls main return, excess and rank columns.

    An ETF missing the selected date remains visible as *stale* but never takes
    part in the selected-date ranking, even if the gap is only one session.
    """
    if not 1 <= int(observation_days) <= 60:
        raise ValueError('observation_days must be between 1 and 60')
    n = int(observation_days)
    asof = pd.Timestamp(asof)
    current = signals.loc[signals.date <= asof].sort_values('date').groupby('etf', as_index=False).tail(1).copy()
    if current.empty:
        return current
    current['age_sessions'] = [int(((calendar > day) & (calendar <= asof)).sum()) for day in current.date]
    current['fresh'] = current['age_sessions'].eq(0)
    current['within_tolerance'] = current['age_sessions'].le(max_stale_sessions)
    current['reference_date'] = _reference_dates(current.date, calendar, n)
    ref = signals[['etf', 'date', 'close', 'benchmark_close']].rename(columns={
        'date': 'reference_date', 'close': 'close_start', 'benchmark_close': 'peer_start'
    })
    current = current.merge(ref, on=['etf', 'reference_date'], how='left', validate='one_to_one')
    current['ret_window'] = current['close'] / current['close_start'] - 1
    current['peer_ret_window'] = current['benchmark_close'] / current['peer_start'] - 1
    current['rel_window'] = current['ret_window'] - current['peer_ret_window']
    current['observation_days'] = n
    # Exclude stale and incomplete bars from *current* ranks, no forward filling.
    current.loc[~current.fresh, ['ret_window', 'peer_ret_window', 'rel_window']] = np.nan
    current['rotation_score'] = current.groupby('group')['rel_window'].rank(pct=True, ascending=True) * 100
    current['rotation_rank'] = current.groupby('group')['rel_window'].rank(ascending=False, method='min')
    return current.sort_values(['group', 'rotation_rank', 'etf'], na_position='last').reset_index(drop=True)


def window_series(signals: pd.DataFrame, symbol: str, asof,
                  calendar: pd.DatetimeIndex, observation_days: int) -> pd.DataFrame:
    """Chart panel on market-session calendar (missing dates stay NaN)."""
    sessions = calendar[calendar <= pd.Timestamp(asof)]
    d = signals[(signals.etf == symbol) & (signals.date <= pd.Timestamp(asof))].set_index('date').sort_index()
    aligned = d.reindex(sessions)
    n = int(observation_days)
    aligned['ret_window'] = aligned['close'] / aligned['close'].shift(n) - 1
    aligned['peer_ret_window'] = aligned['benchmark_close'] / aligned['benchmark_close'].shift(n) - 1
    aligned['rel_window'] = aligned['ret_window'] - aligned['peer_ret_window']
    aligned.index.name = 'date'
    return aligned.reset_index().tail(260)
