#!/usr/bin/env python3
"""Build portable zip for Smyshnikov Preset Downloader (Windows-oriented)."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESKTOP = ROOT / "desktop"
DIST = DESKTOP / "dist"
STAGING = DIST / "SmyshnikovComfyUIHub-portable"
PYTHON_EMBED_URL = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"


def run(cmd: list[str], *, cwd: Path | None = None) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd or ROOT, check=True)


def download_embed_python(target: Path) -> Path:
    import urllib.request

    embed_zip = target / "python-embed.zip"
    target.mkdir(parents=True, exist_ok=True)
    if not embed_zip.is_file():
        print(f"Downloading embedded Python to {embed_zip}")
        urllib.request.urlretrieve(PYTHON_EMBED_URL, embed_zip)
    python_dir = target / "python"
    if not (python_dir / "python.exe").is_file():
        shutil.unpack_archive(str(embed_zip), str(python_dir))
        pth = python_dir / "python311._pth"
        if pth.is_file():
            text = pth.read_text(encoding="utf-8")
            if "import site" not in text:
                pth.write_text(text.rstrip() + "\nimport site\n", encoding="utf-8")
        get_pip = target / "get-pip.py"
        if not get_pip.is_file():
            urllib.request.urlretrieve(GET_PIP_URL, get_pip)
        run([str(python_dir / "python.exe"), str(get_pip)])
    return python_dir / "python.exe"


def stage_portable(python_exe: Path | None) -> Path:
    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir(parents=True)

    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    for name in ("services", "presets", "node_presets"):
        shutil.copytree(ROOT / name, STAGING / name, ignore=ignore)
    shutil.copytree(
        ROOT / "desktop",
        STAGING / "desktop",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "dist", "build"),
    )

    shutil.copy2(ROOT / "requirements.txt", STAGING / "requirements.txt")

    if python_exe and python_exe.is_file():
        embed_dest = STAGING / "python"
        if not embed_dest.exists():
            shutil.copytree(python_exe.parent, embed_dest)
        launcher_py = STAGING / "python" / "python.exe"
    else:
        launcher_py = Path(sys.executable)

    run([str(launcher_py), "-m", "pip", "install", "-r", "requirements.txt", "-q"], cwd=STAGING)

    start_bat = STAGING / "Start ComfyUI Hub.bat"
    py_cmd = "python\\python.exe" if (STAGING / "python" / "python.exe").exists() else sys.executable
    start_bat.write_text(
        "@echo off\r\n"
        "cd /d \"%~dp0\"\r\n"
        "if not exist desktop\\config.json copy desktop\\config.example.json desktop\\config.json\r\n"
        f"\"{py_cmd}\" desktop\\launcher.py\r\n"
        "pause\r\n",
        encoding="utf-8",
    )

    setup_bat = STAGING / "Setup ComfyUI path.bat"
    setup_bat.write_text(
        "@echo off\r\n"
        "cd /d \"%~dp0\"\r\n"
        f"\"{py_cmd}\" desktop\\launcher.py --setup\r\n"
        "pause\r\n",
        encoding="utf-8",
    )

    readme = STAGING / "README.txt"
    readme.write_text(
        "Smyshnikov ComfyUI Hub (portable)\n\n"
        "1. Запустите 'Setup ComfyUI path.bat' и укажите папку ComfyUI\n"
        "2. Запустите 'Start ComfyUI Hub.bat'\n"
        "3. Откроется панель управления на http://127.0.0.1:8084/\n",
        encoding="utf-8",
    )
    return STAGING


def make_zip(staging: Path) -> Path:
    DIST.mkdir(parents=True, exist_ok=True)
    zip_path = DIST / "SmyshnikovComfyUIHub-portable.zip"
    if zip_path.is_file():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in staging.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(staging))
    print(f"Created {zip_path}")
    return zip_path


def ensure_build_venv() -> Path:
    venv = DIST / "_build_venv"
    if sys.platform == "win32":
        py = venv / "Scripts" / "python.exe"
    else:
        py = venv / "bin" / "python"
    if not py.is_file():
        run([sys.executable, "-m", "venv", str(venv)])
        run([str(py), "-m", "pip", "install", "-U", "pip", "wheel", "-q"])
        run([str(py), "-m", "pip", "install", "-r", "requirements.txt", "-q"])
        run([str(py), "-m", "pip", "install", "-r", "desktop/build/requirements-build.txt", "-q"])
    return py


def build_pyinstaller() -> Path:
    py = ensure_build_venv()
    spec = DESKTOP / "build" / "preset_downloader.spec"
    run(
        [
            str(py),
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            f"--distpath={DIST}",
            f"--workpath={DESKTOP / 'build' / 'pyinstaller_work'}",
            str(spec),
        ],
        cwd=DESKTOP / "build",
    )
    out = DIST / "SmyshnikovComfyUIHub"
    if not out.is_dir():
        raise SystemExit(f"PyInstaller output not found: {out}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--portable", action="store_true", help="Build portable zip")
    parser.add_argument("--pyinstaller", action="store_true", help="Build PyInstaller folder")
    parser.add_argument("--embed-python", action="store_true", help="Bundle embedded Python (portable)")
    args = parser.parse_args()

    if not args.portable and not args.pyinstaller:
        args.portable = True

    if args.pyinstaller:
        build_pyinstaller()

    if args.portable:
        python_exe = None
        if args.embed_python:
            python_exe = download_embed_python(DIST / "_cache")
        staging = stage_portable(python_exe)
        make_zip(staging)


if __name__ == "__main__":
    main()
