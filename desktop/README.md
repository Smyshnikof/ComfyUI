# Smyshnikov ComfyUI Hub (Windows desktop)

Локальная **панель управления** — тот же принцип, что вкладка Connect на RunPod: ComfyUI, загрузчик пресетов, CivitAI, output.

## Быстрый старт

```bat
pip install -r requirements.txt
desktop\setup.bat
desktop\start.bat
```

Откроется **http://127.0.0.1:8084/** — Smyshnikov ComfyUI Hub.

Кнопка **«Запустить все»** поднимает ComfyUI (3000), загрузчик пресетов (8081), CivitAI (8082), обзор output (8083) и установщик custom nodes (8085).

**Сменить путь к ComfyUI** (переезд, ошибка при настройке):

- в панели: **«Изменить путь»** под блоком HTTP сервисов;
- или `desktop\configure.bat` (тот же мастер в консоли).

## Файлы в `desktop/`

| Файл | Назначение |
|------|------------|
| `start.bat` | Запуск панели управления |
| `setup.bat` | Первичная настройка пути |
| `configure.bat` | Смена пути позже (без запуска hub) |

## Конфиг `desktop/config.json`

| Поле | Описание |
|------|----------|
| `comfyui_path` | Папка ComfyUI |
| `hub_port` | Порт панели (8084) |
| `auto_start_services` | Запускать сервисы при старте лаунчера |
| `open_browser` | Открыть браузер на hub |

## Сборка

См. `desktop/build/build_portable.bat` и `build_installer.bat`.
