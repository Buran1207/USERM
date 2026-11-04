"""V1 immutable signal specification, research thresholds, NOT optimized parameters."""
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

@dataclass(frozen=True)
class SignalConfig:
    rs_fast_ema: int = 14
    rs_slow_ema: int = 36
    rs_momentum_lag: int = 5
    ma_fast: int = 10
    ma_medium: int = 20
    ma_long: int = 50
    relative_fast: int = 5
    relative_mid: int = 10
    relative_month: int = 20
    relative_long: int = 60
    breakout_window: int = 20
    rvol_window: int = 20
    rvol_confirmation: float = 1.15
    early_momentum_floor: float = 100.05
    hard_risk_relative_5d: float = 0.0
    min_peer_returns: int = 3
    # Condition after daily close; never an automatic order.
    stock_min_daily_dollar_volume: float = 5_000_000.0  # close(adjusted proxy)*volume; NOT raw USD amount
    signal_event_cooldown: int = 5

CONFIG = SignalConfig()
STAGES = {"L1": "早期异动", "L2": "反转候选", "L3": "突破确认", "L4": "强势延续", "W": "风险警示", "N0": "无触发", "NA": "历史不足"}
STAGE_COLORS = {"L1":"#A06B00","L2":"#B15B43","L3":"#8C1D28","L4":"#2C7B65","W":"#B22222","N0":"#8F9BA8","NA":"#C4C9D0"}
QUADRANTS = {"LEADING": "领先强化", "WEAKENING":"领先减弱", "IMPROVING":"落后改善", "LAGGING":"落后持续", "NA":"历史不足"}
