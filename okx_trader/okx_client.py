from __future__ import annotations
import asyncio
import json
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx
import websockets

from .logger import logger


class OkxRestClient:
    def __init__(self, base_url: str = "https://www.okx.com") -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=httpx.Timeout(10.0, read=20.0))

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_tickers(self, inst_type: str = "SWAP") -> List[Dict[str, Any]]:
        r = await self._client.get("/api/v5/market/tickers", params={"instType": inst_type})
        r.raise_for_status()
        data = r.json()
        return data.get("data", [])

    async def get_instruments(self, inst_type: str = "SWAP") -> List[Dict[str, Any]]:
        r = await self._client.get("/api/v5/public/instruments", params={"instType": inst_type})
        r.raise_for_status()
        return r.json().get("data", [])

    async def get_candles(self, inst_id: str, bar: str = "1H", limit: int = 300) -> List[List[str]]:
        r = await self._client.get("/api/v5/market/candles", params={"instId": inst_id, "bar": bar, "limit": limit})
        r.raise_for_status()
        return r.json().get("data", [])

    async def get_top_symbols_by_volume(self, inst_type: str = "SWAP", quote_ccy: str = "USDT", top_n: int = 20) -> List[str]:
        tickers = await self.get_tickers(inst_type)
        # Filter by quote currency (USDT contracts)
        filtered = [t for t in tickers if t.get("instId", "").endswith("-USDT-SWAP")]
        # Sort by 24h quote volume (volCcy24h) descending
        def vol_key(t: Dict[str, Any]) -> float:
            try:
                return float(t.get("volCcy24h") or 0.0)
            except Exception:
                return 0.0
        filtered.sort(key=vol_key, reverse=True)
        return [t["instId"] for t in filtered[:top_n]]


class OkxPublicWs:
    def __init__(self, url: str) -> None:
        self.url = url
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> "OkxPublicWs":
        self._ws = await websockets.connect(self.url, ping_interval=20, ping_timeout=20)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def subscribe_tickers(self, inst_ids: List[str]) -> None:
        if not self._ws:
            raise RuntimeError("WebSocket not connected")
        args = [{"channel": "tickers", "instId": i} for i in inst_ids]
        sub = {"op": "subscribe", "args": args}
        await self._ws.send(json.dumps(sub))

    async def messages(self) -> AsyncIterator[Dict[str, Any]]:
        if not self._ws:
            raise RuntimeError("WebSocket not connected")
        async for msg in self._ws:
            try:
                data = json.loads(msg)
                yield data
            except Exception as e:
                logger.warning(f"WS parse error: {e}")