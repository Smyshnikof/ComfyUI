#!/bin/bash

export PYTHONUNBUFFERED=1

source /workspace/venv/bin/activate

# На случай если pre_start не применил патч (старый образ / ручной запуск)
if [ -f /patch_comfy_cuda_mem.py ]; then
    /workspace/venv/bin/python /patch_comfy_cuda_mem.py 2>/dev/null || true
fi

cd /workspace/ComfyUI

echo "**** Displays the available arguments for running ComfyUI. ****" 

python main.py --help

echo "**** Starts ComfyUI on 0.0.0.0:3000 + CORS (RunPod / внешние ссылки). Extra: COMFYUI_EXTRA_ARGS ****"

# Явный 0.0.0.0: иначе по умолчанию 127.0.0.1 — ссылка RunPod не откроется («нет прав» / пустая страница).
# --enable-cors-header: прокси RunPod, другой origin, WebSocket.
python main.py --listen 0.0.0.0 --port 3000 --enable-cors-header $COMFYUI_EXTRA_ARGS &
