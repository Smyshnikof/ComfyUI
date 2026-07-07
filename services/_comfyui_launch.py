"""Detect and launch ComfyUI (standard venv, Windows portable, .bat profiles)."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from services._config import BIND_HOST, COMFYUI_PORT, COMFYUI_ROOT

_LAUNCHER_PROFILES: dict[str, dict] = {
    "nvidia_gpu": {
        "label": "NVIDIA GPU (run_nvidia_gpu.bat)",
        "args": ["--windows-standalone-build"],
        "env": {},
    },
    "nvidia_gpu_fast_fp16_accumulation": {
        "label": "NVIDIA GPU fast FP16 (run_nvidia_gpu_fast_fp16_accumulation.bat)",
        "args": ["--windows-standalone-build", "--fast", "fp16_accumulation"],
        "env": {},
    },
    "cpu": {
        "label": "CPU (run_cpu.bat)",
        "args": ["--cpu", "--windows-standalone-build"],
        "env": {},
    },
    "nvidia_no_gpu": {
        "label": "Без GPU (run_nvidia_no_gpu.bat)",
        "args": ["--windows-standalone-build"],
        "env": {"CUDA_VISIBLE_DEVICES": ""},
    },
}


@dataclass(frozen=True)
class ComfyUIInstall:
    comfy_dir: Path
    portable_root: Path | None
    embedded_python: Path | None
    main_py: Path


def _has_main(path: Path) -> bool:
    return (path / "main.py").is_file()


def resolve_install(comfy_path: Path | None = None) -> ComfyUIInstall:
    root = Path(comfy_path or COMFYUI_ROOT)
    if _has_main(root):
        comfy_dir = root
        portable_root = root.parent if (root.parent / "python_embeded").is_dir() else None
    elif _has_main(root / "ComfyUI"):
        portable_root = root
        comfy_dir = root / "ComfyUI"
    else:
        comfy_dir = root
        portable_root = None

    embedded = None
    if portable_root and (portable_root / "python_embeded" / "python.exe").is_file():
        embedded = portable_root / "python_embeded" / "python.exe"

    return ComfyUIInstall(
        comfy_dir=comfy_dir.resolve(),
        portable_root=portable_root.resolve() if portable_root else None,
        embedded_python=embedded,
        main_py=(comfy_dir / "main.py").resolve(),
    )


def list_launcher_profiles(install: ComfyUIInstall | None = None) -> list[dict]:
    install = install or resolve_install()
    found: list[dict] = []
    if install.portable_root:
        for bat in sorted(install.portable_root.glob("run_*.bat")):
            key = bat.stem.removeprefix("run_")
            meta = _LAUNCHER_PROFILES.get(key, {})
            found.append({
                "id": key,
                "label": meta.get("label") or bat.name,
                "bat": bat.name,
            })
    if not found:
        found.append({
            "id": "standard",
            "label": "Стандартный (python main.py)",
            "bat": None,
        })
    return found


def get_selected_launcher_id() -> str:
    from services._config import read_desktop_config

    cfg = read_desktop_config().get("comfyui_launcher") or ""
    cfg = str(cfg).strip()
    if cfg:
        return cfg
    install = resolve_install()
    if install.embedded_python and install.portable_root:
        for preferred in ("nvidia_gpu", "nvidia_gpu_fast_fp16_accumulation", "cpu"):
            if (install.portable_root / f"run_{preferred}.bat").is_file():
                return preferred
    return "standard"


def build_comfyui_command(
    launcher_id: str | None = None,
    *,
    port: int | None = None,
    host: str | None = None,
) -> tuple[list[str], str, dict[str, str]]:
    install = resolve_install()
    launcher_id = launcher_id or get_selected_launcher_id()
    listen_host = host or BIND_HOST
    listen_port = port or COMFYUI_PORT

    profile = _LAUNCHER_PROFILES.get(launcher_id, {})
    extra_env = dict(profile.get("env") or {})

    extra_args = os.environ.get("COMFYUI_EXTRA_ARGS", "").strip()
    tail_args = ["--listen", listen_host, "--port", str(listen_port)]
    if extra_args:
        tail_args.extend(extra_args.split())

    if install.embedded_python and launcher_id != "standard":
        if install.portable_root and install.comfy_dir == install.portable_root / "ComfyUI":
            cmd = [
                str(install.embedded_python),
                "-s",
                "ComfyUI\\main.py",
                *(profile.get("args") or ["--windows-standalone-build"]),
                *tail_args,
            ]
            return cmd, str(install.portable_root), extra_env

    py = _find_python(install)
    cmd = [
        py,
        str(install.main_py),
        *(profile.get("args") or []),
        *tail_args,
    ]
    return cmd, str(install.comfy_dir), extra_env


def _find_python(install: ComfyUIInstall) -> str:
    if install.embedded_python and install.embedded_python.is_file():
        return str(install.embedded_python)
    for candidate in (
        install.comfy_dir / "venv" / "Scripts" / "python.exe",
        install.comfy_dir / "venv" / "bin" / "python",
    ):
        if candidate.is_file():
            return str(candidate)
    import sys

    return os.environ.get("COMFYUI_PYTHON") or sys.executable


def start_comfyui_process(log_path: str, launcher_id: str | None = None) -> subprocess.Popen:
    cmd, cwd, extra_env = build_comfyui_command(launcher_id)
    env = os.environ.copy()
    env.update(extra_env)
    log_file = open(log_path, "a", encoding="utf-8")
    return subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=log_file,
        stderr=log_file,
        start_new_session=True,
    )
