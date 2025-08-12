# OKX 永续量化交易机器人（前20热门）

本项目提供一个可运行的 OKX 永续合约量化交易机器人，默认订阅并交易前 20 个 USDT 计价的热门永续合约（依据 24h 成交额）。包含：

- 策略（中英文中：跌10%+反弹2%做多；若不反弹则每跌10%定投；涨10%回落2%止盈。做空对称），含可选止盈/止损与 DCA 梯度。
- 实盘下单与仓位查询（可配置，默认纸面交易）。
- 已实现盈亏统计（累计 USDT）。
- Prometheus 指标导出（交易计数、PnL、持仓等）。
- 历史分析（ATR）定期给出参数建议，辅助优化 `step_pct` 与 `rebound_pct`。

## 快速开始

1) Python 3.10+（已在 3.13 环境验证）

2) 安装依赖
```bash
python3 -m pip install -r requirements.txt --break-system-packages
```

3) 配置
- 复制 `.env.example` 为 `.env` 并根据需要填写私有 API（仅实盘需要）。
- 根据需要修改 `config.yaml` 参数；默认开启纸面交易。

4) 运行（纸面交易）
```bash
python3 run.py trade --paper --log-level INFO
```

5) 单次运行历史分析
```bash
python3 run.py analyze
```

6) 交易 + 定时分析
```bash
python3 run.py trade --with-scheduler
```

## 实盘交易
- 在 `.env` 中填写：
```
OKX_API_KEY=你的key
OKX_API_SECRET=你的secret
OKX_API_PASSPHRASE=你的passphrase
OKX_API_BASE=https://www.okx.com
```
- 关闭纸面模式：`python3 run.py trade --no-paper` 或在 `config.yaml` 设置 `paper_trading: false`。
- 重要说明：本项目对合约张数 `sz` 采用简化计算（名义资金/价格），不同币种合约面值与精度可能存在偏差，实盘前务必核对合约面值与最小下单量、步长等规则。

## 策略说明（核心要点）
- **做多入场**：价格自基准价下跌 `step_pct`（默认10%）后，如从最低点反弹 `rebound_pct`（默认2%）则买入一份；若一直未反弹，则每完整下跌 `step_pct` 再定投一份，最多 `max_dca_steps` 次。
- **做多出场**：价格自基准价上涨 `step_pct` 后，如从最高点回落 `rebound_pct` 则全部止盈；亦可触发 `take_profit_pct` 与 `stop_loss_pct` 的兜底止盈/止损。
- **做空**：与做多对称。
- **参数自适应**：定期用 ATR 评估波动，给出 `step_pct` 与 `rebound_pct` 建议。

## 指标与监控
- Prometheus 指标默认在 `metrics.port`（默认 9108）启动：
  - `trades_total{inst_id,side,action}`：成交计数
  - `pnl_realized_usdt_total`：累计已实现盈亏（USDT）
  - `position_size{inst_id,side}`：本地视角的当前持仓张数
  - `position_avg_price{inst_id,side}`：本地视角的当前持仓均价
  - `errors_total{type}`：错误计数
- 可使用 Grafana 构建可视化大盘。

## 配置项（`config.yaml`）
- `paper_trading`：是否纸面交易（默认 true）
- `top_n`：订阅交易的热门合约个数（默认 20）
- `strategy`：`step_pct`、`rebound_pct`、`max_dca_steps`、`take_profit_pct`、`stop_loss_pct`
- `risk`：`total_usdt`（账户资金规模估计）、`per_step_allocation_pct`（每步投入占比）、`max_symbols`、`max_leverage`
- `ws.public_url`：OKX 公共 WS 地址
- `analysis.*`：ATR 分析参数与周期
- `metrics.enable/port`：Prometheus 指标服务开关与端口

## 重要提示
- 市场有风险，策略无保证盈利；请小额资金、模拟盘充分验证后谨慎实盘。
- 该代码仅用于学习研究，不构成投资建议。你对任何使用后果自行负责。