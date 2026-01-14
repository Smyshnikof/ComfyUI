#!/bin/bash

export PYTHONUNBUFFERED=1

source /workspace/venv/bin/activate
cd /workspace/ComfyUI

echo "**** Displays the available arguments for running ComfyUI. ****" 
python main.py --help

echo "**** ComfyUI will be started by start.sh script. ****"
