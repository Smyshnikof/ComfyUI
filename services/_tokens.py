"""Persistent API tokens on /workspace (survives pod restarts)."""
from __future__ import annotations

import json
import os
import threading

TOKENS_PATH = "/workspace/.downloader_tokens.json"
_lock = threading.Lock()


def load_tokens() -> dict:
    with _lock:
        if not os.path.isfile(TOKENS_PATH):
            return {}
        try:
            with open(TOKENS_PATH, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}


def save_token(service: str, token: str) -> None:
    value = (token or "").strip()
    if not value:
        return
    with _lock:
        data = {}
        if os.path.isfile(TOKENS_PATH):
            try:
                with open(TOKENS_PATH, encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    data = loaded
            except (OSError, json.JSONDecodeError):
                data = {}
        data[service] = value
        os.makedirs(os.path.dirname(TOKENS_PATH) or ".", exist_ok=True)
        tmp_path = TOKENS_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp_path, TOKENS_PATH)
        try:
            os.chmod(TOKENS_PATH, 0o600)
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
