#!/usr/bin/env python3
"""
Патч comfy/model_management.py: если torch.cuda.mem_get_info падает при импорте
(CUDA busy/unavailable на RunPod и др.), используем get_device_properties или запасную оценку VRAM.
Идемпотентен: повторный запуск безопасен.
"""
from __future__ import annotations

import pathlib
import sys

TARGET = pathlib.Path("/workspace/ComfyUI/comfy/model_management.py")

OLD = """            stats = torch.cuda.memory_stats(dev)
            mem_reserved = stats['reserved_bytes.all.current']
            _, mem_total_cuda = torch.cuda.mem_get_info(dev)
            mem_total_torch = mem_reserved
            mem_total = mem_total_cuda"""

NEW = """            stats = torch.cuda.memory_stats(dev)
            mem_reserved = stats['reserved_bytes.all.current']
            # mem_get_info CUDA fallback (RunPod / import-time CUDA quirks)
            try:
                _, mem_total_cuda = torch.cuda.mem_get_info(dev)
            except Exception:
                try:
                    mem_total_cuda = torch.cuda.get_device_properties(dev).total_memory
                except Exception:
                    mem_total_cuda = 24 * 1024 * 1024 * 1024
            mem_total_torch = mem_reserved
            mem_total = mem_total_cuda"""


def main() -> int:
    if not TARGET.is_file():
        print("patch_comfy_cuda_mem: skip, file not found", file=sys.stderr)
        return 0
    text = TARGET.read_text(encoding="utf-8")
    if "mem_get_info CUDA fallback (RunPod / import-time CUDA quirks)" in text:
        print("patch_comfy_cuda_mem: already applied")
        return 0
    if OLD not in text:
        print(
            "patch_comfy_cuda_mem: expected CUDA block not found (upstream model_management.py changed?)",
            file=sys.stderr,
        )
        return 1
    TARGET.write_text(text.replace(OLD, NEW), encoding="utf-8")
    print("patch_comfy_cuda_mem: applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
