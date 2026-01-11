# 🚀 Инструкции по развертыванию

> Для разработчиков и администраторов

## 📋 Предварительные требования

- RunPod аккаунт с API ключом
- Python 3.8+
- Git

---

## 🔧 Автоматическое развертывание

### 1. Клонирование репозитория
```bash
git clone https://github.com/somb1/ComfyUI-Docker.git
cd ComfyUI-Docker
```

### 2. Настройка API ключа
```bash
# Отредактируйте runpod_deploy.py
nano runpod_deploy.py

# Установите ваш API ключ
RUNPOD_API_KEY = "your_api_key_here"
```

### 3. Запуск развертывания
```bash
python runpod_deploy.py
```

---

## ⚙️ Ручное развертывание

### 1. Создание Template

1. Перейдите в [RunPod Console](https://runpod.io/console/templates)
2. Нажмите "New Template"
3. Заполните поля:
   - **Name**: `ComfyUI`
   - **Container Image**: `smyshnikof/comfyui:base-torch2.8.0-cu128`
   - **Container Disk**: `50 GB`
   - **Ports**: `3000, 8081, 8082, 8083, 8888`

### 2. Настройка переменных окружения

Для образа `base` (готовые пресеты) добавьте:

| Key | Value | Описание |
|-----|-------|----------|
| `PRESET_DOWNLOAD` | `WAN_T2V,WAN_T2I,WAN_I2V,WAN_ANIMATE` | Автоскачивание пресетов |
| `ACCESS_PASSWORD` | `your_password` | Пароль для JupyterLab |
| `TIME_ZONE` | `Europe/Moscow` | Часовой пояс |
| `INSTALL_SAGEATTENTION` | `True` | Установка SageAttention2 |

Для образа `slim` (рекомендуется) переменные не обязательны.

### 3. Создание Pod

1. Перейдите в [RunPod Console](https://runpod.io/console/pods)
2. Нажмите "New Pod"
3. Выберите созданный Template
4. Выберите GPU (рекомендуется RTX 4090+)
5. Нажмите "Deploy"

---

## 🔄 Обновление образа

### 1. Обновление Docker образа
```bash
# Сборка нового образа
docker build -t smyshnikof/comfyui:base-torch2.8.0-cu128 .

# Пуш в реестр
docker push smyshnikof/comfyui:base-torch2.8.0-cu128
```

### 2. Обновление Template
1. Откройте Template в RunPod Console
2. Измените Container Image на новую версию
3. Сохраните изменения

---

## 📊 Мониторинг

### 1. Проверка статуса
```bash
# Через API
curl -H "Authorization: Bearer $RUNPOD_API_KEY" \
     https://api.runpod.io/v2/pods

# Через веб-интерфейс
# https://runpod.io/console/pods
```

### 2. Просмотр логов
```bash
# SSH подключение к Pod
ssh root@pod-ip

# Просмотр логов
tail -f /workspace/logs/*.log
```

---

## 🛠️ Кастомизация

### 1. Добавление новых пресетов

1. Отредактируйте `scripts/download_presets.sh`
2. Добавьте новый case для пресета
3. Пересоберите образ

### 2. Добавление кастомных нод

1. Отредактируйте `custom_nodes.txt`
2. Добавьте URL репозитория
3. Пересоберите образ

### 3. Изменение веб-сервисов

1. Отредактируйте файлы в папке `services/`
2. Обновите `scripts/start.sh` при необходимости
3. Пересоберите образ

---

## 🔒 Безопасность

### 1. Настройка SSH
```bash
# Генерация SSH ключей
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"

# Добавление публичного ключа в Template
# Environment Variable: PUBLIC_KEY
# Value: содержимое ~/.ssh/id_rsa.pub
```

### 2. Настройка паролей
```bash
# Установка пароля для JupyterLab
# Environment Variable: ACCESS_PASSWORD
# Value: ваш_пароль
```

### 3. Ограничение доступа
```bash
# Настройка nginx для ограничения доступа
# Отредактируйте proxy/nginx.conf
```

---

## 📈 Масштабирование

### 1. Горизонтальное масштабирование
- Создайте несколько Pod с разными GPU
- Используйте load balancer для распределения нагрузки
- Настройте мониторинг ресурсов

### 2. Вертикальное масштабирование
- Увеличьте Container Disk при необходимости
- Выберите более мощный GPU
- Настройте swap при нехватке RAM

---

## 🐛 Отладка

### 1. Общие проблемы
```bash
# Проверка статуса контейнера
docker ps -a

# Просмотр логов контейнера
docker logs container_id

# Подключение к контейнеру
docker exec -it container_id /bin/bash
```

### 2. Проблемы с GPU
```bash
# Проверка CUDA
nvidia-smi

# Проверка PyTorch
python -c "import torch; print(torch.cuda.is_available())"
```

### 3. Проблемы с сетью
```bash
# Проверка портов
netstat -tlnp

# Проверка nginx
systemctl status nginx
```

---

## 📚 Полезные ссылки

- [RunPod API Documentation](https://docs.runpod.io/reference)
- [Docker Documentation](https://docs.docker.com/)
- [ComfyUI GitHub](https://github.com/comfyanonymous/ComfyUI)
- [ComfyUI Manager](https://github.com/ltdrdata/ComfyUI-Manager)

---

*Для пользовательской документации см. [GUIDE.md](GUIDE.md)*
