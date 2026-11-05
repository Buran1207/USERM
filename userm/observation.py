"""User-selectable trailing ETF returns, aligned to observed market sessions.

An observation horizon is a *display/ranking* parameter, separate from the
fixed L1-L4 signal engine. A missing session invalidates the window; there is
no forward fill and no use of data after the selected research date.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def add_etf_observation(snapshot: pd.DataFrame, signals: pd.DataFrame,
                        calendar: pd.DatetimeIndex, sessions: int) -> pd.DataFrame:
    if not 1 <= int(sessions) <= 60:
        raise ValueError("Observation sessions must be between 1 and 60")
    days = int(sessions)
    out = snapshot.copy()
    for field in ('obs_ret', 'obs_peer_ret', 'obs_rel', 'obs_rank'):
        out[field] = np.nan
    if out.empty:
        return out
    dates = pd.DatetimeIndex(calendar).sort_values().unique()
    # Only past/on-asof bars from the caller's research snapshot are considered.
    cutoff = pd.Timestamp(out['date'].max())
    relevant = signals.loc[signals.date.le(cutoff),
                           ['date', 'etf', 'close', 'benchmark_close']].copy()
    relevant['date'] = pd.to_datetime(relevant.date)
    blocks = {etf: group.set_index('date').sort_index()
              for etf, group in relevant.groupby('etf', sort=False)}
    for idx, row in out.iterrows():
        end = pd.Timestamp(row['date'])
        loc = dates.get_indexer([end])[0]
        if loc < days:
            continue
        expected = dates[loc-days:loc+1]
        available = blocks.get(row['etf'])
        if available is None:
            continue
        block = available.reindex(expected)
        vals = block[['close', 'benchmark_close']]
        if len(vals) != days+1 or vals.isna().any().any() or (vals <= 0).any().any():
            continue
        r = float(vals.close.iloc[-1] / vals.close.iloc[0] - 1)
        pr = float(vals.benchmark_close.iloc[-1] / vals.benchmark_close.iloc[0] - 1)
        out.at[idx, 'obs_ret'] = r
        out.at[idx, 'obs_peer_ret'] = pr
        out.at[idx, 'obs_rel'] = r-pr
    usable = out['fresh'] & out['obs_rel'].notna()
    out.loc[usable, 'obs_rank'] = (out.loc[usable]
                                 .groupby('group')['obs_rel']
                                 .rank(ascending=False, method='min'))
    return out.sort_values(['group', 'obs_rank', 'etf'], na_position='last')
