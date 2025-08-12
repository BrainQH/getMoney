from __future__ import annotations
from dataclasses import dataclass
from typing import Dict

from loguru import logger

from .portfolio import Position, RiskManager


@dataclass
class ExecutionResult:
    filled: bool
    side: str
    size: float
    price: float
    message: str


class Executor:
    def __init__(self, risk: RiskManager, paper_trading: bool = True) -> None:
        self.risk = risk
        self.paper = paper_trading
        self.positions: Dict[str, Position] = {}

    def get_position(self, inst_id: str) -> Position:
        pos = self.positions.get(inst_id)
        if not pos:
            pos = Position(side="none", size=0.0, avg_price=0.0)
            self.positions[inst_id] = pos
        return pos

    def _size_in_contracts(self, inst_id: str, price: float) -> float:
        notional = self.risk.per_step_notional()
        size = max(0.0, notional / max(price, 1e-8))
        return size

    async def execute(self, inst_id: str, action: str, price: float) -> ExecutionResult:
        pos = self.get_position(inst_id)
        side = "buy" if action in ("buy", "close_short") else "sell"
        size = self._size_in_contracts(inst_id, price)
        if size == 0:
            return ExecutionResult(False, side, size, price, "size=0")

        # Paper fills at last price
        if self.paper:
            pos.update_with_fill(side, size, price)
            logger.info(f"[PAPER] {inst_id} {side.upper()} size={size:.6f} price={price:.6f} new_pos=({pos.side}, size={pos.size:.6f}, avg={pos.avg_price:.6f})")
            return ExecutionResult(True, side, size, price, "paper fill")

        # TODO: Real order via OKX private API
        logger.warning("Real trading not implemented; fallback to paper")
        pos.update_with_fill(side, size, price)
        return ExecutionResult(True, side, size, price, "simulated real fill")