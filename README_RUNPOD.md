> 🎥 **Template основан на серии роликов по Wan 2.2** от [Егор Смышников Плейлист](https://www.youtube.com/playlist?list=PLUREBJZfEOoPztQiVSV7vYegAsOtwMiZi)

## 🔌 Открытые порты

| Порт | Тип | Сервис |
| ---- | ---- | ----------- |
| 22   | TCP  | SSH         |
| 3000 | HTTP | ComfyUI     |
| 8081 | HTTP | Загрузчик пресетов и моделей |
| 8082 | HTTP | CivitAI LoRA downloader |
| 8083 | HTTP | Обзор и скачивание output |
| 8888 | HTTP | JupyterLab  |

---

## 🏷️ Формат тегов

```text
smyshnikof/comfyui:(A)-torch2.8.0-cu128
```

* **(A)**: тип образа
  * `full`: ComfyUI + Manager + все кастомные ноды + веб-загрузчик пресетов
  * `base`: ComfyUI + Manager + стабильные кастомные ноды + веб-загрузчик пресетов
  * `minimal`: ComfyUI + Manager без кастомных нод
* **torch2.8.0**: PyTorch версия
* **cu128**: CUDA версия (cu124, cu126, cu128, cu129, cu130, cu131, cu132, cu133)

---

## 🧱 Варианты образов

| Имя образа                                   | Кастомные ноды | Веб-загрузчик | CUDA |
| -------------------------------------------- | ------------ | ---- | ---- |
| `smyshnikof/comfyui:full-torch2.8.0-cu124`   | ✅ Все        | ✅ Да  | 12.4 |
| `smyshnikof/comfyui:full-torch2.8.0-cu126`   | ✅ Все        | ✅ Да  | 12.6 |
| `smyshnikof/comfyui:full-torch2.8.0-cu128`   | ✅ Все        | ✅ Да  | 12.8 |
| `smyshnikof/comfyui:base-torch2.8.0-cu124`   | ✅ Стабильные | ✅ Да  | 12.4 |
| `smyshnikof/comfyui:base-torch2.8.0-cu126`   | ✅ Стабильные | ✅ Да  | 12.6 |
| `smyshnikof/comfyui:base-torch2.8.0-cu128`   | ✅ Стабильные | ✅ Да  | 12.8 |
| `smyshnikof/comfyui:minimal-torch2.8.0-cu124`| ❌ Нет        | ✅ Да  | 12.4 |
| `smyshnikof/comfyui:minimal-torch2.8.0-cu126`| ❌ Нет        | ✅ Да  | 12.6 |
| `smyshnikof/comfyui:minimal-torch2.8.0-cu128`| ❌ Нет        | ✅ Да  | 12.8 |
| `smyshnikof/comfyui:base-torch2.8.0-cu130`   | ✅ Стабильные | ✅ Да  | 13.0 |
| `smyshnikof/comfyui:base-torch2.8.0-cu131`   | ✅ Стабильные | ✅ Да  | 13.1 |
| `smyshnikof/comfyui:base-torch2.8.0-cu132`   | ✅ Стабильные | ✅ Да  | 13.2 |
| `smyshnikof/comfyui:base-torch2.8.0-cu133`   | ✅ Стабильные | ✅ Да  | 13.3 |

> 👉 Для переключения: **Edit Pod/Template** → установите `Container Image`.

---

## ⚙️ Переменные окружения

| Переменная                | Описание                                                                | По умолчанию   |
| ----------------------- | -------------------------------------------------------------------------- | --------- |
| `ACCESS_PASSWORD`       | Пароль для JupyterLab & code-server                                      | (авто)   |
| `TIME_ZONE`             | [Часовой пояс](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) (например, `Asia/Seoul`)   | `Etc/UTC` |
| `COMFYUI_EXTRA_ARGS`    | Дополнительные опции ComfyUI (например `--fast`)                        | --use-sage-attention   |
| `INSTALL_SAGEATTENTION` | Установить [SageAttention2](https://github.com/thu-ml/SageAttention) при запуске (`True`/`False`) | `True`    |

> 👉 Для установки: **Edit Pod/Template** → **Add Environment Variable** (Key/Value).

> ⚠️ SageAttention2 требует **GPU Ampere+** и ~5 минут для установки.

> 🎯 **Этот template идеально подходит для видеокарт 40 и 50 серии**

---

## 🚀 Быстрый старт

### 1. Выберите образ
> Типы: `full` (все ноды), `base` (стабильные), `minimal` (без кастомных нод).  
> В примерах ниже используется `base`.
```
# RTX 5090/5080
smyshnikof/comfyui:base-torch2.8.0-cu128

# RTX 4090/4080
smyshnikof/comfyui:base-torch2.8.0-cu126

# RTX 4070/3090/3080
smyshnikof/comfyui:base-torch2.8.0-cu124

# RunPod с CUDA 13.0 / 13.1 / 13.2 / 13.3
smyshnikof/comfyui:base-torch2.8.0-cu130
smyshnikof/comfyui:base-torch2.8.0-cu131
smyshnikof/comfyui:base-torch2.8.0-cu132
smyshnikof/comfyui:base-torch2.8.0-cu133
```

### 2. Запустите POD
- Дождитесь полной загрузки (~2-3 минуты)

### 3. Откройте загрузчик пресетов
```
https://your-pod-id-8081.proxy.runpod.net
```

### 4. Выберите и скачайте нужные пресеты
- **Wan T2V**: ~40GB (видео из текста)
- **Wan T2I**: ~18GB (изображений из текста)  
- **Wan I2V**: ~40GB (видео из изображения)
- **Wan Animate**: ~30GB (анимация изображений)
- **Wan FLF**: ~40GB (видео из первого и последнего кадра)

> **💡 Дополнительно**: Для пресетов T2V, I2V и FLF доступны экспериментальные Lightning LoRA модели для ускоренной генерации. Отметьте чекбокс "⚡ Дополнительно докачать экспериментальные Lightning LoRA" при выборе пресетов.

### 5. Откройте ComfyUI
```
https://your-pod-id-3000.proxy.runpod.net
```

---

## 🔧 Скачивание пресетов (Wan)

> **Рекомендуется**: Используйте веб-загрузчик (порт 8081) для удобного скачивания пресетов.

> **Альтернативно**: Можно вручную запустить скрипт в JupyterLab:

```bash
bash /download_presets.sh WAN_T2V,WAN_T2I,WAN_I2V,WAN_ANIMATE
```

### Wan пресеты (встроенные workflow)

- `WAN_T2V` - (~40GB)
- `WAN_T2I` - (~18GB)  
- `WAN_I2V` - (~40GB)
- `WAN_ANIMATE` - (~30GB)

---

## 📁 Логи

| Приложение         | Путь к логу                                   |
| ----------- | ------------------------------------------ |
| ComfyUI     | `/workspace/ComfyUI/user/comfyui_3000.log` |
| JupyterLab  | `/workspace/logs/jupyterlab.log`           |
| Preset Downloader | `/workspace/logs/preset_downloader.log` |
| CivitAI Downloader | `/workspace/logs/civitai_downloader.log` |
| Outputs Browser | `/workspace/logs/outputs_browser.log` |

---

## 🧩 Предустановленные компоненты

### Система

* **ОС**: Ubuntu 24.04 (22.02 для CUDA 12.4)
* **Python**: 3.13
* **Фреймворк**: [ComfyUI](https://github.com/comfyanonymous/ComfyUI) + [ComfyUI Manager](https://github.com/Comfy-Org/ComfyUI-Manager) + [JupyterLab](https://jupyter.org/)
* **Библиотеки**: PyTorch 2.8.0 (2.9.0 для CUDA 13.x), CUDA (12.4–13.3), Triton, [hf\_hub](https://huggingface.co/docs/huggingface_hub), [nvtop](https://github.com/Syllo/nvtop)

#### Кастомные ноды (в образе **base**)

Полный список: https://github.com/Smyshnikof/ComfyUIDocker/blob/main/custom_nodes.txt

---

## 🌐 Веб-сервисы

### Загрузчик пресетов и моделей (порт 8081)
- Скачивание пресетов Wan по нажатию кнопки
- Скачивание моделей с HuggingFace
- Поддержка API токенов для приватных репозиториев
- Выбор папки назначения для моделей

### CivitAI LoRA Downloader (порт 8082)
- Простой интерфейс для скачивания LoRA с CivitAI
- Введите API токен и URL модели
- Автоматически сохраняет в `/workspace/ComfyUI/models/loras`

### Обзор результатов (порт 8083)  
- Просмотр всех файлов из `/workspace/ComfyUI/output`
- Скачивание отдельных файлов или архива со всеми результатами
- Удобная навигация по папкам