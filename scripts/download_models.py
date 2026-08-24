#!/usr/bin/env python3
"""一键下载链式导演台工作流所需的模型/LoRA/VAE/CLIP（约 60GB，请确保磁盘空间）。

用法：
    python scripts/download_models.py                # 自动定位 ComfyUI，默认 hf-mirror.com
    python scripts/download_models.py D:/path/to/ComfyUI
    python scripts/download_models.py --mirror hf    # hf-mirror.com（国内快）
    python scripts/download_models.py --mirror hfco  # huggingface.co（原生）

下载清单（来源 HF）：
- Comfy-Org/MiniMax-H3（底座×2、CLIP、VAE×2）
- Kijai/MiniMax-H3_comfy（turbo LoRA）
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.request

FILES = [
    # (HF 仓库, 仓库内路径, 本地目标目录)
    ("Comfy-Org/MiniMax-H3", "diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors", "models/diffusion_models"),
    ("Comfy-Org/MiniMax-H3", "diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors", "models/diffusion_models"),
    ("Comfy-Org/MiniMax-H3", "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "models/text_encoders"),
    ("Comfy-Org/MiniMax-H3", "vae/minimax_h3_video_vae_fp16.safetensors", "models/vae"),
    ("Comfy-Org/MiniMax-H3", "vae/minimax_h3_audio_vae_fp32.safetensors", "models/vae"),
    ("Kijai/MiniMax-H3_comfy", "loras/minimax_h3_fl2v_lightx2v_turbo_4step_v0.1_comfy_resized_avg_rank_21_bf16.safetensors", "models/loras"),
]

MIRRORS = {
    "hf": "https://hf-mirror.com",
    "hfco": "https://huggingface.co",
}


def find_comfy_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    if os.path.isdir(os.path.join(root, "custom_nodes")):
        return root
    raise SystemExit("未找到 ComfyUI 根目录。请显式传参：python download_models.py D:/path/to/ComfyUI")


def download(url: str, dest: str) -> None:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.isfile(dest) and os.path.getsize(dest) > 0:
        print(f"[SKIP] 已存在：{os.path.basename(dest)}", flush=True)
        return
    tmp = dest + ".part"
    print(f"[..] {os.path.basename(dest)} <- {url}", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as fh:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            fh.write(chunk)
            done += len(chunk)
            if total:
                pct = done * 100 // total
                print(f"\r    {pct}% ({done // (1024*1024)}MB / {total // (1024*1024)}MB)", end="", flush=True)
    print("", flush=True)
    os.replace(tmp, dest)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("comfy_root", nargs="?", default=None)
    ap.add_argument("--mirror", choices=list(MIRRORS), default="hf")
    args = ap.parse_args()
    root = os.path.abspath(args.comfy_root) if args.comfy_root else find_comfy_root()
    base = MIRRORS[args.mirror]
    print(f"ComfyUI 根目录：{root}（镜像：{base}）", flush=True)
    total_gb = 0
    for repo, path, dest_dir in FILES:
        url = f"{base}/{repo}/resolve/main/{path}"
        dest = os.path.join(root, dest_dir, os.path.basename(path))
        if not (os.path.isfile(dest) and os.path.getsize(dest) > 0):
            total_gb += 0
        download(url, dest)
    print("\n模型下载完成。重启 ComfyUI 即可使用。", flush=True)


if __name__ == "__main__":
    main()