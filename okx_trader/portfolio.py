from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass
class Position:
    """本地持仓模型（中文注释）。
    side: 持仓方向（long/short/none）
    size: 张数
    avg_price: 持仓均价
    """
    side: str  # long/short/none
    size: float
    avg_price: float

    def apply_fill(self, side: str, fill_size: float, fill_price: float) -> float:
        """应用一次成交并返回已实现盈亏（USDT）。
        逻辑：
        - 同向加仓：加权更新均价与张数；无已实现盈亏。
        - 反向减仓：按持仓均价与成交价计算已实现盈亏，并减少张数；若张数归零则方向置 none。
        """
        realized_pnl = 0.0
        if side == "buy":
            if self.side in ("none", "long"):
                # 加多仓
                new_notional = self.avg_price * self.size + fill_price * fill_size
                self.size += fill_size
                self.side = "long"
                self.avg_price = 0.0 if self.size == 0 else new_notional / self.size
            else:
                # 平空仓（反向）
                close_size = min(self.size, fill_size)
                realized_pnl += (self.avg_price - fill_price) * close_size
                self.size -= close_size
                if self.size <= 0:
                    self.side = "none"
                    self.size = 0.0
                    self.avg_price = 0.0
        elif side == "sell":
            if self.side in ("none", "short"):
                # 加空仓
                new_notional = self.avg_price * self.size + fill_price * fill_size
                self.size += fill_size
                self.side = "short"
                self.avg_price = 0.0 if self.size == 0 else new_notional / self.size
            else:
                # 平多仓（反向）
                close_size = min(self.size, fill_size)
                realized_pnl += (fill_price - self.avg_price) * close_size
                self.size -= close_size
                if self.size <= 0:
                    self.side = "none"
                    self.size = 0.0
                    self.avg_price = 0.0
        return realized_pnl


class RiskManager:
    """风险控制（中文注释）。"""
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