from __future__ import annotations
import json
import os
from dataclasses import dataclass, asdict
from typing import Dict, Any
from threading import RLock


@dataclass
class SymbolState:
    baseline_price: float
    last_extreme: float
    dca_steps_taken: int
    side: str  # none/long/short
    avg_entry: float
    position_size: float


class StateStore:
    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = RLock()
        self._data: Dict[str, Any] = {"symbols": {}}
        self._ensure_dir()
        self._load()

    def _ensure_dir(self) -> None:
        d = os.path.dirname(self.path)
        if d and not os.path.exists(d):
            os.makedirs(d, exist_ok=True)

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {"symbols": {}}

    def save(self) -> None:
        with self._lock:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)

    def get_symbol(self, inst_id: str) -> SymbolState | None:
        with self._lock:
            s = self._data.get("symbols", {}).get(inst_id)
            if not s:
                return None
            return SymbolState(**s)

    def set_symbol(self, inst_id: str, state: SymbolState) -> None:
        with self._lock:
            self._data.setdefault("symbols", {})[inst_id] = asdict(state)
            self.save()

    def delete_symbol(self, inst_id: str) -> None:
        with self._lock:
            self._data.get("symbols", {}).pop(inst_id, None)
            self.save()