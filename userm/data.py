"""Strict data schema and offline read-only snapshot access.
No iFinD/network connection in Streamlit; dates must NEVER be forward-filled.
"""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
from .config import DATA

QUOTE_COLS = ["date","symbol","open","high","low","close","volume","partition"]
NUMERIC = ["open","high","low","close","volume"]


def table(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA / name, encoding="utf-8-sig")


def load_quotes(kind="etfs", path: Path|None=None) -> pd.DataFrame:
    """Load only the 20 ETF adjusted EOD price histories."""
    if kind != "etfs":
        raise ValueError("USERM ETF-only: stock quote loading is no longer supported")
    src = Path(path) if path is not None else DATA / "etf_prices.csv.gz"
    df = pd.read_csv(src, usecols=lambda c: c in QUOTE_COLS, low_memory=False)
    missing = set(QUOTE_COLS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing ETF quote columns in {src.name}: {sorted(missing)}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()
    for c in NUMERIC:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["date", "symbol", "close"])
    df = df[df["close"] > 0]
    df = df.sort_values(["symbol", "date"]).drop_duplicates(["symbol", "date"], keep="last")
    return df.reset_index(drop=True)


def load_etf_master() -> pd.DataFrame:
    return table("etfs.csv")


def manifest() -> dict:
    path = DATA / "snapshot_manifest.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def trading_dates(d: pd.DataFrame) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(sorted(d.date.unique()))


def stale_by_sessions(last_seen, asof, calendar: pd.DatetimeIndex) -> int:
    """Missing business observations measured in observed ETF market sessions."""
    last = pd.Timestamp(last_seen)
    current = pd.Timestamp(asof)
    if pd.isna(last) or pd.isna(current):
        return 9999
    return int(((calendar > last) & (calendar <= current)).sum())
