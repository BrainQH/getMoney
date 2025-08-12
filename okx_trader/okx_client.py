from __future__ import annotations
import asyncio
import json
import hmac
import base64
from hashlib import sha256
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx
import websockets

from .logger import logger


class OkxRestClient:
    """OKX 公共 REST 客户端（中文注释）"""
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
        # 仅保留 USDT 计价的永续合约
        filtered = [t for t in tickers if t.get("instId", "").endswith("-USDT-SWAP")]
        # 以 24h 计价成交额排序
        def vol_key(t: Dict[str, Any]) -> float:
            try:
                return float(t.get("volCcy24h") or 0.0)
            except Exception:
                return 0.0
        filtered.sort(key=vol_key, reverse=True)
        return [t["instId"] for t in filtered[:top_n]]


class OkxPublicWs:
    """OKX 公共 WebSocket 客户端（中文注释）"""
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


class OkxPrivateClient:
    """OKX 私有 REST 客户端，用于实盘下单、查询仓位等（中文注释）。
    说明：签名规则为 base64(hmac_sha256(secret, timestamp + method + path + body))。
    时间戳使用 ISO8601 毫秒格式，UTC 时区。
    """
    def __init__(self, api_key: str, api_secret: str, passphrase: str, base_url: str = "https://www.okx.com") -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=httpx.Timeout(10.0, read=20.0))

    async def aclose(self) -> None:
        await self._client.aclose()

    def _ts(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def _sign(self, ts: str, method: str, path: str, body: str) -> str:
        msg = f"{ts}{method.upper()}{path}{body}".encode("utf-8")
        sig = hmac.new(self.api_secret.encode("utf-8"), msg, sha256).digest()
        return base64.b64encode(sig).decode()

    async def _request(self, method: str, path: str, json_body: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        body = json.dumps(json_body) if json_body else ""
        ts = self._ts()
        sig = self._sign(ts, method, path, body)
        headers = {
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": sig,
            "OK-ACCESS-TIMESTAMP": ts,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
        }
        r = await self._client.request(method, path, headers=headers, params=params, content=body if body else None)
        r.raise_for_status()
        return r.json()

    async def place_order(self, inst_id: str, side: str, sz: str, td_mode: str = "cross", ord_type: str = "market") -> Dict[str, Any]:
        """下单接口：默认使用逐仓/全仓 cross，市价单 ord_type=market。
        注意：OKX 合约的 sz 单位为合约张数，本项目简单按 价格≈名义/价格，可能和合约面值有差异，实盘前请验证合约面值与大小精度。
        """
        path = "/api/v5/trade/order"
        body = {
            "instId": inst_id,
            "tdMode": td_mode,
            "side": side,  # buy/sell
            "ordType": ord_type,
            "sz": str(sz),
        }
        return await self._request("POST", path, json_body=body)

    async def get_positions(self, inst_type: str = "SWAP") -> List[Dict[str, Any]]:
        path = "/api/v5/account/positions"
        resp = await self._request("GET", path, params={"instType": inst_type})
        return resp.get("data", [])