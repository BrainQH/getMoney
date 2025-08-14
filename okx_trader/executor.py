from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional
import os

from loguru import logger

from .portfolio import Position, RiskManager
from .metrics import trades_total, pnl_realized_usdt_total, position_size, position_avg_price, errors_total
from .okx_client import OkxPrivateClient


@dataclass
class ExecutionResult:
    filled: bool
    side: str
    size: float
    price: float
    message: str


class Executor:
    """下单执行器（支持纸面与实盘，中文注释）。"""
    def __init__(self, risk: RiskManager, paper_trading: bool = True, private_client: Optional[OkxPrivateClient] = None) -> None:
        self.risk = risk
        self.paper = paper_trading
        self.positions: Dict[str, Position] = {}
        self.private_client = private_client

    def get_position(self, inst_id: str) -> Position:
        pos = self.positions.get(inst_id)
        if not pos:
            pos = Position(side="none", size=0.0, avg_price=0.0)
            self.positions[inst_id] = pos
        return pos

    def _size_in_contracts(self, inst_id: str, price: float) -> float:
        # 简化：名义资金 / 价格 作为张数；实盘前请校验合约面值与精度
        notional = self.risk.per_step_notional()
        size = max(0.0, notional / max(price, 1e-8))
        return size

    async def execute(self, inst_id: str, action: str, price: float) -> ExecutionResult:
        pos = self.get_position(inst_id)
        side = "buy" if action in ("buy", "close_short") else "sell"
        size = self._size_in_contracts(inst_id, price)
        if size == 0:
            return ExecutionResult(False, side, size, price, "size=0")

        # 纸面交易：按最新价成交
        if self.paper or self.private_client is None:
            realized = pos.apply_fill(side, size, price)
            trades_total.labels(inst_id=inst_id, side=side, action=action).inc()
            if realized != 0:
                pnl_realized_usdt_total.inc(realized)
            position_size.labels(inst_id=inst_id, side=pos.side or "none").set(pos.size)
            position_avg_price.labels(inst_id=inst_id, side=pos.side or "none").set(pos.avg_price)
            logger.info(f"[纸面] {inst_id} {side.upper()} 张数={size:.6f} 价格={price:.6f} 持仓=({pos.side}, 张数={pos.size:.6f}, 均价={pos.avg_price:.6f}) 已实现PnL={realized:.4f}")
            return ExecutionResult(True, side, size, price, "paper fill")

        # 实盘交易
        try:
            resp = await self.private_client.place_order(inst_id=inst_id, side=side, sz=str(int(size)))
            # 简化：默认视为立即按当前价成交
            realized = pos.apply_fill(side, size, price)
            trades_total.labels(inst_id=inst_id, side=side, action=action).inc()
            if realized != 0:
                pnl_realized_usdt_total.inc(realized)
            position_size.labels(inst_id=inst_id, side=pos.side or "none").set(pos.size)
            position_avg_price.labels(inst_id=inst_id, side=pos.side or "none").set(pos.avg_price)
            logger.info(f"[实盘] {inst_id} {side.upper()} 张数={size:.6f} 价格≈{price:.6f} 订单返回={resp} 持仓=({pos.side}, 张数={pos.size:.6f}, 均价={pos.avg_price:.6f}) 已实现PnL={realized:.4f}")
            return ExecutionResult(True, side, size, price, "real order submitted")
        except Exception as e:
            errors_total.labels(type="order").inc()
            logger.error(f"实盘下单失败: {e}")
            return ExecutionResult(False, side, size, price, f"error: {e}")

    async def sync_positions_from_exchange(self) -> None:
        """可选：从交易所同步仓位（实盘）。只更新本地快照以便指标展示（简化）。"""
        if self.private_client is None:
            return
        try:
            all_pos = await self.private_client.get_positions(inst_type="SWAP")
            # 简化处理：对于每个 instId，以净持仓为准（OKX 可为净仓/双向持仓模式）。
            for p in all_pos:
                inst_id = p.get("instId")
                pos_side = p.get("posSide")  # long/short（双向持仓模式）
                pos_sz = float(p.get("pos", 0) or 0)
                avg_px = float(p.get("avgPx", 0) or 0)
                loc = self.get_position(inst_id)
                if pos_sz == 0:
                    loc.side = "none"
                    loc.size = 0.0
                    loc.avg_price = 0.0
                else:
                    # 若 posSide 未给出或为 net，可根据正负张数判断；此处简化：有 posSide 则用之
                    if pos_side in ("long", "short"):
                        loc.side = pos_side
                    else:
                        loc.side = "long" if pos_sz > 0 else "short"
                    loc.size = abs(pos_sz)
                    loc.avg_price = avg_px
                position_size.labels(inst_id=inst_id, side=loc.side or "none").set(loc.size)
                position_avg_price.labels(inst_id=inst_id, side=loc.side or "none").set(loc.avg_price)
        except Exception as e:
            errors_total.labels(type="sync_positions").inc()
            logger.error(f"同步仓位失败: {e}")