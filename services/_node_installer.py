"""Git clone / pip install for ComfyUI custom nodes."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Callable

from services._comfyui_launch import resolve_install
from services._config import CUSTOM_NODES_ROOT
from services._node_presets import repo_folder_name

ProgressCallback = Callable[[str, int, int], None]
LogCallback = Callable[[str], None]

GIT_CLONE_TIMEOUT = 600
PIP_TIMEOUT = 600
INSTALL_SCRIPT_TIMEOUT = 300


def git_available() -> bool:
    import shutil
    return shutil.which("git") is not None


def resolve_python() -> str:
    install = resolve_install()
    if install.embedded_python and install.embedded_python.is_file():
        return str(install.embedded_python)
    for candidate in (
        install.comfy_dir / "venv" / "Scripts" / "python.exe",
        install.comfy_dir / "venv" / "bin" / "python",
    ):
        if candidate.is_file():
            return str(candidate)
    return os.environ.get("COMFYUI_PYTHON") or sys.executable


def _path_under_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def resolve_repo_path(folder_name: str) -> tuple[Path | None, str | None]:
    root = Path(CUSTOM_NODES_ROOT).resolve()
    root.mkdir(parents=True, exist_ok=True)
    safe = os.path.basename(folder_name.strip().rstrip("/\\"))
    if not safe or safe in (".", ".."):
        return None, "Недопустимое имя папки"
    dest = (root / safe).resolve()
    if not _path_under_root(dest, root):
        return None, "Путь выходит за пределы custom_nodes/"
    return dest, None


def _run_cmd(
    cmd: list[str],
    *,
    cwd: str | None = None,
    timeout: int = 300,
    on_log: LogCallback | None = None,
) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        if on_log and output.strip():
            on_log(output.strip()[-2000:])
        return proc.returncode, output
    except subprocess.TimeoutExpired as exc:
        msg = f"Таймаут ({timeout}s): {' '.join(cmd[:3])}..."
        if on_log:
            on_log(msg)
        return -1, msg
    except OSError as exc:
        msg = str(exc)
        if on_log:
            on_log(msg)
        return -1, msg


def clone_or_update_repo(
    url: str,
    dest: Path,
    *,
    branch: str | None = None,
    recursive: bool = True,
    force: bool = False,
    on_log: LogCallback | None = None,
) -> tuple[bool, str]:
    if not git_available():
        return False, "git не найден в PATH — установите Git for Windows"

    if dest.is_dir() and (dest / ".git").is_dir():
        if force:
            code, out = _run_cmd(
                ["git", "fetch", "--all"],
                cwd=str(dest),
                timeout=GIT_CLONE_TIMEOUT,
                on_log=on_log,
            )
            if code != 0:
                return False, f"git fetch failed: {out[-500:]}"
            reset_target = f"origin/{branch}" if branch else "origin/HEAD"
            code, out = _run_cmd(
                ["git", "reset", "--hard", reset_target],
                cwd=str(dest),
                timeout=120,
                on_log=on_log,
            )
            if code != 0:
                return False, f"git reset failed: {out[-500:]}"
        else:
            pull_cmd = ["git", "pull", "--ff-only"]
            if recursive:
                pull_cmd.append("--recurse-submodules")
            code, out = _run_cmd(
                pull_cmd,
                cwd=str(dest),
                timeout=GIT_CLONE_TIMEOUT,
                on_log=on_log,
            )
            if code != 0:
                return False, f"git pull failed: {out[-500:]}"
        if recursive:
            code, out = _run_cmd(
                ["git", "submodule", "update", "--init", "--recursive"],
                cwd=str(dest),
                timeout=GIT_CLONE_TIMEOUT,
                on_log=on_log,
            )
            if code != 0:
                return False, f"git submodule failed: {out[-500:]}"
        return True, "updated"

    if dest.exists() and not (dest / ".git").is_dir():
        return False, f"Папка {dest.name} существует, но это не git-репозиторий"

    cmd = ["git", "clone"]
    if recursive:
        cmd.append("--recursive")
    if branch:
        cmd.extend(["--branch", branch])
    cmd.extend([url, str(dest)])
    code, out = _run_cmd(cmd, timeout=GIT_CLONE_TIMEOUT, on_log=on_log)
    if code != 0:
        return False, f"git clone failed: {out[-500:]}"
    return True, "cloned"


def find_requirements_files(repo_path: Path) -> list[Path]:
    found: list[Path] = []
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules")]
        if "requirements.txt" in files:
            found.append(Path(root) / "requirements.txt")
    return found


def install_requirements(
    repo_path: Path,
    python_exe: str,
    *,
    on_log: LogCallback | None = None,
) -> tuple[bool, str]:
    req_files = find_requirements_files(repo_path)
    if not req_files:
        return True, "no requirements"
    errors: list[str] = []
    for req in req_files:
        if on_log:
            on_log(f"pip install -r {req.relative_to(repo_path)}")
        code, out = _run_cmd(
            [python_exe, "-m", "pip", "install", "--no-cache-dir", "-r", str(req)],
            cwd=str(repo_path),
            timeout=PIP_TIMEOUT,
            on_log=on_log,
        )
        if code != 0:
            errors.append(f"{req.name}: {out[-300:]}")
    if errors:
        return False, "; ".join(errors)
    return True, f"pip ok ({len(req_files)} files)"


def run_install_scripts(
    repo_path: Path,
    python_exe: str,
    *,
    on_log: LogCallback | None = None,
) -> tuple[bool, str]:
    install_py = repo_path / "install.py"
    if not install_py.is_file():
        return True, "no install.py"
    if on_log:
        on_log(f"python install.py in {repo_path.name}")
    code, out = _run_cmd(
        [python_exe, str(install_py)],
        cwd=str(repo_path),
        timeout=INSTALL_SCRIPT_TIMEOUT,
        on_log=on_log,
    )
    if code != 0:
        return False, f"install.py failed: {out[-500:]}"
    return True, "install.py ok"


def install_repo(
    url: str,
    *,
    branch: str | None = None,
    recursive: bool = True,
    folder: str | None = None,
    force: bool = False,
    on_progress: ProgressCallback | None = None,
    on_log: LogCallback | None = None,
) -> tuple[bool, str, str]:
    """Install single repo. Returns (ok, folder_name, message)."""
    folder_name = repo_folder_name(url, folder)
    dest, err = resolve_repo_path(folder_name)
    if err or dest is None:
        return False, folder_name, err or "bad path"

    if on_progress:
        on_progress("cloning", 0, 3)
    ok, msg = clone_or_update_repo(
        url, dest, branch=branch, recursive=recursive, force=force, on_log=on_log,
    )
    if not ok:
        return False, folder_name, msg

    python_exe = resolve_python()
    if on_progress:
        on_progress("pip", 1, 3)
    ok, pip_msg = install_requirements(dest, python_exe, on_log=on_log)
    if not ok:
        return False, folder_name, pip_msg

    if on_progress:
        on_progress("install.py", 2, 3)
    ok, install_msg = run_install_scripts(dest, python_exe, on_log=on_log)
    if not ok:
        return False, folder_name, install_msg

    if on_progress:
        on_progress("done", 3, 3)
    return True, folder_name, f"{msg}; {pip_msg}; {install_msg}"


def is_repo_installed(url: str, folder: str | None = None) -> bool:
    folder_name = repo_folder_name(url, folder)
    dest, err = resolve_repo_path(folder_name)
    if err or dest is None:
        return False
    return dest.is_dir() and ((dest / ".git").is_dir() or any(dest.iterdir()))
