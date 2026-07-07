"""Read/write ComfyUI-Manager config.ini (security_level)."""
from __future__ import annotations

import configparser
import os
from pathlib import Path

from services._config import COMFYUI_ROOT, CUSTOM_NODES_ROOT

VALID_SECURITY_LEVELS = frozenset({"strong", "normal", "normal-", "weak"})
_DEFAULT_SECTION = "default"


def manager_config_candidates() -> list[Path]:
    """Known config.ini locations (newest first)."""
    comfy = Path(COMFYUI_ROOT)
    return [
        comfy / "user" / "__manager" / "config.ini",
        comfy / "user" / "default" / "ComfyUI-Manager" / "config.ini",
        Path(CUSTOM_NODES_ROOT) / "ComfyUI-Manager" / "config.ini",
    ]


def find_manager_config() -> tuple[Path | None, str]:
    """
    Return (path, source).
    source: existing path label, or preferred path for creation.
    """
    for path in manager_config_candidates():
        if path.is_file():
            return path, str(path)
    preferred = manager_config_candidates()[0]
    return preferred, "new"


def _read_parser(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    parser.optionxform = str  # preserve key case
    if path.is_file():
        parser.read(path, encoding="utf-8")
    if not parser.has_section(_DEFAULT_SECTION):
        parser.add_section(_DEFAULT_SECTION)
    return parser


def get_manager_security() -> dict:
    path, source = find_manager_config()
    if path is None:
        return {
            "found": False,
            "path": "",
            "security_level": None,
            "source": source,
            "writable": False,
        }

    parser = _read_parser(path)
    level = parser.get(_DEFAULT_SECTION, "security_level", fallback=None)
    if level:
        level = level.strip().lower()

    return {
        "found": path.is_file(),
        "path": str(path),
        "security_level": level,
        "source": source if path.is_file() else "new",
        "writable": True,
        "valid_levels": sorted(VALID_SECURITY_LEVELS),
    }


def set_manager_security(level: str) -> tuple[bool, str, dict]:
    level = (level or "").strip().lower()
    if level not in VALID_SECURITY_LEVELS:
        return False, f"Недопустимый уровень: {level!r}", {}

    path, _ = find_manager_config()
    if path is None:
        return False, "Не удалось определить путь config.ini", {}

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        parser = _read_parser(path)
        previous = parser.get(_DEFAULT_SECTION, "security_level", fallback="normal").strip().lower()
        parser.set(_DEFAULT_SECTION, "security_level", level)

        tmp = path.with_suffix(".ini.tmp")
        with open(tmp, "w", encoding="utf-8") as handle:
            parser.write(handle)
        os.replace(tmp, path)

        return True, f"security_level: {previous} -> {level}", {
            "path": str(path),
            "previous": previous,
            "security_level": level,
        }
    except OSError as exc:
        return False, str(exc), {}
