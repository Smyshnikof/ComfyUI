"""Load preset manifests (builtin + community) into PRESETS / PRESET_FILES / PRESET_CATEGORIES."""
from __future__ import annotations

import glob
import json
import os
import re
import zlib
import base64
import binascii
from typing import Any
from urllib.parse import urlparse

_SERVICES_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_SERVICES_DIR, ".."))

BUILTIN_DIR = os.path.join(_REPO_ROOT, "presets", "manifest")
COMMUNITY_DIR = os.environ.get("COMMUNITY_PRESETS_DIR", "/workspace/presets/community")
CATEGORIES_FILE = os.path.join(_REPO_ROOT, "presets", "categories.json")
COMMUNITY_CATEGORIES_FILE = os.environ.get(
    "COMMUNITY_CATEGORIES_FILE", "/workspace/presets/community_categories.json")
_DEFAULT_CAT_ICON = "📦"
_DEFAULT_CAT_COLOR = "#9ca3af"

ALLOWED_MODEL_FOLDERS = frozenset({
    "diffusion_models", "loras", "vae", "text_encoders", "upscale_models",
    "latent_upscale_models", "clip_vision", "audio_encoders", "checkpoints",
    "clip", "configs", "controlnet", "diffusers", "embeddings", "gligen",
    "hypernetworks", "ipadapter", "model_patches", "onnx", "photomaker",
    "sams", "style_models", "unet", "vae_approx", "vibevoice", "detection",
})

ALLOWED_URL_HOSTS = frozenset({
    "huggingface.co",
    "civitai.com",
    "github.com",
    "raw.githubusercontent.com",
    "gist.githubusercontent.com",
})

ALLOWED_IMPORT_HOSTS = frozenset({
    "raw.githubusercontent.com",
    "gist.githubusercontent.com",
    "huggingface.co",
    "github.com",
})

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

SHARE_REF_PREFIX = "CUIP1:ref:"
SHARE_Z_PREFIX = "CUIP1:z:"
MAX_SHARE_CODE_CHARS = 2500

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def is_builtin_preset_id(pid: str) -> bool:
    return pid in _collect_ids(sorted(glob.glob(os.path.join(BUILTIN_DIR, "*.json"))))


def encode_preset_share_code(obj: dict) -> str | None:
    """Short ref for built-in presets; gzip+base64 for community. None if too large."""
    pid = obj.get("id", "")
    if isinstance(pid, str) and is_builtin_preset_id(pid):
        return f"{SHARE_REF_PREFIX}{pid}"
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    b64 = base64.urlsafe_b64encode(zlib.compress(raw, level=9)).decode("ascii").rstrip("=")
    code = f"{SHARE_Z_PREFIX}{b64}"
    if len(code) > MAX_SHARE_CODE_CHARS:
        return None
    return code


def decode_preset_share_code(code: str) -> tuple[str, Any]:
    """
    Returns (kind, payload).
    kind='ref' → payload is preset id str.
    kind='preset' → payload is manifest dict.
    """
    code = code.strip()
    if not code:
        raise ValueError("empty")
    if code.startswith(SHARE_REF_PREFIX):
        pid = code[len(SHARE_REF_PREFIX):]
        if not isinstance(pid, str) or not _ID_RE.fullmatch(pid):
            raise ValueError("bad ref")
        return "ref", pid
    if code.startswith(SHARE_Z_PREFIX):
        b64 = code[len(SHARE_Z_PREFIX):]
        pad = (-len(b64)) % 4
        raw = zlib.decompress(base64.urlsafe_b64decode(b64 + "=" * pad))
        return "preset", json.loads(raw.decode("utf-8"))
    pad = (-len(code)) % 4
    try:
        raw = base64.urlsafe_b64decode(code.encode("ascii") + b"=" * pad)
    except binascii.Error as exc:
        raise ValueError("bad b64") from exc
    return "preset", json.loads(raw.decode("utf-8"))


def slug_id(name: str) -> str:
    s = (name or "").lower()
    s = "".join(_TRANSLIT.get(ch, ch) for ch in s)
    s = re.sub(r"[^A-Za-z0-9_-]", "_", s).strip("_")[:48]
    return s or "preset"


def unique_community_id(base: str) -> str:
    """base, base-2, base-3… without conflicting with builtin or existing community."""
    builtin = _collect_ids(sorted(glob.glob(os.path.join(BUILTIN_DIR, "*.json"))))
    community = _collect_ids(sorted(glob.glob(os.path.join(COMMUNITY_DIR, "*.json"))))
    taken = builtin | community
    if base not in taken:
        return base
    i = 2
    while f"{base}-{i}" in taken:
        i += 1
    return f"{base}-{i}"


def _load_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_categories() -> dict:
    """Built-in categories plus community (community never overrides built-in)."""
    cats = _load_json(CATEGORIES_FILE) if os.path.isfile(CATEGORIES_FILE) else {}
    if os.path.isfile(COMMUNITY_CATEGORIES_FILE):
        try:
            for cid, meta in (_load_json(COMMUNITY_CATEGORIES_FILE) or {}).items():
                if cid not in cats:
                    cats[cid] = meta
        except Exception:
            pass
    return cats


def ensure_community_category(
    name: str,
    icon: str | None = None,
    color: str | None = None,
) -> str:
    """Return category id; create in community store if new."""
    name = (name or "").strip()
    if not name:
        return name
    cats = load_categories()
    for cid, meta in cats.items():
        if cid == name or meta.get("name", "").lower() == name.lower():
            return cid
    cid = slug_id(name)
    base = cid
    i = 2
    while cid in cats:
        cid = f"{base}-{i}"
        i += 1
    store: dict = {}
    if os.path.isfile(COMMUNITY_CATEGORIES_FILE):
        try:
            store = _load_json(COMMUNITY_CATEGORIES_FILE) or {}
        except Exception:
            store = {}
    store[cid] = {
        "name": name.strip()[:40] or cid,
        "icon": (icon or _DEFAULT_CAT_ICON)[:4],
        "color": color or _DEFAULT_CAT_COLOR,
    }
    os.makedirs(os.path.dirname(COMMUNITY_CATEGORIES_FILE), exist_ok=True)
    tmp = COMMUNITY_CATEGORIES_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, COMMUNITY_CATEGORIES_FILE)
    return cid


def _ensure_category_from_import(obj: dict) -> dict:
    obj = dict(obj)
    cat = obj.get("category")
    known = load_categories()
    if cat and cat not in known:
        cm = obj.get("category_meta") or {}
        obj["category"] = ensure_community_category(
            cm.get("name", cat), cm.get("icon"), cm.get("color")
        )
    return obj


def _files_to_tuples(files: list[dict]) -> list[tuple[str, str, str | None]]:
    out: list[tuple[str, str, str | None]] = []
    for fl in files or []:
        out.append((fl["url"], fl["folder"], fl.get("filename")))
    return out


def _tuples_to_files(entries: list[tuple[str, str, str | None]]) -> list[dict]:
    return [
        {"url": url, "folder": folder, "filename": custom}
        for url, folder, custom in entries
    ]


def _url_host_ok(url: str) -> bool:
    if not url.startswith("https://"):
        return False
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host in ALLOWED_URL_HOSTS


def validate_preset(
    obj: dict,
    categories: dict,
    seen: set[str],
    *,
    strict_files: bool = True,
) -> tuple[bool, str]:
    if obj.get("schema") != 1:
        return False, "schema must be 1"
    pid = obj.get("id")
    if not isinstance(pid, str) or not _ID_RE.fullmatch(pid):
        return False, "invalid or missing id"
    if pid in seen:
        return False, f"duplicate id: {pid}"
    if not obj.get("name"):
        return False, "missing name"
    category = obj.get("category")
    if not category or category not in categories:
        return False, f"unknown category: {category!r}"
    has_files = bool(obj.get("files"))
    has_variants = bool(obj.get("variant_groups"))
    if has_files and has_variants:
        return False, "cannot have both files and variant_groups"
    if not has_files and not has_variants:
        return False, "need files or variant_groups"

    def _check_file_list(files: list, ctx: str) -> tuple[bool, str]:
        if not isinstance(files, list) or (strict_files and not files):
            return False, f"{ctx}: files must be a non-empty list"
        for fl in files:
            if not isinstance(fl, dict):
                return False, f"{ctx}: bad file entry"
            folder = fl.get("folder")
            url = fl.get("url")
            if folder not in ALLOWED_MODEL_FOLDERS:
                return False, f"{ctx}: invalid folder {folder!r}"
            if not isinstance(url, str) or not _url_host_ok(url):
                return False, f"{ctx}: invalid url {url!r}"
        return True, ""

    if has_files:
        ok, err = _check_file_list(obj["files"], pid)
        if not ok:
            return False, err
    else:
        for grp in obj["variant_groups"]:
            if not grp.get("group"):
                return False, "variant group missing name"
            variants = grp.get("variants")
            if not isinstance(variants, list) or not variants:
                return False, f"empty variants in group {grp.get('group')!r}"
            for v in variants:
                vid = v.get("id")
                if not isinstance(vid, str) or not _ID_RE.fullmatch(vid):
                    return False, f"invalid variant id: {vid!r}"
                if vid in seen:
                    return False, f"duplicate variant id: {vid}"
                if not v.get("name"):
                    return False, f"variant {vid} missing name"
                ok, err = _check_file_list(v.get("files", []), vid)
                if not ok:
                    return False, err
    return True, ""


def _collect_ids(paths: list[str]) -> set[str]:
    ids: set[str] = set()
    for p in paths:
        try:
            obj = _load_json(p)
        except Exception:
            continue
        pid = obj.get("id")
        if isinstance(pid, str):
            ids.add(pid)
        for grp in obj.get("variant_groups") or []:
            for v in grp.get("variants") or []:
                vid = v.get("id")
                if isinstance(vid, str):
                    ids.add(vid)
    return ids


def _ingest_preset(
    obj: dict,
    presets: dict,
    files: dict,
    seen: set[str],
) -> None:
    pid = obj["id"]
    seen.add(pid)
    meta: dict[str, Any] = {
        k: obj[k] for k in ("name", "description", "category", "size", "time") if k in obj
    }
    if obj.get("video_guide"):
        meta["video_guide"] = obj["video_guide"]
    if obj.get("source"):
        meta["source"] = obj["source"]

    if obj.get("variant_groups"):
        meta["has_variants"] = True
        vg: dict[str, dict] = {}
        for grp in obj["variant_groups"]:
            group_name = grp["group"]
            vg[group_name] = {}
            for v in grp["variants"]:
                vid = v["id"]
                seen.add(vid)
                vg[group_name][vid] = {k: v[k] for k in ("name", "size", "time") if k in v}
                files[vid] = _files_to_tuples(v.get("files", []))
        meta["variant_groups"] = vg
    else:
        files[pid] = _files_to_tuples(obj.get("files", []))
    presets[pid] = meta


def load_presets(*, log_skips: bool = True) -> tuple[dict, dict, dict]:
    """Returns (PRESETS, PRESET_FILES, PRESET_CATEGORIES) in legacy format."""
    categories = load_categories()

    presets: dict = {}
    files: dict = {}
    seen: set[str] = set()

    builtin_paths = sorted(glob.glob(os.path.join(BUILTIN_DIR, "*.json")))
    community_paths = sorted(glob.glob(os.path.join(COMMUNITY_DIR, "*.json")))

    for p in builtin_paths + community_paths:
        basename = os.path.basename(p)
        try:
            obj = _load_json(p)
            ok, err = validate_preset(obj, categories, seen)
            if not ok:
                if log_skips:
                    print(f"[presets] skip {basename}: {err}")
                continue
            _ingest_preset(obj, presets, files, seen)
        except Exception as exc:
            if log_skips:
                print(f"[presets] bad json {basename}: {exc}")

    return presets, files, categories


def _safe_preset_id(pid: str) -> str | None:
    pid = (pid or "").strip()
    return pid if _ID_RE.fullmatch(pid) else None


def _community_preset_path(pid: str) -> str | None:
    pid = _safe_preset_id(pid)
    if not pid:
        return None
    path = os.path.join(COMMUNITY_DIR, f"{pid}.json")
    real_root = os.path.realpath(COMMUNITY_DIR)
    real_path = os.path.realpath(path)
    if not (real_path == real_root or real_path.startswith(real_root + os.sep)):
        return None
    return path


def is_community_preset_id(pid: str) -> bool:
    path = _community_preset_path(pid)
    return bool(path and os.path.isfile(path))


def _count_preset_files(obj: dict) -> int:
    if obj.get("files"):
        return len(obj["files"])
    total = 0
    for grp in obj.get("variant_groups") or []:
        for v in grp.get("variants") or []:
            total += len(v.get("files") or [])
    return total


def list_community_presets() -> list[dict]:
    os.makedirs(COMMUNITY_DIR, exist_ok=True)
    items: list[dict] = []
    for path in sorted(glob.glob(os.path.join(COMMUNITY_DIR, "*.json"))):
        try:
            obj = _load_json(path)
        except Exception:
            continue
        pid = obj.get("id")
        if not isinstance(pid, str):
            continue
        items.append({
            "id": pid,
            "name": obj.get("name", pid),
            "category": obj.get("category", ""),
            "description": obj.get("description", ""),
            "file_count": _count_preset_files(obj),
            "has_variants": bool(obj.get("variant_groups")),
        })
    return items


def get_community_preset_raw(pid: str) -> dict | None:
    path = _community_preset_path(pid)
    if not path or not os.path.isfile(path):
        return None
    try:
        return _load_json(path)
    except Exception:
        return None


def delete_community_preset(pid: str) -> tuple[bool, str]:
    if is_builtin_preset_id(pid):
        return False, "Нельзя удалить встроенный пресет"
    path = _community_preset_path(pid)
    if not path or not os.path.isfile(path):
        return False, "Пресет не найден"
    try:
        os.remove(path)
        return True, pid
    except OSError as exc:
        return False, str(exc)


def save_community_preset(obj: dict) -> tuple[bool, str]:
    """Validate and write preset JSON to community dir. Returns (ok, id_or_error)."""
    obj = _ensure_category_from_import(obj)
    categories = load_categories()
    builtin_ids = _collect_ids(sorted(glob.glob(os.path.join(BUILTIN_DIR, "*.json"))))
    ok, err = validate_preset(obj, categories, seen=builtin_ids)
    if not ok:
        return False, err
    pid = _safe_preset_id(obj.get("id", ""))
    if not pid:
        return False, "Недопустимый id пресета"
    if pid in builtin_ids:
        return False, f"Id {pid} зарезервирован встроенным пресетом"
    os.makedirs(COMMUNITY_DIR, exist_ok=True)
    path = os.path.join(COMMUNITY_DIR, f"{pid}.json")
    obj = dict(obj)
    obj["source"] = "community"
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)
    return True, pid


def export_preset_to_json(
    preset_id: str,
    meta: dict,
    preset_files: dict,
) -> dict:
    """Convert legacy dict entry to manifest JSON object."""
    obj: dict[str, Any] = {
        "schema": 1,
        "id": preset_id,
        "name": meta["name"],
        "description": meta.get("description", ""),
        "category": meta["category"],
        "size": meta.get("size", ""),
        "time": meta.get("time", ""),
    }
    cats = load_categories()
    cat = meta["category"]
    if cat in cats:
        obj["category_meta"] = cats[cat]
    if meta.get("video_guide"):
        obj["video_guide"] = meta["video_guide"]
    if meta.get("has_variants") and meta.get("variant_groups"):
        groups = []
        for group_name, variants in meta["variant_groups"].items():
            items = []
            for vid, vmeta in variants.items():
                items.append({
                    "id": vid,
                    "name": vmeta["name"],
                    "size": vmeta.get("size", ""),
                    "time": vmeta.get("time", ""),
                    "files": _tuples_to_files(preset_files.get(vid, [])),
                })
            groups.append({"group": group_name, "variants": items})
        obj["variant_groups"] = groups
    else:
        obj["files"] = _tuples_to_files(preset_files.get(preset_id, []))
    return obj
