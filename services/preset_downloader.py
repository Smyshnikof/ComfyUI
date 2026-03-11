from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os
import subprocess
import threading
import uuid

# Глобальный словарь для отслеживания статуса загрузок
download_status = {}
import requests
import json
from huggingface_hub import hf_hub_download, login
import tempfile

app = FastAPI(title="Preset & Model Downloader")

# Подключаем статические файлы
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Структура файлов для каждого пресета
PRESET_FILES = {
    "WAN_T2V": [
        ("https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/T2V/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/T2V/Wan2_2-T2V-A14B_HIGH_fp8_e4m3fn_scaled_KJ.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors", "vae", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22-Lightning/old/Wan2.2-Lightning_T2V-v1.1-A14B-4steps-lora_HIGH_fp16.safetensors", "loras", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22-Lightning/old/Wan2.2-Lightning_T2V-v1.1-A14B-4steps-lora_LOW_fp16.safetensors", "loras", None),
    ],
    "WAN_T2V_LIGHTNING": [
        ("https://huggingface.co/lightx2v/Wan2.2-Lightning/resolve/main/Wan2.2-T2V-A14B-4steps-lora-250928/high_noise_model.safetensors", "loras", "T2V-Lightning-250928-high_noise_model.safetensors"),
        ("https://huggingface.co/lightx2v/Wan2.2-Lightning/resolve/main/Wan2.2-T2V-A14B-4steps-lora-250928/low_noise_model.safetensors", "loras", "T2V-Lightning-250928-low_noise_model.safetensors"),
    ],
    "WAN_T2I": [
        ("https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/T2V/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors", "vae", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22-Lightning/old/Wan2.2-Lightning_T2V-v1.1-A14B-4steps-lora_HIGH_fp16.safetensors", "loras", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22-Lightning/old/Wan2.2-Lightning_T2V-v1.1-A14B-4steps-lora_LOW_fp16.safetensors", "loras", None),
        ("https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x-UltraSharp.pth", "upscale_models", None),
        ("https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x_NMKD-Siax_200k.pth", "upscale_models", None),
        ("https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x_RealisticRescaler_100000_G.pth", "upscale_models", None),
        ("https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x_fatal_Anime_500000_G.pth", "upscale_models", None),
        ("https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/BSRGAN.pth", "upscale_models", None),
    ],
    "WAN_I2V": [
        ("https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/I2V/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/I2V/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors", "vae", None),
        ("https://huggingface.co/jrewingwannabe/Wan2.2-Lightning_I2V-A14B-4steps-lora/resolve/main/Wan2.2-Lightning_I2V-A14B-4steps-lora_HIGH_fp16.safetensors", "loras", None),
        ("https://huggingface.co/jrewingwannabe/Wan2.2-Lightning_I2V-A14B-4steps-lora/resolve/main/Wan2.2-Lightning_I2V-A14B-4steps-lora_LOW_fp16.safetensors", "loras", None),
    ],
    "WAN_I2V_LIGHTNING": [
        ("https://huggingface.co/lightx2v/Wan2.2-Lightning/resolve/main/Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/high_noise_model.safetensors", "loras", "I2V-Lightning-Seko-V1-high_noise_model.safetensors"),
        ("https://huggingface.co/lightx2v/Wan2.2-Lightning/resolve/main/Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/low_noise_model.safetensors", "loras", "I2V-Lightning-Seko-V1-low_noise_model.safetensors"),
    ],
    "WAN_I2V_LOOP": [
        ("https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/I2V/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/I2V/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors", "vae", None),
        ("https://huggingface.co/jrewingwannabe/Wan2.2-Lightning_I2V-A14B-4steps-lora/resolve/main/Wan2.2-Lightning_I2V-A14B-4steps-lora_HIGH_fp16.safetensors", "loras", None),
        ("https://huggingface.co/jrewingwannabe/Wan2.2-Lightning_I2V-A14B-4steps-lora/resolve/main/Wan2.2-Lightning_I2V-A14B-4steps-lora_LOW_fp16.safetensors", "loras", None),
    ],
    "WAN_ANIMATE": [
        ("https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/Wan22Animate/Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors", "vae", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_fp32.safetensors", "vae", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors", "text_encoders", None),
        ("https://huggingface.co/OreX/Models/resolve/main/WAN/clip_vision_h.safetensors", "clip_vision", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22_relight/WanAnimate_relight_lora_fp16.safetensors", "loras", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors", "loras", None),
    ],
    "WAN_ANIMATE_CLASSIC_V2": [
        ("https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/Wan22Animate/Wan2_2-Animate-14B_fp8_scaled_e4m3fn_KJ_v2.safetensors", "diffusion_models", None),
        ("https://huggingface.co/rahul7star/wan2.2Lora/resolve/main/Wan2.2-Fun-A14B-InP-LOW-HPS2.1_resized_dynamic_avg_rank_15_bf16.safetensors", "loras", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22_relight/WanAnimate_relight_lora_fp16.safetensors", "loras", None),
        ("https://huggingface.co/wangkanai/wan21-lightx2v-i2v-14b-480p/resolve/main/loras/wan/wan21-lightx2v-i2v-14b-480p-cfg-step-distill-rank256-bf16.safetensors", "loras", None),
        ("https://huggingface.co/JunkyByte/easy_ViTPose/resolve/main/onnx/wholebody/vitpose-l-wholebody.onnx", "detection", None),
        ("https://huggingface.co/Wan-AI/Wan2.2-Animate-14B/resolve/main/process_checkpoint/det/yolov10m.onnx", "detection", None),
        ("https://huggingface.co/VeryAladeen/Sec-4B/resolve/main/SeC-4B-fp16.safetensors", "sams", None),
        ("https://huggingface.co/Kyca/KycasFiles/resolve/main/2xNomosUni_esrgan_multijpg.pth", "upscale_models", None),
        ("https://huggingface.co/chatpig/encoder/resolve/main/umt5_xxl_fp16.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors", "clip_vision", None),
        ("https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors", "vae", None),
    ],
    "WAN_FLF": [
        ("https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/Fun/Wan2_2-Fun-InP-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/Fun/Wan2_2-Fun-InP-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors", "vae", None),
        ("https://huggingface.co/jrewingwannabe/Wan2.2-Lightning_I2V-A14B-4steps-lora/resolve/main/Wan2.2-Lightning_I2V-A14B-4steps-lora_HIGH_fp16.safetensors", "loras", None),
        ("https://huggingface.co/jrewingwannabe/Wan2.2-Lightning_I2V-A14B-4steps-lora/resolve/main/Wan2.2-Lightning_I2V-A14B-4steps-lora_LOW_fp16.safetensors", "loras", None),
    ],
    "WAN_FLF_LIGHTNING": [
        ("https://huggingface.co/lightx2v/Wan2.2-Lightning/resolve/main/Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/high_noise_model.safetensors", "loras", "FLF-Lightning-Seko-V1-high_noise_model.safetensors"),
        ("https://huggingface.co/lightx2v/Wan2.2-Lightning/resolve/main/Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/low_noise_model.safetensors", "loras", "FLF-Lightning-Seko-V1-low_noise_model.safetensors"),
    ],
    "WAN_LIGHTX2V": [
        ("https://huggingface.co/lightx2v/Wan2.2-Distill-Models/resolve/main/wan2.2_i2v_A14b_high_noise_lightx2v_4step.safetensors", "diffusion_models", "wan2.2_i2v_A14b_high_noise_lightx2v_4step.safetensors"),
        ("https://huggingface.co/lightx2v/Wan2.2-Distill-Models/resolve/main/wan2.2_i2v_A14b_low_noise_lightx2v_4step.safetensors", "diffusion_models", "wan2.2_i2v_A14b_low_noise_lightx2v_4step.safetensors"),
        ("https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp16.safetensors", "text_encoders", "umt5_xxl_fp16.safetensors"),
        ("https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors", "vae", "wan_2.1_vae.safetensors"),
        ("https://huggingface.co/rahul7star/wan2.2Lora/resolve/main/Wan2.2-Fun-A14B-InP-high-noise-MPS.safetensors", "loras", "Wan2.2-Fun-A14B-InP-high-noise-MPS.safetensors"),
        ("https://huggingface.co/rahul7star/wan2.2Lora/resolve/main/Wan2.2-Fun-A14B-InP-low-noise-HPS2.1.safetensors", "loras", "Wan2.2-Fun-A14B-InP-low-noise-HPS2.1.safetensors"),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank256_bf16.safetensors", "loras", "lightx2v_I2V_14B_480p_cfg_step_distill_rank256_bf16.safetensors"),
        ("https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors", "clip_vision", "clip_vision_h.safetensors"),
    ],
    "WAN_I2I_REFINER": [
        ("https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/T2V/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors", "vae", None),
        ("https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x-UltraSharp.pth", "upscale_models", None),
        ("https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x_NMKD-Siax_200k.pth", "upscale_models", None),
        ("https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x_RealisticRescaler_100000_G.pth", "upscale_models", None),
        ("https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x_fatal_Anime_500000_G.pth", "upscale_models", None),
        ("https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/BSRGAN.pth", "upscale_models", None),
    ],
    "WAN_CHRONOEDIT": [
        ("https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/ChronoEdit/Wan2_1-14B-I2V_ChronoEdit_fp8_scaled_KJ.safetensors", "diffusion_models", None),
        ("https://huggingface.co/nvidia/ChronoEdit-14B-Diffusers/resolve/main/lora/chronoedit_distill_lora.safetensors", "loras", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors", "vae", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors", "text_encoders", None),
        ("https://huggingface.co/OreX/Models/resolve/main/WAN/clip_vision_h.safetensors", "clip_vision", None),
    ],
    "WAN_T2V_T2I_BATCH": [
        ("https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/T2V/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors", "vae", None),
        ("https://huggingface.co/spacepxl/Wan2.1-VAE-upscale2x/resolve/main/Wan2.1_VAE_upscale2x_imageonly_real_v1.safetensors", "vae", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22-Lightning/old/Wan2.2-Lightning_T2V-v1.1-A14B-4steps-lora_HIGH_fp16.safetensors", "loras", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22-Lightning/old/Wan2.2-Lightning_T2V-v1.1-A14B-4steps-lora_LOW_fp16.safetensors", "loras", None),
        ("https://huggingface.co/lightx2v/Wan2.2-Lightning/resolve/main/Wan2.2-T2V-A14B-4steps-250928-dyno/Wan2.2-T2V-A14B-4steps-250928-dyno-high-lightx2v.safetensors", "loras", None),
        ("https://huggingface.co/lightx2v/Wan2.2-Lightning/resolve/main/Wan2.2-T2V-A14B-4steps-lora-250928/low_noise_model.safetensors", "loras", None),
        ("https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x-UltraSharp.pth", "upscale_models", None),
        ("https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x_NMKD-Siax_200k.pth", "upscale_models", None),
        ("https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x_RealisticRescaler_100000_G.pth", "upscale_models", None),
        ("https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x_fatal_Anime_500000_G.pth", "upscale_models", None),
        ("https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/BSRGAN.pth", "upscale_models", None),
    ],
    "WAN_INFINITETALK": [
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1-I2V-14B-480P_fp8_e4m3fn.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/InfiniteTalk/Wan2_1-InfiniTetalk-Single_fp16.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors", "loras", None),
        ("https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors", "clip_vision", None),
        ("https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors", "vae", None),
        ("https://huggingface.co/Kijai/MelBandRoFormer_comfy/resolve/main/MelBandRoformer_fp32.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors", "text_encoders", None),
    ],
    "WAN_2_1_ALPHA": [
        ("https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.1_t2v_14B_fp8_scaled.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/loras/wan_alpha_2.1_rgba_lora.safetensors", "loras", None),
        ("https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_alpha_2.1_vae_rgb_channel.safetensors", "vae", None),
        ("https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_alpha_2.1_vae_alpha_channel.safetensors", "vae", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors", "loras", None),
    ],
    "WAN_REMIX_I2V": [
        ("https://huggingface.co/FX-FeiHou/wan2.2-Remix/resolve/main/NSFW/Wan2.2_Remix_NSFW_i2v_14b_high_lighting_v2.0.safetensors", "diffusion_models", None),
        ("https://huggingface.co/FX-FeiHou/wan2.2-Remix/resolve/main/NSFW/Wan2.2_Remix_NSFW_i2v_14b_low_lighting_v2.0.safetensors", "diffusion_models", None),
        ("https://huggingface.co/NSFW-API/NSFW-Wan-UMT5-XXL/resolve/main/nsfw_wan_umt5-xxl_fp8_scaled.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors", "vae", None),
    ],
    "WAN_ANIMATE_STEADY_DANCER": [
        ("https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/SteadyDancer/Wan21_SteadyDancer_fp8_e4m3fn_scaled_KJ.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors", "vae", None),
        ("https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors", "clip_vision", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors", "text_encoders", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors", "loras", None),
        ("https://huggingface.co/Wan-AI/Wan2.2-Animate-14B/resolve/main/process_checkpoint/det/yolov10m.onnx", "detection", None),
        ("https://huggingface.co/JunkyByte/easy_ViTPose/resolve/main/onnx/wholebody/vitpose-l-wholebody.onnx", "detection", None),
    ],
    "WAN_ANIMATE_ONETOALL": [
        ("https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/OneToAllAnimation/Wan21-OneToAllAnimation_fp8_e4m3fn_scaled_KJ.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors", "vae", None),
        ("https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors", "clip_vision", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors", "text_encoders", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors", "loras", None),
        ("https://huggingface.co/Wan-AI/Wan2.2-Animate-14B/resolve/main/process_checkpoint/det/yolov10m.onnx", "detection", None),
        ("https://huggingface.co/JunkyByte/easy_ViTPose/resolve/main/onnx/wholebody/vitpose-l-wholebody.onnx", "detection", None),
    ],
    "WAN_ANIMATE_SCAIL": [
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/SCAIL/Wan21-14B-SCAIL-preview_comfy_bf16.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors", "vae", None),
        ("https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors", "clip_vision", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors", "text_encoders", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors", "loras", None),
        ("https://huggingface.co/Wan-AI/Wan2.2-Animate-14B/resolve/main/process_checkpoint/det/yolov10m.onnx", "detection", None),
        ("https://huggingface.co/JunkyByte/easy_ViTPose/resolve/main/onnx/wholebody/vitpose-l-wholebody.onnx", "detection", None),
    ],
    # Qwen пресеты
    "QWEN_IMAGE": [
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_fp8_e4m3fn.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors", "vae", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Lightning-4steps-V1.0.safetensors", "loras", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Lightning-8steps-V1.0.safetensors", "loras", None),
        ("https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x_NMKD-Siax_200k.pth", "upscale_models", None),
    ],
    "QWEN_EDIT": [
        ("https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_edit_fp8_e4m3fn.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors", "vae", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Edit-Lightning-4steps-V1.0.safetensors", "loras", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Edit-Lightning-8steps-V1.0.safetensors", "loras", None),
        ("https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x_NMKD-Siax_200k.pth", "upscale_models", None),
    ],
    "QWEN_EDIT_2509_FP8": [
        ("https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_edit_2509_fp8_e4m3fn.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors", "vae", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Edit-2509/Qwen-Image-Edit-2509-Lightning-8steps-V1.0-bf16.safetensors", "loras", None),
        ("https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x_NMKD-Siax_200k.pth", "upscale_models", None),
    ],
    "QWEN_IMAGE_BF16": [
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_bf16.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors", "vae", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Lightning-4steps-V1.0.safetensors", "loras", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Lightning-8steps-V1.0.safetensors", "loras", None),
        ("https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x_NMKD-Siax_200k.pth", "upscale_models", None),
    ],
    "QWEN_IMAGE_2512_FP8": [
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_2512_fp8_e4m3fn.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors", "vae", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-2512-Lightning/resolve/main/Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors", "loras", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-2512-Lightning/resolve/main/Qwen-Image-2512-Lightning-8steps-V1.0-fp32.safetensors", "loras", None),
        ("https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x_NMKD-Siax_200k.pth", "upscale_models", None),
    ],
    "QWEN_IMAGE_2512_BF16": [
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_2512_bf16.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors", "vae", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-2512-Lightning/resolve/main/Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors", "loras", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-2512-Lightning/resolve/main/Qwen-Image-2512-Lightning-8steps-V1.0-fp32.safetensors", "loras", None),
        ("https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x_NMKD-Siax_200k.pth", "upscale_models", None),
    ],
    "QWEN_IMAGE_2512_Q8_GGUF": [
        ("https://huggingface.co/unsloth/Qwen-Image-2512-GGUF/resolve/main/qwen-image-2512-Q8_0.gguf", "diffusion_models", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors", "vae", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-2512-Lightning/resolve/main/Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors", "loras", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-2512-Lightning/resolve/main/Qwen-Image-2512-Lightning-8steps-V1.0-fp32.safetensors", "loras", None),
        ("https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x_NMKD-Siax_200k.pth", "upscale_models", None),
    ],
    "QWEN_EDIT_BF16": [
        ("https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_edit_bf16.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors", "vae", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Edit-Lightning-4steps-V1.0.safetensors", "loras", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Edit-Lightning-8steps-V1.0.safetensors", "loras", None),
        ("https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x_NMKD-Siax_200k.pth", "upscale_models", None),
    ],
    "QWEN_EDIT_2509_BF16": [
        ("https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_edit_2509_bf16.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors", "vae", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Edit-2509/Qwen-Image-Edit-2509-Lightning-8steps-V1.0-bf16.safetensors", "loras", None),
        ("https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x_NMKD-Siax_200k.pth", "upscale_models", None),
    ],
    "QWEN_EDIT_2511_BF16": [
        ("https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_edit_2511_bf16.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors", "vae", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Edit-2511-Lightning/resolve/main/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors", "loras", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Edit-2511-Lightning/resolve/main/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-fp32.safetensors", "loras", None),
        ("https://huggingface.co/DiffSynth-Studio/Qwen-Image-Edit-F2P/resolve/main/edit_0928_lora_step40000.safetensors", "loras", None),
        ("https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x_NMKD-Siax_200k.pth", "upscale_models", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image-InstantX-ControlNets/resolve/main/split_files/controlnet/Qwen-Image-InstantX-ControlNet-Union.safetensors", "controlnet", None),
    ],
    "QWEN_EDIT_2511_FP8": [
        ("https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_edit_2511_fp8mixed.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Comfy-Org/HunyuanVideo_1.5_repackaged/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors", "vae", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Edit-2511-Lightning/resolve/main/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors", "loras", None),
        ("https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x_NMKD-Siax_200k.pth", "upscale_models", None),
    ],
    "QWEN_LAYERED_BF16": [
        ("https://huggingface.co/Comfy-Org/Qwen-Image-Layered_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_layered_bf16.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image-Layered_ComfyUI/resolve/main/split_files/vae/qwen_image_layered_vae.safetensors", "vae", None),
    ],
    "QWEN_LAYERED_FP8": [
        ("https://huggingface.co/Comfy-Org/Qwen-Image-Layered_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_layered_fp8mixed.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/Qwen-Image-Layered_ComfyUI/resolve/main/split_files/vae/qwen_image_layered_vae.safetensors", "vae", None),
    ],
    "QWEN_IMAGE_LIGHTNING": [
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Lightning-4steps-V1.0-bf16.safetensors", "loras", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Lightning-4steps-V1.0.safetensors", "loras", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Lightning-4steps-V2.0-bf16.safetensors", "loras", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Lightning-4steps-V2.0.safetensors", "loras", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Lightning-8steps-V1.0.safetensors", "loras", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Lightning-8steps-V1.1-bf16.safetensors", "loras", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Lightning-8steps-V1.1.safetensors", "loras", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Lightning-8steps-V2.0-bf16.safetensors", "loras", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Lightning-8steps-V2.0.safetensors", "loras", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-fp8-e4m3fn-Lightning-4steps-V1.0-bf16.safetensors", "loras", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-fp8-e4m3fn-Lightning-4steps-V1.0-fp32.safetensors", "loras", None),
    ],
    "QWEN_EDIT_LIGHTNING": [
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors", "loras", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Edit-Lightning-4steps-V1.0.safetensors", "loras", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Edit-Lightning-8steps-V1.0-bf16.safetensors", "loras", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Edit-Lightning-8steps-V1.0.safetensors", "loras", None),
    ],
    "QWEN_EDIT_2509_LIGHTNING": [
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Edit-2509/Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors", "loras", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Edit-2509/Qwen-Image-Edit-2509-Lightning-4steps-V1.0-fp32.safetensors", "loras", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Edit-2509/Qwen-Image-Edit-2509-Lightning-8steps-V1.0-bf16.safetensors", "loras", None),
        ("https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Edit-2509/Qwen-Image-Edit-2509-Lightning-8steps-V1.0-fp32.safetensors", "loras", None),
    ],
    # Z-Image пресеты
    "Z_IMAGE": [
        ("https://huggingface.co/Comfy-Org/z_image/resolve/main/split_files/diffusion_models/z_image_bf16.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Comfy-Org/z_image/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/z_image/resolve/main/split_files/vae/ae.safetensors", "vae", None),
        ("https://huggingface.co/alibaba-pai/Z-Image-Turbo-Fun-Controlnet-Union/resolve/main/Z-Image-Turbo-Fun-Controlnet-Union.safetensors", "model_patches", None),
    ],
    "Z_IMAGE_TURBO": [
        ("https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/diffusion_models/z_image_turbo_bf16.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors", "vae", None),
        ("https://huggingface.co/alibaba-pai/Z-Image-Turbo-Fun-Controlnet-Union/resolve/main/Z-Image-Turbo-Fun-Controlnet-Union.safetensors", "model_patches", None),
    ],
    # Flux пресеты
    "FLUX_2_DEV_FP8": [
        ("https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/text_encoders/mistral_3_small_flux2_bf16.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/diffusion_models/flux2_dev_fp8mixed.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors", "vae", None),
    ],
    "FLUX_2_KLEIN_BASE_FP8": [
        ("https://huggingface.co/Comfy-Org/flux2-klein-4B/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors", "text_encoders", None),
        ("https://huggingface.co/black-forest-labs/FLUX.2-klein-base-4b-fp8/resolve/main/flux-2-klein-base-4b-fp8.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors", "vae", None),
    ],
    "FLUX_2_KLEIN_FP8": [
        ("https://huggingface.co/Comfy-Org/flux2-klein-4B/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors", "text_encoders", None),
        ("https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8/resolve/main/flux-2-klein-4b-fp8.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors", "vae", None),
    ],
    "FLUX_1_KREA_FP8": [
        ("https://huggingface.co/Comfy-Org/FLUX.1-Krea-dev_ComfyUI/resolve/main/split_files/diffusion_models/flux1-krea-dev_fp8_scaled.safetensors", "diffusion_models", None),
        ("https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors", "text_encoders", None),
        ("https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors", "text_encoders", None),
        ("https://huggingface.co/black-forest-labs/FLUX.1-schnell/resolve/main/ae.safetensors", "vae", None),
    ],
    # LTX пресеты
    "LTX_2_FP8": [
        ("https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-19b-dev-fp8.safetensors", "checkpoints", None),
        ("https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/gemma_3_12B_it.safetensors", "text_encoders", None),
        ("https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-19b-distilled-lora-384.safetensors", "loras", None),
        ("https://huggingface.co/Lightricks/LTX-2-19b-LoRA-Camera-Control-Dolly-Left/resolve/main/ltx-2-19b-lora-camera-control-dolly-left.safetensors", "loras", None),
        ("https://huggingface.co/Lightricks/LTX-2-19b-IC-LoRA-Depth-Control/resolve/main/ltx-2-19b-ic-lora-depth-control.safetensors", "loras", None),
        ("https://huggingface.co/Lightricks/LTX-2-19b-IC-LoRA-Canny-Control/resolve/main/ltx-2-19b-ic-lora-canny-control.safetensors", "loras", None),
        ("https://huggingface.co/Lightricks/LTX-2-19b-IC-LoRA-Pose-Control/resolve/main/ltx-2-19b-ic-lora-pose-control.safetensors", "loras", None),
        ("https://huggingface.co/Comfy-Org/lotus/resolve/main/lotus-depth-d-v1-1.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Lightricks/LTX-2-19b-IC-LoRA-Detailer/resolve/main/ltx-2-19b-ic-lora-detailer.safetensors", "loras", None),
        ("https://huggingface.co/stabilityai/sd-vae-ft-mse-original/resolve/main/vae-ft-mse-840000-ema-pruned.safetensors", "vae", None),
        ("https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-spatial-upscaler-x2-1.0.safetensors", "latent_upscale_models", None),
    ],
    "LTX_2_BF16": [
        ("https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-19b-dev.safetensors", "checkpoints", None),
        ("https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/gemma_3_12B_it.safetensors", "text_encoders", None),
        ("https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-19b-distilled-lora-384.safetensors", "loras", None),
        ("https://huggingface.co/Lightricks/LTX-2-19b-LoRA-Camera-Control-Dolly-Left/resolve/main/ltx-2-19b-lora-camera-control-dolly-left.safetensors", "loras", None),
        ("https://huggingface.co/Lightricks/LTX-2-19b-IC-LoRA-Depth-Control/resolve/main/ltx-2-19b-ic-lora-depth-control.safetensors", "loras", None),
        ("https://huggingface.co/Lightricks/LTX-2-19b-IC-LoRA-Canny-Control/resolve/main/ltx-2-19b-ic-lora-canny-control.safetensors", "loras", None),
        ("https://huggingface.co/Lightricks/LTX-2-19b-IC-LoRA-Pose-Control/resolve/main/ltx-2-19b-ic-lora-pose-control.safetensors", "loras", None),
        ("https://huggingface.co/Comfy-Org/lotus/resolve/main/lotus-depth-d-v1-1.safetensors", "diffusion_models", None),
        ("https://huggingface.co/stabilityai/sd-vae-ft-mse-original/resolve/main/vae-ft-mse-840000-ema-pruned.safetensors", "vae", None),
        ("https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-spatial-upscaler-x2-1.0.safetensors", "latent_upscale_models", None),
    ],
    "LTX_2_DISTILLED_FP8": [
        ("https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-19b-distilled-fp8.safetensors", "checkpoints", None),
        ("https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/gemma_3_12B_it.safetensors", "text_encoders", None),
        ("https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-19b-distilled-lora-384.safetensors", "loras", None),
        ("https://huggingface.co/Lightricks/LTX-2-19b-LoRA-Camera-Control-Dolly-Left/resolve/main/ltx-2-19b-lora-camera-control-dolly-left.safetensors", "loras", None),
        ("https://huggingface.co/Lightricks/LTX-2-19b-IC-LoRA-Depth-Control/resolve/main/ltx-2-19b-ic-lora-depth-control.safetensors", "loras", None),
        ("https://huggingface.co/Lightricks/LTX-2-19b-IC-LoRA-Canny-Control/resolve/main/ltx-2-19b-ic-lora-canny-control.safetensors", "loras", None),
        ("https://huggingface.co/Lightricks/LTX-2-19b-IC-LoRA-Pose-Control/resolve/main/ltx-2-19b-ic-lora-pose-control.safetensors", "loras", None),
        ("https://huggingface.co/Comfy-Org/lotus/resolve/main/lotus-depth-d-v1-1.safetensors", "diffusion_models", None),
        ("https://huggingface.co/stabilityai/sd-vae-ft-mse-original/resolve/main/vae-ft-mse-840000-ema-pruned.safetensors", "vae", None),
        ("https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-spatial-upscaler-x2-1.0.safetensors", "latent_upscale_models", None),
    ],
    "LTX_2_DISTILLED_BF16": [
        ("https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-19b-distilled.safetensors", "checkpoints", None),
        ("https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/gemma_3_12B_it.safetensors", "text_encoders", None),
        ("https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-19b-distilled-lora-384.safetensors", "loras", None),
        ("https://huggingface.co/Lightricks/LTX-2-19b-LoRA-Camera-Control-Dolly-Left/resolve/main/ltx-2-19b-lora-camera-control-dolly-left.safetensors", "loras", None),
        ("https://huggingface.co/Lightricks/LTX-2-19b-IC-LoRA-Depth-Control/resolve/main/ltx-2-19b-ic-lora-depth-control.safetensors", "loras", None),
        ("https://huggingface.co/Lightricks/LTX-2-19b-IC-LoRA-Canny-Control/resolve/main/ltx-2-19b-ic-lora-canny-control.safetensors", "loras", None),
        ("https://huggingface.co/Lightricks/LTX-2-19b-IC-LoRA-Pose-Control/resolve/main/ltx-2-19b-ic-lora-pose-control.safetensors", "loras", None),
        ("https://huggingface.co/Comfy-Org/lotus/resolve/main/lotus-depth-d-v1-1.safetensors", "diffusion_models", None),
        ("https://huggingface.co/stabilityai/sd-vae-ft-mse-original/resolve/main/vae-ft-mse-840000-ema-pruned.safetensors", "vae", None),
        ("https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-spatial-upscaler-x2-1.0.safetensors", "latent_upscale_models", None),
    ],
    "LTX_2_3_FP8": [
        ("https://huggingface.co/Lightricks/LTX-2.3-fp8/resolve/main/ltx-2.3-22b-dev-fp8.safetensors", "checkpoints", None),
        ("https://huggingface.co/Lightricks/LTX-2.3/resolve/main/ltx-2.3-22b-distilled-lora-384.safetensors", "loras", None),
        ("https://huggingface.co/Lightricks/LTX-2.3/resolve/main/ltx-2.3-spatial-upscaler-x2-1.0.safetensors", "latent_upscale_models", None),
        ("https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/loras/gemma-3-12b-it-abliterated_lora_rank64_bf16.safetensors", "loras", None),
        ("https://huggingface.co/stabilityai/sd-vae-ft-mse-original/resolve/main/vae-ft-mse-840000-ema-pruned.safetensors", "vae", None),
    ],
    "LTX_2_3_BF16": [
        ("https://huggingface.co/Lightricks/LTX-2.3/resolve/main/ltx-2.3-22b-dev.safetensors", "checkpoints", None),
        ("https://huggingface.co/Lightricks/LTX-2.3/resolve/main/ltx-2.3-22b-distilled-lora-384.safetensors", "loras", None),
        ("https://huggingface.co/Lightricks/LTX-2.3/resolve/main/ltx-2.3-spatial-upscaler-x2-1.0.safetensors", "latent_upscale_models", None),
        ("https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/loras/gemma-3-12b-it-abliterated_lora_rank64_bf16.safetensors", "loras", None),
        ("https://huggingface.co/stabilityai/sd-vae-ft-mse-original/resolve/main/vae-ft-mse-840000-ema-pruned.safetensors", "vae", None),
    ],
    # LTX-2 Talking Avatar
    "LTX_2_TALKING_AVATAR": [
        ("https://huggingface.co/Kijai/LTXV2_comfy/resolve/main/diffusion_models/ltx-2-19b-dev_Q8_0.gguf", "diffusion_models", None),
        ("https://huggingface.co/Kijai/LTXV2_comfy/resolve/main/loras/ltx-2-19b-distilled-lora_resized_dynamic_fro09_avg_rank_175_bf16.safetensors", "loras", None),
        ("https://huggingface.co/Kijai/MelBandRoFormer_comfy/resolve/main/MelBandRoformer_fp16.safetensors", "diffusion_models", None),
        ("https://huggingface.co/unsloth/gemma-3-12b-it-GGUF/resolve/main/gemma-3-12b-it-Q2_K.gguf", "text_encoders", None),
        ("https://huggingface.co/Kijai/LTXV2_comfy/resolve/main/text_encoders/ltx-2-19b-embeddings_connector_dev_bf16.safetensors", "text_encoders", None),
        ("https://huggingface.co/Kijai/LTXV2_comfy/resolve/main/VAE/LTX2_audio_vae_bf16.safetensors", "vae", None),
        ("https://huggingface.co/Kijai/LTXV2_comfy/resolve/main/VAE/LTX2_video_vae_bf16.safetensors", "vae", None),
        ("https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-spatial-upscaler-x2-1.0.safetensors", "latent_upscale_models", None),
        ("https://huggingface.co/Lightricks/LTX-2-19b-LoRA-Camera-Control-Static/resolve/main/ltx-2-19b-lora-camera-control-static.safetensors", "loras", None),
    ],
    # Audio пресеты
    "ACE_STEP_1_5_AIO": [
        ("https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/checkpoints/ace_step_1.5_turbo_aio.safetensors", "checkpoints", None),
    ],
    "ACE_STEP_1_5_TURBO_SPLIT": [
        ("https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/diffusion_models/acestep_v1.5_turbo.safetensors", "diffusion_models", None),
        ("https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/text_encoders/qwen_1.7b_ace15.safetensors", "text_encoders", None),
        ("https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/vae/ace_1.5_vae.safetensors", "vae", None),
    ],
    # Wan VACE пресеты
    "WAN_VACE_F16": [
        ("https://huggingface.co/QuantStack/Wan2.1_14B_VACE-GGUF/resolve/main/Wan2.1_14B_VACE-F16.gguf", "diffusion_models", None),
        ("https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors", "vae", None),
        ("https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp16.safetensors", "text_encoders", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan21_CausVid_14B_T2V_lora_rank32.safetensors", "loras", None),
    ],
    "WAN_VACE_BF16": [
        ("https://huggingface.co/QuantStack/Wan2.1_14B_VACE-GGUF/resolve/main/Wan2.1_14B_VACE-BF16.gguf", "diffusion_models", None),
        ("https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors", "vae", None),
        ("https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp16.safetensors", "text_encoders", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan21_CausVid_14B_T2V_lora_rank32.safetensors", "loras", None),
    ],
    "WAN_VACE_Q5_K_S": [
        ("https://huggingface.co/QuantStack/Wan2.1_14B_VACE-GGUF/resolve/main/Wan2.1_14B_VACE-Q5_K_S.gguf", "diffusion_models", None),
        ("https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors", "vae", None),
        ("https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp16.safetensors", "text_encoders", None),
        ("https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan21_CausVid_14B_T2V_lora_rank32.safetensors", "loras", None),
    ],
}

# Категории пресетов
PRESET_CATEGORIES = {
    "Wan": {
        "name": "Wan",
        "icon": "🎬",
        "color": "#22c55e"
    },
    "Qwen": {
        "name": "Qwen",
        "icon": "🤖",
        "color": "#3b82f6"
    },
    "Z-Image": {
        "name": "Z-Image",
        "icon": "🖼️",
        "color": "#8b5cf6"
    },
    "Flux": {
        "name": "Flux",
        "icon": "⚡",
        "color": "#f59e0b"
    },
    "LTX": {
        "name": "LTX",
        "icon": "🎨",
        "color": "#ec4899"
    },
    "Audio": {
        "name": "Audio",
        "icon": "🎵",
        "color": "#06b6d4"
    }
}

# Доступные пресеты
PRESETS = {
    "WAN_T2V": {
        "name": "Wan T2V (Text-to-Video)",
        "description": "Генерация видео из текста",
        "size": "~40GB",
        "time": "15-20 мин",
        "category": "Wan",
        "video_guide": "https://youtu.be/9Yg02eaFHJI?si=sJeT5NunkyzdDxqp"
    },
    "WAN_T2I": {
        "name": "Wan T2I (Text-to-Image)", 
        "description": "Генерация изображений из текста",
        "size": "~18GB",
        "time": "8-12 мин",
        "category": "Wan",
        "video_guide": "https://youtu.be/D032P5gl5Wg?si=VUSoWugV5VI7e_Q3"
    },
    "WAN_I2V": {
        "name": "Wan I2V (Image-to-Video)",
        "description": "Генерация видео из изображения",
        "size": "~40GB", 
        "time": "15-20 мин",
        "category": "Wan",
        "video_guide": "https://youtu.be/SUh_25b4zeU?si=p8P-aXOYh5HIaIEW"
    },
    "WAN_I2V_LOOP": {
        "name": "Wan I2V Loop",
        "description": "Генерация зацикленного видео из изображения",
        "size": "~40GB",
        "time": "15-20 мин",
        "category": "Wan"
    },
    "WAN_ANIMATE": {
        "name": "Wan Animate",
        "description": "Анимация изображений",
        "size": "~30-40GB",
        "time": "10-18 мин",
        "category": "Wan",
        "has_variants": True,
        "variant_groups": {
            "Базовая версия": {
                "WAN_ANIMATE": {"name": "Классический", "size": "~30GB", "time": "10-15 мин"},
                "WAN_ANIMATE_CLASSIC_V2": {"name": "Classic V2", "size": "~35GB", "time": "12-18 мин"}
            },
            "Специализированные версии": {
                "WAN_ANIMATE_STEADY_DANCER": {"name": "Steady Dancer (танцевальная)", "size": "~30GB", "time": "12-18 мин"},
                "WAN_ANIMATE_ONETOALL": {"name": "OneToAll (согласованная)", "size": "~30GB", "time": "12-18 мин"},
                "WAN_ANIMATE_SCAIL": {"name": "SCAIL (контроль позы)", "size": "~40GB", "time": "12-18 мин"}
            }
        },
        "video_guide": "https://youtu.be/fUNbH3o_cE0?si=VTa-ljuPPaAngf3L"
    },
    "WAN_FLF": {
        "name": "Wan FLF (First Last Frame)",
        "description": "Генерация видео с помощью первого и последнего кадра",
        "size": "~40GB",
        "time": "15-20 мин",
        "category": "Wan"
    },
    "WAN_LIGHTX2V": {
        "name": "Wan LightX2V",
        "description": "LightX2V модели для генерации видео",
        "size": "~70GB",
        "time": "12-18 мин",
        "category": "Wan"
    },
    "WAN_I2I_REFINER": {
        "name": "Wan I2I Refiner",
        "description": "Модели для улучшения изображений (Image-to-Image Refiner)",
        "size": "~15GB",
        "time": "8-12 мин",
        "category": "Wan"
    },
    "WAN_CHRONOEDIT": {
        "name": "ChronoEdit",
        "description": "Редактирование изображений через создание видео",
        "size": "~25GB",
        "time": "10-15 мин",
        "category": "Wan"
    },
    "WAN_T2V_T2I_BATCH": {
        "name": "T2V&T2I Batch",
        "description": "Параллельная генерация изображений и видео",
        "size": "~20GB",
        "time": "8-12 мин",
        "category": "Wan"
    },
    "WAN_INFINITETALK": {
        "name": "Wan InfiniteTalk",
        "description": "LipSync говорящие аватары",
        "size": "~35GB",
        "time": "12-18 мин",
        "category": "Wan"
    },
    "WAN_2_1_ALPHA": {
        "name": "Wan 2.1 Alpha",
        "description": "Генерация видео из текста с поддержкой альфа канала",
        "size": "~25GB",
        "time": "10-15 мин",
        "category": "Wan"
    },
    "WAN_REMIX_I2V": {
        "name": "Wan Remix I2V",
        "description": "Креативная модель для генерации видео с реалистичными движениеми",
        "size": "~30GB",
        "time": "12-18 мин",
        "category": "Wan"
    },
    "WAN_VACE": {
        "name": "Wan VACE",
        "description": "Изменение и стилизация видео на основе исходного ролика с сохранением движения, композиции и таймингов",
        "size": "~35GB",
        "time": "12-18 мин",
        "category": "Wan",
        "has_variants": True,
        "variant_groups": {
            "Версия модели": {
                "WAN_VACE_F16": {"name": "F16 (Full precision)", "size": "~35GB", "time": "12-18 мин"},
                "WAN_VACE_BF16": {"name": "BF16 (Brain float)", "size": "~35GB", "time": "12-18 мин"},
                "WAN_VACE_Q5_K_S": {"name": "Q5_K_S (Quantized)", "size": "~15GB", "time": "8-12 мин"}
            }
        }
    },
    # Qwen пресеты (группированные с двухуровневыми вариантами)
    "QWEN_IMAGE": {
        "name": "Qwen Image (Text-to-Image)", 
        "description": "Генерация изображений из текста",
        "size": "~15-40GB",
        "time": "8-20 мин",
        "category": "Qwen",
        "has_variants": True,
        "variant_groups": {
            "Базовая версия": {
                "QWEN_IMAGE": {"name": "FP8", "size": "~15GB", "time": "8-12 мин"},
                "QWEN_IMAGE_BF16": {"name": "BF16", "size": "~40GB", "time": "10-20 мин"}
            },
            "Версия 2512": {
                "QWEN_IMAGE_2512_FP8": {"name": "FP8", "size": "~15GB", "time": "8-12 мин"},
                "QWEN_IMAGE_2512_BF16": {"name": "BF16", "size": "~40GB", "time": "10-20 мин"},
                "QWEN_IMAGE_2512_Q8_GGUF": {"name": "Q8 GGUF", "size": "~20GB", "time": "10-15 мин"}
            }
        }
    },
    "QWEN_EDIT": {
        "name": "Qwen Edit (Image Edit)",
        "description": "Редактирование изображений",
        "size": "~15-40GB",
        "time": "8-20 мин",
        "category": "Qwen",
        "has_variants": True,
        "variant_groups": {
            "Базовая версия": {
                "QWEN_EDIT": {"name": "FP8", "size": "~15GB", "time": "8-12 мин"},
                "QWEN_EDIT_BF16": {"name": "BF16", "size": "~40GB", "time": "10-20 мин"}
            },
            "Версия 2509": {
                "QWEN_EDIT_2509_FP8": {"name": "FP8", "size": "~15GB", "time": "8-12 мин"},
                "QWEN_EDIT_2509_BF16": {"name": "BF16", "size": "~40GB", "time": "10-20 мин"}
            },
            "Версия 2511": {
                "QWEN_EDIT_2511_FP8": {"name": "FP8", "size": "~15GB", "time": "8-12 мин"},
                "QWEN_EDIT_2511_BF16": {"name": "BF16", "size": "~40GB", "time": "10-20 мин"}
            }
        }
    },
    "QWEN_LAYERED": {
        "name": "Qwen Layered",
        "description": "Разложить изображение на слои",
        "size": "~40GB",
        "time": "10-20 мин",
        "category": "Qwen",
        "has_variants": True,
        "variant_groups": {
            "Форматы": {
                "QWEN_LAYERED_FP8": {"name": "FP8", "size": "~40GB", "time": "10-20 мин"},
                "QWEN_LAYERED_BF16": {"name": "BF16", "size": "~40GB", "time": "10-20 мин"}
            }
        }
    },
    "Z_IMAGE": {
        "name": "Z-Image",
        "description": "Фундаментальная RAW модель генерации изображений",
        "size": "~15-20GB",
        "time": "8-12 мин",
        "category": "Z-Image"
    },
    "Z_IMAGE_TURBO": {
        "name": "Z Image Turbo",
        "description": "Быстрая генерация изображений из текста",
        "size": "~15-20GB",
        "time": "8-12 мин",
        "category": "Z-Image"
    },
    "LTX_2": {
        "name": "LTX-2",
        "description": "Генерация видео из текста и картинки с озвучкой",
        "size": "~20-40GB",
        "time": "10-20 мин",
        "category": "LTX",
        "has_variants": True,
        "variant_groups": {
            "Форматы": {
                "LTX_2_FP8": {"name": "FP8", "size": "~20GB", "time": "10-15 мин"},
                "LTX_2_BF16": {"name": "BF16 (полная версия)", "size": "~40GB", "time": "15-20 мин"}
            }
        }
    },
    "LTX_2_DISTILLED": {
        "name": "LTX-2 Distilled",
        "description": "Дистиллированная версия LTX-2 для более быстрой генерации",
        "size": "~20-40GB",
        "time": "10-20 мин",
        "category": "LTX",
        "has_variants": True,
        "variant_groups": {
            "Форматы": {
                "LTX_2_DISTILLED_FP8": {"name": "FP8", "size": "~20GB", "time": "10-15 мин"},
                "LTX_2_DISTILLED_BF16": {"name": "BF16 (полная версия)", "size": "~40GB", "time": "15-20 мин"}
            }
        }
    },
    "LTX_2_3": {
        "name": "LTX-2.3",
        "description": "Четкая детализация. Чистый звук. Динамичное движение.",
        "size": "~20-60GB",
        "time": "10-20 мин",
        "category": "LTX",
        "has_variants": True,
        "variant_groups": {
            "Форматы": {
                "LTX_2_3_FP8": {"name": "FP8", "size": "~20GB", "time": "10-15 мин"},
                "LTX_2_3_BF16": {"name": "BF16 (полная версия)", "size": "~60GB", "time": "15-20 мин"}
            }
        }
    },
    "LTX_2_TALKING_AVATAR": {
        "name": "LTX-2 Talking Avatar",
        "description": "LipSync говорящие аватары с клонированием голоса",
        "size": "~50GB",
        "time": "10-15 мин",
        "category": "LTX"
    },
    # Audio пресеты
    "ACE_STEP_1_5": {
        "name": "ACE-Step 1.5",
        "description": "Full-song генерация: жанр, вокал, текст и аранжировка",
        "size": "~3GB",
        "time": "3-5 мин",
        "category": "Audio",
        "has_variants": True,
        "variant_groups": {
            "Версия": {
                "ACE_STEP_1_5_AIO": {"name": "AIO (одна нода)", "size": "~3GB", "time": "3-5 мин"},
                "ACE_STEP_1_5_TURBO_SPLIT": {"name": "Turbo Split", "size": "~3GB", "time": "3-5 мин"}
            }
        }
    },
    # Flux пресеты
    "FLUX_2_DEV_FP8": {
        "name": "Flux.2 Dev FP8 Mixed",
        "description": "Генерация изображений из текста с моделью Flux.2 Dev",
        "size": "~29GB",
        "time": "12-18 мин",
        "category": "Flux"
    },
    "FLUX_2_KLEIN": {
        "name": "Flux.2 Klein 4B",
        "description": "Компактная версия Flux.2 для генерации изображений",
        "size": "~13GB",
        "time": "8-12 мин",
        "category": "Flux",
        "has_variants": True,
        "variant_groups": {
            "Версия модели": {
                "FLUX_2_KLEIN_BASE_FP8": {"name": "Base FP8", "size": "~13GB", "time": "8-12 мин"},
                "FLUX_2_KLEIN_FP8": {"name": "Standard FP8", "size": "~13GB", "time": "8-12 мин"}
            }
        }
    },
    "FLUX_1_KREA_FP8": {
        "name": "Flux.1 Krea Dev",
        "description": "Специализированная версия Flux.1 от Krea для генерации изображений",
        "size": "~28GB",
        "time": "12-18 мин",
        "category": "Flux"
    }
}

INDEX_HTML = """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Загрузчик пресетов и моделей</title>
  <style>
    :root { --bg:#1e1e1e; --card:#282828; --text:#ffffff; --muted:#9ca3af; --accent:#ffffff; --accent-border:#000000; }
    html,body { margin:0; padding:0; background:var(--bg); color:var(--text); font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, Arial; }
    .wrap { max-width: 1200px; margin: 0 auto; padding: 40px 20px; }
    .title { font-size: 36px; font-weight: 800; margin: 0 0 8px; color: var(--accent); text-align: center; text-shadow: 0 0 10px rgba(255,255,255,0.3); }
    .subtitle { margin:0 0 40px; color:var(--muted); text-align: center; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin: 0 auto; max-width: 1000px; }
    .card { background: var(--card); border:1px solid #3a3a3a; border-radius: 12px; padding: 24px; box-sizing: border-box; }
    .row { display:grid; grid-template-columns: 200px 1fr; gap:16px; align-items:center; margin:16px 0; }
    .row-full { display:grid; grid-template-columns: 1fr; gap:16px; margin:16px 0; }
    input[type=text], input[type=password] { width:100%; padding:12px 16px; background:#1a1a1a; border:1px solid #3a3a3a; color:var(--text); border-radius:8px; box-sizing: border-box; }
    .btn { display:inline-flex; align-items:center; gap:8px; padding:12px 20px; background: rgba(255,255,255,0.9); color:var(--bg); font-weight:700; border:2px solid rgba(255,255,255,0.5); border-radius:8px; cursor:pointer; transition: all 0.2s; }
    .btn:hover { background: var(--accent); color:var(--bg); border-color: var(--accent); }
    .btn:disabled { opacity:0.5; cursor:not-allowed; }
    .btn-preset { 
      background: rgba(34, 197, 94, 0.9); 
      color: white; 
      border-color: rgba(34, 197, 94, 0.5); 
      box-shadow: 0 4px 12px rgba(34, 197, 94, 0.3);
    }
    .btn-preset:hover { 
      background: rgb(34, 197, 94); 
      color: white;
      border-color: rgb(34, 197, 94); 
      box-shadow: 0 8px 20px rgba(34, 197, 94, 0.5);
    }
    .btn-hf { 
      background: rgba(255, 193, 7, 0.9); 
      color: black; 
      border-color: rgba(255, 193, 7, 0.5); 
      box-shadow: 0 4px 12px rgba(255, 193, 7, 0.3);
    }
    .btn-hf:hover { 
      background: rgb(255, 193, 7); 
      color: black;
      border-color: rgb(255, 193, 7); 
      box-shadow: 0 8px 20px rgba(255, 193, 7, 0.5);
    }
    a { color:var(--accent); text-decoration:none; border-bottom: 1px solid rgba(255,255,255,0.3); }
    a:hover { text-decoration:none; border-bottom-color: var(--accent); }
    .hint { background:#1a1a1a; border:1px dashed #3a3a3a; padding:16px; border-radius:8px; margin-bottom:20px; }
    .result { white-space: pre-wrap; background:#1a1a1a; border:1px solid #3a3a3a; padding:16px; border-radius:8px; margin-top:20px; min-height:24px; }
    .progress { margin-top:20px; }
    .progress-bar { width:100%; height:8px; background:#1a1a1a; border:1px solid #3a3a3a; border-radius:4px; overflow:hidden; }
    .progress-fill { height:100%; background:var(--accent); width:0%; transition:width 0.3s; }
    .progress-text { margin-top:8px; color:var(--muted); font-size:14px; text-align:center; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; }
    .preset-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px; margin: 20px 0; }
    .preset-card { background: #1a1a1a; border: 1px solid #3a3a3a; border-radius: 8px; padding: 16px; cursor: pointer; transition: all 0.2s; position: relative; }
    .preset-card:hover { border-color: var(--accent); background: #222; }
    .preset-card.selected { border-color: var(--accent); background: rgba(255,255,255,0.1); }
    .preset-name { font-weight: 700; margin-bottom: 8px; color: var(--accent); }
    .preset-desc { color: var(--muted); font-size: 14px; margin-bottom: 8px; }
    .preset-info { font-size: 12px; color: var(--muted); }
    .video-guide-icon { 
      position: absolute;
      top: 12px;
      right: 12px;
      width: 22px; 
      height: 22px; 
      background: white; 
      border-radius: 50%; 
      display: inline-flex; 
      align-items: center; 
      justify-content: center; 
      color: black; 
      font-weight: bold; 
      font-size: 14px; 
      text-decoration: none; 
      transition: all 0.2s;
      border: 1px solid rgba(255,255,255,0.3);
      z-index: 10;
    }
    .video-guide-icon:hover { 
      background: var(--accent); 
      color: var(--bg); 
      transform: scale(1.15);
      box-shadow: 0 0 10px rgba(255,255,255,0.4);
    }
    .tabs { display: flex; gap: 8px; margin-bottom: 20px; justify-content: center; flex-wrap: wrap; }
    .tab { padding: 8px 16px; background: #1a1a1a; border: 1px solid #3a3a3a; border-radius: 8px; cursor: pointer; transition: all 0.2s; }
    .tab.active { background: var(--accent); color: var(--bg); }
    .tab-content { display: none; }
    .tab-content.active { display: block; }
    .search-container { margin-bottom: 20px; position: relative; }
    .search-input { width: 100%; padding: 12px 16px 12px 44px; background: #1a1a1a; border: 1px solid #3a3a3a; color: var(--text); border-radius: 8px; box-sizing: border-box; font-size: 14px; }
    .search-icon { position: absolute; left: 14px; top: 50%; transform: translateY(-50%); color: var(--muted); pointer-events: none; }
    .category-filters { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; align-items: center; }
    .category-filter { padding: 8px 16px; background: #1a1a1a; border: 1px solid #3a3a3a; border-radius: 8px; cursor: pointer; transition: all 0.2s; display: flex; align-items: center; gap: 6px; font-size: 14px; }
    .category-filter:hover { border-color: var(--accent); background: #222; }
    .category-filter.active { background: var(--accent); color: var(--bg); border-color: var(--accent); }
    .category-filter.all { background: #2a2a2a; }
    .category-filter.all.active { background: var(--accent); }
    .preset-card.hidden { display: none; }
    .preset-variants { margin-top: 12px; padding-top: 12px; border-top: 1px solid #3a3a3a; display: none; }
    .preset-card.expanded .preset-variants { display: block; }
    .preset-variant-group { margin-bottom: 16px; }
    .preset-variant-group-title { font-size: 13px; font-weight: 600; color: var(--accent); margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #2a2a2a; }
    .preset-variant-item { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; padding: 8px; background: #0f0f0f; border-radius: 6px; cursor: pointer; transition: all 0.2s; }
    .preset-variant-item:hover { background: #151515; }
    .preset-variant-item input[type="checkbox"] { width: 16px; height: 16px; cursor: pointer; }
    .preset-variant-label { flex: 1; font-size: 13px; color: var(--muted); }
    .preset-variant-label strong { color: var(--text); }
    .preset-variant-info { font-size: 11px; color: var(--muted); }
    .preset-expand-icon { position: absolute; top: 50%; right: 16px; transform: translateY(-50%); font-size: 18px; color: var(--muted); transition: transform 0.2s; cursor: pointer; z-index: 5; }
    .preset-card.expanded .preset-expand-icon { transform: translateY(-50%) rotate(180deg); }
    .preset-expand-icon:hover { color: var(--accent); }
  </style>
</head>
<body>
  <div class="wrap">
    <h1 class="title">Загрузчик пресетов и моделей</h1>
    <p class="subtitle">Скачивание пресетов и моделей с HuggingFace</p>
    
    <div class="tabs">
      <div class="tab active" onclick="switchTab('presets')">🎯 Пресеты</div>
      <div class="tab" onclick="switchTab('huggingface')">🤗 HuggingFace</div>
    </div>
    
    <div class="grid">
      <!-- Пресеты -->
      <div class="card tab-content active" id="presets-tab">
        <h3>Выберите пресеты для скачивания</h3>
        
        <!-- Поиск -->
        <div class="search-container">
          <input type="text" class="search-input" id="preset-search" placeholder="Поиск пресетов..." oninput="filterPresets()">
        </div>
        
        <!-- Фильтры категорий -->
        <div class="category-filters" id="category-filters">
          {{ category_filters_html }}
        </div>
        
        <div class="preset-grid" id="preset-grid">
          {{ presets_html }}
        </div>
        <div class="row-full">
          <button class="btn btn-preset" onclick="downloadPresets()" id="download-presets-btn" disabled>
            📥 Скачать выбранные пресеты
          </button>
        </div>
        <div class="result" id="preset-result"></div>
        <div class="progress" id="preset-progress" style="display:none;">
          <div class="progress-bar">
            <div class="progress-fill" id="preset-progress-fill"></div>
          </div>
          <div class="progress-text" id="preset-progress-text">Загрузка...</div>
        </div>
      </div>
      
      <!-- HuggingFace -->
      <div class="card tab-content" id="huggingface-tab">
        <div class="hint">
          <b>Как использовать?</b> Выберите способ: прямая ссылка на файл (рекомендуется) или HuggingFace репозиторий. 
          Для приватных моделей нужен API токен с правами "Read" - см. инструкцию ниже.
        </div>
        
        <div class="tabs" style="margin-bottom: 20px;">
          <div class="tab active" onclick="switchHFMethod('url')">🔗 Прямая ссылка</div>
          <div class="tab" onclick="switchHFMethod('repo')">🤗 HuggingFace Repo</div>
        </div>
        
        <!-- Прямая ссылка метод (дефолтный) -->
        <form id="hf-url-form" method="post" action="/download_url" style="margin-top:12px;">
          <div class="row">
            <label for="hf_url">Прямая ссылка на файл</label>
            <input id="hf_url" type="text" name="url" placeholder="https://huggingface.co/username/model/resolve/main/file.safetensors" required />
          </div>
          <div class="row">
            <label for="hf_url_folder">Папка назначения</label>
            <select id="hf_url_folder" name="folder" style="width:100%; padding:12px 16px; background:#1a1a1a; border:1px solid #3a3a3a; color:var(--text); border-radius:8px;">
              <option value="diffusion_models">diffusion_models</option>
              <option value="loras">loras</option>
              <option value="vae">vae</option>
              <option value="text_encoders">text_encoders</option>
              <option value="upscale_models">upscale_models</option>
              <option value="latent_upscale_models">latent_upscale_models</option>
              <option value="clip_vision">clip_vision</option>
              <option value="audio_encoders">audio_encoders</option>
              <option value="checkpoints">checkpoints</option>
              <option value="clip">clip</option>
              <option value="configs">configs</option>
              <option value="controlnet">controlnet</option>
              <option value="diffusers">diffusers</option>
              <option value="embeddings">embeddings</option>
              <option value="gligen">gligen</option>
              <option value="hypernetworks">hypernetworks</option>
              <option value="ipadapter">ipadapter</option>
              <option value="model_patches">model_patches</option>
              <option value="onnx">onnx</option>
              <option value="photomaker">photomaker</option>
              <option value="sams">sams</option>
              <option value="style_models">style_models</option>
              <option value="unet">unet</option>
              <option value="vae_approx">vae_approx</option>
              <option value="vibevoice">vibevoice</option>
              <option value="detection">detection</option>
            </select>
          </div>
          <div class="row" style="grid-template-columns:1fr;">
            <button class="btn btn-hf" type="submit">🔗 Скачать по ссылке</button>
          </div>
        </form>
        
        <!-- HuggingFace Repo метод -->
        <form id="hf-repo-form" method="post" action="/download_hf" style="margin-top:12px; display:none;">
          <div class="row">
            <label for="hf_repo">Репозиторий</label>
            <input id="hf_repo" type="text" name="repo" placeholder="username/model-name" value="{{ hf_repo_value }}" />
          </div>
          <div class="row">
            <label for="hf_file">Файл (опционально)</label>
            <input id="hf_file" type="text" name="filename" placeholder="model.safetensors" value="{{ hf_file_value }}" />
          </div>
          <div class="row">
            <label for="hf_token">API токен (опционально)</label>
            <input id="hf_token" type="password" name="token" placeholder="hf_..." value="{{ hf_token_value }}" autocomplete="current-password" />
            <div style="margin-top: 8px; padding: 12px; background: #1a1a1a; border: 1px solid #3a3a3a; border-radius: 8px; font-size: 12px; word-wrap: break-word;">
              <div style="color: #4a9eff; font-weight: 600; margin-bottom: 8px;">📋 Как создать токен:</div>
              <div style="color: #ccc; line-height: 1.4;">
                1. Перейдите по ссылке: <a href="https://huggingface.co/settings/tokens" target="_blank" style="color: #4a9eff; text-decoration: underline;">https://huggingface.co/settings/tokens</a><br>
                2. Нажмите "New token"<br>
                3. Выберите "Read" (достаточно для скачивания)<br>
                4. Введите название токена<br>
                5. Нажмите "Create token"<br>
                6. Скопируйте токен (начинается с hf_...)
              </div>
            </div>
          </div>
          <div class="row">
            <label for="hf_folder">Папка назначения</label>
            <select id="hf_folder" name="folder" style="width:100%; padding:12px 16px; background:#1a1a1a; border:1px solid #3a3a3a; color:var(--text); border-radius:8px;">
              <option value="diffusion_models">diffusion_models</option>
              <option value="loras">loras</option>
              <option value="vae">vae</option>
              <option value="text_encoders">text_encoders</option>
              <option value="upscale_models">upscale_models</option>
              <option value="latent_upscale_models">latent_upscale_models</option>
              <option value="clip_vision">clip_vision</option>
              <option value="audio_encoders">audio_encoders</option>
              <option value="checkpoints">checkpoints</option>
              <option value="clip">clip</option>
              <option value="configs">configs</option>
              <option value="controlnet">controlnet</option>
              <option value="diffusers">diffusers</option>
              <option value="embeddings">embeddings</option>
              <option value="gligen">gligen</option>
              <option value="hypernetworks">hypernetworks</option>
              <option value="ipadapter">ipadapter</option>
              <option value="model_patches">model_patches</option>
              <option value="onnx">onnx</option>
              <option value="photomaker">photomaker</option>
              <option value="sams">sams</option>
              <option value="style_models">style_models</option>
              <option value="unet">unet</option>
              <option value="vae_approx">vae_approx</option>
              <option value="vibevoice">vibevoice</option>
              <option value="detection">detection</option>
            </select>
          </div>
          <div class="row" style="grid-template-columns:1fr;">
            <button class="btn btn-hf" type="submit">🤗 Скачать с HuggingFace</button>
          </div>
        </form>
        <div class="result" id="hf-result">{{ hf_result }}</div>
        <div class="progress" id="hf-progress" style="display:none;">
          <div class="progress-bar">
            <div class="progress-fill" id="hf-progress-fill"></div>
          </div>
          <div class="progress-text" id="hf-progress-text">Загрузка...</div>
        </div>
      </div>
    </div>
  </div>
  
  <script src="/static/script.js"></script>
  <script>
    // Дополнительный JavaScript код для HuggingFace функций
    
    // Ждём полной загрузки DOM перед регистрацией обработчиков
    document.addEventListener('DOMContentLoaded', function() {
      console.log('HF handlers initializing...');
      
      // Проверяем наличие форм
      const hfForm = document.querySelector('form[action="/download_hf"]');
      const urlForm = document.querySelector('form[action="/download_url"]');
      
      if (!hfForm || !urlForm) {
        console.error('Forms not found!', { hfForm, urlForm });
        return;
      }
      
      console.log('Forms found, attaching handlers');
      
      // Обработка формы HuggingFace (только для репозитория)
      hfForm.addEventListener('submit', function(e) {
        e.preventDefault(); // Предотвращаем стандартную отправку формы
        console.log('HF form submitted');
        
        const progress = document.getElementById('hf-progress');
        const result = document.getElementById('hf-result');
        const btn = document.querySelector('form[action="/download_hf"] button[type="submit"]');
        
        // Показываем прогресс
        progress.style.display = 'block';
        result.textContent = '';
        btn.disabled = true;
        btn.textContent = 'Загрузка...';
        
        // Отправляем форму через fetch
        const formData = new FormData(this);
        
        fetch('/download_hf', {
          method: 'POST',
          body: formData
        })
        .then(response => response.json())
        .then(data => {
          if (data.task_id) {
            result.textContent = data.message;
            // Начинаем опрос статуса
            pollHFStatus(data.task_id);
          } else {
            result.textContent = data.message;
            progress.style.display = 'none';
            btn.disabled = false;
            btn.textContent = '🤗 Скачать с HuggingFace';
          }
        })
        .catch(error => {
          result.textContent = '❌ Ошибка: ' + error.message;
          progress.style.display = 'none';
          btn.disabled = false;
          btn.textContent = '🤗 Скачать с HuggingFace';
        });
      });
      
      // Обработка формы прямой ссылки
      urlForm.addEventListener('submit', function(e) {
        e.preventDefault(); // Предотвращаем стандартную отправку формы
        console.log('URL form submitted');
        
        const progress = document.getElementById('hf-progress');
        const result = document.getElementById('hf-result');
        const btn = document.querySelector('form[action="/download_url"] button[type="submit"]');
        
        // Показываем прогресс
        progress.style.display = 'block';
        result.textContent = '';
        btn.disabled = true;
        btn.textContent = 'Загрузка...';
        
        // Отправляем форму через fetch
        const formData = new FormData(this);
        
        fetch('/download_url', {
          method: 'POST',
          body: formData
        })
        .then(response => response.json())
        .then(data => {
          if (data.task_id) {
            result.textContent = data.message;
            // Начинаем опрос статуса
            pollHFStatus(data.task_id);
          } else {
            result.textContent = data.message;
            progress.style.display = 'none';
            btn.disabled = false;
            btn.textContent = '🔗 Скачать по ссылке';
          }
        })
        .catch(error => {
          result.textContent = '❌ Ошибка: ' + error.message;
          progress.style.display = 'none';
          btn.disabled = false;
          btn.textContent = '🔗 Скачать по ссылке';
        });
      });
      
      console.log('HF handlers attached successfully');
    });
    
    function pollHFStatus(taskId) {
      const progress = document.getElementById('hf-progress');
      const progressFill = document.getElementById('hf-progress-fill');
      const progressText = document.getElementById('hf-progress-text');
      const result = document.getElementById('hf-result');
      
      // Находим активную кнопку (видимую форму)
      const hfForm = document.getElementById('hf-repo-form');
      const urlForm = document.getElementById('hf-url-form');
      let btn = null;
      
      if (hfForm.style.display !== 'none') {
        btn = hfForm.querySelector('button[type="submit"]');
      } else if (urlForm.style.display !== 'none') {
        btn = urlForm.querySelector('button[type="submit"]');
      }
      
      if (!btn) {
        // Fallback - ищем любую кнопку
        btn = document.querySelector('form[action="/download_hf"] button[type="submit"]') || 
              document.querySelector('form[action="/download_url"] button[type="submit"]');
      }
      
      fetch('/status/' + taskId)
      .then(response => response.json())
      .then(data => {
        if (data.status === 'completed' || data.status === 'error') {
          result.textContent = data.message;
          progress.style.display = 'none';
          if (btn) {
            btn.disabled = false;
            btn.textContent = btn.textContent.includes('HuggingFace') ? '🤗 Скачать с HuggingFace' : '🔗 Скачать по ссылке';
          }
        } else if (data.status === 'running') {
          // Обновляем прогресс-бар
          const progressPercent = data.progress || 0;
          progressFill.style.width = progressPercent + '%';
          progressText.textContent = data.message || 'Загрузка...';
          result.textContent = data.message || 'Загрузка...';
          
          // Повторяем через 500ms для более плавного обновления
          setTimeout(() => pollHFStatus(taskId), 500);
        } else {
          result.textContent = '❌ Неизвестный статус: ' + data.message;
          progress.style.display = 'none';
          if (btn) {
            btn.disabled = false;
            btn.textContent = btn.textContent.includes('HuggingFace') ? '🤗 Скачать с HuggingFace' : '🔗 Скачать по ссылке';
          }
        }
      })
      .catch(error => {
        result.textContent = '❌ Ошибка проверки статуса: ' + error.message;
        progress.style.display = 'none';
        if (btn) {
          btn.disabled = false;
          btn.textContent = btn.textContent.includes('HuggingFace') ? '🤗 Скачать с HuggingFace' : '🔗 Скачать по ссылке';
        }
      });
    }
  </script>
</body>
</html>
"""

def generate_category_filters_html():
    html = '<div class="category-filter all active" onclick="filterByCategory(\'all\', event)">Все</div>'
    for category_id, category_info in PRESET_CATEGORIES.items():
        html += f'''
        <div class="category-filter" onclick="filterByCategory('{category_id}', event)" data-category="{category_id}">
          <span>{category_info['icon']}</span>
          <span>{category_info['name']}</span>
        </div>
        '''
    return html

def generate_presets_html():
    html = ""
    for preset_id, preset_info in PRESETS.items():
        category = preset_info.get('category', 'Wan')
        video_guide_html = ""
        if preset_info.get('video_guide'):
            video_guide_html = f'<a href="{preset_info["video_guide"]}" target="_blank" rel="noopener noreferrer" class="video-guide-icon" onclick="event.stopPropagation();" title="Видео-гайд">i</a>'
        
        # Проверяем, есть ли варианты (для Qwen пресетов)
        if preset_info.get('has_variants') and preset_info.get('variant_groups'):
            variants_html = ""
            for group_name, variants in preset_info['variant_groups'].items():
                group_html = f'<div class="preset-variant-group-title">{group_name}</div>'
                for variant_id, variant_info in variants.items():
                    group_html += f'''
                    <div class="preset-variant-item" onclick="event.stopPropagation();">
                      <input type="checkbox" id="variant-{variant_id}" data-variant="{variant_id}" data-parent="{preset_id}" onchange="toggleVariant('{preset_id}', '{variant_id}')">
                      <label for="variant-{variant_id}" class="preset-variant-label">
                        <strong>{variant_info['name']}</strong>
                        <span class="preset-variant-info"> • {variant_info['size']} • {variant_info['time']}</span>
                      </label>
                    </div>
                    '''
                variants_html += f'<div class="preset-variant-group">{group_html}</div>'
            
            html += f'''
            <div class="preset-card" data-preset="{preset_id}" data-category="{category}" onclick="togglePresetCard('{preset_id}', event)">
              {video_guide_html}
              <span class="preset-expand-icon" onclick="event.stopPropagation(); togglePresetCard('{preset_id}', event)">▼</span>
              <div class="preset-name">{preset_info['name']}</div>
              <div class="preset-desc">{preset_info['description']}</div>
              <div class="preset-info">Размер: {preset_info['size']} • Время: {preset_info['time']}</div>
              <div class="preset-variants">
                <div style="font-size: 12px; color: var(--muted); margin-bottom: 12px;">Выберите версию и формат:</div>
                {variants_html}
              </div>
            </div>
            '''
        else:
            # Обычная карточка без вариантов (Wan пресеты)
            html += f'''
            <div class="preset-card" data-preset="{preset_id}" data-category="{category}" onclick="togglePreset('{preset_id}')">
              {video_guide_html}
              <div class="preset-name">{preset_info['name']}</div>
              <div class="preset-desc">{preset_info['description']}</div>
              <div class="preset-info">Размер: {preset_info['size']} • Время: {preset_info['time']}</div>
            </div>
            '''
    return html

@app.get("/", response_class=HTMLResponse)
def index():
    presets_html = generate_presets_html()
    category_filters_html = generate_category_filters_html()
    return HTMLResponse(INDEX_HTML.replace("{{ presets_html }}", presets_html)
                       .replace("{{ category_filters_html }}", category_filters_html)
                       .replace("{{ hf_repo_value }}", "")
                       .replace("{{ hf_file_value }}", "")
                       .replace("{{ hf_token_value }}", "")
                       .replace("{{ hf_result }}", ""))

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Preset downloader is running"}

@app.get("/status/{task_id}")
def get_status(task_id: str):
    if task_id not in download_status:
        return {"status": "not_found", "message": "Задача не найдена"}
    
    return download_status[task_id]


@app.get("/api/tasks")
def get_all_tasks():
    """Get all download tasks (for dashboard integration)."""
    # Filter to show only active/recent tasks
    active_tasks = []
    for task_id, status in download_status.items():
        task_info = {
            "task_id": task_id,
            **status
        }
        active_tasks.append(task_info)
    
    # Sort by most recent (downloading first, then completed)
    def sort_key(t):
        s = t.get("status", "")
        if s == "downloading":
            return 0
        elif s == "completed":
            return 1
        elif s == "error":
            return 2
        return 3
    
    active_tasks.sort(key=sort_key)
    return {"tasks": active_tasks[:20]}  # Limit to 20 most recent


@app.post("/download_presets")
def download_presets(presets: str = Form(...)):
    try:
        # Парсим строку пресетов
        presets_list = [p.strip() for p in presets.split(',') if p.strip()]
        
        if not presets_list:
            return {"message": "❌ Не выбрано ни одного пресета"}
        
        # Запускаем скрипт скачивания пресетов в фоне
        import threading
        import uuid
        
        # Создаем уникальный ID для отслеживания
        task_id = str(uuid.uuid4())
        
        def download_file_with_progress(url, dest_dir, custom_filename, current_file, total_files, task_id):
            """Скачивает файл с отслеживанием прогресса в реальном времени, как в LoRA загрузчике"""
            import re
            
            # Определяем имя файла
            if custom_filename:
                filename = custom_filename
            else:
                filename = os.path.basename(url)
                # Убираем параметры запроса
                if '?' in filename:
                    filename = filename.split('?')[0]
            
            filepath = os.path.join(dest_dir, filename)
            os.makedirs(dest_dir, exist_ok=True)
            
            # Проверяем, существует ли файл
            if os.path.isfile(filepath) and os.path.getsize(filepath) > 0:
                download_status[task_id] = {
                    "status": "running",
                    "message": f"⏭️ Пропущено (уже существует): {filename} ({current_file}/{total_files})",
                    "progress": (current_file / total_files * 100),
                    "total_files": total_files,
                    "current_file": current_file,
                    "current_filename": filename
                }
                return "SKIP", filename
            
            # Обновляем статус - начало скачивания
            download_status[task_id] = {
                "status": "running",
                "message": f"📥 Скачивание файла {current_file} из {total_files}: {filename} (0%)",
                "progress": ((current_file - 1) / total_files * 100),
                "total_files": total_files,
                "current_file": current_file,
                "current_filename": filename
            }
            
            try:
                # Скачиваем файл с отслеживанием прогресса
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                response = requests.get(url, stream=True, headers=headers, timeout=300)
                response.raise_for_status()
                
                # Получаем размер файла
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                last_update = 0
                update_interval = 1024 * 1024 * 5  # Обновляем каждые 5MB
                
                # Скачиваем по частям и обновляем прогресс
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB chunks
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            # Обновляем прогресс каждые 5MB или если это последний chunk
                            if downloaded - last_update >= update_interval or (total_size > 0 and downloaded >= total_size):
                                last_update = downloaded
                                
                                # Обновляем прогресс
                                if total_size > 0:
                                    file_percent = int((downloaded / total_size) * 100)
                                    # Вычисляем общий прогресс: (current-1)/total + file_percent/(100*total)
                                    overall_progress = ((current_file - 1) / total_files * 100) + (file_percent / total_files)
                                    
                                    download_status[task_id] = {
                                        "status": "running",
                                        "message": f"📥 Скачивание файла {current_file} из {total_files}: {filename} ({file_percent}%)",
                                        "progress": min(overall_progress, 100),
                                        "total_files": total_files,
                                        "current_file": current_file,
                                        "current_filename": filename
                                    }
                                else:
                                    # Если размер неизвестен, показываем только что идет скачивание
                                    size_mb = downloaded / (1024 * 1024)
                                    download_status[task_id] = {
                                        "status": "running",
                                        "message": f"📥 Скачивание файла {current_file} из {total_files}: {filename} ({size_mb:.1f} MB)",
                                        "progress": ((current_file - 1) / total_files * 100) + 0.1,  # Минимальный прогресс
                                        "total_files": total_files,
                                        "current_file": current_file,
                                        "current_filename": filename
                                    }
                
                # Финальное обновление - файл скачан
                download_status[task_id] = {
                    "status": "running",
                    "message": f"✅ Завершено: {filename} ({current_file}/{total_files})",
                    "progress": (current_file / total_files * 100),
                    "total_files": total_files,
                    "current_file": current_file,
                    "current_filename": filename
                }
                
                return "DOWNLOADED", filename
                
            except Exception as e:
                # Удаляем частично скачанный файл
                if os.path.exists(filepath):
                    os.remove(filepath)
                
                download_status[task_id] = {
                    "status": "running",
                    "message": f"❌ Ошибка скачивания: {filename} ({current_file}/{total_files}) - {str(e)[:100]}",
                    "progress": ((current_file - 1) / total_files * 100),
                    "total_files": total_files,
                    "current_file": current_file,
                    "current_filename": filename
                }
                return "FAILED", filename
        
        def run_download():
            try:
                # Собираем все файлы для скачивания
                all_files = []
                for preset_id in presets_list:
                    if preset_id in PRESET_FILES:
                        all_files.extend(PRESET_FILES[preset_id])
                
                total_files = len(all_files)
                
                # Инициализируем статус
                download_status[task_id] = {
                    "status": "running",
                    "message": f"🚀 Начато скачивание пресетов: {', '.join(presets_list)}\n📦 Всего файлов: {total_files}",
                    "progress": 0,
                    "total_files": total_files,
                    "current_file": 0,
                    "current_filename": ""
                }
                
                # Списки для итоговой сводки
                downloaded_files = []
                skipped_files = []
                failed_files = []
                
                # Скачиваем каждый файл
                for idx, (url, folder, custom_filename) in enumerate(all_files, 1):
                    dest_dir = f"/workspace/ComfyUI/models/{folder}"
                    result, filename = download_file_with_progress(
                        url, dest_dir, custom_filename, idx, total_files, task_id
                    )
                    
                    if result == "DOWNLOADED":
                        downloaded_files.append(filename)
                    elif result == "SKIP":
                        skipped_files.append(filename)
                    elif result == "FAILED":
                        failed_files.append(filename)
                
                # Формируем итоговую сводку
                summary_parts = []
                summary_parts.append(f"✅ Скачивание пресетов завершено: {', '.join(presets_list)}")
                summary_parts.append("")
                
                if downloaded_files:
                    summary_parts.append(f"📥 Скачано файлов: {len(downloaded_files)}")
                    for filename in downloaded_files[:10]:  # Показываем первые 10
                        summary_parts.append(f"   ✅ {filename}")
                    if len(downloaded_files) > 10:
                        summary_parts.append(f"   ... и еще {len(downloaded_files) - 10} файлов")
                    summary_parts.append("")
                
                if skipped_files:
                    summary_parts.append(f"⏭️ Пропущено (уже существуют): {len(skipped_files)}")
                    for filename in skipped_files[:10]:  # Показываем первые 10
                        summary_parts.append(f"   ⏭️ {filename}")
                    if len(skipped_files) > 10:
                        summary_parts.append(f"   ... и еще {len(skipped_files) - 10} файлов")
                    summary_parts.append("")
                
                if failed_files:
                    summary_parts.append(f"❌ Ошибки при скачивании: {len(failed_files)}")
                    for filename in failed_files:
                        summary_parts.append(f"   ❌ {filename}")
                    summary_parts.append("")
                
                summary_message = "\n".join(summary_parts)
                
                if failed_files:
                    download_status[task_id] = {
                        "status": "error",
                        "message": summary_message,
                        "progress": 100,
                        "total_files": total_files,
                        "current_file": total_files,
                        "current_filename": ""
                    }
                else:
                    download_status[task_id] = {
                        "status": "completed",
                        "message": summary_message,
                        "progress": 100,
                        "total_files": total_files,
                        "current_file": total_files,
                        "current_filename": ""
                    }
            except Exception as e:
                download_status[task_id] = {
                    "status": "error",
                    "message": f"❌ Ошибка: {str(e)}",
                    "progress": download_status[task_id].get("progress", 0),
                    "total_files": download_status[task_id].get("total_files", 0),
                    "current_file": download_status[task_id].get("current_file", 0),
                    "current_filename": download_status[task_id].get("current_filename", "")
                }
        
        # Запускаем в отдельном потоке
        thread = threading.Thread(target=run_download)
        thread.daemon = True
        thread.start()
        
        # Сохраняем статус
        download_status[task_id] = {
            "status": "running",
            "message": f"🚀 Начато скачивание пресетов: {', '.join(presets_list)}"
        }
        
        return {"message": f"🚀 Скачивание начато! ID задачи: {task_id}", "task_id": task_id}
            
    except Exception as e:
        return {"message": f"❌ Ошибка: {str(e)}"}

@app.post("/download_hf")
def download_hf(repo: str = Form(...), filename: str = Form(""), token: str = Form(""), folder: str = Form("diffusion_models")):
    try:
        # Создаем уникальный ID для отслеживания
        task_id = str(uuid.uuid4())
        
        def run_hf_download():
            try:
                target_dir = f"/workspace/ComfyUI/models/{folder}"
                os.makedirs(target_dir, exist_ok=True)
                
                if filename:
                    # Скачиваем конкретный файл с прогрессом
                    # Формируем прямую ссылку на файл
                    hf_url = f"https://huggingface.co/{repo}/resolve/main/{filename}"
                    
                    # Обновляем статус - начало скачивания
                    download_status[task_id] = {
                        "status": "running",
                        "message": f"📥 Подключение к HuggingFace...",
                        "progress": 0
                    }
                    
                    # Подготавливаем заголовки
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                    if token:
                        headers['Authorization'] = f'Bearer {token}'
                    
                    response = requests.get(hf_url, stream=True, headers=headers, timeout=300)
                    response.raise_for_status()
                    
                    file_path = os.path.join(target_dir, filename)
                    
                    # Получаем размер файла
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    last_update = 0
                    update_interval = 1024 * 1024 * 5  # Обновляем каждые 5MB
                    
                    # Скачиваем файл с отслеживанием прогресса
                    with open(file_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB chunks
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                
                                # Обновляем прогресс каждые 5MB
                                if downloaded - last_update >= update_interval or (total_size > 0 and downloaded >= total_size):
                                    last_update = downloaded
                                    
                                    if total_size > 0:
                                        percent = int((downloaded / total_size) * 100)
                                        size_mb = downloaded / (1024 * 1024)
                                        total_mb = total_size / (1024 * 1024)
                                        download_status[task_id] = {
                                            "status": "running",
                                            "message": f"📥 Скачивание: {filename} ({percent}%) - {size_mb:.1f} MB / {total_mb:.1f} MB",
                                            "progress": percent
                                        }
                                    else:
                                        size_mb = downloaded / (1024 * 1024)
                                        download_status[task_id] = {
                                            "status": "running",
                                            "message": f"📥 Скачивание: {filename} ({size_mb:.1f} MB)",
                                            "progress": 0
                                        }
                    
                    # Финальное обновление
                    size_mb = os.path.getsize(file_path) / (1024 * 1024)
                    success_msg = f"✅ Успешно загружено!\n📁 Файл: {filename}\n💾 Размер: {size_mb:.1f} MB\n📂 Путь: {target_dir}"
                    
                    download_status[task_id] = {
                        "status": "completed",
                        "message": success_msg,
                        "progress": 100
                    }
                else:
                    # Скачиваем весь репозиторий (используем huggingface_hub, так как это сложнее)
                    download_status[task_id] = {
                        "status": "running",
                        "message": f"📥 Скачивание всего репозитория {repo}...",
                        "progress": 0
                    }
                    
                    # Если есть токен, логинимся
                    if token:
                        login(token=token)
                    
                    from huggingface_hub import snapshot_download
                    snapshot_download(
                        repo_id=repo,
                        cache_dir=target_dir,
                        local_dir=target_dir,
                        local_dir_use_symlinks=False
                    )
                    
                    success_msg = f"✅ Успешно загружено!\n📁 Репозиторий: {repo}\n📂 Путь: {target_dir}"
                    
                    download_status[task_id] = {
                        "status": "completed",
                        "message": success_msg,
                        "progress": 100
                    }
                
            except Exception as e:
                error_msg = f"❌ Ошибка: {str(e)}"
                
                # Если ошибка связана с токеном, предлагаем его ввести
                if "authentication" in str(e).lower() or "token" in str(e).lower() or "401" in str(e):
                    error_msg += "\n\n💡 Попробуйте ввести API токен HuggingFace"
                
                download_status[task_id] = {
                    "status": "error",
                    "message": error_msg,
                    "progress": download_status[task_id].get("progress", 0)
                }
        
        # Запускаем в отдельном потоке
        thread = threading.Thread(target=run_hf_download)
        thread.daemon = True
        thread.start()
        
        # Сохраняем статус
        download_status[task_id] = {
            "status": "running",
            "message": f"🚀 Начато скачивание с HuggingFace: {repo}",
            "progress": 0
        }
        
        return {"message": f"🚀 Скачивание начато! ID задачи: {task_id}", "task_id": task_id}
        
    except Exception as e:
        return {"message": f"❌ Ошибка: {str(e)}"}

@app.post("/download_url")
def download_url(url: str = Form(...), folder: str = Form("diffusion_models")):
    try:
        # Создаем уникальный ID для отслеживания
        task_id = str(uuid.uuid4())
        
        def run_url_download():
            try:
                target_dir = f"/workspace/ComfyUI/models/{folder}"
                os.makedirs(target_dir, exist_ok=True)
                
                # Скачиваем файл по прямой ссылке с отслеживанием прогресса
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                # Обновляем статус - начало скачивания
                download_status[task_id] = {
                    "status": "running",
                    "message": f"📥 Подключение к серверу...",
                    "progress": 0
                }
                
                response = requests.get(url, stream=True, headers=headers, timeout=300)
                response.raise_for_status()
                
                # Получаем имя файла из URL
                filename = url.split('/')[-1]
                # Убираем параметры запроса (?download=true и т.д.)
                if '?' in filename:
                    filename = filename.split('?')[0]
                
                # Пытаемся получить имя файла из заголовков Content-Disposition
                if 'content-disposition' in response.headers:
                    import re
                    import urllib.parse
                    content_disposition = response.headers['content-disposition']
                    
                    # Ищем filename* (RFC 5987) для UTF-8 имен
                    utf8_match = re.search(r"filename\*=UTF-8''([^;]+)", content_disposition)
                    if utf8_match:
                        filename = urllib.parse.unquote(utf8_match.group(1))
                    else:
                        # Обычный filename
                        filename_match = re.search(r'filename[^;=\n]*=(([\'"]).*?\2|[^;\n]*)', content_disposition)
                        if filename_match:
                            filename = filename_match.group(1).strip('\'"')
                
                if not filename or '.' not in filename:
                    filename = "downloaded_file"
                
                file_path = os.path.join(target_dir, filename)
                
                # Получаем размер файла
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                last_update = 0
                update_interval = 1024 * 1024 * 5  # Обновляем каждые 5MB
                
                # Скачиваем файл с отслеживанием прогресса
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB chunks
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            # Обновляем прогресс каждые 5MB
                            if downloaded - last_update >= update_interval or (total_size > 0 and downloaded >= total_size):
                                last_update = downloaded
                                
                                if total_size > 0:
                                    percent = int((downloaded / total_size) * 100)
                                    size_mb = downloaded / (1024 * 1024)
                                    total_mb = total_size / (1024 * 1024)
                                    download_status[task_id] = {
                                        "status": "running",
                                        "message": f"📥 Скачивание: {filename} ({percent}%) - {size_mb:.1f} MB / {total_mb:.1f} MB",
                                        "progress": percent
                                    }
                                else:
                                    size_mb = downloaded / (1024 * 1024)
                                    download_status[task_id] = {
                                        "status": "running",
                                        "message": f"📥 Скачивание: {filename} ({size_mb:.1f} MB)",
                                        "progress": 0
                                    }
                
                # Финальное обновление
                size_mb = os.path.getsize(file_path) / (1024 * 1024)
                success_msg = f"✅ Успешно загружено!\n🔗 Ссылка: {url}\n📄 Файл: {filename}\n💾 Размер: {size_mb:.1f} MB\n📂 Путь: {target_dir}"
                
                download_status[task_id] = {
                    "status": "completed",
                    "message": success_msg,
                    "progress": 100
                }
                
            except Exception as e:
                error_msg = f"❌ Ошибка: {str(e)}"
                download_status[task_id] = {
                    "status": "error",
                    "message": error_msg,
                    "progress": download_status[task_id].get("progress", 0)
                }
        
        # Запускаем в отдельном потоке
        thread = threading.Thread(target=run_url_download)
        thread.daemon = True
        thread.start()
        
        # Сохраняем статус
        download_status[task_id] = {
            "status": "running",
            "message": f"🚀 Начато скачивание по ссылке: {url}",
            "progress": 0
        }
        
        return {"message": f"🚀 Скачивание начато! ID задачи: {task_id}", "task_id": task_id}
        
    except Exception as e:
        return {"message": f"❌ Ошибка: {str(e)}"}
