"""USERM V1.3: explainable relative-rotation research, no L1-L4 alerts."""
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'

@dataclass(frozen=True)
class RotationConfig:
    rs_fast_ema: int = 14
    rs_slow_ema: int = 36
    rs_momentum_lag: int = 5
    min_peer_returns: int = 3
    rvol_window: int = 20

CONFIG = RotationConfig()
QUADRANTS = {
    'LEADING': '领先强化', 'WEAKENING': '领先减弱',
    'IMPROVING': '落后改善', 'LAGGING': '落后持续',
    'NA': '历史不足',
}
