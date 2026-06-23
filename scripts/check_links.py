#!/usr/bin/env python3
"""HEAD-check all preset download URLs; exit 1 if any look dead."""
from __future__ import annotations

import os
import sys

import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.preset_downloader import PRESET_FILES  # noqa: E402

USER_AGENT = "ComfyUI-link-check/1.0"
HEADERS = {"User-Agent": USER_AGENT}
OK_STATUSES = {200, 206, 401, 403}


def _check_url(url: str) -> tuple[int | None, str | None]:
    try:
        resp = requests.head(url, headers=HEADERS, timeout=45, allow_redirects=True)
        if resp.status_code == 405:
            resp = requests.get(url, headers=HEADERS, timeout=45, allow_redirects=True, stream=True)
            resp.close()
        return resp.status_code, None
    except requests.RequestException as exc:
        return None, str(exc)


def main() -> int:
    seen: set[str] = set()
    failures: list[tuple[str, str, str]] = []

    for preset_id, files in PRESET_FILES.items():
        for url, folder, _custom in files:
            if url in seen:
                continue
            seen.add(url)
            status, err = _check_url(url)
            if err:
                failures.append((preset_id, url, f"error: {err}"))
            elif status not in OK_STATUSES:
                failures.append((preset_id, url, f"HTTP {status}"))

    if failures:
        print(f"Link check failed: {len(failures)} URL(s)\n")
        for preset_id, url, reason in failures:
            print(f"  [{preset_id}] {reason}\n    {url}")
        return 1

    print(f"Link check OK: {len(seen)} unique URL(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
