"""Persistent API tokens (survives pod restarts / desktop sessions)."""
from __future__ import annotations

import json
import os
import threading

from services._config import TOKENS_PATH

_lock = threading.Lock()
_TOKENS_PATH = str(TOKENS_PATH)


def load_tokens() -> dict:
    with _lock:
        if not os.path.isfile(_TOKENS_PATH):
            return {}
        try:
            with open(_TOKENS_PATH, encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}


def save_token(service: str, token: str) -> None:
    value = (token or "").strip()
    if not value:
        return
    with _lock:
        data = {}
        if os.path.isfile(_TOKENS_PATH):
            try:
                with open(_TOKENS_PATH, encoding="utf-8") as handle:
                    loaded = json.load(handle)
                if isinstance(loaded, dict):
                    data = loaded
            except (OSError, json.JSONDecodeError):
                data = {}
        data[service] = value
        os.makedirs(os.path.dirname(_TOKENS_PATH) or ".", exist_ok=True)
        tmp_path = _TOKENS_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
        os.replace(tmp_path, _TOKENS_PATH)
        try:
            os.chmod(_TOKENS_PATH, 0o600)
        except OSError:
            pass


def resolve_token(service: str, form_token: str | None) -> str:
    provided = (form_token or "").strip()
    if provided:
        return provided
    data = load_tokens()
    return (data.get(service) or "").strip()


def tokens_saved_status() -> dict:
    data = load_tokens()
    return {
        "hf": bool((data.get("hf") or "").strip()),
        "civitai": bool((data.get("civitai") or "").strip()),
    }
