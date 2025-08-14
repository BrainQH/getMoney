from __future__ import annotations
from typing import List, Tuple

from .okx_client import OkxRestClient


async def async_pick_top_symbols(rest: OkxRestClient, inst_type: str, quote_ccy: str, top_n: int) -> List[str]:
    return await rest.get_top_symbols_by_volume(inst_type=inst_type, quote_ccy=quote_ccy, top_n=top_n)


async def fetch_candles_tuples(rest: OkxRestClient, inst_id: str, bar: str, limit: int) -> List[Tuple[int, float, float, float, float]]:
    raw = await rest.get_candles(inst_id, bar=bar, limit=limit)
    # OKX candles: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
    out: List[Tuple[int, float, float, float, float]] = []
    for row in raw:
        try:
            ts = int(row[0])
            o = float(row[1])
            h = float(row[2])
            l = float(row[3])
            c = float(row[4])
            out.append((ts, o, h, l, c))
        except Exception:
            continue
    out.sort(key=lambda x: x[0])
    return out


def compute_atr_from_tuples(candles: List[Tuple[int, float, float, float, float]], window: int = 14) -> Tuple[float, float]:
    if len(candles) < window + 1:
        return 0.0, candles[-1][4] if candles else 0.0
    trs: List[float] = []
    for i in range(1, len(candles)):
        _, _, h, l, _ = candles[i]
        _, _, prev_h, prev_l, prev_c = candles[i - 1]
        # true range = max(h-l, |h-prev_c|, |l-prev_c|)
        prev_close = prev_c
        tr = max(h - l, abs(h - prev_close), abs(l - prev_close))
        trs.append(tr)
    if len(trs) < window:
        return 0.0, candles[-1][4]
    # simple moving average of last `window` TRs
    last_trs = trs[-window:]
    atr = sum(last_trs) / float(window)
    last_close = candles[-1][4]
    return atr, last_close