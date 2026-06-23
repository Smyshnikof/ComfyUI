from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os
import subprocess
import threading
import uuid
from collections import OrderedDict

# Глобальный словарь для отслеживания статуса загрузок
download_status: OrderedDict = OrderedDict()
MAX_DOWNLOAD_TASKS = 50
import requests
import json
from huggingface_hub import hf_hub_download, login
import tempfile
from services._downloader import fetch, probe_url, estimate_size, check_disk_space
from services._tokens import resolve_token, save_token, tokens_saved_status

from services._presets import (
    ALLOWED_MODEL_FOLDERS,
    ALLOWED_IMPORT_HOSTS,
    load_presets,
    save_community_preset,
)

PRESETS, PRESET_FILES, PRESET_CATEGORIES = load_presets()


def reload_presets_data() -> None:
    global PRESETS, PRESET_FILES, PRESET_CATEGORIES
    PRESETS, PRESET_FILES, PRESET_CATEGORIES = load_presets()



app = FastAPI(title="Preset & Model Downloader")

# Подключаем статические файлы
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

MODELS_ROOT = "/workspace/ComfyUI/models"



def validate_model_folder(folder: str) -> str | None:
    if folder not in ALLOWED_MODEL_FOLDERS:
        return f"❌ Недопустимая папка: {folder}"
    return None


def sanitize_filename(filename: str) -> str | None:
    safe = os.path.basename((filename or "").strip())
    if not safe or safe in (".", ".."):
        return None
    return safe


def _path_under_models(path: str) -> bool:
    models_root = os.path.realpath(MODELS_ROOT)
    parent = os.path.realpath(os.path.dirname(path))
    try:
        return os.path.commonpath([models_root, parent]) == models_root
    except ValueError:
        return False


def resolve_models_dir(folder: str) -> tuple[str | None, str | None]:
    err = validate_model_folder(folder)
    if err:
        return None, err
    os.makedirs(os.path.join(MODELS_ROOT, folder), exist_ok=True)
    models_root = os.path.realpath(MODELS_ROOT)
    dest_dir = os.path.realpath(os.path.join(MODELS_ROOT, folder))
    if not _path_under_models(os.path.join(dest_dir, "placeholder")):
        return None, "❌ Путь выходит за пределы models/"
    return dest_dir, None


def resolve_models_file(folder: str, filename: str) -> tuple[str | None, str | None, str | None]:
    dest_dir, err = resolve_models_dir(folder)
    if err:
        return None, None, err
    safe_name = sanitize_filename(filename)
    if not safe_name:
        return None, None, "❌ Недопустимое имя файла"
    file_path = os.path.join(dest_dir, safe_name)
    if not _path_under_models(file_path):
        return None, None, "❌ Путь выходит за пределы models/"
    return file_path, safe_name, None


def resolve_hf_file_path(folder: str, filename: str) -> tuple[str | None, str | None, str | None]:
    """HF filename may include subfolders, e.g. subdir/model.safetensors."""
    dest_dir, err = resolve_models_dir(folder)
    if err:
        return None, None, err
    parts = [p for p in filename.strip().replace("\\", "/").split("/") if p and p != "."]
    if not parts or ".." in parts:
        return None, None, "❌ Недопустимое имя файла"
    rel_path = os.path.join(*parts)
    file_path = os.path.join(dest_dir, rel_path)
    if not _path_under_models(file_path):
        return None, None, "❌ Путь выходит за пределы models/"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    return file_path, rel_path, None


def _trim_download_status() -> None:
    while len(download_status) > MAX_DOWNLOAD_TASKS:
        download_status.popitem(last=False)

INDEX_HTML = """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Загрузчик пресетов и моделей</title>
  <style>
    :root { --bg:#1e1e1e; --card:#282828; --text:#ffffff; --muted:#9ca3af; --accent:#ffffff; --accent-border:#000000; }
    html,body { margin:0; padding:0; background:var(--bg); color:var(--text); font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, Arial; }
    .wrap { max-width: 1200px; margin: 0 auto; padding: 40px 20px; }
    .title { font-size: 36px; font-weight: 800; margin: 0 0 8px; color: var(--accent); text-align: center; text-shadow: 0 0 10px rgba(255,255,255,0.3); }
    .subtitle { margin:0 0 40px; color:var(--muted); text-align: center; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin: 0 auto; max-width: 1000px; }
    .card { background: var(--card); border:1px solid #3a3a3a; border-radius: 12px; padding: 24px; box-sizing: border-box; }
    .row { display:grid; grid-template-columns: 200px 1fr; gap:16px; align-items:center; margin:16px 0; }
    .row-full { display:grid; grid-template-columns: 1fr; gap:16px; margin:16px 0; }
    input[type=text], input[type=password] { width:100%; padding:12px 16px; background:#1a1a1a; border:1px solid #3a3a3a; color:var(--text); border-radius:8px; box-sizing: border-box; }
    .btn { display:inline-flex; align-items:center; gap:8px; padding:12px 20px; background: rgba(255,255,255,0.9); color:var(--bg); font-weight:700; border:2px solid rgba(255,255,255,0.5); border-radius:8px; cursor:pointer; transition: all 0.2s; }
    .btn:hover { background: var(--accent); color:var(--bg); border-color: var(--accent); }
    .btn:disabled { opacity:0.5; cursor:not-allowed; }
    .btn-preset { 
      background: rgba(34, 197, 94, 0.9); 
      color: white; 
      border-color: rgba(34, 197, 94, 0.5); 
      box-shadow: 0 4px 12px rgba(34, 197, 94, 0.3);
    }
    .btn-preset:hover { 
      background: rgb(34, 197, 94); 
      color: white;
      border-color: rgb(34, 197, 94); 
      box-shadow: 0 8px 20px rgba(34, 197, 94, 0.5);
    }
    .btn-hf { 
      background: rgba(255, 193, 7, 0.9); 
      color: black; 
      border-color: rgba(255, 193, 7, 0.5); 
      box-shadow: 0 4px 12px rgba(255, 193, 7, 0.3);
    }
    .btn-hf:hover { 
      background: rgb(255, 193, 7); 
      color: black;
      border-color: rgb(255, 193, 7); 
      box-shadow: 0 8px 20px rgba(255, 193, 7, 0.5);
    }
    a { color:var(--accent); text-decoration:none; border-bottom: 1px solid rgba(255,255,255,0.3); }
    a:hover { text-decoration:none; border-bottom-color: var(--accent); }
    .hint { background:#1a1a1a; border:1px dashed #3a3a3a; padding:16px; border-radius:8px; margin-bottom:20px; }
    .result { white-space: pre-wrap; background:#1a1a1a; border:1px solid #3a3a3a; padding:16px; border-radius:8px; margin-top:20px; min-height:24px; }
    .progress { margin-top:20px; }
    .progress-bar { width:100%; height:8px; background:#1a1a1a; border:1px solid #3a3a3a; border-radius:4px; overflow:hidden; }
    .progress-fill { height:100%; background:var(--accent); width:0%; transition:width 0.3s; }
    .progress-text { margin-top:8px; color:var(--muted); font-size:14px; text-align:center; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; }
    .preset-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px; margin: 20px 0; }
    .preset-card { background: #1a1a1a; border: 1px solid #3a3a3a; border-radius: 8px; padding: 16px; cursor: pointer; transition: all 0.2s; position: relative; }
    .preset-card:hover { border-color: var(--accent); background: #222; }
    .preset-card.selected { border-color: var(--accent); background: rgba(255,255,255,0.1); }
    .preset-name { font-weight: 700; margin-bottom: 8px; color: var(--accent); }
    .preset-desc { color: var(--muted); font-size: 14px; margin-bottom: 8px; }
    .preset-info { font-size: 12px; color: var(--muted); }
    .preset-install-badge {
      display: inline-block;
      font-size: 11px;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 999px;
      margin-bottom: 8px;
    }
    .preset-install-badge.full { background: rgba(34, 197, 94, 0.2); color: #22c55e; }
    .preset-install-badge.partial { background: rgba(234, 179, 8, 0.2); color: #eab308; }
    .preset-variant-badge {
      margin-left: 8px;
      font-size: 11px;
      font-weight: 600;
    }
    .preset-variant-badge.full { color: #22c55e; }
    .preset-variant-badge.partial { color: #eab308; }
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
    .video-guide-icon { 
      position: absolute;
      top: 12px;
      right: 12px;
      width: 22px; 
      height: 22px; 
      background: white; 
      border-radius: 50%; 
      display: inline-flex; 
      align-items: center; 
      justify-content: center; 
      color: black; 
      font-weight: bold; 
      font-size: 14px; 
      text-decoration: none; 
      transition: all 0.2s;
      border: 1px solid rgba(255,255,255,0.3);
      z-index: 10;
    }
    .video-guide-icon:hover { 
      background: var(--accent); 
      color: var(--bg); 
      transform: scale(1.15);
      box-shadow: 0 0 10px rgba(255,255,255,0.4);
    }
    .tabs { display: flex; gap: 8px; margin-bottom: 20px; justify-content: center; flex-wrap: wrap; }
    .tab { padding: 8px 16px; background: #1a1a1a; border: 1px solid #3a3a3a; border-radius: 8px; cursor: pointer; transition: all 0.2s; }
    .tab.active { background: var(--accent); color: var(--bg); }
    .tab-content { display: none; }
    .tab-content.active { display: block; }
    .search-container { margin-bottom: 20px; position: relative; }
    .search-input { width: 100%; padding: 12px 16px 12px 44px; background: #1a1a1a; border: 1px solid #3a3a3a; color: var(--text); border-radius: 8px; box-sizing: border-box; font-size: 14px; }
    .search-icon { position: absolute; left: 14px; top: 50%; transform: translateY(-50%); color: var(--muted); pointer-events: none; }
    .category-filters { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; align-items: center; }
    .category-filter { padding: 8px 16px; background: #1a1a1a; border: 1px solid #3a3a3a; border-radius: 8px; cursor: pointer; transition: all 0.2s; display: flex; align-items: center; gap: 6px; font-size: 14px; }
    .category-filter:hover { border-color: var(--accent); background: #222; }
    .category-filter.active { background: var(--accent); color: var(--bg); border-color: var(--accent); }
    .category-filter.all { background: #2a2a2a; }
    .category-filter.all.active { background: var(--accent); }
    .preset-card.hidden { display: none; }
    .preset-variants { margin-top: 12px; padding-top: 12px; border-top: 1px solid #3a3a3a; display: none; }
    .preset-card.expanded .preset-variants { display: block; }
    .preset-variant-group { margin-bottom: 16px; }
    .preset-variant-group-title { font-size: 13px; font-weight: 600; color: var(--accent); margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #2a2a2a; }
    .preset-variant-item { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; padding: 8px; background: #0f0f0f; border-radius: 6px; cursor: pointer; transition: all 0.2s; }
    .preset-variant-item:hover { background: #151515; }
    .preset-variant-item input[type="checkbox"] { width: 16px; height: 16px; cursor: pointer; }
    .preset-variant-label { flex: 1; font-size: 13px; color: var(--muted); }
    .preset-variant-label strong { color: var(--text); }
    .preset-variant-info { font-size: 11px; color: var(--muted); }
    .preset-expand-icon { position: absolute; top: 50%; right: 16px; transform: translateY(-50%); font-size: 18px; color: var(--muted); transition: transform 0.2s; cursor: pointer; z-index: 5; }
    .preset-card.expanded .preset-expand-icon { transform: translateY(-50%) rotate(180deg); }
    .preset-expand-icon:hover { color: var(--accent); }
  </style>
</head>
<body>
  <div class="wrap">
    <h1 class="title">Загрузчик пресетов и моделей</h1>
    <p class="subtitle">Скачивание пресетов и моделей с HuggingFace</p>
    
    <div class="tabs">
      <div class="tab active" onclick="switchTab('presets')">🎯 Пресеты</div>
      <div class="tab" onclick="switchTab('huggingface')">🤗 HuggingFace</div>
    </div>
    
    <div class="grid">
      <!-- Пресеты -->
      <div class="card tab-content active" id="presets-tab">
        <h3>Выберите пресеты для скачивания</h3>
        
        <!-- Поиск -->
        <div class="search-container">
          <input type="text" class="search-input" id="preset-search" placeholder="Поиск пресетов..." oninput="filterPresets()">
        </div>
        
        <!-- Фильтры категорий -->
        <div class="category-filters" id="category-filters">
          {{ category_filters_html }}
        </div>
        
        <div class="preset-grid" id="preset-grid">
          {{ presets_html }}
        </div>
        <div class="row-full" style="margin-top: 12px; gap: 8px; display: flex; flex-wrap: wrap; align-items: center;">
          <button type="button" class="btn" onclick="reloadPresets()" id="reload-presets-btn" title="Подхватить JSON из /workspace/presets/community/">
            🔄 Обновить пресеты
          </button>
          <input type="text" id="import-preset-url" placeholder="https://raw.githubusercontent.com/.../preset.json" style="flex:1; min-width:220px;" />
          <button type="button" class="btn" onclick="importPresetByUrl()" id="import-preset-btn">📥 Импорт пресета</button>
        </div>
        <div class="row-full">
          <button class="btn btn-preset" onclick="downloadPresets()" id="download-presets-btn" disabled>
            📥 Скачать выбранные пресеты
          </button>
        </div>
        <div class="result" id="preset-result"></div>
        <div class="progress" id="preset-progress" style="display:none;">
          <div class="progress-bar">
            <div class="progress-fill" id="preset-progress-fill"></div>
          </div>
          <div class="progress-text" id="preset-progress-text">Загрузка...</div>
        </div>
      </div>
      
      <!-- HuggingFace -->
      <div class="card tab-content" id="huggingface-tab">
        <div class="hint">
          <b>Как использовать?</b> Выберите способ: прямая ссылка на файл (рекомендуется) или HuggingFace репозиторий. 
          Для приватных моделей нужен API токен с правами "Read" - см. инструкцию ниже.
        </div>
        
        <div class="tabs" style="margin-bottom: 20px;">
          <div class="tab active" onclick="switchHFMethod('url')">🔗 Прямая ссылка</div>
          <div class="tab" onclick="switchHFMethod('repo')">🤗 HuggingFace Repo</div>
        </div>
        
        <!-- Прямая ссылка метод (дефолтный) -->
        <form id="hf-url-form" method="post" action="/download_url" style="margin-top:12px;">
          <div class="row">
            <label for="hf_url">Прямая ссылка на файл</label>
            <input id="hf_url" type="text" name="url" placeholder="https://huggingface.co/username/model/resolve/main/file.safetensors" required />
          </div>
          <div class="row">
            <label for="hf_url_folder">Папка назначения</label>
            <select id="hf_url_folder" name="folder" style="width:100%; padding:12px 16px; background:#1a1a1a; border:1px solid #3a3a3a; color:var(--text); border-radius:8px;">
              <option value="diffusion_models">diffusion_models</option>
              <option value="loras">loras</option>
              <option value="vae">vae</option>
              <option value="text_encoders">text_encoders</option>
              <option value="upscale_models">upscale_models</option>
              <option value="latent_upscale_models">latent_upscale_models</option>
              <option value="clip_vision">clip_vision</option>
              <option value="audio_encoders">audio_encoders</option>
              <option value="checkpoints">checkpoints</option>
              <option value="clip">clip</option>
              <option value="configs">configs</option>
              <option value="controlnet">controlnet</option>
              <option value="diffusers">diffusers</option>
              <option value="embeddings">embeddings</option>
              <option value="gligen">gligen</option>
              <option value="hypernetworks">hypernetworks</option>
              <option value="ipadapter">ipadapter</option>
              <option value="model_patches">model_patches</option>
              <option value="onnx">onnx</option>
              <option value="photomaker">photomaker</option>
              <option value="sams">sams</option>
              <option value="style_models">style_models</option>
              <option value="unet">unet</option>
              <option value="vae_approx">vae_approx</option>
              <option value="vibevoice">vibevoice</option>
              <option value="detection">detection</option>
            </select>
          </div>
          <div class="row" style="grid-template-columns:1fr;">
            <button class="btn btn-hf" type="submit">🔗 Скачать по ссылке</button>
          </div>
        </form>
        
        <!-- HuggingFace Repo метод -->
        <form id="hf-repo-form" method="post" action="/download_hf" style="margin-top:12px; display:none;">
          <div class="row">
            <label for="hf_repo">Репозиторий</label>
            <input id="hf_repo" type="text" name="repo" placeholder="username/model-name" value="{{ hf_repo_value }}" />
          </div>
          <div class="row">
            <label for="hf_file">Файл (опционально)</label>
            <input id="hf_file" type="text" name="filename" placeholder="model.safetensors или subdir/model.safetensors" value="{{ hf_file_value }}" />
          </div>
          <div class="row">
            <label for="hf_revision">Ветка / revision</label>
            <input id="hf_revision" type="text" name="revision" placeholder="main" value="main" />
          </div>
          <div class="row">
            <label for="hf_token">API токен (опционально)</label>
            <input id="hf_token" type="password" name="token" placeholder="hf_..." value="" autocomplete="current-password" />
            <span id="hf-token-saved-badge" class="token-saved-badge" hidden>токен сохранён ✓</span>
            <div style="margin-top: 8px; padding: 12px; background: #1a1a1a; border: 1px solid #3a3a3a; border-radius: 8px; font-size: 12px; word-wrap: break-word;">
              <div style="color: #4a9eff; font-weight: 600; margin-bottom: 8px;">📋 Как создать токен:</div>
              <div style="color: #ccc; line-height: 1.4;">
                1. Перейдите по ссылке: <a href="https://huggingface.co/settings/tokens" target="_blank" style="color: #4a9eff; text-decoration: underline;">https://huggingface.co/settings/tokens</a><br>
                2. Нажмите "New token"<br>
                3. Выберите "Read" (достаточно для скачивания)<br>
                4. Введите название токена<br>
                5. Нажмите "Create token"<br>
                6. Скопируйте токен (начинается с hf_...)
              </div>
            </div>
          </div>
          <div class="row">
            <label for="hf_folder">Папка назначения</label>
            <select id="hf_folder" name="folder" style="width:100%; padding:12px 16px; background:#1a1a1a; border:1px solid #3a3a3a; color:var(--text); border-radius:8px;">
              <option value="diffusion_models">diffusion_models</option>
              <option value="loras">loras</option>
              <option value="vae">vae</option>
              <option value="text_encoders">text_encoders</option>
              <option value="upscale_models">upscale_models</option>
              <option value="latent_upscale_models">latent_upscale_models</option>
              <option value="clip_vision">clip_vision</option>
              <option value="audio_encoders">audio_encoders</option>
              <option value="checkpoints">checkpoints</option>
              <option value="clip">clip</option>
              <option value="configs">configs</option>
              <option value="controlnet">controlnet</option>
              <option value="diffusers">diffusers</option>
              <option value="embeddings">embeddings</option>
              <option value="gligen">gligen</option>
              <option value="hypernetworks">hypernetworks</option>
              <option value="ipadapter">ipadapter</option>
              <option value="model_patches">model_patches</option>
              <option value="onnx">onnx</option>
              <option value="photomaker">photomaker</option>
              <option value="sams">sams</option>
              <option value="style_models">style_models</option>
              <option value="unet">unet</option>
              <option value="vae_approx">vae_approx</option>
              <option value="vibevoice">vibevoice</option>
              <option value="detection">detection</option>
            </select>
          </div>
          <div class="row" style="grid-template-columns:1fr;">
            <button class="btn btn-hf" type="submit">🤗 Скачать с HuggingFace</button>
          </div>
        </form>
        <div class="result" id="hf-result">{{ hf_result }}</div>
        <div class="progress" id="hf-progress" style="display:none;">
          <div class="progress-bar">
            <div class="progress-fill" id="hf-progress-fill"></div>
          </div>
          <div class="progress-text" id="hf-progress-text">Загрузка...</div>
        </div>
      </div>
    </div>
  </div>
  
  <script src="/static/script.js"></script>
  <script>
    // Дополнительный JavaScript код для HuggingFace функций
    
    // Ждём полной загрузки DOM перед регистрацией обработчиков
    document.addEventListener('DOMContentLoaded', function() {
      console.log('HF handlers initializing...');
      
      // Проверяем наличие форм
      const hfForm = document.querySelector('form[action="/download_hf"]');
      const urlForm = document.querySelector('form[action="/download_url"]');
      
      if (!hfForm || !urlForm) {
        console.error('Forms not found!', { hfForm, urlForm });
        return;
      }
      
      console.log('Forms found, attaching handlers');
      
      // Обработка формы HuggingFace (только для репозитория)
      hfForm.addEventListener('submit', function(e) {
        e.preventDefault(); // Предотвращаем стандартную отправку формы
        console.log('HF form submitted');
        
        const progress = document.getElementById('hf-progress');
        const result = document.getElementById('hf-result');
        const btn = document.querySelector('form[action="/download_hf"] button[type="submit"]');
        
        // Показываем прогресс
        progress.style.display = 'block';
        result.textContent = '';
        btn.disabled = true;
        btn.textContent = 'Загрузка...';
        
        // Отправляем форму через fetch
        const formData = new FormData(this);
        
        fetch('/download_hf', {
          method: 'POST',
          body: formData
        })
        .then(response => response.json())
        .then(data => {
          if (data.task_id) {
            result.textContent = data.message;
            // Начинаем опрос статуса
            pollHFStatus(data.task_id);
          } else {
            result.textContent = data.message;
            progress.style.display = 'none';
            btn.disabled = false;
            btn.textContent = '🤗 Скачать с HuggingFace';
          }
        })
        .catch(error => {
          result.textContent = '❌ Ошибка: ' + error.message;
          progress.style.display = 'none';
          btn.disabled = false;
          btn.textContent = '🤗 Скачать с HuggingFace';
        });
      });
      
      // Обработка формы прямой ссылки
      urlForm.addEventListener('submit', function(e) {
        e.preventDefault(); // Предотвращаем стандартную отправку формы
        console.log('URL form submitted');
        
        const progress = document.getElementById('hf-progress');
        const result = document.getElementById('hf-result');
        const btn = document.querySelector('form[action="/download_url"] button[type="submit"]');
        
        // Показываем прогресс
        progress.style.display = 'block';
        result.textContent = '';
        btn.disabled = true;
        btn.textContent = 'Загрузка...';
        
        // Отправляем форму через fetch
        const formData = new FormData(this);
        
        fetch('/download_url', {
          method: 'POST',
          body: formData
        })
        .then(response => response.json())
        .then(data => {
          if (data.task_id) {
            result.textContent = data.message;
            // Начинаем опрос статуса
            pollHFStatus(data.task_id);
          } else {
            result.textContent = data.message;
            progress.style.display = 'none';
            btn.disabled = false;
            btn.textContent = '🔗 Скачать по ссылке';
          }
        })
        .catch(error => {
          result.textContent = '❌ Ошибка: ' + error.message;
          progress.style.display = 'none';
          btn.disabled = false;
          btn.textContent = '🔗 Скачать по ссылке';
        });
      });
      
      console.log('HF handlers attached successfully');
    });
    
    function pollHFStatus(taskId) {
      const progress = document.getElementById('hf-progress');
      const progressFill = document.getElementById('hf-progress-fill');
      const progressText = document.getElementById('hf-progress-text');
      const result = document.getElementById('hf-result');
      
      // Находим активную кнопку (видимую форму)
      const hfForm = document.getElementById('hf-repo-form');
      const urlForm = document.getElementById('hf-url-form');
      let btn = null;
      
      if (hfForm.style.display !== 'none') {
        btn = hfForm.querySelector('button[type="submit"]');
      } else if (urlForm.style.display !== 'none') {
        btn = urlForm.querySelector('button[type="submit"]');
      }
      
      if (!btn) {
        // Fallback - ищем любую кнопку
        btn = document.querySelector('form[action="/download_hf"] button[type="submit"]') || 
              document.querySelector('form[action="/download_url"] button[type="submit"]');
      }
      
      fetch('/status/' + taskId)
      .then(response => response.json())
      .then(data => {
        if (data.status === 'completed' || data.status === 'error') {
          result.textContent = data.message;
          progress.style.display = 'none';
          if (btn) {
            btn.disabled = false;
            btn.textContent = btn.textContent.includes('HuggingFace') ? '🤗 Скачать с HuggingFace' : '🔗 Скачать по ссылке';
          }
          if (data.status === 'completed' && typeof loadTokenSavedStatus === 'function') {
            loadTokenSavedStatus();
          }
        } else if (data.status === 'running') {
          // Обновляем прогресс-бар
          const progressPercent = data.progress || 0;
          progressFill.style.width = progressPercent + '%';
          progressText.textContent = data.message || 'Загрузка...';
          result.textContent = data.message || 'Загрузка...';
          
          // Повторяем через 500ms для более плавного обновления
          setTimeout(() => pollHFStatus(taskId), 500);
        } else {
          result.textContent = '❌ Неизвестный статус: ' + data.message;
          progress.style.display = 'none';
          if (btn) {
            btn.disabled = false;
            btn.textContent = btn.textContent.includes('HuggingFace') ? '🤗 Скачать с HuggingFace' : '🔗 Скачать по ссылке';
          }
        }
      })
      .catch(error => {
        result.textContent = '❌ Ошибка проверки статуса: ' + error.message;
        progress.style.display = 'none';
        if (btn) {
          btn.disabled = false;
          btn.textContent = btn.textContent.includes('HuggingFace') ? '🤗 Скачать с HuggingFace' : '🔗 Скачать по ссылке';
        }
      });
    }
  </script>
</body>
</html>
"""

def generate_category_filters_html():
    html = '<div class="category-filter all active" onclick="filterByCategory(\'all\', event)">Все</div>'
    for category_id, category_info in PRESET_CATEGORIES.items():
        html += f'''
        <div class="category-filter" onclick="filterByCategory('{category_id}', event)" data-category="{category_id}">
          <span>{category_info['icon']}</span>
          <span>{category_info['name']}</span>
        </div>
        '''
    return html

def generate_presets_html():
    html = ""
    for preset_id, preset_info in PRESETS.items():
        category = preset_info.get('category', 'Wan')
        community_badge = ""
        if preset_info.get("source") == "community":
            community_badge = '<span class="preset-community-badge">community</span>'
        video_guide_html = ""
        if preset_info.get('video_guide'):
            video_guide_html = f'<a href="{preset_info["video_guide"]}" target="_blank" rel="noopener noreferrer" class="video-guide-icon" onclick="event.stopPropagation();" title="Видео-гайд">i</a>'
        
        # Проверяем, есть ли варианты (для Qwen пресетов)
        if preset_info.get('has_variants') and preset_info.get('variant_groups'):
            variants_html = ""
            for group_name, variants in preset_info['variant_groups'].items():
                group_html = f'<div class="preset-variant-group-title">{group_name}</div>'
                for variant_id, variant_info in variants.items():
                    group_html += f'''
                    <div class="preset-variant-item" onclick="event.stopPropagation();">
                      <input type="checkbox" id="variant-{variant_id}" data-variant="{variant_id}" data-parent="{preset_id}" onchange="toggleVariant('{preset_id}', '{variant_id}')">
                      <label for="variant-{variant_id}" class="preset-variant-label">
                        <strong>{variant_info['name']}</strong>
                        <span class="preset-variant-info"> • {variant_info['size']} • {variant_info['time']}</span>
                      </label>
                    </div>
                    '''
                variants_html += f'<div class="preset-variant-group">{group_html}</div>'
            
            html += f'''
            <div class="preset-card" data-preset="{preset_id}" data-category="{category}" onclick="togglePresetCard('{preset_id}', event)">
              {video_guide_html}
              <span class="preset-expand-icon" onclick="event.stopPropagation(); togglePresetCard('{preset_id}', event)">▼</span>
              <div class="preset-name">{preset_info['name']}{community_badge}</div>
              <div class="preset-desc">{preset_info['description']}</div>
              <div class="preset-info">Размер: {preset_info['size']} • Время: {preset_info['time']}</div>
              <div class="preset-variants">
                <div style="font-size: 12px; color: var(--muted); margin-bottom: 12px;">Выберите версию и формат:</div>
                {variants_html}
              </div>
            </div>
            '''
        else:
            # Обычная карточка без вариантов (Wan пресеты)
            html += f'''
            <div class="preset-card" data-preset="{preset_id}" data-category="{category}" onclick="togglePreset('{preset_id}')">
              {video_guide_html}
              <div class="preset-name">{preset_info['name']}{community_badge}</div>
              <div class="preset-desc">{preset_info['description']}</div>
              <div class="preset-info">Размер: {preset_info['size']} • Время: {preset_info['time']}</div>
            </div>
            '''
    return html

def _expected_preset_file_path(url: str, folder: str, custom_filename: str | None) -> str | None:
    if folder not in ALLOWED_MODEL_FOLDERS:
        return None
    if custom_filename:
        name = sanitize_filename(custom_filename)
    else:
        url_name = url.split("?")[0] if "?" in url else url
        name = sanitize_filename(os.path.basename(url_name))
    if not name:
        return None
    path = os.path.join(MODELS_ROOT, folder, name)
    if not _path_under_models(path):
        return None
    return path


def _preset_install_state(preset_id: str) -> dict:
    files = PRESET_FILES.get(preset_id, [])
    have = 0
    for url, folder, custom in files:
        path = _expected_preset_file_path(url, folder, custom)
        if path and os.path.isfile(path) and os.path.getsize(path) > 0:
            have += 1
    total = len(files)
    if total > 0 and have == total:
        state = "full"
    elif have > 0:
        state = "partial"
    else:
        state = "none"
    return {"have": have, "total": total, "state": state}


@app.get("/installed")
def installed():
    """Installed preset files status (read-only)."""
    return {preset_id: _preset_install_state(preset_id) for preset_id in PRESET_FILES}


@app.get("/tokens/status")
def tokens_status():
    """Whether HF/CivitAI tokens are saved (values never returned)."""
    return tokens_saved_status()


@app.get("/", response_class=HTMLResponse)
def index():
    presets_html = generate_presets_html()
    category_filters_html = generate_category_filters_html()
    return HTMLResponse(INDEX_HTML.replace("{{ presets_html }}", presets_html)
                       .replace("{{ category_filters_html }}", category_filters_html)
                       .replace("{{ hf_repo_value }}", "")
                       .replace("{{ hf_file_value }}", "")
                       .replace("{{ hf_result }}", ""))

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Preset downloader is running"}

@app.get("/status/{task_id}")
def get_status(task_id: str):
    if task_id not in download_status:
        return {"status": "not_found", "message": "Задача не найдена"}
    
    return download_status[task_id]


@app.get("/api/tasks")
def get_all_tasks():
    """Get all download tasks (for dashboard integration)."""
    _trim_download_status()
    # Filter to show only active/recent tasks
    active_tasks = []
    for task_id, status in download_status.items():
        task_info = {
            "task_id": task_id,
            **status
        }
        active_tasks.append(task_info)
    
    # Sort by most recent (running first, then completed)
    def sort_key(t):
        s = t.get("status", "")
        if s == "running":
            return 0
        elif s == "completed":
            return 1
        elif s == "error":
            return 2
        return 3
    
    active_tasks.sort(key=sort_key)
    return {"tasks": active_tasks[:20]}  # Limit to 20 most recent


def _collect_preset_urls(presets_list: list[str]) -> list[str]:
    urls = []
    for preset_id in presets_list:
        if preset_id in PRESET_FILES:
            for url, _folder, _custom_filename in PRESET_FILES[preset_id]:
                urls.append(url)
    return urls


@app.post("/download_presets")
def download_presets(presets: str = Form(...), force: str = Form("0")):
    try:
        # Парсим строку пресетов
        presets_list = [p.strip() for p in presets.split(',') if p.strip()]
        
        if not presets_list:
            return {"message": "❌ Не выбрано ни одного пресета"}

        force_download = force.strip().lower() in ("1", "true", "yes")
        if not force_download:
            urls = _collect_preset_urls(presets_list)
            needed_bytes = estimate_size(urls)
            disk_warning = check_disk_space(needed_bytes, force=False)
            if disk_warning:
                return disk_warning
        
        # Запускаем скрипт скачивания пресетов в фоне
        import threading
        import uuid
        
        # Создаем уникальный ID для отслеживания
        task_id = str(uuid.uuid4())
        _trim_download_status()
        
        def download_file_with_progress(url, dest_dir, custom_filename, current_file, total_files, task_id):
            """Скачивает файл с отслеживанием прогресса в реальном времени, как в LoRA загрузчике"""
            import re
            
            # Определяем имя файла
            if custom_filename:
                filename = sanitize_filename(custom_filename)
            else:
                url_name = url.split('?')[0] if '?' in url else url
                filename = sanitize_filename(os.path.basename(url_name))

            if not filename:
                return "FAILED", custom_filename or url

            filepath = os.path.join(dest_dir, filename)
            if not _path_under_models(filepath):
                return "FAILED", filename
            os.makedirs(dest_dir, exist_ok=True)

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            _, expected_size = probe_url(url, headers=headers)

            # Проверяем, существует ли файл
            if os.path.isfile(filepath) and os.path.getsize(filepath) > 0:
                if expected_size <= 0 or os.path.getsize(filepath) == expected_size:
                    download_status[task_id] = {
                        "status": "running",
                        "message": f"⏭️ Пропущено (уже существует): {filename} ({current_file}/{total_files})",
                        "progress": (current_file / total_files * 100),
                        "total_files": total_files,
                        "current_file": current_file,
                        "current_filename": filename
                    }
                    return "SKIP", filename
            
            # Обновляем статус - начало скачивания
            download_status[task_id] = {
                "status": "running",
                "message": f"📥 Скачивание файла {current_file} из {total_files}: {filename} (0%)",
                "progress": ((current_file - 1) / total_files * 100),
                "total_files": total_files,
                "current_file": current_file,
                "current_filename": filename
            }
            
            try:
                def on_progress(pct):
                    if expected_size > 0:
                        file_percent = pct
                        overall_progress = ((current_file - 1) / total_files * 100) + (file_percent / total_files)
                        download_status[task_id] = {
                            "status": "running",
                            "message": f"📥 Скачивание файла {current_file} из {total_files}: {filename} ({file_percent}%)",
                            "progress": min(overall_progress, 100),
                            "total_files": total_files,
                            "current_file": current_file,
                            "current_filename": filename
                        }
                    else:
                        size_mb = os.path.getsize(filepath) / (1024 * 1024) if os.path.isfile(filepath) else 0
                        download_status[task_id] = {
                            "status": "running",
                            "message": f"📥 Скачивание файла {current_file} из {total_files}: {filename} ({size_mb:.1f} MB)",
                            "progress": ((current_file - 1) / total_files * 100) + 0.1,
                            "total_files": total_files,
                            "current_file": current_file,
                            "current_filename": filename
                        }

                fetch(url, filepath, on_progress=on_progress, headers=headers)
                
                # Финальное обновление - файл скачан
                download_status[task_id] = {
                    "status": "running",
                    "message": f"✅ Завершено: {filename} ({current_file}/{total_files})",
                    "progress": (current_file / total_files * 100),
                    "total_files": total_files,
                    "current_file": current_file,
                    "current_filename": filename
                }
                
                return "DOWNLOADED", filename
                
            except Exception as e:
                # Удаляем частично скачанный файл
                if os.path.exists(filepath):
                    os.remove(filepath)
                
                download_status[task_id] = {
                    "status": "running",
                    "message": f"❌ Ошибка скачивания: {filename} ({current_file}/{total_files}) - {str(e)[:100]}",
                    "progress": ((current_file - 1) / total_files * 100),
                    "total_files": total_files,
                    "current_file": current_file,
                    "current_filename": filename
                }
                return "FAILED", filename
        
        def run_download():
            try:
                # Собираем все файлы для скачивания
                all_files = []
                for preset_id in presets_list:
                    if preset_id in PRESET_FILES:
                        all_files.extend(PRESET_FILES[preset_id])
                
                total_files = len(all_files)
                
                # Инициализируем статус
                download_status[task_id] = {
                    "status": "running",
                    "message": f"🚀 Начато скачивание пресетов: {', '.join(presets_list)}\n📦 Всего файлов: {total_files}",
                    "progress": 0,
                    "total_files": total_files,
                    "current_file": 0,
                    "current_filename": ""
                }
                
                # Списки для итоговой сводки
                downloaded_files = []
                skipped_files = []
                failed_files = []
                
                # Скачиваем каждый файл
                for idx, (url, folder, custom_filename) in enumerate(all_files, 1):
                    dest_dir, dir_err = resolve_models_dir(folder)
                    if dir_err:
                        failed_files.append(f"{folder}: {dir_err}")
                        continue
                    result, filename = download_file_with_progress(
                        url, dest_dir, custom_filename, idx, total_files, task_id
                    )
                    
                    if result == "DOWNLOADED":
                        downloaded_files.append(filename)
                    elif result == "SKIP":
                        skipped_files.append(filename)
                    elif result == "FAILED":
                        failed_files.append(filename)
                
                # Формируем итоговую сводку
                summary_parts = []
                summary_parts.append(f"✅ Скачивание пресетов завершено: {', '.join(presets_list)}")
                summary_parts.append("")
                
                if downloaded_files:
                    summary_parts.append(f"📥 Скачано файлов: {len(downloaded_files)}")
                    for filename in downloaded_files[:10]:  # Показываем первые 10
                        summary_parts.append(f"   ✅ {filename}")
                    if len(downloaded_files) > 10:
                        summary_parts.append(f"   ... и еще {len(downloaded_files) - 10} файлов")
                    summary_parts.append("")
                
                if skipped_files:
                    summary_parts.append(f"⏭️ Пропущено (уже существуют): {len(skipped_files)}")
                    for filename in skipped_files[:10]:  # Показываем первые 10
                        summary_parts.append(f"   ⏭️ {filename}")
                    if len(skipped_files) > 10:
                        summary_parts.append(f"   ... и еще {len(skipped_files) - 10} файлов")
                    summary_parts.append("")
                
                if failed_files:
                    summary_parts.append(f"❌ Ошибки при скачивании: {len(failed_files)}")
                    for filename in failed_files:
                        summary_parts.append(f"   ❌ {filename}")
                    summary_parts.append("")
                
                summary_message = "\n".join(summary_parts)
                
                if failed_files:
                    download_status[task_id] = {
                        "status": "error",
                        "message": summary_message,
                        "progress": 100,
                        "total_files": total_files,
                        "current_file": total_files,
                        "current_filename": ""
                    }
                else:
                    download_status[task_id] = {
                        "status": "completed",
                        "message": summary_message,
                        "progress": 100,
                        "total_files": total_files,
                        "current_file": total_files,
                        "current_filename": ""
                    }
            except Exception as e:
                download_status[task_id] = {
                    "status": "error",
                    "message": f"❌ Ошибка: {str(e)}",
                    "progress": download_status[task_id].get("progress", 0),
                    "total_files": download_status[task_id].get("total_files", 0),
                    "current_file": download_status[task_id].get("current_file", 0),
                    "current_filename": download_status[task_id].get("current_filename", "")
                }
        
        # Запускаем в отдельном потоке
        thread = threading.Thread(target=run_download)
        thread.daemon = True
        thread.start()
        
        # Сохраняем статус
        download_status[task_id] = {
            "status": "running",
            "message": f"🚀 Начато скачивание пресетов: {', '.join(presets_list)}"
        }
        
        return {"message": f"🚀 Скачивание начато! ID задачи: {task_id}", "task_id": task_id}
            
    except Exception as e:
        return {"message": f"❌ Ошибка: {str(e)}"}

@app.post("/download_hf")
def download_hf(
    repo: str = Form(...),
    filename: str = Form(""),
    token: str = Form(""),
    folder: str = Form("diffusion_models"),
    revision: str = Form("main"),
):
    try:
        form_token = (token or "").strip()
        effective_token = resolve_token("hf", form_token)

        target_dir, dir_err = resolve_models_dir(folder)
        if dir_err:
            return {"message": dir_err}

        hf_revision = (revision or "main").strip() or "main"

        safe_filename = None
        file_path = None
        if filename:
            file_path, safe_filename, file_err = resolve_hf_file_path(folder, filename)
            if file_err:
                return {"message": file_err}

        # Создаем уникальный ID для отслеживания
        task_id = str(uuid.uuid4())
        _trim_download_status()
        
        def run_hf_download():
            try:
                if safe_filename:
                    # Скачиваем конкретный файл с прогрессом
                    hf_url = f"https://huggingface.co/{repo}/resolve/{hf_revision}/{safe_filename}"
                    
                    # Обновляем статус - начало скачивания
                    download_status[task_id] = {
                        "status": "running",
                        "message": f"📥 Подключение к HuggingFace...",
                        "progress": 0
                    }
                    
                    # Подготавливаем заголовки
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                    probe_headers = dict(headers)
                    if effective_token:
                        probe_headers['Authorization'] = f'Bearer {effective_token}'
                    _, expected_size = probe_url(hf_url, headers=probe_headers)

                    def on_progress(pct):
                        size_mb = os.path.getsize(file_path) / (1024 * 1024) if os.path.isfile(file_path) else 0
                        if expected_size > 0:
                            total_mb = expected_size / (1024 * 1024)
                            download_status[task_id] = {
                                "status": "running",
                                "message": f"📥 Скачивание: {safe_filename} ({pct}%) - {size_mb:.1f} MB / {total_mb:.1f} MB",
                                "progress": pct
                            }
                        else:
                            download_status[task_id] = {
                                "status": "running",
                                "message": f"📥 Скачивание: {safe_filename} ({size_mb:.1f} MB)",
                                "progress": pct if pct > 0 else 0
                            }

                    fetch(hf_url, file_path, on_progress=on_progress, token=effective_token, headers=headers)
                    
                    # Финальное обновление
                    size_mb = os.path.getsize(file_path) / (1024 * 1024)
                    success_msg = f"✅ Успешно загружено!\n📁 Файл: {safe_filename}\n💾 Размер: {size_mb:.1f} MB\n📂 Путь: {target_dir}"
                    
                    download_status[task_id] = {
                        "status": "completed",
                        "message": success_msg,
                        "progress": 100
                    }
                    if form_token:
                        save_token("hf", form_token)
                else:
                    # Скачиваем весь репозиторий (используем huggingface_hub, так как это сложнее)
                    download_status[task_id] = {
                        "status": "running",
                        "message": f"📥 Скачивание всего репозитория {repo}...",
                        "progress": 0
                    }
                    
                    # Если есть токен, логинимся
                    if effective_token:
                        login(token=effective_token)
                    
                    from huggingface_hub import snapshot_download
                    snapshot_download(
                        repo_id=repo,
                        revision=hf_revision,
                        local_dir=target_dir,
                    )
                    
                    success_msg = f"✅ Успешно загружено!\n📁 Репозиторий: {repo}\n📂 Путь: {target_dir}"
                    
                    download_status[task_id] = {
                        "status": "completed",
                        "message": success_msg,
                        "progress": 100
                    }
                    if form_token:
                        save_token("hf", form_token)
                
            except Exception as e:
                error_msg = f"❌ Ошибка: {str(e)}"
                
                # Если ошибка связана с токеном, предлагаем его ввести
                if "authentication" in str(e).lower() or "token" in str(e).lower() or "401" in str(e):
                    error_msg += "\n\n💡 Попробуйте ввести API токен HuggingFace"
                
                download_status[task_id] = {
                    "status": "error",
                    "message": error_msg,
                    "progress": download_status[task_id].get("progress", 0)
                }
        
        # Запускаем в отдельном потоке
        thread = threading.Thread(target=run_hf_download)
        thread.daemon = True
        thread.start()
        
        # Сохраняем статус
        download_status[task_id] = {
            "status": "running",
            "message": f"🚀 Начато скачивание с HuggingFace: {repo}",
            "progress": 0
        }
        
        return {"message": f"🚀 Скачивание начато! ID задачи: {task_id}", "task_id": task_id}
        
    except Exception as e:
        return {"message": f"❌ Ошибка: {str(e)}"}

@app.post("/download_url")
def download_url(url: str = Form(...), folder: str = Form("diffusion_models")):
    try:
        _, dir_err = resolve_models_dir(folder)
        if dir_err:
            return {"message": dir_err}

        # Создаем уникальный ID для отслеживания
        task_id = str(uuid.uuid4())
        _trim_download_status()
        
        def run_url_download():
            try:
                target_dir, dir_err = resolve_models_dir(folder)
                if dir_err:
                    download_status[task_id] = {
                        "status": "error",
                        "message": dir_err,
                        "progress": 0,
                    }
                    return
                
                # Скачиваем файл по прямой ссылке с отслеживанием прогресса
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                # Обновляем статус - начало скачивания
                download_status[task_id] = {
                    "status": "running",
                    "message": f"📥 Подключение к серверу...",
                    "progress": 0
                }

                import re
                import urllib.parse

                filename = url.split('/')[-1]
                if '?' in filename:
                    filename = filename.split('?')[0]

                try:
                    head = requests.head(url, headers=headers, timeout=30, allow_redirects=True)
                    if head.ok and 'content-disposition' in head.headers:
                        import urllib.parse
                        content_disposition = head.headers['content-disposition']
                        utf8_match = re.search(r"filename\*=UTF-8''([^;]+)", content_disposition)
                        if utf8_match:
                            filename = urllib.parse.unquote(utf8_match.group(1))
                        else:
                            filename_match = re.search(
                                r'filename[^;=\n]*=(([\'"]).*?\2|[^;\n]*)',
                                content_disposition,
                            )
                            if filename_match:
                                filename = filename_match.group(1).strip('\'"')
                except Exception:
                    pass

                if not filename or '.' not in filename:
                    filename = "downloaded_file"

                file_path, safe_filename, file_err = resolve_models_file(folder, filename)
                if file_err:
                    download_status[task_id] = {
                        "status": "error",
                        "message": file_err,
                        "progress": 0,
                    }
                    return
                filename = safe_filename

                _, expected_size = probe_url(url, headers=headers)

                def on_progress(pct):
                    size_mb = os.path.getsize(file_path) / (1024 * 1024) if os.path.isfile(file_path) else 0
                    if expected_size > 0:
                        total_mb = expected_size / (1024 * 1024)
                        download_status[task_id] = {
                            "status": "running",
                            "message": f"📥 Скачивание: {filename} ({pct}%) - {size_mb:.1f} MB / {total_mb:.1f} MB",
                            "progress": pct
                        }
                    else:
                        download_status[task_id] = {
                            "status": "running",
                            "message": f"📥 Скачивание: {filename} ({size_mb:.1f} MB)",
                            "progress": pct if pct > 0 else 0
                        }

                fetch(url, file_path, on_progress=on_progress, headers=headers)
                
                # Финальное обновление
                size_mb = os.path.getsize(file_path) / (1024 * 1024)
                success_msg = f"✅ Успешно загружено!\n🔗 Ссылка: {url}\n📄 Файл: {filename}\n💾 Размер: {size_mb:.1f} MB\n📂 Путь: {target_dir}"
                
                download_status[task_id] = {
                    "status": "completed",
                    "message": success_msg,
                    "progress": 100
                }
                
            except Exception as e:
                error_msg = f"❌ Ошибка: {str(e)}"
                download_status[task_id] = {
                    "status": "error",
                    "message": error_msg,
                    "progress": download_status[task_id].get("progress", 0)
                }
        
        # Запускаем в отдельном потоке
        thread = threading.Thread(target=run_url_download)
        thread.daemon = True
        thread.start()
        
        # Сохраняем статус
        download_status[task_id] = {
            "status": "running",
            "message": f"🚀 Начато скачивание по ссылке: {url}",
            "progress": 0
        }
        
        return {"message": f"🚀 Скачивание начато! ID задачи: {task_id}", "task_id": task_id}
        
    except Exception as e:
        return {"message": f"❌ Ошибка: {str(e)}"}
