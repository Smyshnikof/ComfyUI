---
name: add-node-preset
description: >-
  Добавляет пресет набора custom nodes в ComfyUI installer через JSON-манифест.
  Используй, когда просят добавить новый набор нод, репозиторий в bundle, или обновить node_presets/manifest/.
---

# Добавление пресета custom nodes

## Где живёт логика

| Что | Файл / папка |
|-----|----------------|
| JSON манифесты (встроенные) | `node_presets/manifest/<ID>.json` |
| Community drop-in | `{DATA_DIR}/node_presets/community/*.json` |
| Категории | `node_presets/categories.json` |
| Лоадер + валидация | `services/_node_presets.py` |
| Установка git/pip | `services/_node_installer.py` |
| UI / API | `services/custom_nodes_installer.py` |
| Проверка JSON | `python scripts/validate_node_presets.py` |

## Формат манифеста (schema 1)

```json
{
  "schema": 1,
  "id": "WAN_VIDEO",
  "name": "Wan Video",
  "description": "Ноды для Wan workflows",
  "category": "Wan",
  "repos": [
    {
      "url": "https://github.com/kijai/ComfyUI-WanVideoWrapper.git",
      "branch": null,
      "recursive": true,
      "folder": null
    }
  ],
  "check_nodes": ["SomeNodeClassName"]
}
```

- `url` — только `https://github.com/...`
- `folder` — опционально, имя папки в `custom_nodes/`
- `check_nodes` — опционально, class names для проверки через ComfyUI `/object_info`
- `category` — ключ из `node_presets/categories.json`
- Share-коды: `CUNP1:ref:WAN_VIDEO` (builtin) / `CUNP1:z:...` (community)

## ComfyUI-Manager security_level

Файл: `ComfyUI/user/__manager/config.ini` (или legacy пути — см. `services/_manager_config.py`).

В UI установщика (8085) или API:
- `GET /api/manager-config`
- `POST /api/manager-config/security-level` с `level=weak`

## Встроенные наборы

| ID | Описание |
|----|----------|
| `FULL_STACK` | Все URL из `custom_nodes.txt` |
| `BASE_STACK` | URL из `custom_nodes_base.txt` |
| `WAN_VIDEO`, `QWEN_SUITE`, … | Тематические наборы |

## После изменений

```bash
python scripts/validate_node_presets.py
```

В UI: кнопка «Обновить» в модале или `POST /reload_presets` на порту 8085.
