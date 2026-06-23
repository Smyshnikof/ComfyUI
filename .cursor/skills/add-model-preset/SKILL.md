---
name: add-model-preset
description: >-
  Добавляет пресет модели в ComfyUI RunPod downloader через JSON-манифест.
  Используй, когда просят добавить новую модель/пресет, вариант, или обновить URL в presets/manifest/.
---

# Добавление пресета модели (manifest)

## Где живёт логика

| Что | Файл / папка |
|-----|----------------|
| JSON манифесты (встроенные) | `presets/manifest/<ID>.json` |
| Community drop-in | `/workspace/presets/community/*.json` |
| Категории | `presets/categories.json` |
| Лоадер + валидация | `services/_presets.py` |
| UI / download | `services/preset_downloader.py` (читает `load_presets()`) |
| Проверка JSON | `python scripts/validate_presets.py` |
| Проверка URL | `python scripts/check_links.py` |
| Re-export (редко) | `python scripts/export_presets.py` |

`scripts/download_presets.sh` — **legacy**, не трогать.

## Формат манифеста (schema 1)

### Пресет без вариантов — один файл `presets/manifest/MY_ID.json`:

```json
{
  "schema": 1,
  "id": "IDEOGRAM_4",
  "name": "Ideogram 4.0",
  "description": "T2I ...",
  "category": "Ideogram",
  "size": "~36GB",
  "time": "15-25 мин",
  "files": [
    {"url": "https://huggingface.co/.../model.safetensors", "folder": "diffusion_models", "filename": null}
  ]
}
```

### Пресет с вариантами — файлы внутри каждого variant:

```json
{
  "schema": 1,
  "id": "ANIMA",
  "name": "Anima",
  "category": "Anima",
  "size": "~6GB на вариант",
  "time": "5-10 мин",
  "variant_groups": [
    {
      "group": "Версия модели",
      "variants": [
        {
          "id": "ANIMA_BASE",
          "name": "base v1.0",
          "size": "~6GB",
          "time": "5-10 мин",
          "files": [
            {"url": "https://huggingface.co/.../anima-base-v1.0.safetensors", "folder": "diffusion_models", "filename": null}
          ]
        }
      ]
    }
  ]
}
```

- `filename: null` — имя из URL
- `folder` — из `ALLOWED_MODEL_FOLDERS` в `_presets.py`
- `category` — ключ из `presets/categories.json`
- **Нельзя** одновременно `files` и `variant_groups`
- ID варианта = ключ для скачивания (как раньше `PRESET_FILES[variant_id]`)

## Новая категория

Добавить в `presets/categories.json`:

```json
"Ideogram": {"name": "Ideogram", "icon": "🎭", "color": "#6366f1"}
```

## Чеклист

1. Создать/обновить `presets/manifest/<ID>.json`
2. `python scripts/validate_presets.py` — exit 0
3. `python scripts/check_links.py` — для новых URL (долго)
4. ID вариантов уникальны глобально; не дублируют встроенные id

## Community (без коммита в репо)

Юзер кладёт JSON в `/workspace/presets/community/` или импортирует по URL в UI → **Обновить пресеты**.

## Именование

UPPER_SNAKE_CASE для `id` / variant `id`. Человекочитаемое — в `name`.
