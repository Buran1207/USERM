"""Read the SPY ETF EOD series as USERM's one and only RRG benchmark.

SPY is an investable ETF, not the $SPX index. Never fabricate SPY from the
other 20 ETFs, and never use a previous close for a missing trade date.
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd

from .config import DATA

SPY_PATH = DATA / 'spy_prices.csv.gz'


def load_spy(path: Path | None = None) -> pd.Series | None:
    path = Path(path) if path is not None else SPY_PATH
    if not path.is_file():
        return None
    data = pd.read_csv(path, low_memory=False)
    columns = {str(c).strip().lower(): c for c in data.columns}
    if not {'date', 'close'}.issubset(columns):
        raise ValueError(f'{path.name} must contain date,close; got {list(data.columns)}')
    data = data.rename(columns={columns['date']: 'date', columns['close']: 'close'})
    data['date'] = pd.to_datetime(data['date'], errors='coerce').dt.normalize()
    data['close'] = pd.to_numeric(data['close'], errors='coerce')
    data = data.dropna(subset=['date', 'close'])
    data = data.loc[data.close.gt(0)].sort_values('date').drop_duplicates('date', keep='last')
    if data.empty:
        return None
    return data.set_index('date')['close'].rename('SPY')
