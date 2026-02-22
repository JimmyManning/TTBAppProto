"""Frontend static configuration loaders."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parent.parent / "static" / "data"
_COUNTRIES_PATH = _DATA_DIR / "countries.json"
_FRONTEND_CONFIG_PATH = _DATA_DIR / "frontend_config.json"


def _read_json(path: Path, default: Any) -> Any:
    """Read JSON from disk and return a default value on any failure."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


@lru_cache(maxsize=1)
def load_countries() -> list[str]:
    """Load country names used by the origin dropdown."""
    data = _read_json(_COUNTRIES_PATH, default=[])
    if not isinstance(data, list):
        return []
    return [str(item) for item in data if isinstance(item, str) and item.strip()]


@lru_cache(maxsize=1)
def load_frontend_config() -> dict[str, Any]:
    """Load frontend behavior config such as additive metadata and limits."""
    data = _read_json(_FRONTEND_CONFIG_PATH, default={})
    if not isinstance(data, dict):
        return {}
    return data
