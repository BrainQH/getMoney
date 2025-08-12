from __future__ import annotations
import asyncio
from typing import Dict, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from .analyzer import Analyzer


class AnalysisScheduler:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.scheduler = AsyncIOScheduler()
        self.analyzer = Analyzer(config)

    async def run_once(self) -> None:
        await self.analyzer.analyze_and_recommend()
        await self.analyzer.aclose()

    async def run(self) -> None:
        interval_minutes = int(self.config.get("analysis", {}).get("interval_minutes", 60))
        self.scheduler.add_job(lambda: asyncio.create_task(self.analyzer.analyze_and_recommend()), "interval", minutes=interval_minutes)
        self.scheduler.start()
        logger.info(f"Analysis scheduler started: every {interval_minutes} minutes")
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            pass
        finally:
            await self.analyzer.aclose()