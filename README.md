# OKX Perp Quant Trader (Top 20 Hot Coins)

This project implements a realtime trading bot for OKX perpetual contracts (SWAP). It monitors the top-20 hot coins by 24h volume and executes a rule-based strategy:

- Buy (long) when price drops by a step percent and then rebounds by a rebound percent. If no rebound, DCA at each step drop.
- Sell/exit long when price rises by a step percent and then pulls back by a rebound percent. 
- Short logic mirrors long: enter short on step up then pullback, scale shorts every step up if no pullback, exit short on step down then rebound.
- Periodically analyze history to adjust parameters to volatility.

Defaults are conservative and paper-trading is enabled by default.

## Features
- Top-20 symbols by 24h volume on OKX USDT-margined SWAP
- Realtime price via public WebSocket
- DCA laddered entries, symmetric long/short
- Risk limits: max exposure, per-step allocation, max DCA steps
- Paper trading with detailed progress logs
- Periodic analyzer to tune `step_pct` and `rebound_pct` using volatility

## Safety
- Real trading requires OKX API keys. Paper-trading is on by default.
- Use at your own risk. Markets are risky; no profitability is guaranteed.

## Quickstart

1) Python 3.10+

2) Install deps
```bash
pip install -r requirements.txt
```

3) Configure
- Copy `.env.example` to `.env` and fill keys ONLY if you want real trading.
- Review `config.yaml` to tune parameters.

4) Run (paper trading)
```bash
python run.py trade --paper --log-level INFO
```

5) Run analyzer once
```bash
python run.py analyze
```

6) Run with scheduler (analysis every N minutes, then trading)
```bash
python run.py trade --with-scheduler
```

## Configuration
See `config.yaml` for:
- `paper_trading`: true/false
- `quote_ccy`: USDT
- `top_n`: 20
- `strategy`: `step_pct`, `rebound_pct`, `max_dca_steps`, `take_profit_pct`, `stop_loss_pct`
- `risk`: `total_usdt`, `per_step_allocation_pct`, `max_symbols`, `max_leverage`
- `analysis`: periodicity and lookbacks

## Real trading (optional)
- Set `.env`:
```
OKX_API_KEY=...
OKX_API_SECRET=...
OKX_API_PASSPHRASE=...
OKX_API_BASE=https://www.okx.com
```
- Disable paper with `--no-paper` or set `paper_trading: false`.

## Disclaimer
This code is for educational purposes. You are responsible for any usage and outcomes.