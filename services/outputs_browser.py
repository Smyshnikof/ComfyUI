from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
import os
import json
from datetime import datetime

app = FastAPI(title="ComfyUI Outputs Gallery")

# Support both RunPod (/workspace) and Vast.ai (/opt/workspace-internal)
ROOT = os.environ.get("OUTPUT_ROOT") or (
    "/opt/workspace-internal/ComfyUI/output" if os.path.exists("/opt/workspace-internal") else "/workspace/ComfyUI/output"
)

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
VIDEO_EXT = {".mp4", ".webm", ".avi", ".mov", ".mkv"}


def safe_path(base: str, *parts: str) -> str:
    """Resolve path and ensure it stays under base."""
    full = os.path.normpath(os.path.join(base, *parts))
    if not full.startswith(os.path.normpath(base)):
        return base
    return full


def list_folders(root: str, rel_path: str = "") -> list[dict]:
    """List subfolders in path."""
    full = safe_path(root, rel_path) if rel_path else root
    if not os.path.isdir(full):
        return []
    out = []
    for name in sorted(os.listdir(full)):
        p = os.path.join(full, name)
        if os.path.isdir(p):
            rel = os.path.join(rel_path, name) if rel_path else name
            out.append({"name": name, "path": rel})
    return out


def list_files(root: str, rel_path: str = "", extensions: list[str] | None = None) -> list[dict]:
    """List files with metadata."""
    full = safe_path(root, rel_path) if rel_path else root
    if not os.path.isdir(full):
        return []
    out = []
    for name in sorted(os.listdir(full)):
        p = os.path.join(full, name)
        if not os.path.isfile(p):
            continue
        ext = os.path.splitext(name)[1].lower()
        if extensions and ext not in extensions:
            continue
        try:
            stat = os.stat(p)
            size = stat.st_size
            mtime = datetime.fromtimestamp(stat.st_mtime)
        except OSError:
            size = 0
            mtime = None
        rel = os.path.join(rel_path, name) if rel_path else name
        is_img = ext in IMAGE_EXT
        is_vid = ext in VIDEO_EXT
        out.append({
            "name": name,
            "path": rel,
            "size": size,
            "mtime": mtime.isoformat() if mtime else None,
            "ext": ext,
            "is_image": is_img,
            "is_video": is_vid,
        })
    return out


def get_tree(root: str, base_path: str = "") -> list[dict]:
    """Build folder tree for sidebar."""
    full = safe_path(root, base_path) if base_path else root
    if not os.path.isdir(full):
        return []
    items = []
    for name in sorted(os.listdir(full)):
        p = os.path.join(full, name)
        if os.path.isdir(p):
            rel = os.path.join(base_path, name) if base_path else name
            items.append({
                "name": name,
                "path": rel,
                "children": get_tree(root, rel),
            })
    return items


@app.get("/api/tree")
def api_tree():
    """Folder tree for sidebar."""
    os.makedirs(ROOT, exist_ok=True)
    return {"root": "Main", "children": get_tree(ROOT)}


@app.get("/api/folders")
def api_folders(path: str = Query("", alias="path")):
    """List subfolders in path."""
    return list_folders(ROOT, path)


@app.get("/api/files")
def api_files(
    path: str = Query("", alias="path"),
    ext: str = Query("", alias="ext"),  # comma-separated: png,mp4,webp
):
    """List files with metadata."""
    exts = [f".{e.strip().lower()}" for e in ext.split(",") if e.strip()] if ext else None
    return list_files(ROOT, path, exts)


@app.get("/api/workflow/{path:path}")
def api_workflow(path: str):
    """Extract workflow from PNG metadata (ComfyUI embeds it)."""
    full = safe_path(ROOT, path)
    if not os.path.isfile(full) or not full.lower().endswith(".png"):
        return JSONResponse({"error": "Not a PNG"}, status_code=400)
    try:
        from PIL import Image  # noqa: F401
        with Image.open(full) as img:
            if "workflow" in img.info:
                return json.loads(img.info["workflow"])
            if "prompt" in img.info:
                return {"prompt": json.loads(img.info["prompt"])}
    except Exception:
        pass
    return JSONResponse({"error": "No workflow in image"}, status_code=404)


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(_GALLERY_HTML)


@app.get("/file/{path:path}")
def get_file(path: str):
    full = safe_path(ROOT, path)
    if not os.path.isfile(full):
        return HTMLResponse("Not found", status_code=404)
    return FileResponse(full)


@app.get("/download-all")
def download_all():
    import tempfile
    import zipfile
    os.makedirs(ROOT, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tmp.close()
    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, _, filenames in os.walk(ROOT):
            for fn in filenames:
                p = os.path.join(dirpath, fn)
                rel = os.path.relpath(p, ROOT)
                z.write(p, arcname=rel)
    return FileResponse(tmp.name, filename="comfyui_outputs.zip")


_GALLERY_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ComfyUI Gallery</title>
  <style>
    :root {
      --bg: #1e1e1e;
      --card: #282828;
      --card-hover: #222;
      --border: #3a3a3a;
      --text: #ffffff;
      --muted: #9ca3af;
      --accent: #ffffff;
      --green: #22c55e;
      --red: #ef4444;
    }
    *, *::before, *::after { box-sizing: border-box; }
    html, body { margin: 0; padding: 0; background: var(--bg); color: var(--text);
      font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      font-size: 14px; line-height: 1.5; }
    .app { display: flex; min-height: 100vh; }
    .sidebar {
      width: 260px; min-width: 260px; background: var(--card); border-right: 1px solid var(--border);
      display: flex; flex-direction: column; overflow: hidden;
    }
    .sidebar-header { padding: 16px; border-bottom: 1px solid var(--border); }
    .sidebar-title { font-size: 18px; font-weight: 700; color: var(--accent); margin: 0; text-shadow: 0 0 10px rgba(255,255,255,0.3); }
    .sidebar-search { width: 100%; margin-top: 12px; padding: 8px 12px; background: #1a1a1a;
      border: 1px solid var(--border); border-radius: 8px; color: var(--text); }
    .sidebar-tree { flex: 1; overflow-y: auto; padding: 12px; }
    .tree-item { padding: 6px 10px; border-radius: 6px; cursor: pointer; display: flex; align-items: center;
      gap: 8px; color: var(--text); text-decoration: none; margin: 2px 0; }
    .tree-item:hover { background: var(--card-hover); }
    .tree-item.active { background: rgba(255,255,255,0.15); color: var(--accent); }
    .tree-item .icon { opacity: 0.6; }
    .tree-children { margin-left: 16px; }
    .main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
    .toolbar {
      display: flex; flex-wrap: wrap; align-items: center; gap: 12px; padding: 16px 20px;
      background: var(--card); border-bottom: 1px solid var(--border);
    }
    .breadcrumb { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
    .breadcrumb a, .breadcrumb span { color: var(--muted); text-decoration: none; }
    .breadcrumb a:hover { color: var(--accent); }
    .breadcrumb .sep { color: var(--border); }
    .toolbar-actions { display: flex; gap: 8px; margin-left: auto; }
    .btn {
      display: inline-flex; align-items: center; gap: 6px; padding: 8px 14px;
      background: rgba(255,255,255,0.1); border: 1px solid var(--border); border-radius: 8px; color: var(--text);
      cursor: pointer; font-size: 13px; transition: all 0.2s; text-decoration: none;
    }
    .btn:hover { background: rgba(255,255,255,0.15); border-color: var(--accent); }
    .btn-primary { background: rgba(255,255,255,0.95); color: #1e1e1e; font-weight: 700; border-color: rgba(255,255,255,0.5); }
    .btn-primary:hover { background: #fff; border-color: #fff; transform: translateY(-2px); box-shadow: 0 8px 20px rgba(0,0,0,0.2); }
    .filters { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
    .filter-input { padding: 6px 10px; background: #1a1a1a; border: 1px solid var(--border);
      border-radius: 6px; color: var(--text); width: 140px; }
    .filter-ext { display: flex; gap: 6px; flex-wrap: wrap; }
    .filter-ext label { display: flex; align-items: center; gap: 4px; cursor: pointer; }
    .gallery { flex: 1; overflow-y: auto; padding: 20px; }
    .gallery-grid {
      display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 16px; align-content: start;
    }
    .card {
      background: var(--card); border: 1px solid var(--border); border-radius: 12px;
      overflow: hidden; transition: all 0.2s;
    }
    .card:hover { border-color: var(--accent); box-shadow: 0 4px 20px rgba(255,255,255,0.1); }
    .card-preview {
      aspect-ratio: 1; background: #1a1a1a; display: flex; align-items: center; justify-content: center;
      overflow: hidden; position: relative;
    }
    .card-preview img, .card-preview video { width: 100%; height: 100%; object-fit: cover; }
    .card-preview .placeholder { color: var(--muted); font-size: 12px; padding: 20px; text-align: center; }
    .card-badge { position: absolute; top: 8px; left: 8px; padding: 4px 8px; background: var(--green);
      color: white; font-size: 10px; font-weight: 600; border-radius: 4px; }
    .card-duration { position: absolute; bottom: 8px; right: 8px; padding: 4px 8px;
      background: rgba(0,0,0,0.7); font-size: 11px; border-radius: 4px; }
    .card-info { padding: 12px; }
    .card-name { font-weight: 600; margin-bottom: 6px; word-break: break-all; font-size: 13px; }
    .card-meta { font-size: 11px; color: var(--muted); margin-bottom: 8px; }
    .card-actions { display: flex; gap: 8px; }
    .card-actions a, .card-actions button {
      padding: 6px 10px; border-radius: 6px; background: rgba(255,255,255,0.1); border: 1px solid var(--border); color: var(--text);
      text-decoration: none; font-size: 12px; cursor: pointer; display: inline-flex;
      align-items: center; gap: 4px; transition: all 0.2s;
    }
    .card-actions a:hover, .card-actions button:hover { background: rgba(255,255,255,0.15); border-color: var(--accent); }
    .empty { text-align: center; padding: 60px 20px; color: var(--muted); }
    .modal { position: fixed; inset: 0; background: rgba(0,0,0,0.9); z-index: 1000;
      display: flex; align-items: center; justify-content: center; padding: 20px; }
    .modal img, .modal video { max-width: 100%; max-height: 90vh; object-fit: contain; }
    .modal-close { position: absolute; top: 20px; right: 20px; background: var(--card); color: var(--text);
      border: 1px solid var(--border); padding: 10px 20px; border-radius: 8px; cursor: pointer; font-size: 16px; }
    .modal-close:hover { background: rgba(255,255,255,0.15); border-color: var(--accent); }
    .sidebar-toggle { display: none; padding: 10px; background: rgba(255,255,255,0.1); border: 1px solid var(--border);
      border-radius: 8px; color: var(--text); cursor: pointer; margin-right: 8px; }
    @media (max-width: 768px) {
      .sidebar { position: fixed; left: 0; top: 0; bottom: 0; z-index: 100; transform: translateX(-100%);
        transition: transform 0.2s; }
      .sidebar.open { transform: translateX(0); }
      .sidebar-toggle { display: inline-flex; }
      .gallery-grid { grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar" id="sidebar">
      <div class="sidebar-header">
        <h1 class="sidebar-title">ComfyUI Gallery</h1>
        <input type="text" class="sidebar-search" id="folderSearch" placeholder="Поиск папок...">
      </div>
      <div class="sidebar-tree" id="folderTree"></div>
    </aside>
    <main class="main">
      <div class="toolbar">
        <button class="sidebar-toggle" id="sidebarToggle" aria-label="Меню">☰</button>
        <div class="breadcrumb" id="breadcrumb">Main</div>
        <div class="toolbar-actions">
          <input type="text" class="filter-input" id="searchFiles" placeholder="Поиск файлов...">
          <div class="filter-ext">
            <label><input type="checkbox" data-ext=".png"> PNG</label>
            <label><input type="checkbox" data-ext=".webp"> WEBP</label>
            <label><input type="checkbox" data-ext=".mp4"> MP4</label>
            <label><input type="checkbox" data-ext=".webm"> WEBM</label>
          </div>
          <button class="btn btn-primary" onclick="refresh()">↻ Обновить</button>
          <a class="btn" href="/download-all">↓ ZIP</a>
        </div>
      </div>
      <div class="gallery">
        <div class="gallery-grid" id="gallery"></div>
        <div class="empty" id="empty" style="display:none">Нет файлов в этой папке</div>
      </div>
    </main>
  </div>
  <div class="modal" id="modal" style="display:none">
    <button class="modal-close" onclick="closeModal()">✕ Закрыть</button>
    <div id="modalContent"></div>
  </div>
  <script>
    let currentPath = '';
    let folderTreeData = [];

    async function fetchJson(url) {
      const r = await fetch(url);
      if (!r.ok) throw new Error(r.statusText);
      return r.json();
    }

    function formatSize(bytes) {
      if (bytes < 1024) return bytes + ' B';
      if (bytes < 1024*1024) return (bytes/1024).toFixed(1) + ' KB';
      return (bytes/(1024*1024)).toFixed(1) + ' MB';
    }

    function formatDate(iso) {
      if (!iso) return '';
      const d = new Date(iso);
      return d.toLocaleString('ru-RU', { day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit' });
    }

    function renderTree(items, parent = '') {
      let html = '';
      for (const item of items) {
        const path = parent ? parent + '/' + item.name : item.name;
        const hasChildren = item.children && item.children.length > 0;
        html += `<div class="tree-folder">
          <a class="tree-item ${currentPath === path ? 'active' : ''}" href="#" data-path="${path}">
            <span class="icon">${hasChildren ? '📁' : '📂'}</span>${item.name}
          </a>
          ${hasChildren ? `<div class="tree-children">${renderTree(item.children, path)}</div>` : ''}
        </div>`;
      }
      return html;
    }

    async function loadTree() {
      const data = await fetchJson('/api/tree');
      folderTreeData = data.children || [];
      document.getElementById('folderTree').innerHTML = renderTree(folderTreeData);
      document.querySelectorAll('.tree-item').forEach(el => {
        el.addEventListener('click', (e) => { e.preventDefault(); navigate(el.dataset.path); });
      });
      document.getElementById('folderSearch').oninput = (e) => {
        const q = e.target.value.toLowerCase();
        const filter = (items, parent) => items.filter(i => {
          const path = parent ? parent + '/' + i.name : i.name;
          const match = i.name.toLowerCase().includes(q);
          if (i.children) i.children = filter(i.children, path);
          return match || (i.children && i.children.length > 0);
        });
        document.getElementById('folderTree').innerHTML = renderTree(filter(JSON.parse(JSON.stringify(folderTreeData)), ''));
        document.querySelectorAll('.tree-item').forEach(el => {
          el.addEventListener('click', (e) => { e.preventDefault(); navigate(el.dataset.path); });
        });
      };
    }

    function buildBreadcrumb() {
      const parts = currentPath ? currentPath.split('/').filter(Boolean) : [];
      let html = '<a href="#" data-path="">Main</a>';
      let acc = '';
      for (const p of parts) {
        acc = acc ? acc + '/' + p : p;
        html += '<span class="sep">/</span><a href="#" data-path="' + acc + '">' + p + '</a>';
      }
      document.getElementById('breadcrumb').innerHTML = html;
      document.querySelectorAll('#breadcrumb a').forEach(a => {
        a.onclick = (e) => { e.preventDefault(); navigate(a.dataset.path); };
      });
    }

    function getExtFilter() {
      const checked = document.querySelectorAll('.filter-ext input:checked');
      if (checked.length === 0) return '';
      return Array.from(checked).map(c => c.dataset.ext.replace('.','')).join(',');
    }

    async function loadFiles() {
      const ext = getExtFilter();
      const url = '/api/files?path=' + encodeURIComponent(currentPath) + (ext ? '&ext=' + ext : '');
      const files = await fetchJson(url);
      const search = document.getElementById('searchFiles').value.toLowerCase();
      const filtered = search ? files.filter(f => f.name.toLowerCase().includes(search)) : files;

      const gallery = document.getElementById('gallery');
      const empty = document.getElementById('empty');
      gallery.innerHTML = '';

      if (filtered.length === 0) {
        empty.style.display = 'block';
        return;
      }
      empty.style.display = 'none';

      for (const f of filtered) {
        const card = document.createElement('div');
        card.className = 'card';
        let preview = '';
        if (f.is_image) {
          preview = `<img src="/file/${f.path}" alt="${f.name}" loading="lazy" onerror="this.parentElement.innerHTML='<span class=placeholder>Ошибка загрузки</span>'">`;
        } else if (f.is_video) {
          preview = `<video src="/file/${f.path}" preload="metadata" muted></video><span class="card-duration" data-duration></span>`;
        } else {
          preview = `<span class="placeholder">${f.ext || 'file'}</span>`;
        }
        const meta = [f.size ? formatSize(f.size) : '', formatDate(f.mtime)].filter(Boolean).join(' · ');
        card.innerHTML = `
          <div class="card-preview" onclick="openModal('${f.path}', ${f.is_video})">
            ${preview}
            ${f.is_image ? '<span class="card-badge">Image</span>' : ''}
          </div>
          <div class="card-info">
            <div class="card-name">${f.name}</div>
            <div class="card-meta">${meta}</div>
            <div class="card-actions">
              <a href="/file/${f.path}" download="${f.name}">↓</a>
              <a href="/file/${f.path}" target="_blank">↗</a>
            </div>
          </div>`;
        gallery.appendChild(card);

        if (f.is_video) {
          const v = card.querySelector('video');
          v.onloadedmetadata = () => {
            const d = card.querySelector('[data-duration]');
            if (d && !isNaN(v.duration)) d.textContent = new Date(v.duration*1000).toISOString().slice(14,19);
          };
        }
      }
    }

    function openModal(path, isVideo) {
      const modal = document.getElementById('modal');
      const content = document.getElementById('modalContent');
      content.innerHTML = isVideo
        ? `<video src="/file/${path}" controls autoplay></video>`
        : `<img src="/file/${path}" alt="">`;
      modal.style.display = 'flex';
    }

    function closeModal() {
      document.getElementById('modal').style.display = 'none';
      document.getElementById('modalContent').innerHTML = '';
    }

    function navigate(path) {
      currentPath = path;
      buildBreadcrumb();
      loadFiles();
      document.querySelectorAll('.tree-item').forEach(el => {
        el.classList.toggle('active', el.dataset.path === path);
      });
      document.getElementById('sidebar').classList.remove('open');
    }

    function refresh() {
      loadTree();
      loadFiles();
    }

    document.getElementById('sidebarToggle').onclick = () => {
      document.getElementById('sidebar').classList.toggle('open');
    };

    document.getElementById('searchFiles').oninput = () => loadFiles();
    document.querySelectorAll('.filter-ext input').forEach(c => {
      c.onchange = () => loadFiles();
    });

    document.getElementById('modal').onclick = (e) => { if (e.target === e.currentTarget) closeModal(); };

    (async () => {
      await loadTree();
      buildBreadcrumb();
      await loadFiles();
    })();
  </script>
</body>
</html>"""
