#!/bin/bash

export PYTHONUNBUFFERED=1

# Определяем путь к Python (используем venv если доступен)
if [ -f /workspace/venv/bin/python ]; then
    PYTHON_CMD="/workspace/venv/bin/python"
else
    PYTHON_CMD="python"
fi

cd /workspace/ComfyUI

echo "**** Displays the available arguments for running ComfyUI. ****" 
$PYTHON_CMD main.py --help 2>&1 | head -20

echo "**** ComfyUI will be started by start.sh script. ****"
