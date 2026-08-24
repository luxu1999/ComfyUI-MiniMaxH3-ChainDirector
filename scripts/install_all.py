#!/usr/bin/env python3
"""一键安装链式导演台工作流所需的所有插件与 Python 依赖。

用法：
    python scripts/install_all.py                # 自动定位 ComfyUI
    python scripts/install_all.py D:/path/to/ComfyUI   # 或显式指定根目录

脚本会：
1. 在 ComfyUI/custom_nodes/ 下补齐缺失插件：
   - ComfyUI_MiniMaxH3_Director（导演台，必须）
   - ComfyUI-VideoHelperSuite（VHS_VideoCombine 保存）
   - ComfyUI-KJNodes（SageAttention 节点）
2. 安装 Python 依赖：导演台 requirements + sageattention==1.0.6
   （自动优先使用 ComfyUI 自带 Python，其次当前 Python）
3. 应用导演台补丁（幂等；链式节点本身不依赖，旧三段拼合工作流需要）

模型文件太大无法内置，请另行运行 scripts/download_models.py 下载。
"""

from __future__ import annotations

import os
import subprocess
import sys

PLUGINS = {
    "ComfyUI_MiniMaxH3_Director": "https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director.git",
    "ComfyUI-VideoHelperSuite": "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git",
    "ComfyUI-KJNodes": "https://github.com/kijai/ComfyUI-KJNodes.git",
}


def find_comfy_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))  # <root>/custom_nodes/<repo>/scripts
    root = os.path.dirname(os.path.dirname(os.path.dirname(here)))  # 上三级
    if os.path.isdir(os.path.join(root, "custom_nodes")):
        return root
    raise SystemExit("未找到 ComfyUI 根目录（没有 custom_nodes 文件夹）。请显式传参：python install_all.py D:/path/to/ComfyUI")


def run(cmd: list[str], cwd: str | None = None) -> None:
    print(">>> " + " ".join(cmd), flush=True)
    subprocess.check_call(cmd, cwd=cwd)


def main() -> None:
    root = sys.argv[1] if len(sys.argv) > 1 else find_comfy_root()
    root = os.path.abspath(root)
    cn = os.path.join(root, "custom_nodes")
    os.makedirs(cn, exist_ok=True)
    print(f"ComfyUI 根目录：{root}", flush=True)

    # 1) 补齐插件
    for name, url in PLUGINS.items():
        dst = os.path.join(cn, name)
        if os.path.isdir(dst):
            print(f"[OK] 已存在：{name}", flush=True)
            continue
        print(f"[..] 克隆 {name} ...", flush=True)
        run(["git", "clone", url], cwd=cn)

    # 2) Python 依赖
    python = os.path.join(root, "python", "python.exe")
    if not os.path.isfile(python):
        python = os.path.join(root, "python", "bin", "python")
    if not os.path.isfile(python):
        python = sys.executable
    print(f"Python：{python}", flush=True)
    req = os.path.join(cn, "ComfyUI_MiniMaxH3_Director", "requirements.txt")
    if os.path.isfile(req):
        run([python, "-m", "pip", "install", "-r", req])
    run([python, "-m", "pip", "install", "sageattention==1.0.6"])

    # 3) 应用导演台补丁（幂等）
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    patch = os.path.join(repo, "patches", "apply_patches.py")
    if os.path.isfile(patch):
        print("[..] 应用导演台补丁（幂等，链式节点不需要也能跑）...", flush=True)
        try:
            run([sys.executable, patch, root])
        except subprocess.CalledProcessError as exc:
            print(f"[WARN] 补丁脚本退出码 {exc.returncode}，可忽略（链式节点自带自动补齐）", flush=True)

    print("\n完成！请重启 ComfyUI，然后运行 scripts/download_models.py 下载模型。", flush=True)


if __name__ == "__main__":
    main()