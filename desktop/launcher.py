#!/usr/bin/env python3
"""Smyshnikov ComfyUI Hub — desktop launcher (starts hub + optional services)."""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

DESKTOP_DIR = Path(__file__).resolve().parent
if getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None):
    REPO_ROOT = Path(sys._MEIPASS)
else:
    REPO_ROOT = DESKTOP_DIR.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.chdir(REPO_ROOT)


def _configure_console() -> None:
    """UTF-8 in Windows cmd/powershell — без кракозябр."""
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


_configure_console()


def _println(text: str = "") -> None:
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"), flush=True)


def _ok(msg: str) -> None:
    _println(f"[OK] {msg}")


def _warn(msg: str) -> None:
    _println(f"[!] {msg}")


def _config_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "desktop" / "config.json"
    return DESKTOP_DIR / "config.json"


def _load_config() -> dict:
    path = _config_path()
    if not path.is_file():
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_config(data: dict) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _apply_config_env(cfg: dict) -> None:
    comfy = (cfg.get("comfyui_path") or "").strip()
    models = (cfg.get("models_root") or "").strip()
    if comfy:
        os.environ["COMFYUI_ROOT"] = comfy
        os.environ["OUTPUT_ROOT"] = str(Path(comfy) / "output")
    if models:
        os.environ["MODELS_ROOT"] = models
    elif comfy:
        os.environ["MODELS_ROOT"] = str(Path(comfy) / "models")
    if cfg.get("hub_port"):
        os.environ["HUB_PORT"] = str(cfg["hub_port"])
    if cfg.get("host"):
        os.environ["PRESET_DOWNLOADER_HOST"] = str(cfg["host"])


def _setup_interactive(*, force: bool = False) -> None:
    from services._config import detect_comfyui_installations, normalize_comfyui_root, validate_comfyui_path

    cfg = _load_config()
    current = (cfg.get("comfyui_path") or "").strip()
    current_check = validate_comfyui_path(current) if current else None

    if not force and current_check and current_check.get("valid"):
        return

    _println()
    _println("=" * 52)
    _println("  Smyshnikov ComfyUI Hub")
    _println("  Настройка пути к ComfyUI" if force else "  Первичная настройка")
    _println("=" * 52)
    _println()
    if current:
        status = "[OK]" if current_check and current_check.get("valid") else "[!]"
        _println(f"  Текущий путь: {current}")
        _println(f"  {status} {(current_check or {}).get('message', '')}")
        _println()

    detected = detect_comfyui_installations()
    comfy_root: Path | None = None

    if detected:
        _println("Найдены установки ComfyUI:")
        for idx, path in enumerate(detected, start=1):
            mark = " *" if current and str(path) == current_check.get("normalized", current) else ""
            _println(f"  [{idx}] {path}{mark}")
        _println("  [0] Указать путь вручную")
        if force and current_check and current_check.get("valid"):
            _println("  [Enter] Оставить текущий путь")
        default_choice = "1"
        if current_check and current_check.get("valid"):
            for idx, path in enumerate(detected, start=1):
                if str(path) == current_check["normalized"]:
                    default_choice = str(idx)
                    break
        prompt = f"\nВыберите номер [{default_choice}]: "
        choice = input(prompt).strip() or default_choice
        if choice == "" and force:
            return
        if choice == "0":
            manual = input("Путь к ComfyUI (папка с models/ или portable-корень): ").strip().strip('"')
            comfy_root = normalize_comfyui_root(Path(manual))
        else:
            try:
                comfy_root = detected[int(choice) - 1]
            except (ValueError, IndexError):
                comfy_root = detected[0]
    else:
        manual = input(
            "Путь к ComfyUI (папка с models/ или portable-корень): "
        ).strip().strip('"')
        comfy_root = normalize_comfyui_root(Path(manual))

    if not comfy_root:
        _warn("Не удалось определить папку ComfyUI — проверьте путь")
        if current_check and current_check.get("valid"):
            return
        sys.exit(1)

    check = validate_comfyui_path(str(comfy_root))
    if not check.get("valid"):
        _warn(check.get("message", "Неверный путь"))

    cfg["comfyui_path"] = check["normalized"]
    cfg.setdefault("hub_port", 8084)
    cfg.setdefault("host", "127.0.0.1")
    cfg.setdefault("open_browser", True)
    cfg.setdefault("auto_start_services", True)
    portable = Path(check["normalized"]).parent
    if (portable / "python_embeded").is_dir():
        cfg.setdefault("comfyui_launcher", "nvidia_gpu")
    _write_config(cfg)
    _apply_config_env(cfg)
    _println()
    _ok(f"Настройки сохранены: {_config_path()}")
    _println(f"     ComfyUI: {check['normalized']}")
    if check.get("portable"):
        _println("     Тип: Windows portable (python_embeded)")
    _println()


def _open_browser_later(url: str, delay: float = 1.5) -> None:
    def _run() -> None:
        time.sleep(delay)
        webbrowser.open(url)

    threading.Thread(target=_run, daemon=True).start()


def _wait_for_health(url: str, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.4)
    return False


def _print_start_all_result(data: dict) -> None:
    _println()
    _println("--- Автозапуск сервисов ---")
    started = data.get("started") or []
    skipped = data.get("skipped") or []
    errors = data.get("errors") or []

    if started:
        _println("Запущено:")
        for name in started:
            _println(f"  + {name}")

    if skipped:
        _println("Уже работали:")
        for name in skipped:
            _println(f"  ~ {name}")

    if errors:
        _println("Не удалось запустить:")
        for err in errors:
            _println(f"  x {err}")

    if not errors and (started or skipped):
        _ok("Сервисы готовы. Панель управления откроется в браузере.")
    elif not started and not skipped and not errors:
        _println("Нет сервисов для запуска.")
    _println("----------------------------")
    _println()


def _auto_start_services(host: str, hub_port: int) -> None:
    cfg = _load_config()
    if not cfg.get("auto_start_services", True):
        return
    health = f"http://{host}:{hub_port}/health"
    _println("Ожидание панели управления...")
    if not _wait_for_health(health):
        _warn("Панель не ответила вовремя — автозапуск пропущен")
        return
    try:
        req = urllib.request.Request(
            f"http://{host}:{hub_port}/api/services/start-all",
            method="POST",
            data=b"",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw) if raw.strip() else {}
        _print_start_all_result(data)
    except json.JSONDecodeError:
        _warn("Не удалось разобрать ответ сервера при автозапуске")
    except Exception as exc:
        _warn(f"Автозапуск: {exc}")


def _run_uvicorn_subprocess(host: str, port: int, env: dict, log_file: Path) -> subprocess.Popen:
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "services.dashboard:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    log_handle = open(log_file, "a", encoding="utf-8")
    return subprocess.Popen(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )


def _run_uvicorn_inprocess(host: str, port: int) -> None:
    import uvicorn

    uvicorn.run(
        "services.dashboard:app",
        host=host,
        port=int(port),
        log_level="info",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Smyshnikov ComfyUI Hub launcher")
    parser.add_argument("--setup", action="store_true", help="Мастер настройки")
    parser.add_argument("--configure", action="store_true", help="Только смена пути (без запуска hub)")
    parser.add_argument("--force", action="store_true", help="Переоткрыть мастер даже если путь уже задан")
    parser.add_argument("--hub-port", type=int, default=None, help="Порт панели управления")
    parser.add_argument("--no-browser", action="store_true", help="Не открывать браузер")
    parser.add_argument("--no-auto-start", action="store_true", help="Не запускать сервисы автоматически")
    parser.add_argument("--host", default=None, help="Хост (127.0.0.1)")
    args = parser.parse_args()

    if args.configure:
        _setup_interactive(force=True)
        return 0

    if args.setup or args.force or not _config_path().is_file():
        _setup_interactive(force=args.force or args.setup)

    cfg = _load_config()
    _apply_config_env(cfg)

    from services._config import HUB_PORT, HOST, LOGS_DIR, ensure_dirs

    hub_port = args.hub_port or int(cfg.get("hub_port") or HUB_PORT)
    host = (args.host or cfg.get("host") or HOST).strip()
    open_browser = not args.no_browser and bool(cfg.get("open_browser", True))
    auto_start = not args.no_auto_start and bool(cfg.get("auto_start_services", True))
    comfy_path = (cfg.get("comfyui_path") or os.environ.get("COMFYUI_ROOT") or "").strip()

    ensure_dirs()
    log_file = LOGS_DIR / "hub.log"
    hub_url = f"http://{host}:{hub_port}/"

    _println()
    _println("Smyshnikov ComfyUI Hub")
    _println(f"  ComfyUI : {comfy_path or '(не указан)'}")
    _println(f"  Панель  : {hub_url}")
    _println(f"  Лог     : {log_file}")
    _println("  Стоп    : Ctrl+C")
    _println()

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")

    if open_browser:
        _open_browser_later(hub_url)

    if auto_start:
        threading.Thread(
            target=_auto_start_services,
            args=(host, hub_port),
            daemon=True,
        ).start()

    if getattr(sys, "frozen", False):
        _run_uvicorn_inprocess(host, hub_port)
        return 0

    proc = _run_uvicorn_subprocess(host, hub_port, env, log_file)

    def _shutdown(signum: int, _frame: object) -> None:
        _println()
        _println("Остановка панели управления...")
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    return proc.wait()


if __name__ == "__main__":
    raise SystemExit(main())
