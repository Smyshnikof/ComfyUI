"""Cross-platform paths for preset downloader (RunPod Docker + Windows desktop)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_SERVICES_DIR = Path(__file__).resolve().parent
if getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None):
    REPO_ROOT = Path(sys._MEIPASS)
else:
    REPO_ROOT = _SERVICES_DIR.parent


def _is_cloud_workspace() -> bool:
    if os.environ.get("RP_WORKSPACE") == "/workspace":
        return True
    if os.environ.get("RUNPOD_POD_ID"):
        return True
    return sys.platform != "win32" and os.path.isdir("/workspace/ComfyUI")


def _load_desktop_config() -> dict:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "config.json")
    candidates.extend([
        REPO_ROOT / "desktop" / "config.json",
        Path.cwd() / "config.json",
    ])
    for path in candidates:
        if not path.is_file():
            continue
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            continue
    return {}


_desktop_cfg = _load_desktop_config()


def read_desktop_config() -> dict:
    """Fresh read (e.g. after hub saves launcher profile)."""
    return _load_desktop_config()


def _env_path(name: str) -> Path | None:
    value = (os.environ.get(name) or "").strip()
    return Path(value) if value else None


def _default_data_dir() -> Path:
    override = _env_path("DOWNLOADER_DATA_DIR")
    if override:
        return override
    cfg = (_desktop_cfg.get("data_dir") or "").strip()
    if cfg:
        return Path(cfg)
    if _is_cloud_workspace():
        return Path("/workspace")
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(appdata) / "SmyshnikovDownloader"
    return Path.home() / ".local" / "share" / "SmyshnikovDownloader"


def _default_models_root() -> Path:
    override = _env_path("MODELS_ROOT")
    if override:
        return override
    cfg_models = (_desktop_cfg.get("models_root") or "").strip()
    if cfg_models:
        return Path(cfg_models)
    comfyui_path = (_desktop_cfg.get("comfyui_path") or "").strip()
    if comfyui_path:
        return Path(comfyui_path) / "models"
    if _is_cloud_workspace():
        return Path("/workspace/ComfyUI/models")
    for candidate in (
        Path.home() / "ComfyUI" / "models",
        Path("C:/ComfyUI/models"),
        Path("D:/ComfyUI/models"),
    ):
        if candidate.is_dir():
            return candidate
    return Path.home() / "ComfyUI" / "models"


def _default_custom_nodes_root() -> Path:
    override = _env_path("CUSTOM_NODES_ROOT")
    if override:
        return override
    return comfyui_root() / "custom_nodes"


def _default_node_presets_community_dir() -> Path:
    override = _env_path("NODE_PRESETS_COMMUNITY_DIR")
    if override:
        return override
    if _is_cloud_workspace():
        return Path("/workspace/node_presets/community")
    return DATA_DIR / "node_presets" / "community"


def _default_node_presets_categories_file() -> Path:
    override = _env_path("NODE_PRESETS_CATEGORIES_FILE")
    if override:
        return override
    if _is_cloud_workspace():
        return Path("/workspace/node_presets/community_categories.json")
    return DATA_DIR / "node_presets" / "community_categories.json"


def _default_community_dir() -> Path:
    override = _env_path("COMMUNITY_PRESETS_DIR")
    if override:
        return override
    cfg = (_desktop_cfg.get("community_dir") or "").strip()
    if cfg:
        return Path(cfg)
    if _is_cloud_workspace():
        return Path("/workspace/presets/community")
    return DATA_DIR / "presets" / "community"


def _default_community_categories_file() -> Path:
    override = _env_path("COMMUNITY_CATEGORIES_FILE")
    if override:
        return override
    cfg = (_desktop_cfg.get("community_categories_file") or "").strip()
    if cfg:
        return Path(cfg)
    if _is_cloud_workspace():
        return Path("/workspace/presets/community_categories.json")
    return DATA_DIR / "presets" / "community_categories.json"


def _default_tokens_path() -> Path:
    override = _env_path("TOKENS_PATH")
    if override:
        return override
    cfg = (_desktop_cfg.get("tokens_path") or "").strip()
    if cfg:
        return Path(cfg)
    if _is_cloud_workspace():
        return Path("/workspace/.downloader_tokens.json")
    return DATA_DIR / "tokens.json"


def _default_workspace_root() -> Path:
    override = _env_path("RP_WORKSPACE")
    if override:
        return override
    if _is_cloud_workspace():
        return Path("/workspace")
    return DATA_DIR


DATA_DIR = _default_data_dir()
MODELS_ROOT = _default_models_root()
COMMUNITY_DIR = _default_community_dir()
COMMUNITY_CATEGORIES_FILE = _default_community_categories_file()
TOKENS_PATH = _default_tokens_path()
WORKSPACE_ROOT = _default_workspace_root()
LOGS_DIR = DATA_DIR / "logs"
DEFAULT_PORT = int(_desktop_cfg.get("port") or os.environ.get("PRESET_DOWNLOADER_PORT", "8081"))
HUB_PORT = int(_desktop_cfg.get("hub_port") or os.environ.get("HUB_PORT", "8084"))
COMFYUI_PORT = int(_desktop_cfg.get("comfyui_port") or os.environ.get("COMFYUI_PORT", "3000"))
HOST = (_desktop_cfg.get("host") or os.environ.get("PRESET_DOWNLOADER_HOST") or "127.0.0.1").strip()
BIND_HOST = (
    os.environ.get("BIND_HOST")
    or (_desktop_cfg.get("bind_host") or "").strip()
    or ("0.0.0.0" if _is_cloud_workspace() else HOST)
)


def is_desktop_mode() -> bool:
    return sys.platform == "win32" and not _is_cloud_workspace()


def comfyui_root() -> Path:
    override = _env_path("COMFYUI_ROOT")
    if override:
        return override
    cfg = (_desktop_cfg.get("comfyui_path") or "").strip()
    if cfg:
        return Path(cfg)
    if _is_cloud_workspace():
        return Path("/workspace/ComfyUI")
    if os.path.isdir("/opt/workspace-internal/ComfyUI"):
        return Path("/opt/workspace-internal/ComfyUI")
    return Path.home() / "ComfyUI"


COMFYUI_ROOT = comfyui_root()
CUSTOM_NODES_ROOT = _default_custom_nodes_root()
NODE_PRESETS_COMMUNITY_DIR = _default_node_presets_community_dir()
NODE_PRESETS_CATEGORIES_FILE = _default_node_presets_categories_file()
OUTPUT_ROOT = Path(os.environ.get("OUTPUT_ROOT", str(COMFYUI_ROOT / "output")))
AUTO_START_SERVICES = bool(_desktop_cfg.get("auto_start_services", True))
CUSTOM_NODES_PORT = int(
    _desktop_cfg.get("custom_nodes_port")
    or os.environ.get("CUSTOM_NODES_PORT", "8085")
)


def service_url(port: int, host: str | None = None) -> str:
    h = (host or HOST).strip()
    pod_id = os.environ.get("RUNPOD_POD_ID", "")
    if pod_id:
        return f"https://{pod_id}-{port}.proxy.runpod.net/"
    return f"http://{h}:{port}/"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    COMMUNITY_DIR.mkdir(parents=True, exist_ok=True)
    NODE_PRESETS_COMMUNITY_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_ROOT.mkdir(parents=True, exist_ok=True)
    CUSTOM_NODES_ROOT.mkdir(parents=True, exist_ok=True)


def save_desktop_config(
    *,
    comfyui_path: str | None = None,
    models_root: str | None = None,
    port: int | None = None,
    hub_port: int | None = None,
    comfyui_launcher: str | None = None,
) -> Path:
    """Persist desktop launcher settings next to the app."""
    config_path = REPO_ROOT / "desktop" / "config.json"
    if getattr(sys, "frozen", False):
        config_path = Path(sys.executable).resolve().parent / "config.json"
    data = dict(_desktop_cfg)
    if comfyui_path is not None:
        data["comfyui_path"] = comfyui_path
    if models_root is not None:
        data["models_root"] = models_root
    if port is not None:
        data["port"] = port
    if hub_port is not None:
        data["hub_port"] = hub_port
    if comfyui_launcher is not None:
        data["comfyui_launcher"] = comfyui_launcher
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return config_path


def detect_comfyui_installations() -> list[Path]:
    """Return candidate ComfyUI root directories (folder with models/)."""
    found: list[Path] = []
    seen: set[str] = set()

    def add(path: Path | None) -> None:
        if path is None:
            return
        key = str(path.resolve()).lower()
        if key in seen:
            return
        seen.add(key)
        found.append(path.resolve())

    cfg_path = (_desktop_cfg.get("comfyui_path") or "").strip()
    if cfg_path:
        add(normalize_comfyui_root(Path(cfg_path)))

    if getattr(sys, "frozen", False):
        add(normalize_comfyui_root(Path(sys.executable).resolve().parent.parent / "ComfyUI"))
        add(normalize_comfyui_root(Path(sys.executable).resolve().parent / "ComfyUI"))

    scan_roots = [
        Path.home() / "ComfyUI",
        Path("C:/ComfyUI"),
        Path("D:/ComfyUI"),
        Path.home() / "Documents" / "ComfyUI",
        Path.home() / "Desktop" / "ComfyUI",
        Path("C:/ComfyUI/ComfyUI_windows_portable"),
        Path("D:/ComfyUI/ComfyUI_windows_portable"),
        Path.home() / "ComfyUI_windows_portable",
    ]
    for base in scan_roots:
        if not base.is_dir():
            continue
        normalized = normalize_comfyui_root(base)
        if normalized:
            add(normalized)
        try:
            for child in base.iterdir():
                if child.is_dir():
                    add(normalize_comfyui_root(child))
        except OSError:
            pass

    return found


def normalize_comfyui_root(path: Path) -> Path | None:
    """Accept ComfyUI dir or portable root; return folder with models/ (+ main.py)."""
    try:
        p = path.expanduser().resolve()
    except OSError:
        return None
    if (p / "main.py").is_file() and (p / "models").is_dir():
        return p
    inner = p / "ComfyUI"
    if (inner / "main.py").is_file() and (inner / "models").is_dir():
        return inner
    if (p / "models").is_dir():
        return p
    return None


def validate_comfyui_path(path: str) -> dict:
    """Check path and return {valid, normalized, message, portable}."""
    raw = (path or "").strip().strip('"')
    if not raw:
        return {"valid": False, "normalized": "", "message": "Укажите путь", "portable": False}
    normalized = normalize_comfyui_root(Path(raw))
    if not normalized:
        return {
            "valid": False,
            "normalized": raw,
            "message": "Не найдена папка ComfyUI с models/ (укажите …\\ComfyUI или portable-корень)",
            "portable": False,
        }
    portable_root = normalized.parent if (normalized.parent / "python_embeded").is_dir() else None
    return {
        "valid": True,
        "normalized": str(normalized),
        "message": "OK",
        "portable": portable_root is not None,
        "portable_root": str(portable_root) if portable_root else None,
    }


def apply_comfyui_path(path: str) -> dict:
    """Save path to config and update runtime env for the running hub process."""
    check = validate_comfyui_path(path)
    if not check["valid"]:
        return {"success": False, "message": check["message"]}

    normalized = check["normalized"]
    save_desktop_config(comfyui_path=normalized)

    global _desktop_cfg, COMFYUI_ROOT, MODELS_ROOT, OUTPUT_ROOT
    _desktop_cfg = _load_desktop_config()
    os.environ["COMFYUI_ROOT"] = normalized
    os.environ["MODELS_ROOT"] = str(Path(normalized) / "models")
    os.environ["OUTPUT_ROOT"] = str(Path(normalized) / "output")
    COMFYUI_ROOT = Path(normalized)
    MODELS_ROOT = Path(normalized) / "models"
    OUTPUT_ROOT = Path(normalized) / "output"

    return {
        "success": True,
        "message": f"Путь сохранён: {normalized}",
        "comfyui_path": normalized,
        "portable": check.get("portable", False),
    }
