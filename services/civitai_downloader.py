from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import html
import os
import re
import requests
import zipfile
import threading
import uuid
from services._downloader import fetch, probe_url
from services._tokens import resolve_token, save_token, tokens_saved_status

app = FastAPI(title="CivitAI LoRA Downloader")

download_status = {}


def render_index(result: str = "", url_value: str = "") -> str:
    """Подстановка в HTML с экранированием; токен в форму не возвращаем."""
    return (
        INDEX_HTML
        .replace("{{ result }}", html.escape(result, quote=True))
        .replace("{{ url_value }}", html.escape(url_value, quote=True))
    )

INDEX_HTML = """
<!doctype html>
<html lang=\"ru\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Загрузчик LoRA с CivitAI</title>
  <style>
    :root { --bg:#1e1e1e; --card:#282828; --text:#ffffff; --muted:#9ca3af; --accent:#ffffff; --accent-border:#000000; }
    html,body { margin:0; padding:0; background:var(--bg); color:var(--text); font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, Arial; }
    .wrap { max-width: 1200px; margin: 0 auto; padding: 40px 20px; }
    .title { font-size: 36px; font-weight: 800; margin: 0 0 8px; color: var(--accent); text-align: center; text-shadow: 0 0 10px rgba(255,255,255,0.3); }
    .subtitle { margin:0 0 40px; color:var(--muted); text-align: center; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin: 0 auto; max-width: 1000px; }
    .card { background: var(--card); border:1px solid #3a3a3a; border-radius: 12px; padding: 24px; box-sizing: border-box; }
    .row { display:grid; grid-template-columns: 200px 1fr; gap:16px; align-items:center; margin:16px 0; }
    input[type=text], input[type=password] { width:100%; padding:12px 16px; background:#1a1a1a; border:1px solid #3a3a3a; color:var(--text); border-radius:8px; box-sizing: border-box; }
    .btn { display:inline-flex; align-items:center; gap:8px; padding:12px 20px; background: rgba(255,255,255,0.9); color:var(--bg); font-weight:700; border:2px solid rgba(255,255,255,0.5); border-radius:8px; cursor:pointer; transition: all 0.2s; }
    .btn:hover { background: var(--accent); color:var(--bg); border-color: var(--accent); }
    a { color:var(--accent); text-decoration:none; border-bottom: 1px solid rgba(255,255,255,0.3); }
    a:hover { text-decoration:none; border-bottom-color: var(--accent); }
    .hint { background:#1a1a1a; border:1px dashed #3a3a3a; padding:16px; border-radius:8px; margin-bottom:20px; }
    .result { white-space: pre-wrap; background:#1a1a1a; border:1px solid #3a3a3a; padding:16px; border-radius:8px; margin-top:20px; min-height:24px; }
    .progress { margin-top:20px; }
    .progress-bar { width:100%; height:8px; background:#1a1a1a; border:1px solid #3a3a3a; border-radius:4px; overflow:hidden; }
    .progress-fill { height:100%; background:var(--accent); width:0%; transition:width 0.3s; }
    .progress-text { margin-top:8px; color:var(--muted); font-size:14px; text-align:center; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; }
    .token-saved-badge {
      display: inline-block;
      margin-top: 8px;
      font-size: 12px;
      font-weight: 600;
      color: #22c55e;
      background: rgba(34, 197, 94, 0.15);
      padding: 4px 10px;
      border-radius: 999px;
    }
  </style>
</head>
<body>
  <div class=\"wrap\">
    <h1 class=\"title\">Загрузчик LoRA</h1>
    <p class=\"subtitle\">Загрузчик LoRA · сохранение в <span class=\"mono\">/workspace/ComfyUI/models/loras</span></p>
    <div class=\"grid\">
      <div class=\"card\">
        <div class=\"hint\"><b>Где взять API-токен?</b> Создайте токен на странице аккаунта CivitAI: <a href=\"https://civitai.com/user/account\" target=\"_blank\">civitai.com/user/account</a>.</div>
        <form method=\"post\" action=\"/download\" style=\"margin-top:12px\">
          <div class=\"row\">
            <label for=\"token\">Токен</label>
            <input id=\"token\" type=\"password\" name=\"token\" placeholder=\"Скопируйте токен с CivitAI\" value=\"\" />
            <span id=\"civitai-token-saved-badge\" class=\"token-saved-badge\" hidden>токен сохранён ✓</span>
          </div>
          <div class=\"row\">
            <label for=\"url\">Ссылка на модель</label>
            <input id=\"url\" type=\"text\" name=\"url\" placeholder=\"Страница модели или API: https://civitai.com/api/download/models/123456\" value=\"{{ url_value }}\" required />
          </div>
          <div class=\"row\" style=\"grid-template-columns:1fr;\">
            <button class=\"btn\" type=\"submit\">Скачать LoRA</button>
          </div>
        </form>
        <div class=\"result\" id=\"result\">{{ result }}</div>
        <div class=\"progress\" id=\"progress\" style=\"display:none;\">
          <div class=\"progress-bar\">
            <div class=\"progress-fill\" id=\"progress-fill\"></div>
          </div>
          <div class=\"progress-text\" id=\"progress-text\">Загрузка...</div>
        </div>
      </div>
    </div>
  </div>
  <script>
    function updateTokenSavedBadge(saved) {
      const badge = document.getElementById('civitai-token-saved-badge');
      if (badge) badge.hidden = !saved;
    }

    fetch('/tokens/status')
      .then(response => response.json())
      .then(data => updateTokenSavedBadge(!!data.civitai))
      .catch(() => {});

    document.querySelector('form').addEventListener('submit', function(e) {
      e.preventDefault();

      const tokenInput = document.getElementById('token');
      const tokenValue = (tokenInput && tokenInput.value || '').trim();
      if (!tokenValue) {
        fetch('/tokens/status')
          .then(response => response.json())
          .then(data => {
            if (!data.civitai) {
              document.getElementById('result').textContent = '❌ Введите токен CivitAI';
              return;
            }
            startDownload(this);
          })
          .catch(() => {
            document.getElementById('result').textContent = '❌ Введите токен CivitAI';
          });
        return;
      }
      startDownload(this);
    });

    function startDownload(form) {

      const progress = document.getElementById('progress');
      const result = document.getElementById('result');
      const btn = document.querySelector('.btn');
      const progressFill = document.getElementById('progress-fill');
      const progressText = document.getElementById('progress-text');

      progress.style.display = 'block';
      result.textContent = '';
      btn.disabled = true;
      btn.textContent = 'Загрузка...';
      progressFill.style.width = '0%';
      progressText.textContent = 'Загрузка...';

      fetch('/download', {
        method: 'POST',
        body: new FormData(form)
      })
      .then(response => response.json())
      .then(data => {
        if (data.task_id) {
          result.textContent = data.message;
          pollDownloadStatus(data.task_id);
        } else {
          result.textContent = data.message || '❌ Ошибка';
          progress.style.display = 'none';
          btn.disabled = false;
          btn.textContent = 'Скачать LoRA';
        }
      })
      .catch(error => {
        result.textContent = '❌ Ошибка: ' + error.message;
        progress.style.display = 'none';
        btn.disabled = false;
        btn.textContent = 'Скачать LoRA';
      });
    }

    function pollDownloadStatus(taskId) {
      const progress = document.getElementById('progress');
      const progressFill = document.getElementById('progress-fill');
      const progressText = document.getElementById('progress-text');
      const result = document.getElementById('result');
      const btn = document.querySelector('.btn');

      fetch('/status/' + taskId)
      .then(response => response.json())
      .then(data => {
        if (data.status === 'completed' || data.status === 'error') {
          result.textContent = data.message;
          progress.style.display = 'none';
          btn.disabled = false;
          btn.textContent = 'Скачать LoRA';
          if (data.status === 'completed') {
            updateTokenSavedBadge(true);
          }
        } else if (data.status === 'running') {
          const progressPercent = data.progress || 0;
          progressFill.style.width = progressPercent + '%';
          progressText.textContent = data.message || 'Загрузка...';
          result.textContent = data.message || 'Загрузка...';
          setTimeout(() => pollDownloadStatus(taskId), 500);
        } else {
          result.textContent = data.message || '❌ Неизвестный статус';
          progress.style.display = 'none';
          btn.disabled = false;
          btn.textContent = 'Скачать LoRA';
        }
      })
      .catch(error => {
        result.textContent = '❌ Ошибка проверки статуса: ' + error.message;
        progress.style.display = 'none';
        btn.disabled = false;
        btn.textContent = 'Скачать LoRA';
      });
    }
  </script>
</body>
</html>
"""

def civitai_api_url_from_page(url: str) -> str | None:
    m = re.search(r"/models/(\d+)", url)
    if m:
        return f"https://civitai.com/api/download/models/{m.group(1)}"
    return None

def unzip_file(zip_path, extract_to=None):
    """Распаковывает zip-файл прямо в указанную папку без лишней подпапки"""
    if extract_to is None:
        extract_to = os.path.dirname(zip_path)
    
    extracted_files = []
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for member in zip_ref.namelist():
            filename = os.path.basename(member)
            # пропускаем папки внутри архива
            if not filename:
                continue
            source = zip_ref.open(member)
            target_path = os.path.join(extract_to, filename)
            with open(target_path, "wb") as target:
                with source as src:
                    target.write(src.read())
            extracted_files.append(filename)
    
    # Удаляем zip файл после распаковки
    os.remove(zip_path)
    return extracted_files

@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(render_index())


@app.get("/status/{task_id}")
def get_status(task_id: str):
    if task_id not in download_status:
        return {"status": "not_found", "message": "Задача не найдена"}
    return download_status[task_id]


def _run_civitai_download(token: str, api_url: str, task_id: str, form_token: str = "") -> None:
    target_dir = "/workspace/ComfyUI/models/loras"
    os.makedirs(target_dir, exist_ok=True)

    try:
        download_status[task_id] = {
            "status": "running",
            "message": "📥 Подключение к CivitAI...",
            "progress": 0,
        }

        headers = {"Authorization": f"Bearer {token}"}
        status_code, expected_size = probe_url(api_url, headers=headers)

        head = None
        try:
            head = requests.head(api_url, headers=headers, timeout=30, allow_redirects=True)
            if not status_code:
                status_code = head.status_code
        except Exception:
            pass

        if status_code and status_code != 200:
            error_msg = f"❌ Ошибка {status_code}"
            if status_code == 401:
                error_msg = "❌ Ошибка авторизации: Проверьте API-ключ"
            elif status_code == 404:
                error_msg = "❌ Модель не найдена: Проверьте URL"
            download_status[task_id] = {
                "status": "error",
                "message": error_msg,
                "progress": 0,
            }
            return

        try:
            content_type = head.headers.get("content-type", "").lower() if head is not None else ""
        except Exception:
            content_type = ""

        if "text/html" in content_type:
            download_status[task_id] = {
                "status": "error",
                "message": "❌ Ошибка: получена страница, а не файл. Проверьте URL и API-токен",
                "progress": 0,
            }
            return

        cd = head.headers.get("content-disposition", "") if head is not None else ""
        filename = re.findall('filename="?([^";]+)"?', cd)
        fname = os.path.basename(filename[0] if filename else api_url.split("?")[0].rstrip("/").split("/")[-1])
        path = os.path.join(target_dir, fname)

        def on_progress(pct):
            size_mb = os.path.getsize(path) / (1024 * 1024) if os.path.isfile(path) else 0
            if expected_size > 0:
                total_mb = expected_size / (1024 * 1024)
                download_status[task_id] = {
                    "status": "running",
                    "message": f"📥 Скачивание: {fname} ({pct}%) - {size_mb:.1f} MB / {total_mb:.1f} MB",
                    "progress": pct,
                }
            else:
                download_status[task_id] = {
                    "status": "running",
                    "message": f"📥 Скачивание: {fname} ({size_mb:.1f} MB)",
                    "progress": pct if pct > 0 else 0,
                }

        fetch(api_url, path, on_progress=on_progress, token=token)

        with open(path, "rb") as sniff_file:
            sniff = sniff_file.read(512).lstrip().lower()
        if sniff.startswith(b"<!doctype") or sniff.startswith(b"<html"):
            os.remove(path)
            download_status[task_id] = {
                "status": "error",
                "message": "❌ Ошибка: получена страница, а не файл. Проверьте URL и API-токен",
                "progress": 0,
            }
            return

        size_mb = os.path.getsize(path) / (1024 * 1024)
        success_msg = f"✅ Успешно загружено!\n📁 Файл: {fname}\n💾 Размер: {size_mb:.1f} MB\n📂 Путь: {path}"

        if fname.endswith(".zip"):
            try:
                extracted_files = unzip_file(path, target_dir)
                success_msg += f"\n📦 Архив распакован! Извлечено файлов: {len(extracted_files)}"
                if extracted_files:
                    success_msg += f"\n📄 Файлы: {', '.join(extracted_files[:3])}"
                    if len(extracted_files) > 3:
                        success_msg += f" и еще {len(extracted_files) - 3} файлов"
            except Exception as e:
                success_msg += f"\n⚠️ Ошибка распаковки: {str(e)}"

        download_status[task_id] = {
            "status": "completed",
            "message": success_msg,
            "progress": 100,
        }
        if (form_token or "").strip():
            save_token("civitai", form_token)

    except requests.exceptions.Timeout:
        download_status[task_id] = {
            "status": "error",
            "message": "❌ Таймаут: Загрузка заняла слишком много времени",
            "progress": download_status[task_id].get("progress", 0),
        }
    except requests.exceptions.ConnectionError:
        download_status[task_id] = {
            "status": "error",
            "message": "❌ Ошибка соединения: Проверьте интернет-соединение",
            "progress": download_status[task_id].get("progress", 0),
        }
    except Exception as e:
        download_status[task_id] = {
            "status": "error",
            "message": f"❌ Неожиданная ошибка: {str(e)}",
            "progress": download_status[task_id].get("progress", 0),
        }


@app.get("/tokens/status")
def tokens_status():
    return tokens_saved_status()


@app.post("/download")
def download(token: str = Form(""), url: str = Form(...)):
    try:
        form_token = (token or "").strip()
        effective_token = resolve_token("civitai", form_token)
        if not effective_token:
            return {"message": "❌ Введите токен CivitAI или сохраните его ранее на этом поде"}

        api_url = url
        if "civitai.com/api/download/models/" not in api_url:
            maybe = civitai_api_url_from_page(url)
            if not maybe:
                return {"message": "❌ Ошибка: Не удалось извлечь ID модели из URL"}
            api_url = maybe

        task_id = str(uuid.uuid4())
        thread = threading.Thread(
            target=_run_civitai_download,
            args=(effective_token, api_url, task_id, form_token),
            daemon=True,
        )
        thread.start()

        download_status[task_id] = {
            "status": "running",
            "message": "🚀 Начата загрузка с CivitAI",
            "progress": 0,
        }

        return {"message": f"🚀 Загрузка начата! ID задачи: {task_id}", "task_id": task_id}

    except Exception as e:
        return {"message": f"❌ Ошибка: {str(e)}"}


