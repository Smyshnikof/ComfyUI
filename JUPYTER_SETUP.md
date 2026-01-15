# 💻 Установка через JupyterLab - Рекомендуемый метод

> **Для всех пользователей**: Рекомендуемый способ установки с полным контролем

## 🎯 Когда использовать этот метод

- Хотите полный контроль над установкой
- Нужны только определенные пресеты
- Планируете кастомизацию
- Используете образ `minimal`
- **Рекомендуется для новичков** - чтобы понять как работает система

---

## 🚀 Пошаговая установка

### 1. Запустите POD с образом minimal
```
smyshnikof/comfyui:minimal-torch2.8.0-cu128
```

### 2. Откройте JupyterLab
```
https://your-pod-id-8888.proxy.runpod.net
```

### 3. Откройте терминал
- File → New → Terminal

### 4. Установите нужные пресеты

#### Все пресеты Wan
```bash
bash /download_presets.sh WAN_T2V,WAN_T2I,WAN_I2V,WAN_ANIMATE
```

#### Только определенные пресеты
```bash
# Только T2V и I2V
bash /download_presets.sh WAN_T2V,WAN_I2V

# Только Animate
bash /download_presets.sh WAN_ANIMATE
```

#### Тихий режим (без прогресс-бара)
```bash
bash /download_presets.sh --quiet WAN_T2V,WAN_I2I
```

### 5. Проверьте установку
```bash
# Проверить загруженные модели
ls -la /workspace/ComfyUI/models/diffusion_models/

# Проверить workflow
ls -la /workspace/ComfyUI/user/workflows/Wan/
```

### 6. Запустите ComfyUI
```bash
cd /ComfyUI
python main.py --listen 0.0.0.0 --port 3000
```

---

## 🔧 Дополнительные возможности

### Установка дополнительных кастомных нод
```bash
cd /ComfyUI/custom_nodes

# Пример: установка новой ноды
git clone https://github.com/username/node-name.git
cd node-name
pip install -r requirements.txt

# Перезапустить ComfyUI
pkill -f comfyui
cd /ComfyUI && python main.py --listen 0.0.0.0 --port 3000 &
```

### Скачивание дополнительных моделей
```bash
# Скачать модель в нужную папку
cd /workspace/ComfyUI/models/diffusion_models
wget "URL_TO_MODEL"

# Скачать LoRA
cd /workspace/ComfyUI/models/loras
wget "URL_TO_LORA"
```

### Настройка переменных окружения
```bash
# Установить переменную
export COMFYUI_EXTRA_ARGS="--fast --cpu"

# Сохранить в .bashrc
echo 'export COMFYUI_EXTRA_ARGS="--fast --cpu"' >> ~/.bashrc
```

---

## 📊 Мониторинг и отладка

### Проверка статуса
```bash
# Проверить запущенные процессы
ps aux | grep comfyui

# Проверить использование GPU
nvidia-smi

# Проверить логи
tail -f /workspace/ComfyUI/user/comfyui_3000.log
```

### Очистка и оптимизация
```bash
# Очистить кэш pip
rm -rf /workspace/.cache/pip/*

# Очистить кэш HuggingFace
rm -rf /workspace/.cache/huggingface/*

# Проверить свободное место
df -h
```

---

## 🐍 Python скрипты

### Создание собственных скриптов
```python
# В JupyterLab создайте новый Python notebook

# Проверка GPU
import torch
print(f"CUDA доступна: {torch.cuda.is_available()}")
print(f"Количество GPU: {torch.cuda.device_count()}")
print(f"Название GPU: {torch.cuda.get_device_name(0)}")

# Проверка установленных моделей
import os
models_path = "/workspace/ComfyUI/models/diffusion_models"
models = os.listdir(models_path)
print("Установленные модели:")
for model in models:
    print(f"  - {model}")
```

### Автоматизация установки
```python
# Скрипт для автоматической установки пресетов
import subprocess
import time

def install_presets(presets):
    """Установить пресеты"""
    cmd = f"bash /download_presets.sh {','.join(presets)}"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode == 0

# Использование
presets = ["WAN_T2V", "WAN_I2V"]
if install_presets(presets):
    print("✅ Пресеты установлены успешно")
else:
    print("❌ Ошибка установки пресетов")
```

---

## 🔄 Управление сервисами

### Перезапуск ComfyUI
```bash
# Остановить ComfyUI
pkill -f comfyui

# Запустить ComfyUI
cd /ComfyUI
nohup python main.py --listen 0.0.0.0 --port 3000 > /workspace/logs/comfyui.log 2>&1 &
```

### Управление веб-сервисами
```bash
# Запустить CivitAI Downloader
nohup uvicorn services.civitai_downloader:app --host 0.0.0.0 --port 8081 > /workspace/logs/civitai_downloader.log 2>&1 &

# Запустить Outputs Browser
nohup uvicorn services.outputs_browser:app --host 0.0.0.0 --port 8082 > /workspace/logs/outputs_browser.log 2>&1 &
```

---

## 📁 Структура файлов

```
/workspace/
├── ComfyUI/
│   ├── models/
│   │   ├── diffusion_models/    # Основные модели
│   │   ├── vae/                 # VAE модели
│   │   ├── loras/               # LoRA модели
│   │   ├── text_encoders/       # Текстовые энкодеры
│   │   └── upscale_models/      # Модели апскейла
│   ├── custom_nodes/            # Кастомные ноды
│   ├── user/
│   │   └── workflows/           # Пользовательские workflow
│   └── output/                  # Результаты генерации
├── logs/                        # Логи сервисов
└── .cache/                      # Кэш
```

---

## ⚡ Полезные команды

### Быстрые команды
```bash
# Перезапустить все сервисы
pkill -f comfyui && pkill -f uvicorn
cd /ComfyUI && python main.py --listen 0.0.0.0 --port 3000 &
nohup uvicorn services.civitai_downloader:app --host 0.0.0.0 --port 8081 &
nohup uvicorn services.outputs_browser:app --host 0.0.0.0 --port 8082 &

# Проверить все логи
tail -f /workspace/logs/*.log

# Очистить все кэши
rm -rf /workspace/.cache/*

# Проверить место на диске
du -sh /workspace/ComfyUI/models/*
```

### Создание алиасов
```bash
# Добавить в .bashrc
echo 'alias restart-comfy="pkill -f comfyui && cd /ComfyUI && python main.py --listen 0.0.0.0 --port 3000 &"' >> ~/.bashrc
echo 'alias check-logs="tail -f /workspace/logs/*.log"' >> ~/.bashrc
echo 'alias check-gpu="nvidia-smi"' >> ~/.bashrc

# Перезагрузить .bashrc
source ~/.bashrc
```

---

*Для полной документации см. [GUIDE.md](GUIDE.md)*
