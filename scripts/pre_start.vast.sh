#!/bin/bash

export PYTHONUNBUFFERED=1

# Vast.ai workspace directory
VAST_WORKSPACE=/opt/workspace-internal

echo "**** Setting the timezone based on the TIME_ZONE environment variable. If not set, it defaults to Etc/UTC. ****"
export TZ=${TIME_ZONE:-"Etc/UTC"}
echo "**** Timezone set to $TZ ****"
echo "$TZ" | sudo tee /etc/timezone > /dev/null
sudo ln -sf "/usr/share/zoneinfo/$TZ" /etc/localtime
sudo dpkg-reconfigure -f noninteractive tzdata

# Update VIRTUAL_ENV paths in all text files under workspace venv bin
update_venv_paths() {
    local bin_dir="${VAST_WORKSPACE}/venv/bin"
    echo "Updating '/venv' to '${VAST_WORKSPACE}/venv' in all text files under '$bin_dir'..."

    find "$bin_dir" -type f | while read -r file; do
        if file "$file" | grep -q "text"; then
            # VIRTUAL_ENV='/venv' → VIRTUAL_ENV='${VAST_WORKSPACE}/venv'
            sed -i "s|VIRTUAL_ENV='/venv'|VIRTUAL_ENV='${VAST_WORKSPACE}/venv'|g" "$file"
            
            # VIRTUAL_ENV '/venv' → VIRTUAL_ENV '${VAST_WORKSPACE}/venv'
            sed -i "s|VIRTUAL_ENV '/venv'|VIRTUAL_ENV '${VAST_WORKSPACE}/venv'|g" "$file"
            
            # #!/venv/bin/python → #!${VAST_WORKSPACE}/venv/bin/python
            sed -i "s|#!/venv/bin/python|#!${VAST_WORKSPACE}/venv/bin/python|g" "$file"

            # Uncomment to debug
            # echo "Updated: $file"
        fi
    done
}

echo "**** syncing venv to workspace, please wait. This could take a while on first startup! ****"
if [ -d /venv ]; then
    if rsync -au --remove-source-files /venv/ ${VAST_WORKSPACE}/venv/ && rm -rf /venv; then
        update_venv_paths
    fi
else
    echo "Skip: /venv does not exist."
fi

# Fix for preset_downloader (port 8081) after Python updates - upgrade huggingface_hub and deps
if [ -f ${VAST_WORKSPACE}/venv/bin/activate ]; then
    echo "**** Upgrading huggingface_hub, click, typer (fix for preset downloader compatibility) ****"
    source ${VAST_WORKSPACE}/venv/bin/activate && pip install --upgrade --quiet click typer huggingface_hub 2>/dev/null || true
fi

echo "**** syncing ComfyUI to workspace, please wait ****"
if [ -d /ComfyUI ]; then

    SRC_MODELS="/ComfyUI/models"
    DST_MODELS="${VAST_WORKSPACE}/ComfyUI/models"

    EXCLUDE_MODELS=""

    if [ -d "$DST_MODELS" ] && [ "$(ls -A "$DST_MODELS")" ]; then
        for d in "$DST_MODELS"/*/; do
            [ -d "$d" ] || continue
            folder_name=$(basename "$d")
            EXCLUDE_MODELS="$EXCLUDE_MODELS --exclude='models/$folder_name/**'"
        done
        echo "**** Excluding existing model folders: $EXCLUDE_MODELS ****"
    fi

    if [ -d "${VAST_WORKSPACE}/ComfyUI/output" ]; then
        EXCLUDE_MODELS="$EXCLUDE_MODELS --exclude='output/'"
        echo "**** Excluding existing output folder ****"
    fi

    rsync -au --remove-source-files $EXCLUDE_MODELS /ComfyUI/ ${VAST_WORKSPACE}/ComfyUI/ && rm -rf /ComfyUI

else
    echo "Skip: /ComfyUI does not exist."
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
DST_WORKFLOWS_DIR="${VAST_WORKSPACE}/ComfyUI/user/default/workflows"
if [ -d "$SRC_PRESETS_DIR" ]; then
    mkdir -p "$DST_WORKFLOWS_DIR"
    # Copy all subdirectories from /presets (wan, qwen, snippets, etc.)
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

# Also import user-provided workflows from workspace if present
USER_WORKFLOWS_DIR="${VAST_WORKSPACE}/MyDocker"
if [ -d "$USER_WORKFLOWS_DIR" ]; then
    echo "**** Importing workflows from $USER_WORKFLOWS_DIR ****"
    mkdir -p "$DST_WORKFLOWS_DIR"
    # Copy JSON workflows under any 'Workflows' subfolders
    find "$USER_WORKFLOWS_DIR" -type d -name "Workflows" | while read -r wfdir; do
        rsync -au --include='*/' --include='*.json' --exclude='*' "$wfdir/" "$DST_WORKFLOWS_DIR/"
    done
    # Copy top-level JSONs commonly used as workflows (e.g., T2V/T2I roots)
    find "$USER_WORKFLOWS_DIR" -maxdepth 2 -type f -name "*.json" -print0 | xargs -0 -I {} rsync -au {} "$DST_WORKFLOWS_DIR/"
fi
