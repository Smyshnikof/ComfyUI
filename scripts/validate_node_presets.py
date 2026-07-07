#!/usr/bin/env python3
"""Validate node_presets/manifest/*.json against schema rules."""
from __future__ import annotations

import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from services._node_presets import BUILTIN_DIR, load_categories, validate_preset  # noqa: E402


def main() -> int:
    categories = load_categories()
    paths = sorted(glob.glob(os.path.join(BUILTIN_DIR, "*.json")))
    seen: set[str] = set()
    errors: list[str] = []

    for path in paths:
        basename = os.path.basename(path)
        try:
            with open(path, encoding="utf-8") as handle:
                obj = json.load(handle)
        except Exception as exc:
            errors.append(f"{basename}: invalid JSON — {exc}")
            continue
        ok, err = validate_preset(obj, categories, seen)
        if not ok:
            errors.append(f"{basename}: {err}")

    if errors:
        print("Validation failed:")
        for e in errors:
            print("  -", e)
        return 1

    print(f"OK: {len(paths)} manifests validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
