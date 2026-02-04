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
import threading
import time
import shutil
import httpx

app = FastAPI(title="Dashboard Service")

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
    """Get memory information from /proc/meminfo."""
    meminfo = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                key, val = line.split(":", 1)
                meminfo[key.strip()] = int(val.strip().split()[0]) * 1024
    except FileNotFoundError:
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
    host = os.environ.get("RUNPOD_POD_ID") or os.environ.get("RUNPOD_HOST_ID") or "local"

    # Container uptime
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
        uptime_seconds = 0.0

    load_avg = list(os.getloadavg()) if hasattr(os, "getloadavg") else [0.0, 0.0, 0.0]
    cpu_count = os.cpu_count() or 1

    # Memory
    mem_total, mem_used, mem_free = get_meminfo()

    # Disks
    disks = [disk_usage("/")]
    if os.path.exists("/workspace"):
        disks.append(disk_usage("/workspace"))

    # GPUs
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


# ============================================================================
# Services Status
# ============================================================================

SERVICES = [
    {"name": "preset_downloader", "display": "Preset Downloader", "port": 8081},
    {"name": "civitai_downloader", "display": "CivitAI Downloader", "port": 8082},
    {"name": "outputs_browser", "display": "Outputs Browser", "port": 8083},
    {"name": "comfyui", "display": "ComfyUI", "port": 3000},
    {"name": "jupyter", "display": "JupyterLab", "port": 8888},
]


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
    for svc in SERVICES:
        running = await check_service_health(svc["port"])
        # Build external URL
        pod_id = os.environ.get("RUNPOD_POD_ID", "")
        if pod_id:
            url = f"https://{pod_id}-{svc['port']}.proxy.runpod.net/"
        else:
            url = f"http://localhost:{svc['port']}/"
        
        entries.append(ServiceEntry(
            name=svc["name"],
            display=svc["display"],
            port=svc["port"],
            running=running,
            url=url,
        ))
    return entries


def get_service_log(name: str, lines: int = 100) -> dict:
    """Get service log from /workspace/logs/."""
    log_path = f"/workspace/logs/{name}.log"
    if not os.path.exists(log_path):
        return {"log": f"Log file not found: {log_path}", "path": log_path}
    
    try:
        result = subprocess.run(
            ["tail", "-n", str(lines), log_path],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return {"log": result.stdout, "path": log_path}
    except Exception as e:
        return {"log": f"Error reading log: {str(e)}", "path": log_path}


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/api/telemetry", response_model=Telemetry)
def telemetry_endpoint():
    """Get system telemetry data."""
    return get_telemetry()


@app.get("/api/services")
async def services_endpoint():
    """Get status of all services."""
    return await get_services_status()


@app.get("/api/services/{name}/log")
def service_log_endpoint(name: str, lines: int = 100):
    """Get service log."""
    return get_service_log(name, lines)


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
    return {"status": "ok", "message": "Dashboard service is running"}


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
      background: linear-gradient(135deg, #ff6b4a 0%, #f35a3c 50%, #e04d31 100%);
      box-shadow: 0 18px 50px rgba(0,0,0,0.35);
      overflow: hidden;
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
    .shutdown-btn.primary { background: rgba(255,255,255,0.95); color: #e04d31; }
    .shutdown-btn.primary:hover { background: #fff; transform: translateY(-2px); box-shadow: 0 8px 20px rgba(0,0,0,0.2); }
    .shutdown-btn.secondary { background: rgba(0,0,0,0.2); color: rgba(255,255,255,0.9); border: 1px solid rgba(255,255,255,0.2); }
    .shutdown-btn.secondary:hover { background: rgba(0,0,0,0.3); }
    .shutdown-meta { position: relative; margin-top: 12px; font-size: 13px; opacity: 0.85; text-align: center; }
    .hidden { display: none !important; }
    
    /* Services */
    .services-list { display: flex; flex-direction: column; gap: 12px; }
    .service-card { background: #1a1a1a; border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .service-info { display: flex; align-items: center; gap: 12px; }
    .service-dot { width: 10px; height: 10px; border-radius: 50%; }
    .service-dot.running { background: #22c55e; box-shadow: 0 0 8px rgba(34,197,94,0.5); }
    .service-dot.stopped { background: #ef4444; }
    .service-name { font-weight: 600; }
    .service-port { color: var(--muted); font-size: 13px; margin-left: 8px; }
    .service-btn { padding: 8px 16px; background: rgba(255,255,255,0.1); border: 1px solid var(--border); border-radius: 8px; color: var(--text); font-size: 13px; cursor: pointer; text-decoration: none; transition: all 0.2s; }
    .service-btn:hover { background: rgba(255,255,255,0.15); border-color: var(--accent); }
    .service-btn:disabled { opacity: 0.5; cursor: not-allowed; }
    
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
    <h1 class="title">Dashboard</h1>
    <p class="subtitle">Мониторинг системы и управление сервисами</p>
    
    <div class="pills" id="info-pills">
      <div class="pill">RunPod ID: <strong id="pod-id">-</strong></div>
      <div class="pill">Uptime: <strong id="uptime">-</strong></div>
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
        <h3>Disks</h3>
        <table>
          <thead>
            <tr><th>Mount</th><th>Usage</th><th></th></tr>
          </thead>
          <tbody id="disk-body">
            <tr><td colspan="3" class="loading">Loading disk info...</td></tr>
          </tbody>
        </table>
      </div>
      
      <!-- Shutdown Scheduler -->
      <div class="card" style="padding:0; border:none; background:transparent;">
        <div class="shutdown-widget" id="shutdown-widget">
          <div class="shutdown-header">
            <div>
              <div class="shutdown-title">Shutdown Pod</div>
              <div class="shutdown-subtitle">Schedule automatic termination</div>
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
              <div class="shutdown-lbl">Hours</div>
            </div>
            <div class="shutdown-sep">:</div>
            <div class="shutdown-seg">
              <input type="number" class="shutdown-input" id="shutdown-mins" min="0" max="59" value="30">
              <div class="shutdown-lbl">Mins</div>
            </div>
            <div class="shutdown-sep">:</div>
            <div class="shutdown-seg">
              <input type="number" class="shutdown-input" id="shutdown-secs" min="0" max="59" value="0">
              <div class="shutdown-lbl">Secs</div>
            </div>
          </div>
          
          <!-- Countdown mode -->
          <div class="shutdown-timebox hidden" id="shutdown-countdown">
            <div class="shutdown-seg">
              <div class="shutdown-num" id="countdown-hours">00</div>
              <div class="shutdown-lbl">Hours</div>
            </div>
            <div class="shutdown-sep">:</div>
            <div class="shutdown-seg">
              <div class="shutdown-num" id="countdown-mins">00</div>
              <div class="shutdown-lbl">Mins</div>
            </div>
            <div class="shutdown-sep">:</div>
            <div class="shutdown-seg">
              <div class="shutdown-num" id="countdown-secs">00</div>
              <div class="shutdown-lbl">Secs</div>
            </div>
          </div>
          
          <div class="shutdown-actions">
            <button class="shutdown-btn primary" id="schedule-btn" onclick="scheduleShutdown()">Schedule Shutdown</button>
            <button class="shutdown-btn secondary hidden" id="cancel-btn" onclick="cancelShutdown()">Cancel</button>
          </div>
          
          <div class="shutdown-meta hidden" id="shutdown-meta">
            Shutdown at: <span id="shutdown-time">-</span>
          </div>
        </div>
      </div>
      
      <!-- Services -->
      <div class="card">
        <h3>Services</h3>
        <div class="services-list" id="services-list">
          <div class="loading">Loading services...</div>
        </div>
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
    
    // Load services
    async function loadServices() {
      try {
        const res = await fetch('/api/services');
        const services = await res.json();
        
        const list = document.getElementById('services-list');
        list.innerHTML = services.map(svc => `
          <div class="service-card">
            <div class="service-info">
              <div class="service-dot ${svc.running ? 'running' : 'stopped'}"></div>
              <span class="service-name">${svc.display}</span>
              <span class="service-port">:${svc.port}</span>
            </div>
            <a href="${svc.url}" target="_blank" class="service-btn" ${!svc.running ? 'disabled' : ''}>Open</a>
          </div>
        `).join('');
        
      } catch (e) {
        console.error('Services error:', e);
      }
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
        alert('Please set a countdown greater than 0 seconds.');
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
        alert('Failed to schedule shutdown: ' + e.message);
      }
    }
    
    async function cancelShutdown() {
      try {
        await fetch('/api/shutdown/cancel', { method: 'POST' });
        loadShutdownStatus();
      } catch (e) {
        alert('Failed to cancel shutdown: ' + e.message);
      }
    }
    
    // Initialize
    loadTelemetry();
    loadServices();
    loadShutdownStatus();
    
    // Auto-refresh telemetry every 5 seconds
    setInterval(loadTelemetry, 5000);
    setInterval(loadServices, 10000);
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index():
    """Serve the dashboard HTML page."""
    return HTMLResponse(INDEX_HTML)
