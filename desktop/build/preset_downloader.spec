# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Smyshnikov Preset Downloader."""

import os

ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))

a = Analysis(
    [os.path.join(ROOT, "desktop", "launcher.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[
        (os.path.join(ROOT, "presets"), "presets"),
        (os.path.join(ROOT, "node_presets"), "node_presets"),
        (os.path.join(ROOT, "services", "static"), "services" + os.sep + "static"),
        (os.path.join(ROOT, "desktop", "config.example.json"), "desktop"),
    ],
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "services.dashboard",
        "services.preset_downloader",
        "services.civitai_downloader",
        "services.outputs_browser",
        "services.custom_nodes_installer",
        "services._config",
        "services._comfyui_launch",
        "services._presets",
        "services._node_presets",
        "services._node_installer",
        "services._manager_config",
        "services._downloader",
        "services._tokens",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch",
        "torchvision",
        "torchaudio",
        "transformers",
        "diffusers",
        "accelerate",
        "scipy",
        "pandas",
        "matplotlib",
        "cv2",
        "nltk",
        "numba",
        "llvmlite",
        "sympy",
        "sklearn",
        "tensorflow",
        "onnxruntime",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SmyshnikovHub",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SmyshnikovComfyUIHub",
)
