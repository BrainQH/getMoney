from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

from .utils import pct_move


@dataclass
class StrategyParams:
    step_pct: float
    rebound_pct: float
    max_dca_steps: int
    take_profit_pct: float
    stop_loss_pct: float


@dataclass
class Signal:
    action: str  # buy/sell/close_long/close_short
    size: float
    reason: str


@dataclass
class PerSymbolRuntime:
    baseline_price: Optional[float] = None
    last_extreme: Optional[float] = None
    dca_steps_taken: int = 0
    long_position: float = 0.0
    short_position: float = 0.0
    avg_long: float = 0.0
    avg_short: float = 0.0
    highest_since_long: Optional[float] = None
    lowest_since_short: Optional[float] = None


class Strategy:
    def __init__(self, params: StrategyParams) -> None:
        self.p = params
        self.state = {}

    def _get(self, inst_id: str) -> PerSymbolRuntime:
        s = self.state.get(inst_id)
        if not s:
            s = PerSymbolRuntime()
            self.state[inst_id] = s
        return s

    def on_price(self, inst_id: str, price: float) -> List[Signal]:
        s = self._get(inst_id)
        if s.baseline_price is None:
            s.baseline_price = price
            s.last_extreme = price
        signals: List[Signal] = []

        # Long side logic
        if s.long_position <= 0.0:
            # Entry conditions: drop by step then rebound by rebound
            drop_pct = pct_move(s.baseline_price, price)
            if drop_pct <= -self.p.step_pct:
                # update extreme low
                s.last_extreme = min(s.last_extreme or price, price)
                rebound = pct_move(s.last_extreme, price)
                if rebound >= self.p.rebound_pct and s.dca_steps_taken < self.p.max_dca_steps:
                    signals.append(Signal("buy", 1.0, f"Long entry after drop {drop_pct:.2%} and rebound {rebound:.2%}"))
                elif s.dca_steps_taken < self.p.max_dca_steps:
                    # DCA at each full step down without rebound
                    step_index = int(abs(drop_pct) / self.p.step_pct)
                    if step_index > s.dca_steps_taken:
                        signals.append(Signal("buy", 1.0, f"Long DCA step {step_index} at drop {drop_pct:.2%}"))
        else:
            # Manage long position
            s.highest_since_long = price if s.highest_since_long is None else max(s.highest_since_long, price)
            # Take profit on rise then pullback
            rise_pct = pct_move(s.baseline_price, price)
            pullback = pct_move(s.highest_since_long, price) if s.highest_since_long else 0.0
            if rise_pct >= self.p.step_pct and pullback <= -self.p.rebound_pct:
                signals.append(Signal("close_long", 1.0, f"Exit long after rise {rise_pct:.2%} and pullback {pullback:.2%}"))
            else:
                # Failsafe SL/TP
                if rise_pct >= self.p.take_profit_pct:
                    signals.append(Signal("close_long", 1.0, f"TP long at +{rise_pct:.2%}"))
                elif rise_pct <= -self.p.stop_loss_pct:
                    signals.append(Signal("close_long", 1.0, f"SL long at {rise_pct:.2%}"))

        # Short side logic (mirror)
        if s.short_position <= 0.0:
            rise_pct = pct_move(s.baseline_price, price)
            if rise_pct >= self.p.step_pct:
                s.last_extreme = max(s.last_extreme or price, price)
                pullback = pct_move(s.last_extreme, price)
                if pullback <= -self.p.rebound_pct and s.dca_steps_taken < self.p.max_dca_steps:
                    signals.append(Signal("sell", 1.0, f"Short entry after rise {rise_pct:.2%} and pullback {pullback:.2%}"))
                elif s.dca_steps_taken < self.p.max_dca_steps:
                    step_index = int(abs(rise_pct) / self.p.step_pct)
                    if step_index > s.dca_steps_taken:
                        signals.append(Signal("sell", 1.0, f"Short DCA step {step_index} at rise {rise_pct:.2%}"))
        else:
            # Manage short position
            s.lowest_since_short = price if s.lowest_since_short is None else min(s.lowest_since_short, price)
            drop_pct = pct_move(s.baseline_price, price)
            rebound = pct_move(s.lowest_since_short, price) if s.lowest_since_short else 0.0
            if drop_pct <= -self.p.step_pct and rebound >= self.p.rebound_pct:
                signals.append(Signal("close_short", 1.0, f"Exit short after drop {drop_pct:.2%} and rebound {rebound:.2%}"))
            else:
                if drop_pct <= -self.p.take_profit_pct:
                    signals.append(Signal("close_short", 1.0, f"TP short at {drop_pct:.2%}"))
                elif drop_pct >= self.p.stop_loss_pct:
                    signals.append(Signal("close_short", 1.0, f"SL short at +{drop_pct:.2%}"))

        return signals

    def apply_fill(self, inst_id: str, side: str, size: float, price: float) -> None:
        s = self._get(inst_id)
        if side == "buy":
            if s.short_position > 0:
                # reduce short first
                s.short_position = max(0.0, s.short_position - size)
                if s.short_position == 0.0:
                    s.lowest_since_short = None
                    s.dca_steps_taken = 0
                    s.baseline_price = price
            else:
                # add/increase long
                s.long_position += size
                s.highest_since_long = price if s.highest_since_long is None else max(s.highest_since_long, price)
                if s.long_position == size:  # first long entry
                    s.baseline_price = price
                    s.dca_steps_taken = 1
        elif side == "sell":
            if s.long_position > 0:
                # reduce long first
                s.long_position = max(0.0, s.long_position - size)
                if s.long_position == 0.0:
                    s.highest_since_long = None
                    s.dca_steps_taken = 0
                    s.baseline_price = price
            else:
                # add/increase short
                s.short_position += size
                s.lowest_since_short = price if s.lowest_since_short is None else min(s.lowest_since_short, price)
                if s.short_position == size:  # first short entry
                    s.baseline_price = price
                    s.dca_steps_taken = 1