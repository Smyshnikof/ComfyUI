---
name: add-model-preset
description: >-
  Добавляет пресет модели в ComfyUI RunPod downloader (PRESET_FILES + PRESETS UI).
  Используй, когда просят добавить новую модель/пресет, вариант существующего пресета,
  или обновить ссылки на HuggingFace/Civitai в preset_downloader.
---

# Добавление пресета модели

## Где живёт логика

| Что | Файл |
|-----|------|
| URL → папка models/* | `services/preset_downloader.py` → `PRESET_FILES` |
| Карточка в UI | `services/preset_downloader.py` → `PRESETS` |
| Категория (фильтр) | `services/preset_downloader.py` → `CATEGORIES` |
| Проверка ссылок | `scripts/check_links.py` (HEAD по всем URL из `PRESET_FILES`) |

UI рендерится из `PRESETS` автоматически (`generate_presets_html()`). Отдельный HTML/JS править не нужно, если только не меняется поведение фронта.

`scripts/download_presets.sh` — **legacy**, только старые Wan-пресеты. Новые пресеты добавлять **только** в Python.

## Формат PRESET_FILES

Ключ — ID пресета (UPPER_SNAKE_CASE). Значение — список кортежей:

```python
"PRESET_ID": [
    ("https://huggingface.co/<org>/<repo>/resolve/main/<path>/<file>.safetensors", "diffusion_models", None),
    ("https://huggingface.co/.../text_encoders/<file>.safetensors", "text_encoders", None),
    ("https://huggingface.co/.../vae/<file>.safetensors", "vae", None),
],
```

Третий элемент — `custom_filename` или `None` (имя берётся из URL).

### Допустимые папки (`folder`)

`diffusion_models`, `loras`, `vae`, `text_encoders`, `upscale_models`, `checkpoints`, `clip_vision`, `controlnet`, `detection`, … — полный список в `ALLOWED_MODEL_FOLDERS` в том же файле.

### URL HuggingFace

Предпочитай прямые resolve-ссылки:

```
https://huggingface.co/<org>/<repo>/resolve/main/<path>/<filename>
```

Для split_files из Comfy-Org / circlestone-labs часто путь вида `split_files/diffusion_models/...`.

## Формат PRESETS

### Простой пресет (без вариантов)

```python
"WAN_T2I": {
    "name": "Wan T2I (Text-to-Image)",
    "description": "Генерация изображений из текста",
    "size": "~18GB",
    "time": "8-12 мин",
    "category": "Wan",
    "video_guide": "https://youtu.be/...",  # опционально
},
```

ID в `PRESETS` = ключ в `PRESET_FILES`.

### Пресет с вариантами

Родительская карточка — один ключ в `PRESETS`. Каждый вариант — **отдельный** ключ в `PRESET_FILES`:

```python
"ANIMA": {
    "name": "Anima",
    "description": "Генерация изображений (circlestone-labs / Qwen-бэкенд)",
    "size": "~6GB на вариант",
    "time": "5-10 мин",
    "category": "Anima",
    "has_variants": True,
    "variant_groups": {
        "Версия модели": {
            "ANIMA_BASE": {"name": "base v1.0 (релизная)", "size": "~6GB", "time": "5-10 мин"},
            "ANIMA_PREVIEW": {"name": "preview (исходная)", "size": "~6GB", "time": "5-10 мин"},
        }
    },
},
```

Пользователь выбирает чекбоксы вариантов → в `/download_presets` уходит `ANIMA_BASE`, не `ANIMA`.

### Общие файлы между вариантами

Если у вариантов один text_encoder/vae, а отличается только diffusion — **дублируй общие URL в каждом варианте**. Downloader пропускает уже существующие файлы (skip by size).

## Новая категория

Если `category` ещё нет в `CATEGORIES`:

```python
"Anima": {
    "name": "Anima",
    "icon": "✨",
    "color": "#c084fc"
},
```

## Чеклист после добавления

1. **ID согласованы**: каждый ключ из `variant_groups` есть в `PRESET_FILES`.
2. **Размер/время**: оцени через HEAD (`X-Linked-Size` на HF) или суммируй файлы; округляй до «~N GB».
3. **Проверка ссылок**:
   ```bash
   python scripts/check_links.py
   ```
4. **Не трогай** `download_presets.sh`, README и GUIDE — только если явно просят обновить документацию.

## Пример: Anima base v1.0

Запрос: base diffusion + общие encoder/vae.

```python
# PRESET_FILES
"ANIMA_BASE": [
    ("https://huggingface.co/circlestone-labs/Anima/resolve/main/split_files/diffusion_models/anima-base-v1.0.safetensors", "diffusion_models", None),
    ("https://huggingface.co/circlestone-labs/Anima/resolve/main/split_files/text_encoders/qwen_3_06b_base.safetensors", "text_encoders", None),
    ("https://huggingface.co/circlestone-labs/Anima/resolve/main/split_files/vae/qwen_image_vae.safetensors", "vae", None),
],
```

Скачивание в UI: карточка **Anima** → чекбокс **base v1.0 (релизная)** → «Скачать выбранные».

Или env/CLI (если вызывается API): `presets=ANIMA_BASE`.

## Именование ID

| Паттерн | Пример |
|---------|--------|
| Семейство | `ANIMA`, `QWEN_IMAGE`, `WAN_T2V` |
| Вариант | `ANIMA_BASE`, `QWEN_IMAGE_FP8`, `WAN_T2V_LIGHTNING` |
| UPPER_SNAKE_CASE | всегда |

Не используй пробелы, кириллицу или дефисы в ID — только в `name` для UI.
