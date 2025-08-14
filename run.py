import argparse
import asyncio
import os

from okx_trader.config import load_config
from okx_trader.logger import setup_logging
from okx_trader.scheduler import AnalysisScheduler
from okx_trader.trader import TraderApp


async def main():
    parser = argparse.ArgumentParser(description="OKX Perp Quant Trader")
    subparsers = parser.add_subparsers(dest="command")

    trade_parser = subparsers.add_parser("trade", help="Run trading loop")
    trade_parser.add_argument("--paper", dest="paper", action="store_true", help="Force paper trading on")
    trade_parser.add_argument("--no-paper", dest="paper", action="store_false", help="Force paper trading off (real)")
    trade_parser.set_defaults(paper=None)
    trade_parser.add_argument("--with-scheduler", action="store_true", help="Run analyzer scheduler alongside trading")
    trade_parser.add_argument("--log-level", default=None, help="Override log level (INFO/DEBUG)")

    analyze_parser = subparsers.add_parser("analyze", help="Run analyzer once and exit")

    args = parser.parse_args()

    config = load_config()
    if hasattr(args, "paper") and args.paper is not None:
        config["paper_trading"] = args.paper
    if args.command == "trade" and getattr(args, "log_level", None):
        config["log_level"] = args.log_level

    setup_logging(config.get("log_level", "INFO"))

    if args.command == "analyze":
        scheduler = AnalysisScheduler(config)
        await scheduler.run_once()
        return

    if args.command == "trade":
        trader = TraderApp(config)
        if getattr(args, "with_scheduler", False) or config.get("analysis", {}).get("enable_scheduler", False):
            scheduler = AnalysisScheduler(config)
            await asyncio.gather(trader.run(), scheduler.run())
        else:
            await trader.run()
        return

    parser.print_help()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass