from __future__ import annotations
import asyncio
from typing import Dict, Any, List

from loguru import logger

from .okx_client import OkxRestClient, OkxPublicWs
from .strategy import Strategy, StrategyParams
from .executor import Executor
from .portfolio import RiskManager


class TraderApp:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.rest = OkxRestClient(base_url=config.get("api", {}).get("base_url", "https://www.okx.com"))
        p = config.get("strategy", {})
        self.strategy = Strategy(StrategyParams(
            step_pct=float(p.get("step_pct", 0.10)),
            rebound_pct=float(p.get("rebound_pct", 0.02)),
            max_dca_steps=int(p.get("max_dca_steps", 4)),
            take_profit_pct=float(p.get("take_profit_pct", 0.12)),
            stop_loss_pct=float(p.get("stop_loss_pct", 0.15)),
        ))

        r = config.get("risk", {})
        self.risk = RiskManager(
            total_usdt=float(r.get("total_usdt", 10000)),
            per_step_pct=float(r.get("per_step_allocation_pct", 0.02)),
            max_symbols=int(r.get("max_symbols", 6)),
            max_leverage=float(r.get("max_leverage", 3)),
        )
        self.executor = Executor(self.risk, paper_trading=bool(config.get("paper_trading", True)))
        self.ws_url = config.get("ws", {}).get("public_url", "wss://ws.okx.com:8443/ws/v5/public")
        self.inst_type = config.get("inst_type", "SWAP")
        self.quote_ccy = config.get("quote_ccy", "USDT")
        self.top_n = int(config.get("top_n", 20))

    async def _pick_symbols(self) -> List[str]:
        symbols = await self.rest.get_top_symbols_by_volume(inst_type=self.inst_type, quote_ccy=self.quote_ccy, top_n=self.top_n)
        logger.info(f"Picked top symbols: {symbols}")
        return symbols

    async def _ws_loop(self, symbols: List[str]) -> None:
        async with OkxPublicWs(self.ws_url) as ws:
            await ws.subscribe_tickers(symbols)
            async for msg in ws.messages():
                if "arg" in msg and msg.get("arg", {}).get("channel") == "tickers":
                    for item in msg.get("data", []):
                        inst_id = item.get("instId")
                        last = float(item.get("last"))
                        await self._on_price(inst_id, last)

    async def _on_price(self, inst_id: str, price: float) -> None:
        signals = self.strategy.on_price(inst_id, price)
        for sig in signals:
            res = await self.executor.execute(inst_id, sig.action, price)
            # Update strategy state only on fills
            if res.filled:
                self.strategy.apply_fill(inst_id, res.side, res.size, res.price)
            logger.info(f"Trade {inst_id} {sig.action} reason={sig.reason} -> {res.message}")

    async def run(self) -> None:
        symbols = await self._pick_symbols()
        symbols = symbols[: self.top_n]
        logger.info("Starting trading...")
        try:
            await self._ws_loop(symbols)
        finally:
            await self.rest.aclose()