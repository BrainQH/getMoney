from __future__ import annotations
import json
import os
from typing import Dict, Any, List

from loguru import logger

from .okx_client import OkxRestClient
from .data import async_pick_top_symbols, fetch_candles_tuples, compute_atr_from_tuples


class Analyzer:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.rest = OkxRestClient(base_url=config.get("api", {}).get("base_url", "https://www.okx.com"))

    async def analyze_and_recommend(self) -> Dict[str, Any]:
        inst_type = self.config.get("inst_type", "SWAP")
        quote_ccy = self.config.get("quote_ccy", "USDT")
        top_n = self.config.get("top_n", 20)
        symbols = await async_pick_top_symbols(self.rest, inst_type, quote_ccy, top_n)
        logger.info(f"Analyzer: symbols={symbols}")

        bar = self.config.get("analysis", {}).get("history_timeframe", "1H")
        limit = int(self.config.get("analysis", {}).get("lookback_candles", 500))
        atr_window = int(self.config.get("analysis", {}).get("atr_window", 14))
        k = float(self.config.get("analysis", {}).get("atr_k_step", 4.0))
        rebound_frac = float(self.config.get("analysis", {}).get("rebound_fraction_of_step", 0.2))

        atr_pcts: List[float] = []
        for inst_id in symbols:
            candles = await fetch_candles_tuples(self.rest, inst_id, bar=bar, limit=limit)
            if not candles:
                continue
            atr, last_close = compute_atr_from_tuples(candles, atr_window)
            if last_close <= 0:
                continue
            atr_pct = atr / last_close
            atr_pcts.append(atr_pct)
            logger.debug(f"{inst_id} ATR={atr:.6f} last={last_close:.6f} ATR%={atr_pct:.2%}")

        if not atr_pcts:
            logger.warning("Analyzer: no ATR data; keeping defaults")
            return {}

        median_atr_pct = sorted(atr_pcts)[len(atr_pcts)//2]
        step_pct = max(0.03, min(0.20, k * median_atr_pct))
        rebound_pct = max(0.005, min(step_pct * rebound_frac, 0.05))

        rec = {
            "strategy": {
                "step_pct": round(step_pct, 4),
                "rebound_pct": round(rebound_pct, 4)
            }
        }

        os.makedirs(".state", exist_ok=True)
        with open(".state/strategy_recommendation.json", "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=2)
        logger.info(f"Analyzer recommendation: {rec}")
        return rec

    async def aclose(self) -> None:
        await self.rest.aclose()