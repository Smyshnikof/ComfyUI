"""
Dashboard Service for ComfyUI Docker
Provides system telemetry, service status, and RunPod shutdown scheduling.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Tuple
import os
import subprocess
import sys
import threading
import time
import shutil
import httpx
from pathlib import Path

from services._config import (
    AUTO_START_SERVICES,
    BIND_HOST,
    COMFYUI_PORT,
    COMFYUI_ROOT,
    HOST,
    LOGS_DIR,
    HUB_PORT,
    is_desktop_mode,
    service_url,
)

app = FastAPI(title="Smyshnikov ComfyUI Hub")

# ============================================================================
# Pydantic Models
# ============================================================================

class ShutdownRequest(BaseModel):
    value: int
    unit: str  # "seconds", "minutes", "hours"


class ShutdownStatus(BaseModel):
    scheduled: bool
    time_remaining: Optional[int] = None
    shutdown_time: Optional[str] = None


class DiskUsage(BaseModel):
    mount: str
    total: int
    used: int
    free: int
    pct: int


class GPUInfo(BaseModel):
    index: int
    name: str
    util: Optional[int] = None
    mem_used: Optional[int] = None
    mem_total: Optional[int] = None


class Telemetry(BaseModel):
    host: str
    uptime_seconds: float
    load_avg: List[float]
    cpu_count: int
    mem_total: int
    mem_used: int
    mem_free: int
    disks: List[DiskUsage]
    gpus: List[GPUInfo]


class ServiceEntry(BaseModel):
    name: str
    display: str
    port: int
    running: bool
    state: str = "stopped"  # running | starting | stopped
    managed: bool = False
    url: Optional[str] = None


# ============================================================================
# Shutdown Scheduler
# ============================================================================

shutdown_scheduled = False
shutdown_time = None
shutdown_thread = None
shutdown_lock = threading.Lock()


def _runpod_shutdown_command() -> Tuple[Optional[List[str]], Optional[str], str]:
    """Determine the appropriate RunPod shutdown command."""
    pod_id = os.environ.get("RUNPOD_POD_ID", "").strip()
    if not pod_id:
        return None, None, ""

    mode = os.environ.get("RUNPOD_POD_SHUTDOWN", "").strip().lower()
    if mode in ("remove", "terminate", "delete"):
        return ["runpodctl", "remove", "pod", pod_id], "remove", pod_id
    if mode in ("stop", "halt"):
        return ["runpodctl", "stop", "pod", pod_id], "stop", pod_id

    volume_type = os.environ.get("RUNPOD_VOLUME_TYPE", "").strip().lower()
    if volume_type in ("network", "network-volume", "nfs", "volume"):
        return ["runpodctl", "remove", "pod", pod_id], "remove", pod_id
    if volume_type in ("local", "local-storage", "ephemeral", "local-ssd"):
        return ["runpodctl", "stop", "pod", pod_id], "stop", pod_id

    if os.environ.get("RUNPOD_NETWORK_VOLUME_ID"):
        return ["runpodctl", "remove", "pod", pod_id], "remove", pod_id

    # Default to stop to avoid deleting pods with local storage.
    return ["runpodctl", "stop", "pod", pod_id], "stop", pod_id


def shutdown_worker():
    """Worker function that waits for shutdown time and executes shutdown."""
    global shutdown_scheduled, shutdown_time

    while True:
        with shutdown_lock:
            if not shutdown_scheduled or shutdown_time is None:
                break

            time_remaining = shutdown_time - time.time()

            if time_remaining <= 0:
                # Time to shutdown
                cmd, _mode, _pod_id = _runpod_shutdown_command()
                if cmd:
                    try:
                        subprocess.run(cmd, check=False)
                    except FileNotFoundError:
                        os.system("shutdown -h now")
                else:
                    os.system("shutdown -h now")
                break

            # Sleep for a short time, then check again
            shutdown_lock.release()
            time.sleep(min(10, time_remaining))
            shutdown_lock.acquire()


def schedule_shutdown(request: ShutdownRequest) -> None:
    """Schedule a shutdown for the specified time."""
    global shutdown_scheduled, shutdown_time, shutdown_thread

    if request.value <= 0:
        raise HTTPException(status_code=400, detail="Value must be greater than 0")

    multipliers = {"seconds": 1, "minutes": 60, "hours": 3600}
    if request.unit not in multipliers:
        raise HTTPException(
            status_code=400,
            detail="Invalid unit. Must be: seconds, minutes, hours",
        )

    delay_seconds = request.value * multipliers[request.unit]

    with shutdown_lock:
        shutdown_scheduled = True
        shutdown_time = time.time() + delay_seconds

        if shutdown_thread is None or not shutdown_thread.is_alive():
            shutdown_thread = threading.Thread(target=shutdown_worker, daemon=True)
            shutdown_thread.start()


def cancel_shutdown() -> None:
    """Cancel the scheduled shutdown."""
    global shutdown_scheduled, shutdown_time, shutdown_thread

    with shutdown_lock:
        shutdown_scheduled = False
        shutdown_time = None
        shutdown_thread = None


def get_shutdown_status() -> ShutdownStatus:
    """Get the current shutdown status."""
    global shutdown_scheduled, shutdown_time

    with shutdown_lock:
        if not shutdown_scheduled or shutdown_time is None:
            return ShutdownStatus(scheduled=False)

        time_remaining = max(0, int(shutdown_time - time.time()))
        shutdown_time_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(shutdown_time))

        return ShutdownStatus(
            scheduled=True,
            time_remaining=time_remaining,
            shutdown_time=shutdown_time_str,
        )


# ============================================================================
# Telemetry Functions
# ============================================================================

def get_meminfo():
    """Get memory information (Linux /proc or Windows)."""
    meminfo = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                key, val = line.split(":", 1)
                meminfo[key.strip()] = int(val.strip().split()[0]) * 1024
    except FileNotFoundError:
        if os.name == "nt":
            try:
                import ctypes

                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]

                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                    total = int(stat.ullTotalPhys)
                    free = int(stat.ullAvailPhys)
                    return total, max(total - free, 0), free
            except Exception:
                pass
    total = meminfo.get("MemTotal", 0)
    free = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
    used = max(total - free, 0)
    return total, used, free


def disk_usage(path: str) -> DiskUsage:
    """Get disk usage for a path."""
    try:
        st = shutil.disk_usage(path)
        pct = int((st.used / st.total) * 100) if st.total else 0
        return DiskUsage(mount=path, total=st.total, used=st.used, free=st.free, pct=pct)
    except Exception:
        return DiskUsage(mount=path, total=0, used=0, free=0, pct=0)


def get_gpus() -> List[GPUInfo]:
    """Get GPU information via nvidia-smi."""
    gpus: List[GPUInfo] = []
    candidates = [
        shutil.which("nvidia-smi"),
        "/usr/bin/nvidia-smi",
        "/usr/local/bin/nvidia-smi",
    ]
    candidates = [c for c in candidates if c]
    for exe in candidates:
        try:
            out = subprocess.check_output(
                [
                    exe,
                    "--query-gpu=index,name,utilization.gpu,memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                text=True,
                timeout=5,
            )
            for line in out.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 5:
                    gpus.append(
                        GPUInfo(
                            index=int(parts[0]),
                            name=parts[1],
                            util=int(parts[2]) if parts[2].isdigit() else 0,
                            mem_used=int(parts[3]) * 1024 * 1024 if parts[3].isdigit() else 0,
                            mem_total=int(parts[4]) * 1024 * 1024 if parts[4].isdigit() else 0,
                        )
                    )
            if gpus:
                break
        except Exception:
            continue
    return gpus


def get_telemetry() -> Telemetry:
    """Collect all telemetry data."""
    import socket

    host = os.environ.get("RUNPOD_POD_ID") or os.environ.get("RUNPOD_HOST_ID") or ""
    if not host:
        host = socket.gethostname() if is_desktop_mode() else "local"

    uptime_seconds = 0.0
    try:
        with open("/proc/uptime") as f:
            host_uptime = float(f.read().split()[0])
        with open("/proc/1/stat") as f:
            stat = f.read().split()
            start_ticks = float(stat[21])
        hz = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
        start_secs = start_ticks / hz
        uptime_seconds = max(host_uptime - start_secs, 0.0)
    except Exception:
        if is_desktop_mode():
            try:
                uptime_seconds = float(time.time() - ps_boot_time())
            except Exception:
                uptime_seconds = 0.0

    load_avg = list(os.getloadavg()) if hasattr(os, "getloadavg") else [0.0, 0.0, 0.0]
    cpu_count = os.cpu_count() or 1

    mem_total, mem_used, mem_free = get_meminfo()

    disks = []
    if is_desktop_mode():
        for path in (str(COMFYUI_ROOT), str(COMFYUI_ROOT / "models"), str(LOGS_DIR.parent)):
            if os.path.exists(path):
                disks.append(disk_usage(path))
        if not disks:
            disks.append(disk_usage(os.path.expanduser("~")))
    else:
        disks = [disk_usage("/")]
        if os.path.exists("/workspace"):
            disks.append(disk_usage("/workspace"))

    gpus = get_gpus()

    return Telemetry(
        host=host,
        uptime_seconds=uptime_seconds,
        load_avg=load_avg,
        cpu_count=cpu_count,
        mem_total=mem_total,
        mem_used=mem_used,
        mem_free=mem_free,
        disks=disks,
        gpus=gpus,
    )


def ps_boot_time() -> float:
    """Approximate system boot time (Windows-friendly)."""
    if os.name == "nt":
        try:
            import ctypes

            tick_ms = ctypes.windll.kernel32.GetTickCount64()
            return time.time() - tick_ms / 1000.0
        except Exception:
            pass
    return time.time()


# ============================================================================
# Services Status
# ============================================================================

_SERVICE_DEFS = [
    {
        "name": "comfyui",
        "display": "ComfyUI Web UI",
        "port": COMFYUI_PORT,
        "module": None,
        "managed": False,
        "icon": "🎨",
        "description": "Генерация изображений и видео",
    },
    {
        "name": "preset_downloader",
        "display": "Загрузчик пресетов и моделей",
        "port": 8081,
        "module": "services.preset_downloader:app",
        "managed": True,
        "icon": "📦",
        "description": "Каталог Wan / Qwen / Flux пресетов",
    },
    {
        "name": "civitai_downloader",
        "display": "CivitAI LoRA downloader",
        "port": 8082,
        "module": "services.civitai_downloader:app",
        "managed": True,
        "icon": "🧩",
        "description": "Скачивание LoRA с CivitAI",
    },
    {
        "name": "outputs_browser",
        "display": "Обзор и скачивание output",
        "port": 8083,
        "module": "services.outputs_browser:app",
        "managed": True,
        "icon": "🖼️",
        "description": "Галерея результатов ComfyUI",
    },
    {
        "name": "custom_nodes_installer",
        "display": "Установщик custom nodes",
        "port": 8085,
        "module": "services.custom_nodes_installer:app",
        "managed": True,
        "icon": "🔌",
        "description": "Git clone наборов нод + перезапуск ComfyUI",
    },
    {
        "name": "jupyter",
        "display": "JupyterLab",
        "port": 8888,
        "module": None,
        "managed": False,
        "icon": "📓",
        "description": "Облачная среда (RunPod)",
    },
]


def get_services_registry() -> list[dict]:
    services = [dict(s) for s in _SERVICE_DEFS]
    if is_desktop_mode():
        for svc in services:
            if svc["name"] == "comfyui":
                svc["managed"] = True
        services = [s for s in services if s["name"] != "jupyter"]
    return services


SERVICES = get_services_registry()

# Track service PIDs
service_pids: dict = {}


def is_process_alive(pid: int) -> bool:
    """Return True if a process with this PID exists."""
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            out = result.stdout or ""
            if "No tasks" in out or "нет задач" in out.lower():
                return False
            return str(pid) in out
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError, subprocess.SubprocessError):
        return False


def kill_process(pid: int, *, tree: bool = True) -> None:
    """Terminate a process (optionally with its child tree on Windows)."""
    if pid <= 0:
        return
    try:
        if os.name == "nt":
            args = ["taskkill", "/F", "/PID", str(pid)]
            if tree:
                args.insert(2, "/T")
            subprocess.run(args, check=False, capture_output=True, timeout=15)
        else:
            try:
                os.killpg(os.getpgid(pid), 15)
            except (OSError, ProcessLookupError):
                os.kill(pid, 15)
            time.sleep(0.5)
            if is_process_alive(pid):
                try:
                    os.killpg(os.getpgid(pid), 9)
                except (OSError, ProcessLookupError):
                    os.kill(pid, 9)
    except (OSError, ProcessLookupError, subprocess.SubprocessError):
        pass


def find_pids_by_port(port: int) -> List[int]:
    """Find PIDs listening on a port (locale-safe netstat parsing on Windows)."""
    pids: list[int] = []
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.splitlines():
                if f":{port}" not in line:
                    continue
                upper = line.upper()
                if "ESTABLISHED" in upper or "УСТАНОВ" in upper:
                    continue
                if "TIME_WAIT" in upper or "ОЖИДАН" in upper:
                    continue
                parts = line.split()
                if len(parts) < 5 or parts[0] not in ("TCP", "TCPv6"):
                    continue
                try:
                    pid = int(parts[-1])
                except ValueError:
                    continue
                if pid > 0 and pid not in pids:
                    pids.append(pid)
        else:
            result = subprocess.run(
                ["lsof", "-i", f":{port}", "-sTCP:LISTEN", "-t"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for token in result.stdout.strip().split():
                try:
                    pid = int(token)
                    if pid not in pids:
                        pids.append(pid)
                except ValueError:
                    pass
    except Exception:
        pass
    return pids


def find_process_by_port(port: int) -> Optional[int]:
    """Find PID of process listening on a port."""
    pids = find_pids_by_port(port)
    return pids[0] if pids else None


def wait_port_free(port: int, timeout: float = 8.0) -> bool:
    """Wait until nothing listens on the port."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not find_pids_by_port(port):
            return True
        time.sleep(0.25)
    return not find_pids_by_port(port)


def _prune_service_pid(name: str) -> None:
    pid = service_pids.get(name)
    if pid and not is_process_alive(pid):
        service_pids.pop(name, None)


def service_is_busy(name: str, port: int) -> bool:
    """True if service is up or still starting (process alive / port in use)."""
    _prune_service_pid(name)
    if find_pids_by_port(port):
        return True
    tracked = service_pids.get(name)
    return bool(tracked and is_process_alive(tracked))


def _service_python() -> str:
    """Python for managed aux services — portable embedded or venv."""
    from services._comfyui_launch import resolve_install

    install = resolve_install()
    if install.embedded_python and install.embedded_python.is_file():
        return str(install.embedded_python)
    candidates = [
        str(COMFYUI_ROOT / "venv" / "Scripts" / "python.exe"),
        str(COMFYUI_ROOT / "venv" / "bin" / "python"),
        "/workspace/venv/bin/python",
        "/venv/bin/python",
    ]
    for path in candidates:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return sys.executable


def _log_dir() -> str:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return str(LOGS_DIR)


def _uvicorn_cmd(module: str, port: int) -> list[str]:
    return [
        _service_python(),
        "-m",
        "uvicorn",
        module,
        "--host",
        BIND_HOST,
        "--port",
        str(port),
    ]


def start_comfyui(launcher_id: str | None = None) -> dict:
    """Start ComfyUI (portable embedded python or venv)."""
    from services._comfyui_launch import (
        get_selected_launcher_id,
        resolve_install,
        start_comfyui_process,
    )

    install = resolve_install()
    if not install.main_py.is_file():
        return {"success": False, "message": f"ComfyUI не найден: {install.comfy_dir}"}

    if service_is_busy("comfyui", COMFYUI_PORT):
        pid = find_process_by_port(COMFYUI_PORT) or service_pids.get("comfyui")
        return {"success": False, "message": f"ComfyUI уже запущен или запускается (PID: {pid})"}

    launcher_id = launcher_id or get_selected_launcher_id()
    log_path = os.path.join(_log_dir(), "comfyui.log")
    try:
        proc = start_comfyui_process(log_path, launcher_id)
        service_pids["comfyui"] = proc.pid
        mode = launcher_id if launcher_id != "standard" else "python main.py"
        return {
            "success": True,
            "message": f"ComfyUI запускается ({mode}, PID: {proc.pid}). Подождите 30–60 с.",
            "launcher": launcher_id,
            "pid": proc.pid,
            "state": "starting",
        }
    except Exception as e:
        return {"success": False, "message": f"Ошибка запуска ComfyUI: {e}"}


def start_service(name: str) -> dict:
    """Start a service by name."""
    global SERVICES
    SERVICES = get_services_registry()
    svc = next((s for s in SERVICES if s["name"] == name), None)
    if not svc:
        return {"success": False, "message": f"Сервис {name} не найден"}

    if not svc.get("managed"):
        return {"success": False, "message": f"Сервис {name} не управляется через hub"}

    if name == "comfyui":
        return start_comfyui()

    if service_is_busy(name, svc["port"]):
        pid = find_process_by_port(svc["port"]) or service_pids.get(name)
        return {"success": False, "message": f"Сервис уже запущен или запускается (PID: {pid})"}

    try:
        log_dir = _log_dir()
        log_file = open(os.path.join(log_dir, f"{name}.log"), "a", encoding="utf-8")

        proc = subprocess.Popen(
            _uvicorn_cmd(svc["module"], svc["port"]),
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
        )
        service_pids[name] = proc.pid
        return {
            "success": True,
            "message": f"Сервис {name} запускается (PID: {proc.pid})",
            "pid": proc.pid,
            "state": "starting",
        }
    except Exception as e:
        return {"success": False, "message": f"Ошибка запуска: {str(e)}"}


def stop_service(name: str) -> dict:
    """Stop a service by name."""
    global SERVICES
    SERVICES = get_services_registry()
    svc = next((s for s in SERVICES if s["name"] == name), None)
    if not svc:
        return {"success": False, "message": f"Сервис {name} не найден"}

    if not svc.get("managed"):
        return {"success": False, "message": f"Сервис {name} не управляется через hub"}

    _prune_service_pid(name)
    pids: set[int] = set(find_pids_by_port(svc["port"]))
    tracked = service_pids.get(name)
    if tracked:
        pids.add(tracked)

    if not pids:
        return {"success": False, "message": f"Сервис {name} не запущен"}

    try:
        for pid in pids:
            kill_process(pid, tree=True)

        wait_port_free(svc["port"], timeout=10.0)
        service_pids.pop(name, None)
        return {"success": True, "message": f"Сервис {name} остановлен"}
    except Exception as e:
        return {"success": False, "message": f"Ошибка остановки: {str(e)}"}


def restart_service(name: str) -> dict:
    """Restart a service by name."""
    global SERVICES
    SERVICES = get_services_registry()
    svc = next((s for s in SERVICES if s["name"] == name), None)
    if not svc:
        return {"success": False, "message": f"Сервис {name} не найден"}

    launcher_id = None
    if name == "comfyui":
        from services._comfyui_launch import get_selected_launcher_id
        launcher_id = get_selected_launcher_id()

    stop_result = stop_service(name)
    if not stop_result.get("success") and service_is_busy(name, svc["port"]):
        return stop_result

    wait_port_free(svc["port"], timeout=12.0)
    time.sleep(0.5)

    if name == "comfyui":
        start_result = start_comfyui(launcher_id)
    else:
        start_result = start_service(name)

    if start_result.get("success"):
        return {
            "success": True,
            "message": f"Сервис {name} перезапускается. {start_result.get('message', '')}",
            "state": start_result.get("state", "starting"),
        }
    return start_result


async def resolve_service_state(svc: dict) -> Tuple[str, bool]:
    """Return (state, running) for a service."""
    name = svc["name"]
    port = svc["port"]
    _prune_service_pid(name)

    healthy = await check_service_health(port)
    if healthy:
        return "running", True

    if service_is_busy(name, port):
        return "starting", False

    return "stopped", False


async def check_service_health(port: int) -> bool:
    """Check if a service is responding on the given port."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"http://127.0.0.1:{port}/")
            return response.status_code < 500
    except Exception:
        # Try health endpoint if root fails
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"http://127.0.0.1:{port}/health")
                return response.status_code < 500
        except Exception:
            return False


async def get_services_status() -> List[ServiceEntry]:
    """Get status of all services."""
    entries = []
    for svc in get_services_registry():
        state, running = await resolve_service_state(svc)
        entries.append(ServiceEntry(
            name=svc["name"],
            display=svc["display"],
            port=svc["port"],
            running=running,
            state=state,
            managed=svc.get("managed", False),
            url=service_url(svc["port"]),
        ))
    return entries


def start_all_managed_services() -> dict:
    """Start every managed service that is not already running."""
    started = []
    skipped = []
    errors = []
    for svc in get_services_registry():
        if not svc.get("managed"):
            continue
        if service_is_busy(svc["name"], svc["port"]):
            skipped.append(svc["display"])
            continue
        result = start_service(svc["name"])
        if result.get("success"):
            started.append(svc["display"])
        else:
            errors.append(f"{svc['display']}: {result.get('message', 'ошибка')}")
    return {
        "success": not errors,
        "started": started,
        "skipped": skipped,
        "errors": errors,
    }


def stop_all_managed_services() -> dict:
    """Stop every managed service that is running."""
    stopped = []
    skipped = []
    errors = []
    for svc in reversed(get_services_registry()):
        if not svc.get("managed"):
            continue
        if not service_is_busy(svc["name"], svc["port"]):
            skipped.append(svc["display"])
            continue
        result = stop_service(svc["name"])
        if result.get("success"):
            stopped.append(svc["display"])
        else:
            errors.append(f"{svc['display']}: {result.get('message', 'ошибка')}")
    return {
        "success": not errors,
        "stopped": stopped,
        "skipped": skipped,
        "errors": errors,
    }


def get_service_log(name: str, lines: int = 100) -> dict:
    """Get service log from logs directory."""
    log_path = os.path.join(_log_dir(), f"{name}.log")
    if not os.path.exists(log_path):
        return {"log": f"Лог-файл не найден: {log_path}", "path": log_path}
    
    try:
        # Cross-platform log reading
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()
            last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return {"log": ''.join(last_lines), "path": log_path}
    except Exception as e:
        return {"log": f"Ошибка чтения лога: {str(e)}", "path": log_path}


# ============================================================================
# Environment Info
# ============================================================================

class EnvironmentInfo(BaseModel):
    python_version: str
    cuda_version: str
    torch_version: str
    container_image: str
    hostname: str


def get_environment_info() -> EnvironmentInfo:
    """Get environment information."""
    import sys
    import socket
    
    # Python version
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    # CUDA version
    cuda_version = "N/A"
    cuda_env = os.environ.get("CUDA_VERSION", "")
    if cuda_env:
        cuda_version = cuda_env
    else:
        try:
            result = subprocess.run(
                ["nvcc", "--version"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                if "release" in line.lower():
                    parts = line.split("release")
                    if len(parts) > 1:
                        cuda_version = parts[1].split(",")[0].strip()
                        break
        except Exception:
            # Try nvidia-smi
            try:
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                    capture_output=True, text=True, timeout=5
                )
                if result.stdout.strip():
                    cuda_version = f"Driver {result.stdout.strip()}"
            except Exception:
                pass
    
    # PyTorch version
    torch_version = "N/A"
    try:
        import torch
        torch_version = torch.__version__
    except ImportError:
        pass
    
    # Container image
    container_image = os.environ.get("CONTAINER_IMAGE", "")
    if not container_image:
        container_image = os.environ.get("RUNPOD_POD_HOSTNAME", "local")
    
    # Hostname
    hostname = socket.gethostname()
    
    return EnvironmentInfo(
        python_version=python_version,
        cuda_version=cuda_version,
        torch_version=torch_version,
        container_image=container_image,
        hostname=hostname,
    )


# ============================================================================
# Network Speed Test
# ============================================================================

class NetworkSpeed(BaseModel):
    download_speed: float  # MB/s
    latency: float  # ms
    test_url: str
    file_size: int  # bytes
    duration: float  # seconds


_network_speed_cache: Optional[NetworkSpeed] = None
_network_speed_cache_at: float = 0
_NETWORK_SPEED_CACHE_SEC = 60


def test_network_speed() -> NetworkSpeed:
    """Test network download speed."""
    global _network_speed_cache, _network_speed_cache_at

    now = time.time()
    if _network_speed_cache and (now - _network_speed_cache_at) < _NETWORK_SPEED_CACHE_SEC:
        return _network_speed_cache

    import urllib.request
    import ssl
    
    # Create SSL context that doesn't verify (for testing)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    latency = 0
    
    # Test URLs - various sizes and sources
    test_configs = [
        # (url, expected_bytes, is_for_latency)
        ("http://ipv4.download.thinkbroadband.com/5MB.zip", 5242880, False),
        ("http://ipv4.download.thinkbroadband.com/1MB.zip", 1048576, False),
        ("http://speedtest.tele2.net/1MB.zip", 1048576, False),
        ("https://www.google.com/generate_204", 0, True),  # Just for latency
    ]
    
    # Measure latency with a lightweight endpoint
    for url, _, is_latency in test_configs:
        if not is_latency:
            continue
        try:
            latency_start = time.time()
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            urllib.request.urlopen(req, timeout=5, context=ctx if url.startswith('https') else None)
            latency = (time.time() - latency_start) * 1000
            break
        except Exception:
            continue
    
    # Speed test with larger files
    for url, expected_size, is_latency in test_configs:
        if is_latency:
            continue
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            start_time = time.time()
            response = urllib.request.urlopen(req, timeout=30, context=ctx if url.startswith('https') else None)
            data = response.read()
            duration = time.time() - start_time
            
            file_size = len(data)
            if file_size < 10000:  # Too small, skip
                continue
                
            speed_mbps = (file_size / 1024 / 1024) / duration if duration > 0 else 0
            
            result = NetworkSpeed(
                download_speed=round(speed_mbps, 2),
                latency=round(latency, 1),
                test_url=url.split("/")[-1],
                file_size=file_size,
                duration=round(duration, 3),
            )
            _network_speed_cache = result
            _network_speed_cache_at = time.time()
            return result
        except Exception:
            continue
    
    result = NetworkSpeed(
        download_speed=0,
        latency=round(latency, 1) if latency > 0 else 0,
        test_url="failed",
        file_size=0,
        duration=0,
    )
    _network_speed_cache = result
    _network_speed_cache_at = time.time()
    return result


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/api/telemetry", response_model=Telemetry)
def telemetry_endpoint():
    """Get system telemetry data."""
    return get_telemetry()


@app.get("/api/network/speed", response_model=NetworkSpeed)
def network_speed_endpoint():
    """Test network download speed."""
    return test_network_speed()


@app.get("/api/environment", response_model=EnvironmentInfo)
def environment_endpoint():
    """Get environment information."""
    return get_environment_info()


@app.get("/api/downloads")
async def downloads_endpoint():
    """Get active downloads from preset_downloader and custom_nodes_installer."""
    tasks: list[dict] = []
    endpoints = [
        ("http://127.0.0.1:8081/api/tasks", "presets"),
        ("http://127.0.0.1:8085/api/tasks", "nodes"),
    ]
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            for url, source in endpoints:
                try:
                    response = await client.get(url)
                    if response.status_code != 200:
                        continue
                    data = response.json()
                    for task in data.get("tasks", []):
                        item = dict(task)
                        item.setdefault("source", source)
                        tasks.append(item)
                except Exception:
                    continue
    except Exception:
        pass

    def sort_key(t: dict) -> int:
        s = t.get("status", "")
        if s == "running":
            return 0
        if s == "completed":
            return 1
        if s == "error":
            return 2
        return 3

    tasks.sort(key=sort_key)
    return {"tasks": tasks[:30]}


@app.get("/api/services")
async def services_endpoint():
    """Get status of all services."""
    return await get_services_status()


@app.get("/api/services/{name}/log")
def service_log_endpoint(name: str, lines: int = 100):
    """Get service log."""
    return get_service_log(name, lines)


@app.get("/api/hub/info")
def hub_info_endpoint():
    """Hub metadata for UI (desktop vs cloud)."""
    from services._config import read_desktop_config, validate_comfyui_path

    cfg = read_desktop_config()
    path_check = validate_comfyui_path(str(COMFYUI_ROOT))
    config_path = ""
    if is_desktop_mode():
        from services._config import REPO_ROOT
        import sys as _sys

        if getattr(_sys, "frozen", False):
            config_path = str(Path(_sys.executable).resolve().parent / "config.json")
        else:
            config_path = str(REPO_ROOT / "desktop" / "config.json")

    return {
        "title": "Smyshnikov ComfyUI Hub",
        "subtitle": (
            "Панель управления — пресеты, модели, ComfyUI"
            if is_desktop_mode()
            else "Мониторинг системы и управление сервисами"
        ),
        "mode": "desktop" if is_desktop_mode() else "cloud",
        "host_label": "ПК" if is_desktop_mode() else "RunPod ID",
        "comfyui_path": str(COMFYUI_ROOT),
        "comfyui_path_valid": bool(path_check.get("valid")),
        "comfyui_path_message": path_check.get("message", ""),
        "models_path": str(COMFYUI_ROOT / "models"),
        "config_path": config_path,
        "show_path_settings": is_desktop_mode(),
        "show_shutdown": not is_desktop_mode() and bool(os.environ.get("RUNPOD_POD_ID")),
        "hub_port": HUB_PORT,
    }


@app.get("/api/settings/comfyui")
def comfyui_settings_get_endpoint():
    """List detected ComfyUI installs and validate current path (desktop)."""
    if not is_desktop_mode():
        raise HTTPException(status_code=404, detail="Только для desktop hub")

    from services._config import detect_comfyui_installations, read_desktop_config, validate_comfyui_path

    cfg = read_desktop_config()
    current = (cfg.get("comfyui_path") or str(COMFYUI_ROOT)).strip()
    check = validate_comfyui_path(current)
    detected = [
        {"path": str(p), "label": str(p)}
        for p in detect_comfyui_installations()
    ]
    return {
        "current": current,
        "current_normalized": check.get("normalized") or current,
        "valid": bool(check.get("valid")),
        "message": check.get("message", ""),
        "portable": bool(check.get("portable")),
        "detected": detected,
    }


@app.post("/api/settings/comfyui")
def comfyui_settings_post_endpoint(payload: dict):
    """Save ComfyUI path from hub UI."""
    if not is_desktop_mode():
        raise HTTPException(status_code=404, detail="Только для desktop hub")

    from services._config import apply_comfyui_path

    path = (payload.get("path") or "").strip()
    if not path:
        return {"success": False, "message": "Укажите путь к ComfyUI"}

    was_running = service_is_busy("comfyui", COMFYUI_PORT)
    if was_running:
        stop_service("comfyui")

    result = apply_comfyui_path(path)
    if not result.get("success"):
        return result

    note = "Перезапустите сервисы (кнопка «Запустить все»), чтобы применить новый путь."
    if was_running:
        note = "ComfyUI остановлен. " + note
    return {
        **result,
        "message": f"{result['message']}. {note}",
        "restart_recommended": True,
    }


@app.get("/api/comfyui/launchers")
def comfyui_launchers_endpoint():
    from services._comfyui_launch import get_selected_launcher_id, list_launcher_profiles, resolve_install

    install = resolve_install()
    return {
        "selected": get_selected_launcher_id(),
        "profiles": list_launcher_profiles(install),
        "portable": install.portable_root is not None,
        "embedded_python": str(install.embedded_python) if install.embedded_python else None,
    }


@app.post("/api/comfyui/launcher")
def set_comfyui_launcher_endpoint(payload: dict):
    launcher = (payload.get("launcher") or "").strip()
    if not launcher:
        return {"success": False, "message": "Не указан профиль запуска"}
    from services._config import REPO_ROOT, save_desktop_config

    path = REPO_ROOT / "desktop" / "config.json"
    data = {}
    if path.is_file():
        import json
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            data = {}
    data["comfyui_launcher"] = launcher
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return {"success": True, "message": f"Профиль запуска: {launcher}", "launcher": launcher}


@app.post("/api/services/start-all")
def service_start_all_endpoint():
    """Start all managed services."""
    return start_all_managed_services()


@app.post("/api/services/stop-all")
def service_stop_all_endpoint():
    """Stop all managed services."""
    return stop_all_managed_services()


@app.post("/api/services/{name}/start")
def service_start_endpoint(name: str, launcher: Optional[str] = None):
    """Start a service."""
    if name == "comfyui":
        return start_comfyui(launcher)
    return start_service(name)


@app.post("/api/services/{name}/stop")
def service_stop_endpoint(name: str):
    """Stop a service."""
    return stop_service(name)


@app.post("/api/services/{name}/restart")
def service_restart_endpoint(name: str):
    """Restart a service."""
    return restart_service(name)


@app.post("/api/shutdown/schedule")
def schedule_shutdown_endpoint(request: ShutdownRequest):
    """Schedule a shutdown."""
    schedule_shutdown(request)
    return {"status": "scheduled", "message": f"Shutdown scheduled in {request.value} {request.unit}"}


@app.post("/api/shutdown/cancel")
def cancel_shutdown_endpoint():
    """Cancel the scheduled shutdown."""
    cancel_shutdown()
    return {"status": "cancelled", "message": "Shutdown cancelled"}


@app.get("/api/shutdown/status", response_model=ShutdownStatus)
def shutdown_status_endpoint():
    """Get the current shutdown status."""
    return get_shutdown_status()


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "message": "Smyshnikov ComfyUI Hub is running"}


# ============================================================================
# HTML Frontend
# ============================================================================

INDEX_HTML = """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Dashboard</title>
  <style>
    :root { --bg:#1e1e1e; --card:#282828; --text:#ffffff; --muted:#9ca3af; --accent:#ffffff; --border:#3a3a3a; }
    html,body { margin:0; padding:0; background:var(--bg); color:var(--text); font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, Arial; }
    .wrap { max-width: 1200px; margin: 0 auto; padding: 40px 20px; }
    .title { font-size: 36px; font-weight: 800; margin: 0 0 8px; color: var(--accent); text-align: center; text-shadow: 0 0 10px rgba(255,255,255,0.3); }
    .subtitle { margin:0 0 40px; color:var(--muted); text-align: center; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; }
    .card { background: var(--card); border:1px solid var(--border); border-radius: 12px; padding: 24px; box-sizing: border-box; }
    .card-full { grid-column: 1 / -1; }
    .card h3 { margin: 0 0 16px; font-size: 18px; font-weight: 700; }
    
    /* Pills */
    .pills { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 24px; justify-content: center; }
    .pill { background: #1a1a1a; border: 1px solid var(--border); padding: 8px 16px; border-radius: 20px; font-size: 14px; }
    .pill strong { color: var(--accent); }
    
    /* Progress bars */
    .bar-wrap { width: 100%; height: 8px; background: #1a1a1a; border: 1px solid var(--border); border-radius: 4px; overflow: hidden; margin: 8px 0; }
    .bar-fill { height: 100%; background: linear-gradient(90deg, #22c55e, #4ade80); transition: width 0.3s; }
    .bar-fill.warning { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
    .bar-fill.danger { background: linear-gradient(90deg, #ef4444, #f87171); }
    
    /* Stats */
    .stat-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
    .stat-label { font-weight: 600; }
    .stat-value { color: var(--muted); font-size: 14px; }
    
    /* GPU grid */
    .gpu-grid { display: grid; gap: 16px; }
    .gpu-item { background: #1a1a1a; border: 1px solid var(--border); border-radius: 8px; padding: 12px; }
    .gpu-name { font-weight: 600; margin-bottom: 8px; font-size: 14px; }
    .gpu-stats { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .gpu-stat-label { font-size: 12px; color: var(--muted); }
    
    /* Disks table */
    table { width: 100%; border-collapse: collapse; }
    th, td { padding: 12px; text-align: left; border-bottom: 1px solid var(--border); }
    th { font-weight: 600; color: var(--muted); font-size: 12px; text-transform: uppercase; }
    
    /* Shutdown widget */
    .shutdown-widget {
      position: relative;
      border-radius: 18px;
      padding: 20px;
      color: #fff;
      background: linear-gradient(135deg, #4a4a4a 0%, #3a3a3a 50%, #2a2a2a 100%);
      box-shadow: 0 18px 50px rgba(0,0,0,0.35);
      overflow: hidden;
      border: 1px solid var(--border);
    }
    .shutdown-widget::before {
      content: "";
      position: absolute;
      top: -50%;
      left: -50%;
      width: 200%;
      height: 200%;
      background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 60%);
      pointer-events: none;
    }
    .shutdown-header { position: relative; display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 16px; }
    .shutdown-title { font-size: 20px; font-weight: 800; margin: 0; }
    .shutdown-subtitle { font-size: 13px; opacity: 0.85; margin-top: 4px; }
    .shutdown-icon { width: 36px; height: 36px; border-radius: 50%; background: rgba(0,0,0,0.15); display: flex; align-items: center; justify-content: center; }
    .shutdown-timebox {
      position: relative;
      background: rgba(0,0,0,0.15);
      border: 1px solid rgba(255,255,255,0.2);
      border-radius: 14px;
      padding: 16px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      margin-bottom: 16px;
    }
    .shutdown-seg { text-align: center; min-width: 60px; }
    .shutdown-num { font-size: 32px; font-weight: 900; font-variant-numeric: tabular-nums; }
    .shutdown-input {
      width: 60px;
      border: none;
      outline: none;
      background: transparent;
      color: #fff;
      font-size: 32px;
      font-weight: 900;
      text-align: center;
      font-variant-numeric: tabular-nums;
      padding: 0;
    }
    .shutdown-input::-webkit-outer-spin-button,
    .shutdown-input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
    .shutdown-lbl { font-size: 11px; text-transform: uppercase; opacity: 0.8; letter-spacing: 0.5px; margin-top: 4px; }
    .shutdown-sep { font-size: 28px; font-weight: 800; opacity: 0.5; }
    .shutdown-actions { display: flex; gap: 12px; }
    .shutdown-btn {
      flex: 1;
      border: none;
      border-radius: 12px;
      padding: 14px 20px;
      font-weight: 800;
      font-size: 14px;
      cursor: pointer;
      transition: all 0.2s;
    }
    .shutdown-btn.primary { background: rgba(255,255,255,0.95); color: #1e1e1e; }
    .shutdown-btn.primary:hover { background: #fff; transform: translateY(-2px); box-shadow: 0 8px 20px rgba(0,0,0,0.2); }
    .shutdown-btn.secondary { background: rgba(0,0,0,0.2); color: rgba(255,255,255,0.9); border: 1px solid rgba(255,255,255,0.2); }
    .shutdown-btn.secondary:hover { background: rgba(0,0,0,0.3); }
    .shutdown-meta { position: relative; margin-top: 12px; font-size: 13px; opacity: 0.85; text-align: center; }
    .hidden { display: none !important; }
    
    /* Services — RunPod Connect style */
    .services-hero { margin-bottom: 28px; }
    .services-hero-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; margin-bottom: 16px; }
    .services-hero h2 { margin: 0; font-size: 22px; font-weight: 800; }
    .btn-hub {
      display: inline-flex; align-items: center; gap: 8px;
      padding: 12px 20px; background: rgba(34, 197, 94, 0.9); color: #fff; font-weight: 700;
      border: 2px solid rgba(34, 197, 94, 0.5); border-radius: 8px; cursor: pointer; transition: all 0.2s;
    }
    .btn-hub:hover { background: rgb(34, 197, 94); box-shadow: 0 8px 20px rgba(34, 197, 94, 0.35); }
    .btn-hub:disabled { opacity: 0.55; cursor: wait; box-shadow: none; }
    .services-hero-actions { display: flex; gap: 10px; flex-wrap: wrap; }
    .btn-hub-danger {
      background: rgba(239, 68, 68, 0.15); color: #ef4444;
      border: 2px solid rgba(239, 68, 68, 0.45);
    }
    .btn-hub-danger:hover { background: rgba(239, 68, 68, 0.28); box-shadow: 0 8px 20px rgba(239, 68, 68, 0.2); }
    .connect-list { display: flex; flex-direction: column; gap: 10px; }
    .connect-row {
      display: grid; grid-template-columns: auto auto 1fr auto auto; gap: 14px; align-items: center;
      background: #1a1a1a; border: 1px solid var(--border); border-radius: 10px; padding: 14px 18px;
      transition: border-color 0.2s, background 0.2s;
    }
    .connect-row:hover { border-color: rgba(255,255,255,0.25); background: #222; }
    .connect-port { font-family: monospace; font-weight: 700; color: #a78bfa; min-width: 52px; }
    .connect-icon { font-size: 20px; }
    .connect-meta { min-width: 0; }
    .connect-name { font-weight: 700; margin-bottom: 2px; }
    .connect-desc { font-size: 12px; color: var(--muted); }
    .connect-status { font-size: 12px; font-weight: 600; white-space: nowrap; }
    .connect-status.running { color: #22c55e; }
    .connect-status.stopped { color: #9ca3af; }
    .connect-status.starting { color: #3b82f6; animation: pulse-status 1.2s ease-in-out infinite; }
    .connect-status.stopping { color: #f59e0b; animation: pulse-status 1.2s ease-in-out infinite; }
    .connect-status.init { color: #3b82f6; }
    @keyframes pulse-status { 0%, 100% { opacity: 1; } 50% { opacity: 0.45; } }
    .connect-row.busy { border-color: rgba(59, 130, 246, 0.35); }
    .connect-actions { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; align-items: center; }
    .launcher-select {
      background: #1a1a1a; color: var(--text); border: 1px solid var(--border);
      border-radius: 6px; padding: 6px 10px; font-size: 12px; max-width: 220px;
    }
    .path-pill { font-size: 12px; color: var(--muted); margin-top: 8px; word-break: break-all; }
    .path-pill code { color: #d1d5db; }
    .path-pill.invalid code { color: #f87171; }
    .path-settings-row {
      display: flex; align-items: flex-start; justify-content: space-between; gap: 12px;
      flex-wrap: wrap; margin-top: 8px; padding: 10px 12px;
      background: #1a1a1a; border: 1px solid var(--border); border-radius: 8px;
    }
    .path-settings-row.invalid { border-color: rgba(239,68,68,0.45); }
    .path-settings-text { font-size: 12px; color: var(--muted); min-width: 0; flex: 1; }
    .path-settings-text strong { color: var(--text); font-weight: 600; }
    .path-settings-hint { margin-top: 4px; font-size: 11px; }
    .path-settings-hint.warn { color: #f87171; }
    .path-settings-hint.ok { color: #22c55e; }
    .btn-path { padding: 6px 12px; font-size: 12px; white-space: nowrap; }
    .settings-detected { display: flex; flex-direction: column; gap: 8px; margin: 12px 0; max-height: 200px; overflow: auto; }
    .settings-option {
      display: flex; gap: 10px; align-items: flex-start; padding: 10px 12px;
      border: 1px solid var(--border); border-radius: 8px; cursor: pointer; background: #1a1a1a;
    }
    .settings-option:hover { border-color: rgba(255,255,255,0.25); }
    .settings-option input { margin-top: 3px; }
    .settings-option code { font-size: 11px; word-break: break-all; color: #d1d5db; }
    .settings-input {
      width: 100%; box-sizing: border-box; margin-top: 8px;
      background: #0f0f0f; color: var(--text); border: 1px solid var(--border);
      border-radius: 8px; padding: 10px 12px; font-family: monospace; font-size: 12px;
    }

    /* Services */
    .services-list { display: flex; flex-direction: column; gap: 12px; }
    .service-card { background: #1a1a1a; border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; }
    .service-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .service-info { display: flex; align-items: center; gap: 12px; }
    .service-dot { width: 10px; height: 10px; border-radius: 50%; }
    .service-dot.running { background: #22c55e; box-shadow: 0 0 8px rgba(34,197,94,0.5); }
    .service-dot.stopped { background: #ef4444; }
    .service-name { font-weight: 600; }
    .service-port { color: var(--muted); font-size: 13px; margin-left: 8px; }
    .service-actions { display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; }
    .service-btn { padding: 6px 12px; background: rgba(255,255,255,0.1); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 12px; cursor: pointer; text-decoration: none; transition: all 0.2s; }
    .service-btn:hover { background: rgba(255,255,255,0.15); border-color: var(--accent); }
    .service-btn:disabled { opacity: 0.5; cursor: not-allowed; }
    .service-btn.start { border-color: #22c55e; color: #22c55e; }
    .service-btn.start:hover { background: rgba(34,197,94,0.15); }
    .service-btn.stop { border-color: #ef4444; color: #ef4444; }
    .service-btn.stop:hover { background: rgba(239,68,68,0.15); }
    .service-btn.restart { border-color: #f59e0b; color: #f59e0b; }
    .service-btn.restart:hover { background: rgba(245,158,11,0.15); }
    .service-btn.busy { opacity: 0.55; pointer-events: none; cursor: wait; }

    /* Toast */
    .toast-host {
      position: fixed; right: 20px; bottom: 20px; z-index: 2000;
      display: flex; flex-direction: column; gap: 10px; max-width: min(420px, calc(100vw - 40px));
    }
    .toast {
      padding: 12px 16px; border-radius: 10px; font-size: 13px; line-height: 1.45;
      border: 1px solid var(--border); background: #1f1f1f; box-shadow: 0 12px 32px rgba(0,0,0,0.45);
      animation: toast-in 0.25s ease;
    }
    .toast.ok { border-color: rgba(34,197,94,0.45); }
    .toast.err { border-color: rgba(239,68,68,0.45); }
    .toast.info { border-color: rgba(59,130,246,0.45); }
    @keyframes toast-in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
    
    /* Network */
    .network-stats { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .network-stat { background: #1a1a1a; border: 1px solid var(--border); border-radius: 8px; padding: 16px; text-align: center; }
    .network-value { font-size: 28px; font-weight: 800; margin-bottom: 4px; }
    .network-value.speed { color: #22c55e; }
    .network-value.latency { color: #3b82f6; }
    .network-label { font-size: 12px; color: var(--muted); text-transform: uppercase; }
    .network-sublabel { font-size: 11px; color: var(--muted); margin-top: 4px; opacity: 0.7; }
    .network-test-btn { margin-top: 16px; width: 100%; padding: 12px; background: rgba(255,255,255,0.1); border: 1px solid var(--border); border-radius: 8px; color: var(--text); font-weight: 600; cursor: pointer; transition: all 0.2s; }
    .network-test-btn:hover { background: rgba(255,255,255,0.15); border-color: var(--accent); }
    .network-test-btn:disabled { opacity: 0.5; cursor: wait; }
    
    /* Environment */
    .env-list { display: flex; flex-direction: column; gap: 12px; }
    .env-item { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; background: #1a1a1a; border: 1px solid var(--border); border-radius: 8px; }
    .env-label { font-size: 13px; color: var(--muted); }
    .env-value { font-size: 13px; font-weight: 600; font-family: monospace; color: #a78bfa; }
    
    /* Downloads */
    .downloads-list { display: flex; flex-direction: column; gap: 12px; }
    .download-item { background: #1a1a1a; border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; }
    .download-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
    .download-name { font-weight: 600; font-size: 14px; max-width: 70%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .download-status { font-size: 12px; padding: 4px 10px; border-radius: 12px; font-weight: 600; }
    .download-status.running,
    .download-status.downloading { background: rgba(59,130,246,0.2); color: #3b82f6; }
    .download-status.completed { background: rgba(34,197,94,0.2); color: #22c55e; }
    .download-status.error { background: rgba(239,68,68,0.2); color: #ef4444; }
    .download-progress { margin-top: 8px; }
    .download-info { display: flex; justify-content: space-between; font-size: 12px; color: var(--muted); margin-top: 6px; }
    .no-downloads { color: var(--muted); font-style: italic; text-align: center; padding: 20px; }
    
    /* Modal */
    .modal-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); display: flex; align-items: center; justify-content: center; z-index: 1000; }
    .modal { background: var(--card); border: 1px solid var(--border); border-radius: 16px; width: 90%; max-width: 800px; max-height: 80vh; display: flex; flex-direction: column; }
    .modal-header { padding: 20px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
    .modal-title { font-size: 18px; font-weight: 700; margin: 0; }
    .modal-close { background: none; border: none; color: var(--muted); font-size: 24px; cursor: pointer; padding: 0; line-height: 1; }
    .modal-close:hover { color: var(--text); }
    .modal-body { padding: 20px; overflow: auto; flex: 1; }
    .log-content { background: #0a0a0a; border: 1px solid var(--border); border-radius: 8px; padding: 16px; font-family: monospace; font-size: 12px; line-height: 1.5; white-space: pre-wrap; word-break: break-all; max-height: 400px; overflow: auto; }
    .modal-footer { padding: 16px 20px; border-top: 1px solid var(--border); display: flex; justify-content: flex-end; gap: 12px; }
    
    /* Loading */
    .loading { color: var(--muted); font-style: italic; }
    
    /* Responsive */
    @media (max-width: 900px) {
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <h1 class="title" id="hub-title">Smyshnikov ComfyUI Hub</h1>
    <p class="subtitle" id="hub-subtitle">Панель управления — пресеты, модели, ComfyUI</p>
    
    <div class="pills" id="info-pills">
      <div class="pill"><span id="host-label">ПК</span>: <strong id="pod-id">-</strong></div>
      <div class="pill">Uptime: <strong id="uptime">-</strong></div>
    </div>

    <div class="card card-full services-hero">
      <div class="services-hero-head">
        <h2>HTTP сервисы</h2>
        <div class="services-hero-actions">
          <button type="button" class="btn-hub btn-hub-danger" id="stop-all-btn" onclick="stopAllServices()">■ Остановить все</button>
          <button type="button" class="btn-hub" id="start-all-btn" onclick="startAllServices()">▶ Запустить все</button>
        </div>
      </div>
      <p class="path-pill" id="comfyui-path-line"></p>
      <div id="path-settings-row" class="path-settings-row hidden">
        <div class="path-settings-text">
          <div><strong>ComfyUI</strong></div>
          <div id="path-settings-display"><code>-</code></div>
          <div class="path-settings-hint" id="path-settings-hint"></div>
        </div>
        <button type="button" class="service-btn btn-path" onclick="openPathSettings()">Изменить путь</button>
      </div>
      <div class="connect-list" id="services-list">
        <div class="loading">Загрузка сервисов...</div>
      </div>
    </div>
    
    <div class="grid">
      <!-- CPU / Memory -->
      <div class="card">
        <h3>CPU / Memory</h3>
        <div class="stat-row">
          <span class="stat-label">CPU Load</span>
          <span class="stat-value" id="cpu-value">-</span>
        </div>
        <div class="bar-wrap"><div class="bar-fill" id="cpu-bar" style="width:0%"></div></div>
        
        <div class="stat-row" style="margin-top:20px;">
          <span class="stat-label">Memory</span>
          <span class="stat-value" id="mem-value">-</span>
        </div>
        <div class="bar-wrap"><div class="bar-fill" id="mem-bar" style="width:0%"></div></div>
      </div>
      
      <!-- GPU -->
      <div class="card">
        <h3>GPU</h3>
        <div class="gpu-grid" id="gpu-grid">
          <div class="loading">Loading GPU info...</div>
        </div>
      </div>
      
      <!-- Disks -->
      <div class="card">
        <h3>Диски</h3>
        <table>
          <thead>
            <tr><th>Mount</th><th>Usage</th><th></th></tr>
          </thead>
          <tbody id="disk-body">
            <tr><td colspan="3" class="loading">Loading disk info...</td></tr>
          </tbody>
        </table>
      </div>
      
      <!-- Environment -->
      <div class="card">
        <h3>Окружение</h3>
        <div class="env-list" id="env-list">
          <div class="loading">Загрузка...</div>
        </div>
      </div>
      
      <!-- Network -->
      <div class="card">
        <h3>Сеть</h3>
        <div class="network-stats">
          <div class="network-stat">
            <div class="network-value speed" id="net-speed">-</div>
            <div class="network-label">Скорость (MB/s)</div>
            <div class="network-sublabel" id="net-speed-mbps"></div>
          </div>
          <div class="network-stat">
            <div class="network-value latency" id="net-latency">-</div>
            <div class="network-label">Задержка (ms)</div>
          </div>
        </div>
        <button class="network-test-btn" id="net-test-btn" onclick="testNetwork()">Тест скорости</button>
      </div>
      
      <!-- Shutdown Scheduler -->
      <div class="card hidden" id="shutdown-card" style="padding:0; border:none; background:transparent;">
        <div class="shutdown-widget" id="shutdown-widget">
          <div class="shutdown-header">
            <div>
              <div class="shutdown-title">Shutdown Pod</div>
              <div class="shutdown-subtitle">Запланировать автоматическое завершение</div>
            </div>
            <div class="shutdown-icon">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none">
                <path d="M12 8v5l3 2" stroke="rgba(255,255,255,0.9)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M21 12a9 9 0 1 1-9-9 9 9 0 0 1 9 9Z" stroke="rgba(255,255,255,0.9)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
          </div>
          
          <!-- Picker mode -->
          <div class="shutdown-timebox" id="shutdown-picker">
            <div class="shutdown-seg">
              <input type="number" class="shutdown-input" id="shutdown-hours" min="0" max="99" value="0">
              <div class="shutdown-lbl">Часы</div>
            </div>
            <div class="shutdown-sep">:</div>
            <div class="shutdown-seg">
              <input type="number" class="shutdown-input" id="shutdown-mins" min="0" max="59" value="30">
              <div class="shutdown-lbl">Мин</div>
            </div>
            <div class="shutdown-sep">:</div>
            <div class="shutdown-seg">
              <input type="number" class="shutdown-input" id="shutdown-secs" min="0" max="59" value="0">
              <div class="shutdown-lbl">Сек</div>
            </div>
          </div>
          
          <!-- Countdown mode -->
          <div class="shutdown-timebox hidden" id="shutdown-countdown">
            <div class="shutdown-seg">
              <div class="shutdown-num" id="countdown-hours">00</div>
              <div class="shutdown-lbl">Часы</div>
            </div>
            <div class="shutdown-sep">:</div>
            <div class="shutdown-seg">
              <div class="shutdown-num" id="countdown-mins">00</div>
              <div class="shutdown-lbl">Мин</div>
            </div>
            <div class="shutdown-sep">:</div>
            <div class="shutdown-seg">
              <div class="shutdown-num" id="countdown-secs">00</div>
              <div class="shutdown-lbl">Сек</div>
            </div>
          </div>
          
          <div class="shutdown-actions">
            <button class="shutdown-btn primary" id="schedule-btn" onclick="scheduleShutdown()">Запланировать</button>
            <button class="shutdown-btn secondary hidden" id="cancel-btn" onclick="cancelShutdown()">Отменить</button>
          </div>
          
          <div class="shutdown-meta hidden" id="shutdown-meta">
            Завершение в: <span id="shutdown-time">-</span>
          </div>
        </div>
      </div>
      
      <!-- Active Downloads -->
      <div class="card card-full">
        <h3>Активные загрузки</h3>
        <div class="downloads-list" id="downloads-list">
          <div class="no-downloads">Нет активных загрузок</div>
        </div>
      </div>
    </div>
  </div>
  
  <!-- Log Modal -->
  <div id="toast-host" class="toast-host" aria-live="polite"></div>

  <div class="modal-overlay hidden" id="path-modal" onclick="closePathModal(event)">
    <div class="modal" onclick="event.stopPropagation()">
      <div class="modal-header">
        <h3 class="modal-title">Путь к ComfyUI</h3>
        <button class="modal-close" onclick="closePathModal()">&times;</button>
      </div>
      <div class="modal-body">
        <p style="margin:0 0 8px;font-size:13px;color:var(--muted)">
          Укажите папку <code>ComfyUI</code> (с <code>models/</code>) или корень portable-сборки
          (<code>ComfyUI_windows_portable</code>).
        </p>
        <div id="path-detected-list" class="settings-detected"></div>
        <label style="font-size:12px;color:var(--muted)">Или введите вручную:</label>
        <input type="text" class="settings-input" id="path-manual-input" placeholder="C:\ComfyUI\ComfyUI_windows_portable\ComfyUI">
        <p style="margin:12px 0 0;font-size:11px;color:var(--muted)">
          Файл настроек: <code id="path-config-file">desktop\config.json</code>.
          То же самое: <code>desktop\configure.bat</code>
        </p>
      </div>
      <div class="modal-footer">
        <button class="service-btn" onclick="closePathModal()">Отмена</button>
        <button class="service-btn start" id="path-save-btn" onclick="saveComfyPath()">Сохранить</button>
      </div>
    </div>
  </div>

  <div class="modal-overlay hidden" id="log-modal" onclick="closeLogModal(event)">
    <div class="modal" onclick="event.stopPropagation()">
      <div class="modal-header">
        <h3 class="modal-title" id="log-modal-title">Логи сервиса</h3>
        <button class="modal-close" onclick="closeLogModal()">&times;</button>
      </div>
      <div class="modal-body">
        <pre class="log-content" id="log-content">Загрузка...</pre>
      </div>
      <div class="modal-footer">
        <button class="service-btn" onclick="refreshLog()">Обновить</button>
        <button class="service-btn" onclick="closeLogModal()">Закрыть</button>
      </div>
    </div>
  </div>
  
  <script>
    // Format bytes to human readable
    function formatBytes(bytes) {
      if (bytes === 0) return '0 B';
      const k = 1024;
      const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }
    
    // Format uptime
    function formatUptime(seconds) {
      const d = Math.floor(seconds / 86400);
      seconds %= 86400;
      const h = Math.floor(seconds / 3600);
      seconds %= 3600;
      const m = Math.floor(seconds / 60);
      return `${d}d ${h}h ${m}m`;
    }
    
    // Pad number with zeros
    function pad2(n) {
      return String(Math.max(0, Math.min(99, n))).padStart(2, '0');
    }
    
    // Load telemetry
    async function loadTelemetry() {
      try {
        const res = await fetch('/api/telemetry');
        const data = await res.json();
        
        // Update pills
        document.getElementById('pod-id').textContent = data.host || 'local';
        document.getElementById('uptime').textContent = formatUptime(data.uptime_seconds);
        
        // CPU
        const cpuPct = Math.min(100, Math.round((data.load_avg[0] / data.cpu_count) * 100));
        document.getElementById('cpu-value').textContent = `${cpuPct}% of ${data.cpu_count} cores (load ${data.load_avg[0].toFixed(2)})`;
        const cpuBar = document.getElementById('cpu-bar');
        cpuBar.style.width = `${cpuPct}%`;
        cpuBar.className = 'bar-fill' + (cpuPct > 80 ? ' danger' : cpuPct > 60 ? ' warning' : '');
        
        // Memory
        const memPct = data.mem_total ? Math.round((data.mem_used / data.mem_total) * 100) : 0;
        document.getElementById('mem-value').textContent = `${formatBytes(data.mem_used)} / ${formatBytes(data.mem_total)} (${memPct}%)`;
        const memBar = document.getElementById('mem-bar');
        memBar.style.width = `${memPct}%`;
        memBar.className = 'bar-fill' + (memPct > 80 ? ' danger' : memPct > 60 ? ' warning' : '');
        
        // GPUs
        const gpuGrid = document.getElementById('gpu-grid');
        if (data.gpus && data.gpus.length > 0) {
          gpuGrid.innerHTML = data.gpus.map(gpu => {
            const memPct = gpu.mem_total ? Math.round((gpu.mem_used / gpu.mem_total) * 100) : 0;
            return `
              <div class="gpu-item">
                <div class="gpu-name">GPU ${gpu.index}: ${gpu.name}</div>
                <div class="gpu-stats">
                  <div>
                    <div class="gpu-stat-label">Utilization</div>
                    <div class="bar-wrap"><div class="bar-fill${gpu.util > 80 ? ' danger' : gpu.util > 60 ? ' warning' : ''}" style="width:${gpu.util}%"></div></div>
                    <div class="stat-value">${gpu.util}%</div>
                  </div>
                  <div>
                    <div class="gpu-stat-label">Memory</div>
                    <div class="bar-wrap"><div class="bar-fill${memPct > 80 ? ' danger' : memPct > 60 ? ' warning' : ''}" style="width:${memPct}%"></div></div>
                    <div class="stat-value">${formatBytes(gpu.mem_used)} / ${formatBytes(gpu.mem_total)}</div>
                  </div>
                </div>
              </div>
            `;
          }).join('');
        } else {
          gpuGrid.innerHTML = '<div class="stat-value">No GPU detected</div>';
        }
        
        // Disks
        const diskBody = document.getElementById('disk-body');
        diskBody.innerHTML = data.disks.map(disk => `
          <tr>
            <td>${disk.mount}</td>
            <td>${formatBytes(disk.used)} / ${formatBytes(disk.total)} (${disk.pct}%)</td>
            <td style="width:100px"><div class="bar-wrap"><div class="bar-fill${disk.pct > 80 ? ' danger' : disk.pct > 60 ? ' warning' : ''}" style="width:${disk.pct}%"></div></div></td>
          </tr>
        `).join('');
        
      } catch (e) {
        console.error('Telemetry error:', e);
      }
    }
    
    // Network speed test
    async function testNetwork() {
      const btn = document.getElementById('net-test-btn');
      const speedEl = document.getElementById('net-speed');
      const speedMbpsEl = document.getElementById('net-speed-mbps');
      const latencyEl = document.getElementById('net-latency');
      
      btn.disabled = true;
      btn.textContent = 'Тестирование...';
      speedEl.textContent = '...';
      speedMbpsEl.textContent = '';
      latencyEl.textContent = '...';
      
      try {
        const res = await fetch('/api/network/speed');
        const data = await res.json();
        
        if (data.download_speed > 0) {
          speedEl.textContent = data.download_speed.toFixed(2);
          const mbps = (data.download_speed * 8).toFixed(1);
          speedMbpsEl.textContent = `≈ ${mbps} Mbps`;
        } else {
          speedEl.textContent = 'Ошибка';
          speedMbpsEl.textContent = '';
        }
        latencyEl.textContent = data.latency > 0 ? Math.round(data.latency) : 'Ошибка';
      } catch (e) {
        speedEl.textContent = 'Ошибка';
        speedMbpsEl.textContent = '';
        latencyEl.textContent = 'Ошибка';
      }
      
      btn.disabled = false;
      btn.textContent = 'Тест скорости';
    }
    
    // Load environment info
    async function loadEnvironment() {
      try {
        const res = await fetch('/api/environment');
        const env = await res.json();
        
        const list = document.getElementById('env-list');
        list.innerHTML = `
          <div class="env-item">
            <span class="env-label">Python</span>
            <span class="env-value">${env.python_version}</span>
          </div>
          <div class="env-item">
            <span class="env-label">CUDA</span>
            <span class="env-value">${env.cuda_version}</span>
          </div>
          <div class="env-item">
            <span class="env-label">PyTorch</span>
            <span class="env-value">${env.torch_version}</span>
          </div>
          <div class="env-item">
            <span class="env-label">Hostname</span>
            <span class="env-value">${env.hostname}</span>
          </div>
        `;
      } catch (e) {
        console.error('Environment error:', e);
      }
    }
    
    // Load active downloads
    async function loadDownloads() {
      try {
        const res = await fetch('/api/downloads');
        const data = await res.json();
        
        const list = document.getElementById('downloads-list');
        
        if (!data.tasks || data.tasks.length === 0) {
          list.innerHTML = '<div class="no-downloads">Нет активных загрузок</div>';
          return;
        }
        
        list.innerHTML = data.tasks.map(task => {
          const statusClass = task.status || 'unknown';
          const statusText = {
            'running': 'Загрузка',
            'completed': 'Завершено',
            'error': 'Ошибка'
          }[task.status] || task.status;
          
          const progress = task.progress || 0;
          const filename = task.current_filename || task.filename || 'Файл';
          const fileInfo = task.total_files > 1 ? `${task.current_file || 1}/${task.total_files}` : '';
          
          return `
            <div class="download-item">
              <div class="download-header">
                <span class="download-name" title="${filename}">${filename}</span>
                <span class="download-status ${statusClass}">${statusText}</span>
              </div>
              ${task.status === 'running' ? `
                <div class="download-progress">
                  <div class="bar-wrap"><div class="bar-fill" style="width:${progress}%"></div></div>
                </div>
                <div class="download-info">
                  <span>${progress}%</span>
                  <span>${fileInfo}</span>
                </div>
              ` : ''}
              ${task.status === 'error' ? `<div class="download-info"><span style="color:#ef4444">${task.message || 'Ошибка загрузки'}</span></div>` : ''}
            </div>
          `;
        }).join('');
        
      } catch (e) {
        // Silent fail - preset_downloader might not be running
      }
    }
    
    // Hub info (desktop vs cloud)
    async function loadHubInfo() {
      try {
        const info = await fetch('/api/hub/info').then(r => r.json());
        document.getElementById('hub-title').textContent = info.title || 'Smyshnikov ComfyUI Hub';
        document.getElementById('hub-subtitle').textContent = info.subtitle || '';
        document.getElementById('host-label').textContent = info.host_label || 'Host';

        const pathLine = document.getElementById('comfyui-path-line');
        const pathRow = document.getElementById('path-settings-row');
        const pathDisplay = document.getElementById('path-settings-display');
        const pathHint = document.getElementById('path-settings-hint');

        if (info.show_path_settings) {
          pathLine.classList.add('hidden');
          pathRow.classList.remove('hidden');
          pathRow.classList.toggle('invalid', info.comfyui_path_valid === false);
          pathDisplay.innerHTML = '<code>' + (info.comfyui_path || 'не указан') + '</code>';
          if (info.comfyui_path_valid) {
            pathHint.className = 'path-settings-hint ok';
            pathHint.textContent = 'Путь найден, models/ на месте';
          } else {
            pathHint.className = 'path-settings-hint warn';
            pathHint.textContent = info.comfyui_path_message || 'Проверьте путь — нажмите «Изменить путь»';
          }
          if (info.config_path) {
            const cfgEl = document.getElementById('path-config-file');
            if (cfgEl) cfgEl.textContent = info.config_path;
          }
        } else if (info.comfyui_path) {
          pathRow.classList.add('hidden');
          pathLine.classList.remove('hidden');
          pathLine.innerHTML = 'ComfyUI: <code>' + info.comfyui_path + '</code>';
        }

        if (info.show_shutdown) {
          document.getElementById('shutdown-card').classList.remove('hidden');
        }
      } catch (e) {
        console.error('Hub info error:', e);
      }
    }

    async function openPathSettings() {
      document.getElementById('path-modal').classList.remove('hidden');
      const list = document.getElementById('path-detected-list');
      const input = document.getElementById('path-manual-input');
      list.innerHTML = '<div class="loading">Поиск установок...</div>';
      try {
        const data = await fetch('/api/settings/comfyui').then(r => r.json());
        input.value = data.current_normalized || data.current || '';
        if (!data.detected || !data.detected.length) {
          list.innerHTML = '<div class="path-settings-hint warn">Автопоиск ничего не нашёл — введите путь вручную.</div>';
          return;
        }
        const selected = data.current_normalized || data.current;
        list.innerHTML = data.detected.map((item, idx) => `
          <label class="settings-option">
            <input type="radio" name="comfy-path" value="${item.path.replace(/"/g, '&quot;')}"
              ${item.path === selected ? 'checked' : ''}
              onchange="document.getElementById('path-manual-input').value=this.value">
            <code>${item.label}</code>
          </label>
        `).join('');
      } catch (e) {
        list.innerHTML = '<div class="path-settings-hint warn">Ошибка загрузки: ' + e.message + '</div>';
      }
    }

    function closePathModal(event) {
      if (event && event.target !== event.currentTarget) return;
      document.getElementById('path-modal').classList.add('hidden');
    }

    async function saveComfyPath() {
      const btn = document.getElementById('path-save-btn');
      const path = document.getElementById('path-manual-input').value.trim();
      if (!path) {
        showToast('Укажите путь к ComfyUI', 'err');
        return;
      }
      btn.disabled = true;
      btn.textContent = 'Сохранение...';
      try {
        const res = await fetch('/api/settings/comfyui', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path }),
        });
        const data = await res.json();
        if (data.success) {
          showToast(data.message, 'ok');
          comfyLauncherData = null;
          closePathModal();
          loadHubInfo();
          bumpServicesPoll();
        } else {
          showToast(data.message || 'Ошибка', 'err');
        }
      } catch (e) {
        showToast('Ошибка: ' + e.message, 'err');
      }
      btn.disabled = false;
      btn.textContent = 'Сохранить';
    }

    let comfyLauncherData = null;

    async function loadComfyLauncherData() {
      if (comfyLauncherData) return comfyLauncherData;
      try {
        const res = await fetch('/api/comfyui/launchers');
        comfyLauncherData = await res.json();
      } catch (e) {
        comfyLauncherData = { profiles: [], selected: 'standard' };
      }
      return comfyLauncherData;
    }

    async function saveComfyLauncher(value) {
      try {
        await fetch('/api/comfyui/launcher', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ launcher: value }),
        });
        comfyLauncherData = null;
      } catch (e) {
        console.error(e);
      }
    }

    function comfyLauncherSelect(selected, profiles) {
      if (!profiles || profiles.length <= 1) return '';
      const opts = profiles.map(p =>
        `<option value="${p.id}" ${p.id === selected ? 'selected' : ''}>${p.label}</option>`
      ).join('');
      return `<select class="launcher-select" title="Профиль запуска ComfyUI" onchange="saveComfyLauncher(this.value)">${opts}</select>`;
    }

    const servicePending = {};
    let servicesFastPollTimer = null;

    function showToast(message, kind = 'info') {
      const host = document.getElementById('toast-host');
      if (!host) return;
      const el = document.createElement('div');
      el.className = `toast ${kind}`;
      el.textContent = message;
      host.appendChild(el);
      setTimeout(() => {
        el.style.opacity = '0';
        el.style.transition = 'opacity 0.3s';
        setTimeout(() => el.remove(), 320);
      }, 5000);
    }

    function bumpServicesPoll() {
      loadServices();
      if (servicesFastPollTimer) clearInterval(servicesFastPollTimer);
      let ticks = 0;
      servicesFastPollTimer = setInterval(() => {
        loadServices();
        ticks += 1;
        if (ticks >= 45) {
          clearInterval(servicesFastPollTimer);
          servicesFastPollTimer = null;
        }
      }, 2000);
    }

    function serviceStatusLabel(svc) {
      const pending = servicePending[svc.name];
      if (pending === 'starting') return { cls: 'starting', text: '◐ Запускается…' };
      if (pending === 'stopping') return { cls: 'stopping', text: '◐ Останавливается…' };
      if (pending === 'restarting') return { cls: 'starting', text: '◐ Перезапуск…' };
      const state = svc.state || (svc.running ? 'running' : 'stopped');
      if (state === 'running') return { cls: 'running', text: '● Работает' };
      if (state === 'starting') return { cls: 'starting', text: '◐ Запускается…' };
      return { cls: 'stopped', text: '○ Остановлен' };
    }

    function serviceIsActive(svc) {
      const pending = servicePending[svc.name];
      if (pending === 'starting' || pending === 'restarting') return true;
      const state = svc.state || (svc.running ? 'running' : 'stopped');
      return state === 'running' || state === 'starting';
    }

    // Load services (RunPod Connect style)
    async function loadServices() {
      try {
        const [services, launcherInfo] = await Promise.all([
          fetch('/api/services').then(r => r.json()),
          loadComfyLauncherData(),
        ]);
        const icons = {
          comfyui: '🎨',
          preset_downloader: '📦',
          civitai_downloader: '🧩',
          outputs_browser: '🖼️',
          custom_nodes_installer: '🔌',
          jupyter: '📓',
        };
        const desc = {
          comfyui: 'Генерация изображений и видео',
          preset_downloader: 'Каталог Wan / Qwen / Flux пресетов',
          civitai_downloader: 'Скачивание LoRA с CivitAI',
          outputs_browser: 'Галерея результатов ComfyUI',
          custom_nodes_installer: 'Git clone наборов нод + перезапуск ComfyUI',
          jupyter: 'JupyterLab (облако)',
        };

        const list = document.getElementById('services-list');
        list.innerHTML = services.map(svc => {
          const status = serviceStatusLabel(svc);
          const active = serviceIsActive(svc);
          const pending = servicePending[svc.name];
          const rowBusy = !!pending || status.cls === 'starting';
          const icon = icons[svc.name] || '🔗';
          const subtitle = desc[svc.name] || '';
          const openDisabled = !svc.running ? 'style="pointer-events:none;opacity:0.45"' : '';
          const busyCls = rowBusy ? 'busy' : '';
          const btnBusy = pending ? 'busy' : '';
          const managedBtns = svc.managed ? `
            ${svc.name === 'comfyui' ? comfyLauncherSelect(launcherInfo.selected, launcherInfo.profiles) : ''}
            ${!active ? `<button class="service-btn start ${btnBusy}" onclick="serviceAction('${svc.name}', 'start')">Запустить</button>` : ''}
            ${active ? `<button class="service-btn stop ${btnBusy}" onclick="serviceAction('${svc.name}', 'stop')">Стоп</button>` : ''}
            ${active ? `<button class="service-btn restart ${btnBusy}" onclick="serviceAction('${svc.name}', 'restart')">↻</button>` : ''}
          ` : '';
          return `
          <div class="connect-row ${busyCls}" data-service="${svc.name}">
            <span class="connect-icon">${icon}</span>
            <span class="connect-port">${svc.port}</span>
            <div class="connect-meta">
              <div class="connect-name">${svc.display}</div>
              <div class="connect-desc">${subtitle}</div>
            </div>
            <span class="connect-status ${status.cls}">${status.text}</span>
            <div class="connect-actions">
              <a href="${svc.url}" target="_blank" class="service-btn" ${openDisabled}>Открыть ↗</a>
              ${managedBtns}
              <button class="service-btn" onclick="showLog('${svc.name}', '${svc.display}')">Логи</button>
            </div>
          </div>`;
        }).join('');

        for (const svc of services) {
          const pending = servicePending[svc.name];
          if (!pending) continue;
          const state = svc.state || (svc.running ? 'running' : 'stopped');
          if (pending === 'starting' && state === 'running') delete servicePending[svc.name];
          if (pending === 'stopping' && state === 'stopped') delete servicePending[svc.name];
          if (pending === 'restarting' && state === 'running') delete servicePending[svc.name];
        }
      } catch (e) {
        console.error('Services error:', e);
      }
    }

    async function startAllServices() {
      const btn = document.getElementById('start-all-btn');
      btn.disabled = true;
      btn.textContent = 'Запуск...';
      showToast('Запускаем все сервисы…', 'info');
      try {
        const res = await fetch('/api/services/start-all', { method: 'POST' });
        const data = await res.json();
        if (data.started && data.started.length) {
          showToast('Запущено: ' + data.started.join(', '), 'ok');
        }
        if (data.skipped && data.skipped.length) {
          showToast('Уже работали: ' + data.skipped.join(', '), 'info');
        }
        if (data.errors && data.errors.length) {
          showToast(data.errors.join('; '), 'err');
        }
        bumpServicesPoll();
      } catch (e) {
        showToast('Ошибка: ' + e.message, 'err');
      }
      btn.disabled = false;
      btn.textContent = '▶ Запустить все';
    }

    async function stopAllServices() {
      const btn = document.getElementById('stop-all-btn');
      btn.disabled = true;
      btn.textContent = 'Остановка...';
      showToast('Останавливаем все сервисы…', 'info');
      try {
        const res = await fetch('/api/services/stop-all', { method: 'POST' });
        const data = await res.json();
        if (data.stopped && data.stopped.length) {
          showToast('Остановлено: ' + data.stopped.join(', '), 'ok');
        }
        if (data.skipped && data.skipped.length) {
          showToast('Уже были остановлены: ' + data.skipped.join(', '), 'info');
        }
        if (data.errors && data.errors.length) {
          showToast(data.errors.join('; '), 'err');
        }
        bumpServicesPoll();
      } catch (e) {
        showToast('Ошибка: ' + e.message, 'err');
      }
      btn.disabled = false;
      btn.textContent = '■ Остановить все';
    }
    
    // Service actions
    async function serviceAction(name, action) {
      const pendingKey = action === 'restart' ? 'restarting' : (action === 'start' ? 'starting' : 'stopping');
      servicePending[name] = pendingKey;
      loadServices();

      const actionLabels = { start: 'Запуск', stop: 'Остановка', restart: 'Перезапуск' };
      showToast(`${actionLabels[action] || action}: ${name}…`, 'info');

      try {
        let url = `/api/services/${name}/${action}`;
        if (name === 'comfyui' && action === 'start') {
          const sel = document.querySelector('.launcher-select');
          if (sel && sel.value) {
            url += `?launcher=${encodeURIComponent(sel.value)}`;
          }
        }
        const res = await fetch(url, { method: 'POST' });
        const result = await res.json();
        
        if (result.success) {
          showToast(result.message || 'Готово', 'ok');
          bumpServicesPoll();
        } else {
          delete servicePending[name];
          loadServices();
          showToast(result.message || 'Ошибка', 'err');
        }
      } catch (e) {
        delete servicePending[name];
        loadServices();
        showToast('Ошибка: ' + e.message, 'err');
      }
    }
    
    // Log modal
    let currentLogService = null;
    
    function showLog(name, display) {
      currentLogService = name;
      document.getElementById('log-modal-title').textContent = `Логи: ${display}`;
      document.getElementById('log-modal').classList.remove('hidden');
      refreshLog();
    }
    
    async function refreshLog() {
      if (!currentLogService) return;
      
      const content = document.getElementById('log-content');
      content.textContent = 'Загрузка...';
      
      try {
        const res = await fetch(`/api/services/${currentLogService}/log?lines=200`);
        const data = await res.json();
        content.textContent = data.log || 'Лог пуст';
        content.scrollTop = content.scrollHeight;
      } catch (e) {
        content.textContent = 'Ошибка загрузки: ' + e.message;
      }
    }
    
    function closeLogModal(event) {
      if (event && event.target !== event.currentTarget) return;
      document.getElementById('log-modal').classList.add('hidden');
      currentLogService = null;
    }
    
    // Shutdown scheduler
    let shutdownTimer = null;
    
    async function loadShutdownStatus() {
      try {
        const res = await fetch('/api/shutdown/status');
        const status = await res.json();
        
        const picker = document.getElementById('shutdown-picker');
        const countdown = document.getElementById('shutdown-countdown');
        const scheduleBtn = document.getElementById('schedule-btn');
        const cancelBtn = document.getElementById('cancel-btn');
        const meta = document.getElementById('shutdown-meta');
        
        if (status.scheduled) {
          picker.classList.add('hidden');
          countdown.classList.remove('hidden');
          scheduleBtn.classList.add('hidden');
          cancelBtn.classList.remove('hidden');
          meta.classList.remove('hidden');
          document.getElementById('shutdown-time').textContent = status.shutdown_time;
          
          // Start countdown timer
          if (shutdownTimer) clearInterval(shutdownTimer);
          let remaining = status.time_remaining;
          updateCountdown(remaining);
          shutdownTimer = setInterval(() => {
            remaining = Math.max(0, remaining - 1);
            updateCountdown(remaining);
            if (remaining <= 0) {
              clearInterval(shutdownTimer);
              loadShutdownStatus();
            }
          }, 1000);
        } else {
          picker.classList.remove('hidden');
          countdown.classList.add('hidden');
          scheduleBtn.classList.remove('hidden');
          cancelBtn.classList.add('hidden');
          meta.classList.add('hidden');
          if (shutdownTimer) {
            clearInterval(shutdownTimer);
            shutdownTimer = null;
          }
        }
      } catch (e) {
        console.error('Shutdown status error:', e);
      }
    }
    
    function updateCountdown(seconds) {
      const h = Math.floor(seconds / 3600);
      const m = Math.floor((seconds % 3600) / 60);
      const s = seconds % 60;
      document.getElementById('countdown-hours').textContent = pad2(h);
      document.getElementById('countdown-mins').textContent = pad2(m);
      document.getElementById('countdown-secs').textContent = pad2(s);
    }
    
    async function scheduleShutdown() {
      const hours = parseInt(document.getElementById('shutdown-hours').value) || 0;
      const mins = parseInt(document.getElementById('shutdown-mins').value) || 0;
      const secs = parseInt(document.getElementById('shutdown-secs').value) || 0;
      const totalSeconds = hours * 3600 + mins * 60 + secs;
      
      if (totalSeconds < 1) {
        alert('Укажите время больше 0 секунд.');
        return;
      }
      
      try {
        await fetch('/api/shutdown/schedule', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ value: totalSeconds, unit: 'seconds' })
        });
        loadShutdownStatus();
      } catch (e) {
        alert('Ошибка планирования: ' + e.message);
      }
    }
    
    async function cancelShutdown() {
      try {
        await fetch('/api/shutdown/cancel', { method: 'POST' });
        loadShutdownStatus();
      } catch (e) {
        alert('Ошибка отмены: ' + e.message);
      }
    }
    
    // Initialize
    loadHubInfo();
    loadTelemetry();
    loadServices();
    loadShutdownStatus();
    loadEnvironment();
    loadDownloads();
    
    // Auto-refresh
    setInterval(loadTelemetry, 5000);
    setInterval(loadServices, 5000);
    setInterval(loadDownloads, 3000);  // Downloads refresh more frequently
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index():
    """Serve the dashboard HTML page."""
    return HTMLResponse(INDEX_HTML)
