#!/bin/bash

export PYTHONUNBUFFERED=1

echo "**** Setting the timezone based on the TIME_ZONE environment variable. If not set, it defaults to Etc/UTC. ****"
export TZ=${TIME_ZONE:-"Etc/UTC"}
echo "**** Timezone set to $TZ ****"
echo "$TZ" | sudo tee /etc/timezone > /dev/null
sudo ln -sf "/usr/share/zoneinfo/$TZ" /etc/localtime
sudo dpkg-reconfigure -f noninteractive tzdata

# Update VIRTUAL_ENV paths in all text files under /workspace/venv/bin
update_venv_paths() {
    local bin_dir="/workspace/venv/bin"
    echo "Updating '/venv' to '/workspace/venv' in all text files under '$bin_dir'..."

    find "$bin_dir" -type f | while read -r file; do
        if file "$file" | grep -q "text"; then
            # VIRTUAL_ENV='/venv' → VIRTUAL_ENV='/workspace/venv'
            sed -i "s|VIRTUAL_ENV='/venv'|VIRTUAL_ENV='/workspace/venv'|g" "$file"
            
            # VIRTUAL_ENV '/venv' → VIRTUAL_ENV '/workspace/venv'
            sed -i "s|VIRTUAL_ENV '/venv'|VIRTUAL_ENV '/workspace/venv'|g" "$file"
            
            # #!/venv/bin/python → #!/workspace/venv/bin/python
            sed -i "s|#!/venv/bin/python|#!/workspace/venv/bin/python|g" "$file"

            # Uncomment to debug
            # echo "Updated: $file"
        fi
    done
}

echo "**** syncing venv to workspace, please wait. This could take a while on first startup! ****"
if [ -d /venv ]; then
    if rsync -au --remove-source-files /venv/ /workspace/venv/ && rm -rf /venv; then
        update_venv_paths
    fi
else
    echo "Skip: /venv does not exist."
fi

# Fix for preset_downloader (port 8081) after Python updates - upgrade huggingface_hub and deps
if [ -f /workspace/venv/bin/activate ]; then
    echo "**** Upgrading huggingface_hub, click, typer (fix for preset downloader compatibility) ****"
    source /workspace/venv/bin/activate && pip install --upgrade --quiet click typer huggingface_hub 2>/dev/null || true
fi

# ComfyUI requirements.txt ломает связку torch/torchaudio → нужны wheel'ы torch==X.Y.Z+cu*** с pytorch.org
if [ -f /workspace/venv/bin/activate ] && [ -f /comfy_pytorch_pin.txt ]; then
    if ! bash -c 'source /workspace/venv/bin/activate && python -c "import torchaudio"' 2>/dev/null; then
        TV=$(sed -n '1p' /comfy_pytorch_pin.txt)
        CV=$(sed -n '2p' /comfy_pytorch_pin.txt)
        TVIS=$(sed -n '3p' /comfy_pytorch_pin.txt)
        echo "**** Восстановление torch-стека (ABI / torchaudio) ****"
        source /workspace/venv/bin/activate && pip uninstall -y torch torchvision torchaudio 2>/dev/null || true
        if [ "$TVIS" = "legacy" ]; then
            pip install --no-cache-dir "torch==${TV}" torchvision torchaudio --extra-index-url "https://download.pytorch.org/whl/${CV}" 2>/dev/null || true
        elif [ -n "$TVIS" ]; then
            pip install --no-cache-dir \
                "torch==${TV}+${CV}" "torchvision==${TVIS}+${CV}" "torchaudio==${TV}+${CV}" \
                --extra-index-url "https://download.pytorch.org/whl/${CV}" 2>/dev/null || true
        else
            [ "$TV" = "2.9.0" ] && TVIS=0.24.0 || TVIS=0.23.0
            if echo "$CV" | grep -qE '^cu(126|128|129|130)$'; then
                pip install --no-cache-dir \
                    "torch==${TV}+${CV}" "torchvision==${TVIS}+${CV}" "torchaudio==${TV}+${CV}" \
                    --extra-index-url "https://download.pytorch.org/whl/${CV}" 2>/dev/null || true
            else
                pip install --no-cache-dir "torch==${TV}" torchvision torchaudio --extra-index-url "https://download.pytorch.org/whl/${CV}" 2>/dev/null || true
            fi
        fi
    fi
fi

echo "**** syncing ComfyUI to workspace, please wait ****"
if [ -d /ComfyUI ]; then

    SRC_MODELS="/ComfyUI/models"
    DST_MODELS="/workspace/ComfyUI/models"

    EXCLUDE_MODELS=""

    if [ -d "$DST_MODELS" ] && [ "$(ls -A "$DST_MODELS")" ]; then
        for d in "$DST_MODELS"/*/; do
            [ -d "$d" ] || continue
            folder_name=$(basename "$d")
            EXCLUDE_MODELS="$EXCLUDE_MODELS --exclude='models/$folder_name/**'"
        done
        echo "**** Excluding existing model folders: $EXCLUDE_MODELS ****"
    fi

    if [ -d /workspace/ComfyUI/output ]; then
        EXCLUDE_MODELS="$EXCLUDE_MODELS --exclude='output/'"
        echo "**** Excluding existing output folder ****"
    fi

    rsync -au --remove-source-files $EXCLUDE_MODELS /ComfyUI/ /workspace/ComfyUI/ && rm -rf /ComfyUI

else
    echo "Skip: /ComfyUI does not exist."
fi

# Старый volume / detached HEAD (клон по тегу): git pull без ветки не работает — делаем checkout -B main|master.
if [ "${COMFYUI_UPDATE_ON_START,,}" = "true" ] || [ "$COMFYUI_UPDATE_ON_START" = "1" ]; then
    if [ -d /workspace/ComfyUI/.git ]; then
        echo "**** COMFYUI_UPDATE_ON_START: обновление ComfyUI из GitHub ****"
        cd /workspace/ComfyUI || true
        git config --global --add safe.directory /workspace/ComfyUI 2>/dev/null || true
        git remote set-url origin https://github.com/comfy-org/ComfyUI.git 2>/dev/null || true
        if ! git fetch origin 2>/dev/null; then
            echo "**** git fetch не удался ****"
        fi
        # shallow по тегу: после первого fetch часто нет refs на main/master
        if ! git rev-parse --verify origin/main >/dev/null 2>&1 && ! git rev-parse --verify origin/master >/dev/null 2>&1; then
            git fetch origin main:refs/remotes/origin/main --depth=64 2>/dev/null || true
            git fetch origin master:refs/remotes/origin/master --depth=64 2>/dev/null || true
        fi
        if git rev-parse --verify origin/main >/dev/null 2>&1; then
            git checkout -B main origin/main && git reset --hard origin/main && echo "**** ComfyUI → main @ origin/main ****"
        elif git rev-parse --verify origin/master >/dev/null 2>&1; then
            git checkout -B master origin/master && git reset --hard origin/master && echo "**** ComfyUI → master @ origin/master ****"
        else
            echo "**** Нет origin/main и origin/master. Вручную: git fetch --unshallow && git fetch origin ****"
        fi
        if [ -f /workspace/venv/bin/activate ]; then
            source /workspace/venv/bin/activate && pip install --no-cache-dir -q -r /workspace/ComfyUI/requirements.txt 2>/dev/null || true
        fi
    else
        echo "**** COMFYUI_UPDATE_ON_START: в /workspace/ComfyUI нет .git — обновление пропущено ****"
    fi
fi

# pip install -r requirements.txt после git pull может перезаписать torch — вернуть wheel'ы из образа
if [ "${COMFYUI_UPDATE_ON_START,,}" = "true" ] || [ "$COMFYUI_UPDATE_ON_START" = "1" ]; then
    if [ -f /workspace/venv/bin/activate ] && [ -f /comfy_pytorch_pin.txt ]; then
        echo "**** Re-applying PyTorch wheels after ComfyUI requirements.txt ****"
        TV=$(sed -n '1p' /comfy_pytorch_pin.txt)
        CV=$(sed -n '2p' /comfy_pytorch_pin.txt)
        TVIS=$(sed -n '3p' /comfy_pytorch_pin.txt)
        source /workspace/venv/bin/activate
        if [ "$TVIS" = "legacy" ]; then
            pip install --no-cache-dir "torch==${TV}" torchvision torchaudio --extra-index-url "https://download.pytorch.org/whl/${CV}" 2>/dev/null || true
        elif [ -n "$TVIS" ]; then
            pip install --no-cache-dir \
                "torch==${TV}+${CV}" "torchvision==${TVIS}+${CV}" "torchaudio==${TV}+${CV}" \
                --extra-index-url "https://download.pytorch.org/whl/${CV}" 2>/dev/null || true
        else
            [ "$TV" = "2.9.0" ] && TVIS_FALLBACK=0.24.0 || TVIS_FALLBACK=0.23.0
            if echo "$CV" | grep -qE '^cu(126|128|129|130)$'; then
                pip install --no-cache-dir \
                    "torch==${TV}+${CV}" "torchvision==${TVIS_FALLBACK}+${CV}" "torchaudio==${TV}+${CV}" \
                    --extra-index-url "https://download.pytorch.org/whl/${CV}" 2>/dev/null || true
            else
                pip install --no-cache-dir "torch==${TV}" torchvision torchaudio --extra-index-url "https://download.pytorch.org/whl/${CV}" 2>/dev/null || true
            fi
        fi
    fi
fi

if [ "${INSTALL_SAGEATTENTION,,}" = "true" ]; then
    if pip show sageattention > /dev/null 2>&1; then
        echo "**** SageAttention2 is already installed. Skipping installation. ****"
    else
        echo "**** SageAttention2 is not installed. Installing, please wait.... (This may take a long time, approximately 5+ minutes.) ****"
        git clone https://github.com/thu-ml/SageAttention.git /SageAttention
        cd /SageAttention
        export EXT_PARALLEL=4 NVCC_APPEND_FLAGS="--threads 8" MAX_JOBS=32
        python setup.py install
        echo "**** SageAttention2 installation completed. ****"
    fi
fi

if [ "${INSTALL_CUSTOM_NODES,,}" = "true" ]; then
    if [ -f /install_custom_nodes.sh ]; then
        echo "**** INSTALL_CUSTOM_NODES is set. Running /install_custom_nodes.sh ****"
        /install_custom_nodes.sh
    else
        echo "**** /install_custom_nodes.sh not found. Skipping. ****"
    fi
fi

# Preset downloads are now handled via the web interface (port 8081)
# Users can download presets through the convenient preset downloader service
echo "**** Preset downloads available via web interface at port 8081 ****"

# Copy all presets (wan, qwen, snippets, etc.) into ComfyUI user dir if present
echo "**** Copying presets workflows (wan, qwen, snippets, etc.) ****"
SRC_PRESETS_DIR="/presets"
DST_WORKFLOWS_DIR="/workspace/ComfyUI/user/default/workflows"
if [ -d "$SRC_PRESETS_DIR" ]; then
    mkdir -p "$DST_WORKFLOWS_DIR"
    # Copy all subdirectories from /presets (wan, qwen, snippets, etc.)
    # Убираем / в конце пути, чтобы rsync копировал саму папку, а не её содержимое
    for preset_subdir in "$SRC_PRESETS_DIR"/*/; do
        if [ -d "$preset_subdir" ]; then
            subdir_name=$(basename "$preset_subdir")
            echo "**** Copying $subdir_name workflows... ****"
            # Убираем завершающий / чтобы сохранить структуру папок
            rsync -au "${preset_subdir%/}" "$DST_WORKFLOWS_DIR/"
        fi
    done
    echo "**** All presets workflows copied to $DST_WORKFLOWS_DIR ****"
else
    echo "Skip: $SRC_PRESETS_DIR does not exist."
fi

# Also import user-provided workflows from /workspace/MyDocker if present
USER_MYDOCKER_DIR="/workspace/MyDocker"
if [ -d "$USER_MYDOCKER_DIR" ]; then
    echo "**** Importing workflows from $USER_MYDOCKER_DIR ****"
    mkdir -p "$DST_WORKFLOWS_DIR"
    # Copy JSON workflows under any 'Workflows' subfolders
    find "$USER_MYDOCKER_DIR" -type d -name "Workflows" | while read -r wfdir; do
        rsync -au --include='*/' --include='*.json' --exclude='*' "$wfdir/" "$DST_WORKFLOWS_DIR/"
    done
    # Copy top-level JSONs commonly used as workflows (e.g., T2V/T2I roots)
    find "$USER_MYDOCKER_DIR" -maxdepth 2 -type f -name "*.json" -print0 | xargs -0 -I {} rsync -au {} "$DST_WORKFLOWS_DIR/"
fi

# ComfyUI: если torch.cuda.mem_get_info падает при импорте (CUDA busy/unavailable на RunPod)
if [ -f /workspace/ComfyUI/comfy/model_management.py ] && [ -x /workspace/venv/bin/python ] && [ -f /patch_comfy_cuda_mem.py ]; then
    echo "**** ComfyUI: patch model_management CUDA mem_get_info fallback ****"
    /workspace/venv/bin/python /patch_comfy_cuda_mem.py || echo "**** patch_comfy_cuda_mem.py: check logs above ****"
fi