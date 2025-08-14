from dataclasses import dataclass
from typing import Optional


def pct_move(from_price: float, to_price: float) -> float:
    if from_price <= 0:
        return 0.0
    return (to_price - from_price) / from_price


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


@dataclass
class Ticker:
    inst_id: str
    last: float
    ts: int