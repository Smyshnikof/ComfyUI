#!/usr/bin/env python3
"""
Скрипт для автоматического развертывания ComfyUI на RunPod
"""

import requests
import json
import time

# Настройки
RUNPOD_API_KEY = "YOUR_RUNPOD_API_KEY"  # Получите на https://runpod.io/console/user/settings
DOCKER_IMAGE = "smyshnikof/comfyui:base-torch2.8.0-cu128"  # base = стабильные ноды, full = все ноды
GPU_TYPE = "NVIDIA GeForce RTX 4090"  # Или другой GPU
CONTAINER_DISK_SIZE = 50  # GB

def create_pod():
    """Создает новый Pod на RunPod"""
    
    headers = {
        "Authorization": f"Bearer {RUNPOD_API_KEY}",
        "Content-Type": "application/json"
    }
    
    pod_config = {
        "name": "ComfyUI-Custom",
        "imageName": DOCKER_IMAGE,
        "gpuTypeId": GPU_TYPE,
        "containerDiskInGb": CONTAINER_DISK_SIZE,
        "ports": "3000/http,8081/http,8082/http,8083/http,8888/http",
        "env": [
            {
                "key": "RP_WORKSPACE",
                "value": "/workspace"
            }
        ],
        "startJupyter": True,
        "startSsh": True
    }
    
    response = requests.post(
        "https://api.runpod.io/v2/pods",
        headers=headers,
        json=pod_config
    )
    
    if response.status_code == 200:
        pod_data = response.json()
        pod_id = pod_data["id"]
        print(f"✅ Pod создан успешно! ID: {pod_id}")
        print(f"🌐 URL: https://runpod.io/console/pods/{pod_id}")
        return pod_id
    else:
        print(f"❌ Ошибка создания Pod: {response.text}")
        return None

def get_pod_status(pod_id):
    """Получает статус Pod"""
    
    headers = {
        "Authorization": f"Bearer {RUNPOD_API_KEY}"
    }
    
    response = requests.get(
        f"https://api.runpod.io/v2/pods/{pod_id}",
        headers=headers
    )
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ Ошибка получения статуса: {response.text}")
        return None

if __name__ == "__main__":
    print("🚀 Создание Pod на RunPod...")
    
    # Создаем Pod
    pod_id = create_pod()
    
    if pod_id:
        print("\n⏳ Ожидание запуска Pod...")
        
        # Ждем пока Pod запустится
        while True:
            status = get_pod_status(pod_id)
            if status and status.get("desiredStatus") == "RUNNING":
                print("✅ Pod запущен и готов к работе!")
                print(f"🌐 ComfyUI: https://{pod_id}-3000.proxy.runpod.net")
                print(f"📥 Загрузчик пресетов: https://{pod_id}-8081.proxy.runpod.net")
                print(f"🔗 CivitAI Downloader: https://{pod_id}-8082.proxy.runpod.net")
                print(f"📁 Обзор результатов: https://{pod_id}-8083.proxy.runpod.net")
                print(f"📓 Jupyter: https://{pod_id}-8888.proxy.runpod.net")
                break
            else:
                print("⏳ Ожидание...")
                time.sleep(10)

