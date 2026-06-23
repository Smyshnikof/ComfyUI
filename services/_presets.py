"""Load preset manifests (builtin + community) into PRESETS / PRESET_FILES / PRESET_CATEGORIES."""
from __future__ import annotations

import glob
import json
import os
import re
from typing import Any
from urllib.parse import urlparse

_SERVICES_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_SERVICES_DIR, ".."))

BUILTIN_DIR = os.path.join(_REPO_ROOT, "presets", "manifest")
COMMUNITY_DIR = os.environ.get("COMMUNITY_PRESETS_DIR", "/workspace/presets/community")
CATEGORIES_FILE = os.path.join(_REPO_ROOT, "presets", "categories.json")

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

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


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
    categories: dict = {}
    if os.path.isfile(CATEGORIES_FILE):
        categories = _load_json(CATEGORIES_FILE)

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


def save_community_preset(obj: dict) -> tuple[bool, str]:
    """Validate and write preset JSON to community dir. Returns (ok, id_or_error)."""
    categories = _load_json(CATEGORIES_FILE) if os.path.isfile(CATEGORIES_FILE) else {}
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
