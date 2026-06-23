# Community presets

Drop-in JSON manifests for the Preset Downloader (port 8081).

## How to add

1. Create a JSON file (see format below) or import via UI: **Импорт пресета** on the presets tab.
2. Save the file here: `/workspace/presets/community/<ID>.json` (persists on network volume).
3. Click **Обновить пресеты** in the UI (or restart the preset downloader service).

Built-in presets live in `presets/manifest/` in the repo and cannot be overridden.

## Format (schema 1)

```json
{
  "schema": 1,
  "id": "MY_PRESET",
  "name": "My Custom Preset",
  "description": "Short description",
  "category": "Wan",
  "size": "~10GB",
  "time": "5-10 min",
  "files": [
    {
      "url": "https://huggingface.co/org/repo/resolve/main/model.safetensors",
      "folder": "diffusion_models",
      "filename": null
    }
  ]
}
```

Categories must exist in `presets/categories.json`. Allowed `folder` values match ComfyUI `models/*` subfolders (see `services/_presets.py`).

For variants, use `variant_groups` instead of `files` (same structure as built-in manifests in `presets/manifest/`).

## Import by URL

Supported hosts: `huggingface.co`, `github.com`, `raw.githubusercontent.com`, `gist.githubusercontent.com`.

Max JSON size: 256 KB.
