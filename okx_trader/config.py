import os
from typing import Any, Dict
import yaml
from dotenv import load_dotenv


def load_config(path: str = "config.yaml") -> Dict[str, Any]:
    load_dotenv()
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # env overrides
    api_base = os.getenv("OKX_API_BASE")
    if api_base:
        cfg.setdefault("api", {})
        cfg["api"]["base_url"] = api_base

    return cfg