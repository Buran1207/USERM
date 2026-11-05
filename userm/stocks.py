"""ETF top-five-holdings Alpha screen (snapshot-based, not PIT).

Reports relative performance without applying unvalidated L1-L4 trade signals.
Both stock and ETF quotes must exist at the two *exact* endpoints of the
selected market-session window. Historical membership is not inferred.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def alpha_table(stocks: pd.DataFrame, etf_signals: pd.DataFrame,
                holdings: pd.DataFrame, asof, calendar: pd.DatetimeIndex,
                observation_days: int = 20) -> pd.DataFrame:
    n = int(observation_days)
    if not 1 <= n <= 60:
        raise ValueError('observation_days must be 1..60')
    asof = pd.Timestamp(asof)
    universe = holdings[holdings.symbol.notna() & holdings.symbol.astype(str).str.strip().ne('')].copy()
    if universe.empty:
        return pd.DataFrame()
    quotes = stocks[stocks.symbol.isin(set(universe.symbol)) & (stocks.date <= asof)]
    etfs = etf_signals.loc[etf_signals.date <= asof, ['date', 'etf', 'close']]
    merged = universe.merge(quotes, on='symbol', how='inner').merge(
        etfs, on=['date', 'etf'], how='inner', suffixes=('_stock', '_etf'))
    if merged.empty:
        return pd.DataFrame()
    sessions = calendar[calendar <= asof]
    outputs = []
    for (_, _), block in merged.groupby(['etf', 'symbol'], sort=False):
        block = block.sort_values('date')
        observed = pd.DatetimeIndex(block.date)
        aligned = block.set_index('date').reindex(sessions)
        for h in set((5, 20, 60, n)):
            sr = aligned.close_stock / aligned.close_stock.shift(h) - 1
            er = aligned.close_etf / aligned.close_etf.shift(h) - 1
            aligned[f'stock_ret_{h}'] = sr
            aligned[f'etf_ret_{h}'] = er
            aligned[f'alpha_{h}'] = sr - er
            # The chosen period may also be a standard reference horizon.
            if h == n:
                aligned['stock_ret_window'] = sr
                aligned['etf_ret_window'] = er
                aligned['alpha_window'] = sr - er
        last_day = observed[-1]
        last = aligned.loc[last_day].copy()
        last['date'] = last_day
        last['etf'] = block.iloc[-1]['etf']
        last['symbol'] = block.iloc[-1]['symbol']
        last['ticker'] = block.iloc[-1]['ticker']
        last['weight_pct'] = block.iloc[-1]['weight_pct']
        last['age_sessions'] = int(((calendar > last_day) & (calendar <= asof)).sum())
        last['fresh'] = last_day == asof
        last['position'] = '领先' if pd.notna(last.alpha_window) and last.alpha_window > 0 else (
            '落后' if pd.notna(last.alpha_window) else '历史不足')
        if not last.fresh:
            last['position'] = '行情过期'
            last['alpha_window'] = np.nan
        outputs.append(last)
    result = pd.DataFrame(outputs)
    return result.sort_values(['fresh', 'alpha_window'], ascending=[False, False], na_position='last').reset_index(drop=True)
