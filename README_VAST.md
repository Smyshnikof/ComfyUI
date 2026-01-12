# ComfyUI для Vast.ai

> 🎥 **Template основан на серии роликов по Wan 2.2** от [Егор Смышников Плейлист](https://www.youtube.com/playlist?list=PLUREBJZfEOoPztQiVSV7vYegAsOtwMiZi)

## 🔌 Открытые порты

| Порт | Тип | Сервис |
| ---- | ---- | ----------- |
| 22   | TCP  | SSH         |
| 3000 | HTTP | ComfyUI     |
| 8080 | HTTP | Code Server |
| 8081 | HTTP | Загрузчик пресетов и моделей |
| 8082 | HTTP | CivitAI LoRA downloader |
| 8083 | HTTP | Обзор и скачивание output |
| 8888 | HTTP | JupyterLab  |

---

## 🏷️ Формат тегов

```text
smyshnikof/comfyui:vast-base-torch2.8.0-cu128
```

* **vast**: Префикс для Vast.ai версий
* **base**: ComfyUI + Manager + кастомные ноды + веб-загрузчик пресетов
* **torch2.8.0**: PyTorch версия
* **cu128**: CUDA версия (cu124, cu126, cu128)

---

## 🧱 Варианты образов

| Имя образа                                       | Кастомные ноды | Веб-загрузчик | CUDA | Базовый образ |
| ------------------------------------------------ | -------------- | ------------- | ---- | ------------- |
| `smyshnikof/comfyui:vast-base-torch2.8.0-cu124` | ✅ Да          | ✅ Да         | 12.4 | nvidia/cuda:12.4.1-devel-ubuntu22.04 |
| `smyshnikof/comfyui:vast-base-torch2.8.0-cu126` | ✅ Да          | ✅ Да         | 12.6 | nvidia/cuda:12.6.3-devel-ubuntu24.04 |
| `smyshnikof/comfyui:vast-base-torch2.8.0-cu128` | ✅ Да          | ✅ Да         | 12.8 | nvidia/cuda:12.8.1-devel-ubuntu24.04 |

> 👉 Для переключения: **Edit Template** → установите `Image Path:Tag`.

---

## ⚙️ Переменные окружения

| Переменная                | Описание                                                                | По умолчанию   |
| ------------------------- | ----------------------------------------------------------------------- | -------------- |
| `ACCESS_PASSWORD`         | Пароль для JupyterLab & code-server                                    | (авто)         |
| `TIME_ZONE`               | [Часовой пояс](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) (например, `Asia/Seoul`) | `Etc/UTC`      |
| `INSTALL_SAGEATTENTION`   | Установить SageAttention2 (true/false)                                 | `false`        |
| `INSTALL_CUSTOM_NODES`    | Установить дополнительные кастомные ноды (true/false)                 | `false`        |
| `PUBLIC_KEY`              | SSH публичный ключ для доступа                                         | (не установлен)|

---

## 🚀 Сборка образов

### Локальная сборка

```bash
# Сборка всех версий CUDA
docker buildx bake -f docker-bake.vast.hcl

# Сборка конкретной версии
docker buildx bake -f docker-bake.vast.hcl vast-12-4
docker buildx bake -f docker-bake.vast.hcl vast-12-6
docker buildx bake -f docker-bake.vast.hcl vast-12-8
```

### Публикация на Docker Hub

```bash
# Вход в Docker Hub
docker login

# Сборка и публикация
docker buildx bake -f docker-bake.vast.hcl --push
```

---

## 📋 Использование на Vast.ai

### 1. Создание Template

1. Перейдите в раздел **Templates** на Vast.ai
2. Нажмите **Create Template**
3. В поле **Image Path:Tag** укажите один из образов:
   - `smyshnikof/comfyui:vast-base-torch2.8.0-cu124`
   - `smyshnikof/comfyui:vast-base-torch2.8.0-cu126`
   - `smyshnikof/comfyui:vast-base-torch2.8.0-cu128`

### 2. Настройка PORTAL_CONFIG

Образ уже настроен с `PORTAL_CONFIG` для автоматического создания ссылок в Instance Portal:

```
localhost:3000:3000:/:ComfyUI
localhost:8081:8081:/:Preset Downloader
localhost:8082:8082:/:CivitAI LoRA Downloader
localhost:8083:8083:/:Outputs Browser
localhost:8888:8888:/:JupyterLab
localhost:8080:8080:/:Code Server
```

Если нужно изменить конфигурацию, добавьте переменную окружения `PORTAL_CONFIG` в Template.

### 3. Переменные окружения (опционально)

В разделе **Environment Variables** Template можно добавить:

- `ACCESS_PASSWORD` - пароль для JupyterLab и code-server
- `TIME_ZONE` - часовой пояс (например, `Europe/Moscow`)
- `INSTALL_SAGEATTENTION=true` - для установки SageAttention2
- `INSTALL_CUSTOM_NODES=true` - для установки дополнительных кастомных нод
- `PUBLIC_KEY` - ваш SSH публичный ключ

### 4. Настройка Launch Mode

**ВАЖНО:** Выберите режим запуска **"Docker ENTRYPOINT"** (не "Jupyter-python notebook + SSH")!

Наш образ использует собственный скрипт запуска `/start.sh`, который запускает все сервисы:
- ComfyUI на порту 3000
- Preset Downloader на порту 8081
- CivitAI LoRA Downloader на порту 8082
- Outputs Browser на порту 8083
- JupyterLab на порту 8888
- Code Server на порту 8080

### 5. Запуск Instance

1. Выберите созданный Template
2. Выберите подходящий GPU
3. **Убедитесь, что выбран режим "Docker ENTRYPOINT"**
4. Нажмите **Create Instance**
5. После запуска откройте Instance Portal для доступа к сервисам

---

## 📁 Структура директорий

### Рабочая директория

Vast.ai использует `/opt/workspace-internal/` для постоянного хранения данных:

```
/opt/workspace-internal/
├── ComfyUI/              # ComfyUI и все модели
│   ├── models/
│   ├── custom_nodes/
│   └── user/
│       └── default/
│           └── workflows/ # Workflow файлы (wan, qwen, snippets, zit)
├── .cache/                # Кэш (huggingface, pip, uv)
└── logs/                  # Логи сервисов
```

### Пресеты (Workflows)

Пресеты автоматически копируются из `/presets/` в `/opt/workspace-internal/ComfyUI/user/default/workflows/` с сохранением структуры папок:

- `wan/` - Workflows для Wan 2.2
- `qwen/` - Workflows для Qwen
- `snippets/` - Переиспользуемые компоненты
- `zit/` - Workflows для Z-Image Turbo

---

## 🌐 Веб-сервисы

После запуска инстанса доступны следующие веб-сервисы:

### ComfyUI
- **URL**: `http://<instance-ip>:3000` или через Instance Portal
- Основной интерфейс ComfyUI для генерации изображений

### Preset Downloader
- **URL**: `http://<instance-ip>:8081` или через Instance Portal
- Веб-интерфейс для скачивания пресетов и моделей:
  - Пресеты (Z Image Turbo, LTX-2, LTX-2 Distilled)
  - Прямое скачивание по URL
  - Скачивание с HuggingFace

### CivitAI LoRA Downloader
- **URL**: `http://<instance-ip>:8082` или через Instance Portal
- Скачивание LoRA моделей с CivitAI по URL

### Outputs Browser
- **URL**: `http://<instance-ip>:8083` или через Instance Portal
- Просмотр и скачивание сгенерированных изображений

### JupyterLab
- **URL**: `http://<instance-ip>:8888` или через Instance Portal
- Интерактивная среда разработки

### Code Server
- **URL**: `http://<instance-ip>:8080` или через Instance Portal
- VS Code в браузере

---

## 🔧 Дополнительные возможности

### Установка SageAttention2

Добавьте переменную окружения `INSTALL_SAGEATTENTION=true` в Template. Установка займет ~5 минут при первом запуске.

### Установка дополнительных кастомных нод

Добавьте переменную окружения `INSTALL_CUSTOM_NODES=true` в Template. Это запустит скрипт `/install_custom_nodes.sh`.

### Использование PROVISIONING_SCRIPT (альтернатива)

Вместо использования готового образа можно использовать базовый образ Vast.ai и добавить `PROVISIONING_SCRIPT`:

1. Создайте Template с базовым образом `vastai/pytorch:2.6.0-cuda-12.6.3-py312`
2. Добавьте переменную окружения `PROVISIONING_SCRIPT` со ссылкой на скрипт настройки
3. Скрипт должен устанавливать ComfyUI, кастомные ноды и настраивать сервисы

---

## 📚 Дополнительная документация

- [Vast.ai Templates Documentation](https://docs.vast.ai/documentation/templates/advanced-setup)
- [ComfyUI Official Documentation](https://github.com/comfy-org/ComfyUI)
- [ComfyUI Manager](https://github.com/ltdrdata/ComfyUI-Manager)

---

## 🐛 Решение проблем

### Ошибка: `cat: /var/lib/vastai_kaalia/data/instance_extra_logs/...: No such file or directory`

**Решение:** Убедитесь, что выбран режим запуска **"Docker ENTRYPOINT"** вместо "Jupyter-python notebook + SSH".

Наш образ использует собственный скрипт запуска, поэтому режим Jupyter не подходит.

### ComfyUI не запускается

Проверьте логи:
```bash
cat /opt/workspace-internal/logs/comfyui.log
```

Или через SSH:
```bash
# Подключитесь по SSH и проверьте процессы
ps aux | grep comfyui
```

### Пресеты не копируются

Убедитесь, что папка `/presets` существует в образе. Проверьте логи pre_start:
```bash
# В логах должно быть сообщение о копировании пресетов
tail -f /opt/workspace-internal/logs/*.log
```

### Проблемы с доступом через Instance Portal

Проверьте, что `PORTAL_CONFIG` правильно настроен. Можно переопределить его через переменную окружения в Template.

Если ссылки не появляются автоматически, добавьте переменную окружения `PORTAL_CONFIG` в Template с нужными портами.

---

## 📝 Примечания

- Все данные сохраняются в `/opt/workspace-internal/` и синхронизируются между инстансами
- Модели и кэш хранятся в `.cache/` внутри workspace
- Логи всех сервисов находятся в `logs/`
- При первом запуске может потребоваться время на синхронизацию venv и ComfyUI

---

**Создано для Vast.ai** | Основано на [ComfyUI](https://github.com/comfy-org/ComfyUI)

