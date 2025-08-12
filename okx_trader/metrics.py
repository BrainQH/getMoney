from __future__ import annotations
from typing import Optional
from prometheus_client import Counter, Gauge, start_http_server

# Prometheus 指标定义（中文注释）
trades_total = Counter(
    "trades_total",
    "成交笔数（含买卖与平仓）",
    ["inst_id", "side", "action"],
)

pnl_realized_usdt_total = Counter(
    "pnl_realized_usdt_total",
    "累计已实现盈亏（USDT）",
)

position_size = Gauge(
    "position_size",
    "当前持仓张数（本地视角）",
    ["inst_id", "side"],
)

position_avg_price = Gauge(
    "position_avg_price",
    "当前持仓均价（本地视角）",
    ["inst_id", "side"],
)

errors_total = Counter(
    "errors_total",
    "错误次数计数",
    ["type"],
)


def start_metrics_server(port: int = 9108) -> None:
    """启动 Prometheus 指标 HTTP 服务（中文注释）。"""
    start_http_server(port)