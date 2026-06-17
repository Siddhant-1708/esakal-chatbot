"""
Token usage persistence layer.

Currently backed by a local JSON file. To migrate to a database (Postgres,
InfluxDB, etc.) at enterprise scale, replace _load/_save with DB reads/writes
and keep the public interface (record, get_totals, get_daily) unchanged.
"""
import json
import threading
from datetime import date
from pathlib import Path

_STORE_PATH = Path(__file__).parent.parent / "usage_data.json"
_lock = threading.Lock()

_EMPTY_PROVIDER: dict = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}
_PROVIDERS = ("openai", "groq")


def _empty_store() -> dict:
    return {
        "totals": {p: dict(_EMPTY_PROVIDER) for p in _PROVIDERS},
        "daily": {},
    }


def _load() -> dict:
    try:
        return json.loads(_STORE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return _empty_store()


def _save(data: dict) -> None:
    _STORE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def record(provider: str, prompt_tokens: int, completion_tokens: int) -> None:
    """Add token counts for one API call. Thread-safe."""
    today = date.today().isoformat()
    with _lock:
        data = _load()

        t = data["totals"].setdefault(provider, dict(_EMPTY_PROVIDER))
        t["prompt_tokens"] += prompt_tokens
        t["completion_tokens"] += completion_tokens
        t["calls"] += 1

        day = data["daily"].setdefault(today, {})
        d = day.setdefault(provider, dict(_EMPTY_PROVIDER))
        d["prompt_tokens"] += prompt_tokens
        d["completion_tokens"] += completion_tokens
        d["calls"] += 1

        _save(data)


def get_totals() -> dict:
    with _lock:
        data = _load()
    result = {}
    for provider, counts in data["totals"].items():
        result[provider] = {
            **counts,
            "total_tokens": counts["prompt_tokens"] + counts["completion_tokens"],
        }
    return result


def get_daily() -> dict:
    with _lock:
        data = _load()
    result = {}
    for day, providers in sorted(data["daily"].items()):
        result[day] = {}
        for provider, counts in providers.items():
            result[day][provider] = {
                **counts,
                "total_tokens": counts["prompt_tokens"] + counts["completion_tokens"],
            }
    return result


def reset() -> None:
    with _lock:
        _save(_empty_store())
