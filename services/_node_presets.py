"""Load custom node preset manifests (builtin + community)."""
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

from services._config import NODE_PRESETS_CATEGORIES_FILE, NODE_PRESETS_COMMUNITY_DIR, REPO_ROOT

BUILTIN_DIR = os.path.join(REPO_ROOT, "node_presets", "manifest")
CATEGORIES_FILE = os.path.join(REPO_ROOT, "node_presets", "categories.json")
COMMUNITY_DIR = str(NODE_PRESETS_COMMUNITY_DIR)
COMMUNITY_CATEGORIES_FILE = str(NODE_PRESETS_CATEGORIES_FILE)
_DEFAULT_CAT_ICON = "🔌"
_DEFAULT_CAT_COLOR = "#9ca3af"

ALLOWED_REPO_HOSTS = frozenset({"github.com"})
ALLOWED_IMPORT_HOSTS = frozenset({
    "raw.githubusercontent.com",
    "gist.githubusercontent.com",
    "github.com",
})

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

SHARE_REF_PREFIX = "CUNP1:ref:"
SHARE_Z_PREFIX = "CUNP1:z:"
MAX_SHARE_CODE_CHARS = 2500

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def repo_folder_name(url: str, folder: str | None = None) -> str:
    if folder:
        return folder.strip().rstrip("/\\")
    path = urlparse(url).path.rstrip("/")
    name = path.split("/")[-1] if path else "repo"
    if name.endswith(".git"):
        name = name[:-4]
    return name or "repo"


def repo_entry(url: str, *, branch: str | None = None, recursive: bool = True, folder: str | None = None) -> dict:
    return {
        "url": url.strip(),
        "branch": branch,
        "recursive": recursive,
        "folder": folder,
    }


def is_builtin_preset_id(pid: str) -> bool:
    return pid in _collect_ids(sorted(glob.glob(os.path.join(BUILTIN_DIR, "*.json"))))


def encode_preset_share_code(obj: dict) -> str | None:
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
    return s or "nodes"


def unique_community_id(base: str) -> str:
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


def _repos_to_tuples(repos: list[dict]) -> list[tuple[str, str | None, bool, str | None]]:
    out: list[tuple[str, str | None, bool, str | None]] = []
    for repo in repos or []:
        out.append((
            repo["url"],
            repo.get("branch"),
            bool(repo.get("recursive", True)),
            repo.get("folder"),
        ))
    return out


def _tuples_to_repos(entries: list[tuple[str, str | None, bool, str | None]]) -> list[dict]:
    return [
        {
            "url": url,
            "branch": branch,
            "recursive": recursive,
            "folder": folder,
        }
        for url, branch, recursive, folder in entries
    ]


def _url_host_ok(url: str) -> bool:
    if not url.startswith("https://"):
        return False
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host in ALLOWED_REPO_HOSTS


def _check_repo_list(repos: list, ctx: str) -> tuple[bool, str]:
    if not isinstance(repos, list) or not repos:
        return False, f"{ctx}: repos must be a non-empty list"
    for repo in repos:
        if not isinstance(repo, dict):
            return False, f"{ctx}: bad repo entry"
        url = repo.get("url")
        if not isinstance(url, str) or not _url_host_ok(url):
            return False, f"{ctx}: invalid url {url!r}"
        folder = repo.get("folder")
        if folder is not None and (not isinstance(folder, str) or ".." in folder or "/" in folder or "\\" in folder):
            return False, f"{ctx}: invalid folder {folder!r}"
        branch = repo.get("branch")
        if branch is not None and not isinstance(branch, str):
            return False, f"{ctx}: invalid branch"
    return True, ""


def validate_preset(
    obj: dict,
    categories: dict,
    seen: set[str],
    *,
    strict_repos: bool = True,
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
    has_repos = bool(obj.get("repos"))
    has_variants = bool(obj.get("variant_groups"))
    if has_repos and has_variants:
        return False, "cannot have both repos and variant_groups"
    if not has_repos and not has_variants:
        return False, "need repos or variant_groups"

    check_nodes = obj.get("check_nodes")
    if check_nodes is not None:
        if not isinstance(check_nodes, list) or not all(isinstance(n, str) for n in check_nodes):
            return False, "check_nodes must be a list of strings"

    if has_repos:
        ok, err = _check_repo_list(obj["repos"], pid)
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
                ok, err = _check_repo_list(v.get("repos", []), vid)
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
    repos: dict,
    seen: set[str],
) -> None:
    pid = obj["id"]
    seen.add(pid)
    meta: dict[str, Any] = {
        k: obj[k] for k in ("name", "description", "category") if k in obj
    }
    if obj.get("check_nodes"):
        meta["check_nodes"] = list(obj["check_nodes"])
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
                vg[group_name][vid] = {k: v[k] for k in ("name",) if k in v}
                if v.get("check_nodes"):
                    vg[group_name][vid]["check_nodes"] = list(v["check_nodes"])
                repos[vid] = _repos_to_tuples(v.get("repos", []))
        meta["variant_groups"] = vg
    else:
        repos[pid] = _repos_to_tuples(obj.get("repos", []))
    presets[pid] = meta


def load_presets(*, log_skips: bool = True) -> tuple[dict, dict, dict]:
    """Returns (PRESETS, PRESET_REPOS, PRESET_CATEGORIES)."""
    categories = load_categories()
    presets: dict = {}
    repos: dict = {}
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
                    print(f"[node_presets] skip {basename}: {err}")
                continue
            _ingest_preset(obj, presets, repos, seen)
        except Exception as exc:
            if log_skips:
                print(f"[node_presets] bad json {basename}: {exc}")

    return presets, repos, categories


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


def _count_preset_repos(obj: dict) -> int:
    if obj.get("repos"):
        return len(obj["repos"])
    total = 0
    for grp in obj.get("variant_groups") or []:
        for v in grp.get("variants") or []:
            total += len(v.get("repos") or [])
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
            "repo_count": _count_preset_repos(obj),
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
    preset_repos: dict,
) -> dict:
    obj: dict[str, Any] = {
        "schema": 1,
        "id": preset_id,
        "name": meta["name"],
        "description": meta.get("description", ""),
        "category": meta["category"],
    }
    cats = load_categories()
    cat = meta["category"]
    if cat in cats:
        obj["category_meta"] = cats[cat]
    if meta.get("check_nodes"):
        obj["check_nodes"] = meta["check_nodes"]
    if meta.get("has_variants") and meta.get("variant_groups"):
        groups = []
        for group_name, variants in meta["variant_groups"].items():
            items = []
            for vid, vmeta in variants.items():
                item: dict[str, Any] = {
                    "id": vid,
                    "name": vmeta["name"],
                    "repos": _tuples_to_repos(preset_repos.get(vid, [])),
                }
                if vmeta.get("check_nodes"):
                    item["check_nodes"] = vmeta["check_nodes"]
                items.append(item)
            groups.append({"group": group_name, "variants": items})
        obj["variant_groups"] = groups
    else:
        obj["repos"] = _tuples_to_repos(preset_repos.get(preset_id, []))
    return obj


def urls_from_txt(path: str) -> list[str]:
    urls: list[str] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    return urls
