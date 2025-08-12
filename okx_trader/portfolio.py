from __future__ import annotations
from dataclasses import dataclass
from typing import Dict


@dataclass
class Position:
    side: str  # long/short/none
    size: float
    avg_price: float

    def update_with_fill(self, side: str, fill_size: float, fill_price: float) -> None:
        if side == "buy":
            if self.side in ("none", "long"):
                new_notional = self.avg_price * self.size + fill_price * fill_size
                self.size += fill_size
                self.side = "long"
                self.avg_price = 0.0 if self.size == 0 else new_notional / self.size
            else:  # reducing short
                self.size -= fill_size
                if self.size <= 0:
                    self.side = "none"
                    self.size = 0.0
                    self.avg_price = 0.0
        elif side == "sell":
            if self.side in ("none", "short"):
                new_notional = self.avg_price * self.size + fill_price * fill_size
                self.size += fill_size
                self.side = "short"
                self.avg_price = 0.0 if self.size == 0 else new_notional / self.size
            else:  # reducing long
                self.size -= fill_size
                if self.size <= 0:
                    self.side = "none"
                    self.size = 0.0
                    self.avg_price = 0.0


class RiskManager:
    def __init__(self, total_usdt: float, per_step_pct: float, max_symbols: int, max_leverage: float) -> None:
        self.total_usdt = total_usdt
        self.per_step_pct = per_step_pct
        self.max_symbols = max_symbols
        self.max_leverage = max_leverage
        self.active_symbols: Dict[str, None] = {}

    def per_step_notional(self) -> float:
        return self.total_usdt * self.per_step_pct

    def can_add_symbol(self, inst_id: str) -> bool:
        return inst_id in self.active_symbols or len(self.active_symbols) < self.max_symbols

    def register_symbol(self, inst_id: str) -> None:
        self.active_symbols.setdefault(inst_id, None)

    def unregister_symbol(self, inst_id: str) -> None:
        self.active_symbols.pop(inst_id, None)