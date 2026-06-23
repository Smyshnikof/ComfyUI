#!/usr/bin/env python3
"""One-shot export: current PRESETS → JSON manifests (re-export from loaded data)."""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services._presets import export_preset_to_json, load_presets  # noqa: E402

MANIFEST_DIR = os.path.join(ROOT, "presets", "manifest")
CATEGORIES_PATH = os.path.join(ROOT, "presets", "categories.json")


def main() -> int:
    presets, preset_files, categories = load_presets(log_skips=False)
    os.makedirs(MANIFEST_DIR, exist_ok=True)
    with open(CATEGORIES_PATH, "w", encoding="utf-8") as f:
        json.dump(categories, f, ensure_ascii=False, indent=2)
        f.write("\n")
    count = 0
    for pid, meta in presets.items():
        obj = export_preset_to_json(pid, meta, preset_files)
        path = os.path.join(MANIFEST_DIR, f"{pid}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.write("\n")
        count += 1
    print(f"Exported {count} presets -> {MANIFEST_DIR}")
    print(f"Categories -> {CATEGORIES_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
