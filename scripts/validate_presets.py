#!/usr/bin/env python3
"""Validate all builtin preset manifests; exit 1 on any error."""
from __future__ import annotations

import glob
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services._presets import (  # noqa: E402
    BUILTIN_DIR,
    CATEGORIES_FILE,
    _load_json,
    load_presets,
    validate_preset,
)


def main() -> int:
    if not os.path.isdir(BUILTIN_DIR):
        print(f"Missing manifest dir: {BUILTIN_DIR}")
        return 1
    categories = _load_json(CATEGORIES_FILE) if os.path.isfile(CATEGORIES_FILE) else {}
    paths = sorted(glob.glob(os.path.join(BUILTIN_DIR, "*.json")))
    if not paths:
        print("No manifest JSON files found")
        return 1

    errors: list[str] = []
    seen: set[str] = set()
    for path in paths:
        name = os.path.basename(path)
        try:
            obj = _load_json(path)
        except Exception as exc:
            errors.append(f"{name}: invalid JSON ({exc})")
            continue
        ok, err = validate_preset(obj, categories, seen)
        if not ok:
            errors.append(f"{name}: {err}")
            continue
        pid = obj["id"]
        seen.add(pid)
        for grp in obj.get("variant_groups") or []:
            for v in grp.get("variants") or []:
                seen.add(v["id"])

    if errors:
        print(f"Preset validation failed: {len(errors)} error(s)\n")
        for line in errors:
            print(f"  {line}")
        return 1

    presets, files, cats = load_presets(log_skips=False)
    print(
        f"Preset validation OK: {len(paths)} manifest(s), "
        f"{len(presets)} card(s), {len(files)} file-set key(s), "
        f"{len(cats)} categor(ies)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
