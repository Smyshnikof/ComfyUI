"""Custom nodes installer service — git clone presets + ComfyUI restart."""
from __future__ import annotations

import html
import json
import os
import re
import threading
import uuid
from collections import OrderedDict
from urllib.parse import urlparse

import requests
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from services._config import (
    COMFYUI_PORT,
    CUSTOM_NODES_ROOT,
    HUB_PORT,
    HOST,
    LOGS_DIR,
    NODE_PRESETS_COMMUNITY_DIR,
    ensure_dirs,
)
from services._manager_config import get_manager_security, set_manager_security
from services._node_installer import git_available, install_repo, is_repo_installed
from services._node_presets import (
    ALLOWED_IMPORT_HOSTS,
    decode_preset_share_code,
    delete_community_preset,
    encode_preset_share_code,
    ensure_community_category,
    export_preset_to_json,
    get_community_preset_raw,
    is_builtin_preset_id,
    is_community_preset_id,
    list_community_presets,
    load_presets,
    repo_folder_name,
    save_community_preset,
    slug_id,
    unique_community_id,
)

ensure_dirs()

PRESETS, PRESET_REPOS, PRESET_CATEGORIES = load_presets()

install_status: OrderedDict = OrderedDict()
MAX_INSTALL_TASKS = 50

app = FastAPI(title="Custom Nodes Installer")

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

_LOG_ERROR_PATTERNS = (
    "IMPORT FAILED",
    "Error while calling configure",
    "ModuleNotFoundError",
    "cannot import name",
    "No module named",
)


def reload_presets_data() -> None:
    global PRESETS, PRESET_REPOS, PRESET_CATEGORIES
    PRESETS, PRESET_REPOS, PRESET_CATEGORIES = load_presets()


def _trim_tasks() -> None:
    while len(install_status) > MAX_INSTALL_TASKS:
        install_status.popitem(last=False)


def _collect_preset_repos(preset_ids: list[str]) -> list[tuple[str, str | None, bool, str | None]]:
    items: list[tuple[str, str | None, bool, str | None]] = []
    seen: set[str] = set()
    for pid in preset_ids:
        for entry in PRESET_REPOS.get(pid, []):
            url = entry[0]
            key = url.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            items.append(entry)
    return items


def _preset_install_state(preset_id: str) -> dict:
    repos = PRESET_REPOS.get(preset_id, [])
    have = sum(1 for url, _b, _r, folder in repos if is_repo_installed(url, folder))
    total = len(repos)
    if total > 0 and have == total:
        state = "full"
    elif have > 0:
        state = "partial"
    else:
        state = "none"
    return {"have": have, "total": total, "state": state}


def _fetch_object_info() -> dict | None:
    try:
        resp = requests.get(f"http://127.0.0.1:{COMFYUI_PORT}/object_info", timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            return data if isinstance(data, dict) else None
    except Exception:
        pass
    return None


def _read_comfyui_log_tail(lines: int = 200) -> list[str]:
    log_path = os.path.join(str(LOGS_DIR), "comfyui.log")
    if not os.path.isfile(log_path):
        return []
    try:
        with open(log_path, encoding="utf-8", errors="replace") as handle:
            content = handle.readlines()
        return [ln.rstrip("\n") for ln in content[-lines:]]
    except OSError:
        return []


def _parse_log_errors() -> list[str]:
    errors: list[str] = []
    for line in _read_comfyui_log_tail():
        if any(pat in line for pat in _LOG_ERROR_PATTERNS):
            errors.append(line.strip()[:300])
    return errors[-20:]


def _check_nodes_for_preset(preset_id: str, object_info: dict | None) -> dict:
    meta = PRESETS.get(preset_id, {})
    check_nodes = meta.get("check_nodes") or []
    result = {"preset_id": preset_id, "check_nodes": check_nodes, "nodes_ok": None, "missing": []}
    if not check_nodes:
        result["nodes_ok"] = None
        return result
    if not object_info:
        result["nodes_ok"] = False
        result["missing"] = list(check_nodes)
        return result
    missing = [n for n in check_nodes if n not in object_info]
    result["missing"] = missing
    result["nodes_ok"] = len(missing) == 0
    return result


def _restart_comfyui() -> tuple[bool, str]:
    try:
        resp = requests.post(
            f"http://127.0.0.1:{HUB_PORT}/api/services/comfyui/restart",
            timeout=120,
        )
        data = resp.json() if resp.content else {}
        if resp.status_code == 200 and data.get("success", True):
            return True, data.get("message", "ComfyUI перезапущен")
        return False, data.get("message", f"HTTP {resp.status_code}")
    except Exception as exc:
        return False, str(exc)


def generate_category_filters_html() -> str:
    html_out = '''
        <div class="category-filter all active" onclick="filterByCategory('all', event)" data-category="all">
          <span>📦</span>
          <span>Все</span>
        </div>
        '''
    for category_id, category_info in PRESET_CATEGORIES.items():
        html_out += f'''
        <div class="category-filter" onclick="filterByCategory('{category_id}', event)" data-category="{category_id}">
          <span>{category_info.get("icon", "🔌")}</span>
          <span>{category_info.get("name", category_id)}</span>
        </div>
        '''
    return html_out


def _repo_count_html(preset_id: str) -> str:
    count = len(PRESET_REPOS.get(preset_id, []))
    if count <= 0:
        return ""
    return f'<div class="preset-info">Репозиториев: {count}</div>'


def _preset_actions_html(preset_id: str, is_community: bool = False) -> str:
    code_btn = ""
    if is_community:
        code_btn = (
            f'<button type="button" class="preset-action-btn" '
            f'onclick="copyPresetCode(\'{preset_id}\', event)">📋 Код набора</button>'
        )
    return f'''
              <div class="preset-card-footer" onclick="event.stopPropagation();">
                <button type="button" class="preset-action-btn" onclick="downloadPresetFile('{preset_id}', event)">💾 Скачать .json</button>
                {code_btn}
              </div>'''


def generate_presets_html() -> str:
    html_out = ""
    for preset_id, preset_info in PRESETS.items():
        category = preset_info.get("category", "Essentials")
        community_badge = ""
        if preset_info.get("source") == "community":
            community_badge = '<span class="preset-community-badge">community</span>'
        is_community = preset_info.get("source") == "community"
        actions_html = _preset_actions_html(preset_id, is_community)
        info_html = _repo_count_html(preset_id)

        if preset_info.get("has_variants") and preset_info.get("variant_groups"):
            variants_html = ""
            for group_name, variants in preset_info["variant_groups"].items():
                group_html = f'<div class="preset-variant-group-title">{group_name}</div>'
                for variant_id, variant_info in variants.items():
                    group_html += f'''
                    <div class="preset-variant-item" onclick="event.stopPropagation();">
                      <input type="checkbox" id="variant-{variant_id}" data-variant="{variant_id}" data-parent="{preset_id}" onchange="toggleVariant('{preset_id}', '{variant_id}')">
                      <label for="variant-{variant_id}" class="preset-variant-label">
                        <strong>{variant_info["name"]}</strong>
                      </label>
                    </div>
                    '''
                variants_html += f'<div class="preset-variant-group">{group_html}</div>'

            expand_html = f'<span class="preset-expand-icon" onclick="event.stopPropagation(); togglePresetCard(\'{preset_id}\', event)">▼</span>'
            html_out += f'''
            <div class="preset-card" data-preset="{preset_id}" data-category="{category}" onclick="togglePresetCard('{preset_id}', event)">
              <div class="preset-card-top">
                <div class="preset-install-slot"></div>
                <div class="preset-card-top-right">{expand_html}</div>
              </div>
              <div class="preset-name">{preset_info["name"]}{community_badge}</div>
              <div class="preset-desc">{preset_info.get("description", "")}</div>
              {info_html}
              <div class="preset-variants">
                <div style="font-size: 12px; color: var(--muted); margin-bottom: 12px;">Выберите вариант:</div>
                {variants_html}
              </div>
              {actions_html}
            </div>
            '''
        else:
            html_out += f'''
            <div class="preset-card" data-preset="{preset_id}" data-category="{category}" onclick="togglePreset('{preset_id}')">
              <div class="preset-card-top"><div class="preset-install-slot"></div></div>
              <div class="preset-name">{preset_info["name"]}{community_badge}</div>
              <div class="preset-desc">{preset_info.get("description", "")}</div>
              {info_html}
              {actions_html}
            </div>
            '''
    return html_out


def _run_install_task(
    task_id: str,
    repos: list[tuple[str, str | None, bool, str | None]],
    *,
    force: bool = False,
    auto_restart: bool = False,
    label: str = "",
) -> None:
    total = len(repos)
    installed: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []

    try:
        for idx, (url, branch, recursive, folder) in enumerate(repos, 1):
            folder_name = repo_folder_name(url, folder)
            install_status[task_id] = {
                "status": "running",
                "source": "nodes",
                "message": f"📦 {idx}/{total}: {folder_name}",
                "progress": ((idx - 1) / max(total, 1)) * 100,
                "current_repo": folder_name,
                "total_repos": total,
                "current_index": idx,
            }

            if not force and is_repo_installed(url, folder):
                skipped.append(folder_name)
                continue

            def on_log(msg: str) -> None:
                install_status[task_id]["log_tail"] = msg[-500:]

            ok, _fname, msg = install_repo(
                url,
                branch=branch,
                recursive=recursive,
                folder=folder,
                force=force,
                on_log=on_log,
            )
            if ok:
                installed.append(folder_name)
            else:
                failed.append(f"{folder_name}: {msg[:200]}")

        summary = [f"✅ Установка завершена{': ' + label if label else ''}", ""]
        if installed:
            summary.append(f"📥 Установлено/обновлено: {len(installed)}")
            summary.extend(f"   ✅ {n}" for n in installed[:15])
            if len(installed) > 15:
                summary.append(f"   ... и ещё {len(installed) - 15}")
            summary.append("")
        if skipped:
            summary.append(f"⏭️ Уже установлено: {len(skipped)}")
            summary.append("")
        if failed:
            summary.append(f"❌ Ошибки: {len(failed)}")
            summary.extend(f"   ❌ {n}" for n in failed)

        restart_msg = ""
        if auto_restart and not failed:
            ok, restart_msg = _restart_comfyui()
            summary.append("")
            summary.append(f"{'✅' if ok else '❌'} {restart_msg}")

        install_status[task_id] = {
            "status": "error" if failed else "completed",
            "source": "nodes",
            "message": "\n".join(summary),
            "progress": 100,
            "total_repos": total,
            "installed": installed,
            "failed": failed,
            "restart": restart_msg,
        }
    except Exception as exc:
        install_status[task_id] = {
            "status": "error",
            "source": "nodes",
            "message": f"❌ Ошибка: {exc}",
            "progress": 100,
        }


_GITHUB_URL_RE = re.compile(
    r"^https://github\.com/[\w.\-]+/[\w.\-]+(?:\.git)?/?$",
    re.IGNORECASE,
)


def _validate_repo_url(url: str) -> str | None:
    url = url.strip()
    if not _GITHUB_URL_RE.match(url):
        return "Ссылка должна быть https://github.com/user/repo"
    return None


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "git": git_available(),
        "custom_nodes_root": str(CUSTOM_NODES_ROOT),
        "presets": len(PRESETS),
    }


@app.get("/installed")
def installed():
    return {preset_id: _preset_install_state(preset_id) for preset_id in PRESET_REPOS}


@app.get("/api/form-meta")
def form_meta():
    return {
        "categories": [
            {"id": k, "name": v.get("name", k), "icon": v.get("icon", "")}
            for k, v in PRESET_CATEGORIES.items()
        ],
    }


@app.post("/reload_presets")
def reload_presets_endpoint():
    reload_presets_data()
    return {"ok": True, "count": len(PRESETS)}


def _manifest_obj_for(pid: str) -> dict | None:
    if pid not in PRESETS:
        return None
    return export_preset_to_json(pid, PRESETS[pid], PRESET_REPOS)


@app.get("/api/community-presets")
def api_community_presets_list():
    return {"presets": list_community_presets()}


@app.get("/api/community-presets/{pid}")
def api_community_preset_get(pid: str):
    obj = get_community_preset_raw(pid)
    if not obj:
        return JSONResponse({"ok": False, "message": "Пресет не найден"}, status_code=404)
    return {"ok": True, "preset": obj}


@app.delete("/presets/community/{pid}")
def presets_community_delete(pid: str):
    ok, msg = delete_community_preset(pid)
    if ok:
        reload_presets_data()
        return {"ok": True, "message": "Пресет удалён", "id": msg}
    return JSONResponse({"ok": False, "message": msg})


@app.get("/api/presets/fragment")
def presets_fragment():
    community_count = sum(1 for p in PRESETS.values() if p.get("source") == "community")
    return {
        "presets_html": generate_presets_html(),
        "category_filters_html": generate_category_filters_html(),
        "count": len(PRESETS),
        "community_count": community_count,
    }


@app.get("/presets/export/{pid}")
def presets_export(pid: str):
    obj = _manifest_obj_for(pid)
    if not obj:
        return JSONResponse({"ok": False, "message": "Пресет не найден"}, status_code=404)
    body = json.dumps(obj, ensure_ascii=False, indent=2)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{pid}.json"'},
    )


@app.post("/presets/import_file")
async def presets_import_file(file: UploadFile = File(...)):
    raw = await file.read()
    if len(raw) > 256 * 1024:
        return JSONResponse({"ok": False, "message": "Файл слишком большой"})
    try:
        obj = json.loads(raw.decode("utf-8"))
    except Exception:
        return JSONResponse({"ok": False, "message": "Некорректный JSON"})
    ok, msg = save_community_preset(obj)
    if ok:
        reload_presets_data()
        return {"ok": True, "message": "Набор загружен", "id": msg}
    return JSONResponse({"ok": False, "message": msg})


@app.get("/presets/code/{pid}")
def presets_code(pid: str):
    obj = _manifest_obj_for(pid)
    if not obj:
        return JSONResponse({"ok": False, "message": "Пресет не найден"}, status_code=404)
    code = encode_preset_share_code(obj)
    if code is None:
        return JSONResponse({
            "ok": False,
            "kind": "too_large",
            "message": "Набор слишком большой для кода — скачайте .json",
        })
    kind = "ref" if code.startswith("CUNP1:ref:") else "compressed"
    return {"ok": True, "code": code, "kind": kind}


@app.post("/presets/import_code")
def presets_import_code(code: str = Form(...)):
    code = code.strip()
    if not code or len(code) > 350_000:
        return JSONResponse({"ok": False, "message": "Пустой или слишком длинный код"})
    try:
        kind, payload = decode_preset_share_code(code)
    except Exception:
        return JSONResponse({"ok": False, "message": "Битый код набора"})
    if kind == "ref":
        ref_id = payload
        if ref_id not in PRESETS:
            return JSONResponse({"ok": False, "message": f"Набор {ref_id} не найден"})
        name = PRESETS[ref_id].get("name", ref_id)
        if is_builtin_preset_id(ref_id):
            return JSONResponse({
                "ok": True,
                "message": f"«{name}» — встроенный набор, уже в списке",
                "id": ref_id,
            })
        obj = export_preset_to_json(ref_id, PRESETS[ref_id], PRESET_REPOS)
        ok, msg = save_community_preset(obj)
        if ok:
            reload_presets_data()
            return {"ok": True, "message": "Набор добавлен", "id": msg}
        return JSONResponse({"ok": False, "message": msg})
    ok, msg = save_community_preset(payload)
    if ok:
        reload_presets_data()
        return {"ok": True, "message": "Набор добавлен", "id": msg}
    return JSONResponse({"ok": False, "message": msg})


@app.post("/presets/import")
def presets_import(url: str = Form(...)):
    url = url.strip()
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if not url.startswith("https://") or host not in ALLOWED_IMPORT_HOSTS:
        return JSONResponse({"ok": False, "message": "Ссылка должна быть https с доверенного хоста"})
    try:
        resp = requests.get(url, timeout=20, headers={"User-Agent": "ComfyUI-node-preset-import/1.0"})
        resp.raise_for_status()
        if len(resp.content) > 256 * 1024:
            return JSONResponse({"ok": False, "message": "Файл слишком большой"})
        obj = resp.json()
    except Exception as exc:
        return JSONResponse({"ok": False, "message": f"Не удалось загрузить JSON: {exc}"})
    ok, msg = save_community_preset(obj)
    if ok:
        reload_presets_data()
        return JSONResponse({"ok": True, "message": "Набор импортирован", "id": msg})
    return JSONResponse({"ok": False, "message": msg})


@app.post("/presets/create")
def presets_create(
    name: str = Form(...),
    category: str = Form(...),
    category_icon: str = Form(""),
    description: str = Form(""),
    repos_json: str = Form(...),
):
    return _save_preset_from_form(None, name, category, category_icon, description, repos_json)


@app.post("/presets/update")
def presets_update(
    preset_id: str = Form(...),
    name: str = Form(...),
    category: str = Form(...),
    category_icon: str = Form(""),
    description: str = Form(""),
    repos_json: str = Form(...),
):
    return _save_preset_from_form(preset_id.strip(), name, category, category_icon, description, repos_json)


def _save_preset_from_form(
    preset_id: str | None,
    name: str,
    category: str,
    category_icon: str,
    description: str,
    repos_json: str,
):
    try:
        repos = json.loads(repos_json)
    except Exception:
        return JSONResponse({"ok": False, "message": "Битый список репозиториев"})
    if not isinstance(repos, list) or not repos:
        return JSONResponse({"ok": False, "message": "Нужен хотя бы один репозиторий"})
    cat_id = ensure_community_category(category.strip(), category_icon.strip() or None)
    if not cat_id:
        return JSONResponse({"ok": False, "message": "Укажите категорию"})
    if preset_id:
        if not is_community_preset_id(preset_id):
            return JSONResponse({"ok": False, "message": "Можно редактировать только свои наборы"})
        pid = preset_id
    else:
        pid = unique_community_id(slug_id(name.strip()))
    obj = {
        "schema": 1,
        "id": pid,
        "name": name.strip(),
        "category": cat_id,
        "description": description.strip(),
        "repos": repos,
    }
    ok, msg = save_community_preset(obj)
    if ok:
        reload_presets_data()
        action = "обновлён" if preset_id else "добавлен"
        return JSONResponse({"ok": True, "message": f"Набор {action}", "id": msg})
    return JSONResponse({"ok": False, "message": msg})


@app.post("/install_presets")
def install_presets(
    presets: str = Form(...),
    force: str = Form("0"),
    auto_restart: str = Form("0"),
):
    if not git_available():
        return {"message": "❌ git не найден в PATH — установите Git"}

    preset_ids = [p.strip() for p in presets.split(",") if p.strip()]
    if not preset_ids:
        return {"message": "❌ Не выбрано ни одного набора"}

    repos = _collect_preset_repos(preset_ids)
    if not repos:
        return {"message": "❌ Нет репозиториев для установки"}

    task_id = str(uuid.uuid4())
    _trim_tasks()
    install_status[task_id] = {
        "status": "running",
        "source": "nodes",
        "message": "Запуск установки...",
        "progress": 0,
    }
    force_flag = force.strip().lower() in ("1", "true", "yes")
    restart_flag = auto_restart.strip().lower() in ("1", "true", "yes")
    label = ", ".join(preset_ids)

    thread = threading.Thread(
        target=_run_install_task,
        args=(task_id, repos),
        kwargs={"force": force_flag, "auto_restart": restart_flag, "label": label},
        daemon=True,
    )
    thread.start()
    return {"task_id": task_id, "message": f"Установка {len(repos)} репозиториев..."}


@app.post("/install_repo")
def install_single_repo(
    url: str = Form(...),
    force: str = Form("0"),
    auto_restart: str = Form("0"),
):
    if not git_available():
        return {"message": "❌ git не найден в PATH — установите Git"}
    err = _validate_repo_url(url)
    if err:
        return {"message": f"❌ {err}"}

    task_id = str(uuid.uuid4())
    _trim_tasks()
    install_status[task_id] = {
        "status": "running",
        "source": "nodes",
        "message": "Запуск установки...",
        "progress": 0,
    }
    force_flag = force.strip().lower() in ("1", "true", "yes")
    restart_flag = auto_restart.strip().lower() in ("1", "true", "yes")
    repos = [(url.strip(), None, True, None)]

    thread = threading.Thread(
        target=_run_install_task,
        args=(task_id, repos),
        kwargs={"force": force_flag, "auto_restart": restart_flag, "label": url.strip()},
        daemon=True,
    )
    thread.start()
    return {"task_id": task_id, "message": "Установка репозитория..."}


@app.post("/restart_comfyui")
def restart_comfyui_endpoint():
    ok, msg = _restart_comfyui()
    if ok:
        return {"ok": True, "message": msg}
    return JSONResponse({"ok": False, "message": msg}, status_code=500)


@app.get("/api/validate")
def validate_nodes(presets: str = ""):
    preset_ids = [p.strip() for p in presets.split(",") if p.strip()] if presets else list(PRESET_REPOS.keys())
    object_info = _fetch_object_info()
    log_errors = _parse_log_errors()
    comfyui_running = object_info is not None

    results = []
    for pid in preset_ids:
        if pid not in PRESET_REPOS:
            continue
        state = _preset_install_state(pid)
        node_check = _check_nodes_for_preset(pid, object_info)
        repos_detail = []
        for url, _b, _r, folder in PRESET_REPOS.get(pid, []):
            fname = repo_folder_name(url, folder)
            repos_detail.append({
                "url": url,
                "folder": fname,
                "installed": is_repo_installed(url, folder),
            })
        results.append({
            "preset_id": pid,
            "name": PRESETS.get(pid, {}).get("name", pid),
            "install": state,
            "repos": repos_detail,
            "nodes_ok": node_check.get("nodes_ok"),
            "missing_nodes": node_check.get("missing", []),
        })

    return {
        "comfyui_running": comfyui_running,
        "log_errors": log_errors,
        "presets": results,
    }


@app.get("/status/{task_id}")
def get_status(task_id: str):
    if task_id not in install_status:
        return {"status": "not_found", "message": "Задача не найдена"}
    return install_status[task_id]


@app.get("/api/tasks")
def get_all_tasks():
    _trim_tasks()
    tasks = [{"task_id": tid, **status} for tid, status in install_status.items()]

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
    return {"tasks": tasks[:20]}


@app.get("/api/manager-config")
def manager_config_get():
    """Current ComfyUI-Manager security_level from user/__manager/config.ini."""
    data = get_manager_security()
    return {"ok": True, **data}


@app.post("/api/manager-config/security-level")
def manager_config_set_security(level: str = Form(...)):
    """Set security_level (e.g. weak) in ComfyUI-Manager config.ini."""
    ok, message, details = set_manager_security(level)
    if ok:
        return {"ok": True, "message": message, **details}
    return JSONResponse({"ok": False, "message": message}, status_code=400)


INDEX_HTML = """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Установщик Custom Nodes</title>
  <link rel="stylesheet" href="/static/nodes_styles.css?v={{ static_version }}" />
</head>
<body>
  <div class="wrap">
    <h1 class="title">🔌 Custom Nodes</h1>
    <p class="subtitle">Git clone наборов нод · <span class="mono">{{ custom_nodes_root }}</span></p>
    <div id="git-warning" class="banner banner-warn" hidden>⚠️ Git не найден в PATH — установите <a href="https://git-scm.com/download/win" target="_blank">Git</a></div>
    <div id="presets-empty-warning" class="banner banner-warn" hidden>⚠️ Встроенные наборы не загрузились (presets: 0). Пересоберите Docker-образ с <span class="mono">COPY node_presets</span> или импортируйте набор через «Свои наборы».</div>

    <div class="manager-compact" id="manager-config-card" title="">
      <span class="manager-title">🛡️ ComfyUI-Manager</span>
      <span class="manager-status">Текущий уровень: <b id="manager-security-level">—</b></span>
      <div class="seg-control" role="group" aria-label="security_level">
        <button type="button" class="seg" id="btn-security-weak" data-level="weak" onclick="setManagerSecurity('weak')">🔓 weak</button>
        <button type="button" class="seg" id="btn-security-normal" data-level="normal" onclick="setManagerSecurity('normal')">🔒 normal</button>
      </div>
    </div>

    <div class="tabs">
      <div class="tab active" data-tab="bundles" onclick="switchTab('bundles')">Наборы</div>
      <div class="tab" data-tab="single" onclick="switchTab('single')">Одна нода</div>
    </div>

    <div id="tab-bundles" class="tab-content active">
      <div class="toolbar">
        <button class="btn btn-install" type="button" onclick="installSelected()">📥 Установить выбранное</button>
        <label class="chk-restart" title="Перезагрузить ComfyUI автоматически, когда установка нод завершится">
          <input type="checkbox" id="install-restart" />
          <span>↻ перезапустить ComfyUI после установки</span>
        </label>
        <span class="toolbar-sep" aria-hidden="true"></span>
        <button class="btn" type="button" onclick="restartComfyUI()" title="Перезапустить ComfyUI прямо сейчас">↻ Перезапустить</button>
        <button class="btn" type="button" onclick="validateNodes()">✅ Проверить ноды</button>
        <button class="btn" type="button" onclick="openCommunityModal()">📁 Свои наборы<span id="community-badge" class="badge-count{{ community_badge_hidden }}">{{ community_count }}</span></button>
      </div>

      <div class="search-container">
        <span class="search-icon">🔍</span>
        <input type="text" class="search-input" id="search-input" placeholder="Поиск наборов..." oninput="filterPresets()" />
      </div>

      <div class="category-filters" id="category-filters">
        {{ category_filters_html }}
      </div>

      <div class="preset-grid" id="preset-grid">
        {{ presets_html }}
      </div>
    </div>

    <div id="tab-single" class="tab-content">
      <div class="card">
        <div class="hint">Вставьте ссылку на GitHub-репозиторий custom node (как в ComfyUI Manager).</div>
        <form id="single-repo-form" onsubmit="installSingleRepo(event)">
          <div class="row-full">
            <input type="text" id="repo-url" name="url" placeholder="https://github.com/author/ComfyUI-SomeNode.git" required />
          </div>
          <div class="row-actions">
            <button type="submit" class="btn btn-install">📥 Установить</button>
            <label class="chk-restart" title="Перезагрузить ComfyUI после установки репозитория">
              <input type="checkbox" id="single-restart" />
              <span>↻ перезапустить ComfyUI после установки</span>
            </label>
          </div>
        </form>
        <div class="result" id="single-result"></div>
      </div>
    </div>

    <div class="result" id="validate-result"></div>
  </div>

  <div id="preset-progress" class="preset-progress hidden">
    <div class="preset-progress-bar"><div class="preset-progress-fill" id="progress-fill"></div></div>
    <div class="preset-progress-text" id="progress-text">Установка...</div>
  </div>

  <div id="community-modal" class="modal hidden">
    <div class="modal-backdrop" onclick="closeCommunityModal()"></div>
    <div class="modal-panel">
      <div class="modal-header">
        <h2>Свои наборы</h2>
        <button class="modal-close" onclick="closeCommunityModal()">×</button>
      </div>
      <div class="modal-body" id="community-modal-body">
        <p class="muted">Загрузка...</p>
      </div>
    </div>
  </div>

  <script src="/static/nodes_script.js?v={{ static_version }}"></script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index():
    presets_html = generate_presets_html()
    category_filters_html = generate_category_filters_html()
    community_count = sum(1 for p in PRESETS.values() if p.get("source") == "community")
    community_badge_hidden = "" if community_count else " hidden"
    try:
        css_mtime = os.path.getmtime(os.path.join(static_dir, "nodes_styles.css"))
        js_mtime = os.path.getmtime(os.path.join(static_dir, "nodes_script.js"))
        static_version = str(int(max(css_mtime, js_mtime)))
    except OSError:
        static_version = "1"
    page = (
        INDEX_HTML
        .replace("{{ presets_html }}", presets_html)
        .replace("{{ category_filters_html }}", category_filters_html)
        .replace("{{ community_count }}", str(community_count))
        .replace("{{ community_badge_hidden }}", community_badge_hidden)
        .replace("{{ custom_nodes_root }}", html.escape(str(CUSTOM_NODES_ROOT)))
        .replace("{{ static_version }}", static_version)
    )
    return HTMLResponse(page)
