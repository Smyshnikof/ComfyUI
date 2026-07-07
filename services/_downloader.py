"""Shared file download: aria2c when available, requests fallback."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import Callable, Optional

import requests

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
DEFAULT_HEADERS = {"User-Agent": DEFAULT_USER_AGENT}

from services._config import WORKSPACE_ROOT
MIN_FREE_GB = 15
DISK_USAGE_THRESHOLD = 0.95


def _bytes_to_gb(num_bytes: int) -> float:
    return round(num_bytes / (1024 ** 3), 1)


def get_workspace_free_bytes() -> int:
    for path in (str(WORKSPACE_ROOT), "/opt/workspace-internal", "/"):
        try:
            if os.path.isdir(path):
                return shutil.disk_usage(path).free
        except Exception:
            continue
    return 0


def estimate_size(urls: list[str], token: Optional[str] = None) -> int:
    """Sum Content-Length from HEAD for all urls (0 for unknown sizes)."""
    hdrs = _build_headers(token)
    total = 0
    for url in urls:
        _, size = probe_url(url, headers=hdrs, timeout=15)
        total += size
    return total


def check_disk_space(needed_bytes: int, force: bool = False) -> Optional[dict]:
    """
    Return warning payload if download should be blocked, else None.
    When needed_bytes is 0 (unknown), apply MIN_FREE_GB MVP guard.
    """
    if force:
        return None

    free_bytes = get_workspace_free_bytes()
    min_free_bytes = MIN_FREE_GB * (1024 ** 3)

    if needed_bytes <= 0:
        if free_bytes < min_free_bytes:
            return {
                "warning": True,
                "message": (
                    f"⚠️ Мало места на диске: свободно {_bytes_to_gb(free_bytes)} GB "
                    f"(рекомендуется ≥ {MIN_FREE_GB} GB)"
                ),
                "needed_bytes": 0,
                "free_bytes": free_bytes,
                "needed_gb": 0,
                "free_gb": _bytes_to_gb(free_bytes),
            }
        return None

    if needed_bytes > free_bytes * DISK_USAGE_THRESHOLD:
        return {
            "warning": True,
            "message": (
                f"⚠️ Не хватит места: нужно ~{_bytes_to_gb(needed_bytes)} GB, "
                f"свободно {_bytes_to_gb(free_bytes)} GB"
            ),
            "needed_bytes": needed_bytes,
            "free_bytes": free_bytes,
            "needed_gb": _bytes_to_gb(needed_bytes),
            "free_gb": _bytes_to_gb(free_bytes),
        }
    return None


def probe_url(url: str, headers: Optional[dict] = None, timeout: int = 30) -> tuple[int, int]:
    """HEAD request: (status_code, content_length). content_length is 0 if unknown."""
    hdrs = dict(DEFAULT_HEADERS)
    if headers:
        hdrs.update(headers)
    try:
        resp = requests.head(url, headers=hdrs, timeout=timeout, allow_redirects=True)
        size = int(resp.headers.get("content-length", 0) or 0)
        return resp.status_code, size
    except Exception:
        return 0, 0


def _build_headers(token: Optional[str] = None, headers: Optional[dict] = None) -> dict:
    hdrs = dict(DEFAULT_HEADERS)
    if headers:
        hdrs.update(headers)
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    return hdrs


def _try_aria2c(
    url: str,
    dest_dir: str,
    filename: str,
    header_lines: list[str],
    on_progress: Optional[Callable[[int], None]],
) -> Optional[str]:
    if not shutil.which("aria2c"):
        return None

    os.makedirs(dest_dir, exist_ok=True)
    out_path = os.path.join(dest_dir, filename)

    cmd = [
        "aria2c",
        "-x", "16",
        "-s", "16",
        "-k", "1M",
        "--continue=true",
        "--auto-file-renaming=false",
        "--summary-interval=1",
        "--console-log-level=warn",
    ]
    for line in header_lines:
        cmd.extend(["--header", line])
    cmd.extend(["-d", dest_dir, "-o", filename, url])

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            match = re.search(r"\((\d+)%\)", line)
            if match and on_progress:
                on_progress(int(match.group(1)))
        proc.wait()
        if proc.returncode == 0 and os.path.isfile(out_path) and os.path.getsize(out_path) > 0:
            return out_path
    except Exception:
        pass
    return None


def _fetch_requests(
    url: str,
    output_path: str,
    hdrs: dict,
    on_progress: Optional[Callable[[int], None]],
    timeout: int,
) -> str:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    response = requests.get(url, stream=True, headers=hdrs, timeout=timeout)
    response.raise_for_status()

    total_size = int(response.headers.get("content-length", 0) or 0)
    downloaded = 0
    last_pct = -1
    last_bytes_update = 0
    update_interval = 1024 * 1024 * 5

    with open(output_path, "wb") as handle:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue
            handle.write(chunk)
            downloaded += len(chunk)

            if not on_progress:
                continue

            if total_size > 0:
                pct = min(int((downloaded / total_size) * 100), 100)
                if pct != last_pct:
                    last_pct = pct
                    on_progress(pct)
            elif downloaded - last_bytes_update >= update_interval:
                last_bytes_update = downloaded
                on_progress(0)

    if on_progress and total_size > 0 and last_pct < 100:
        on_progress(100)

    return output_path


def fetch(
    url: str,
    output_path: str,
    on_progress: Optional[Callable[[int], None]] = None,
    token: Optional[str] = None,
    headers: Optional[dict] = None,
    timeout: int = 300,
) -> str:
    """
    Download url to output_path.
    Uses aria2c when available, otherwise streams via requests.
    on_progress receives percent 0-100 (0 may mean unknown size / in progress).
    """
    dest_dir = os.path.dirname(output_path) or "."
    filename = os.path.basename(output_path)
    if not filename or filename in (".", ".."):
        raise ValueError("Invalid output filename")

    hdrs = _build_headers(token, headers)
    header_lines = [f"{key}: {value}" for key, value in hdrs.items()]

    aria2_path = _try_aria2c(url, dest_dir, filename, header_lines, on_progress)
    if aria2_path:
        if on_progress:
            on_progress(100)
        return aria2_path

    return _fetch_requests(url, output_path, hdrs, on_progress, timeout)
