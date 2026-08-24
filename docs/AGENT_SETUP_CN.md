# MiniMax H3 链式导演台工作流 · AI Agent 自动搭建流程

> 本文件是写给 **Codex / OpenClaw 等 AI Agent** 的指令：让 AI 读懂后可以自动下载插件、放模型、载入工作流并跑起来。
> 复现目标：**480p / 30 秒 / 6 段拼接** 的 MiniMax H3 视频。一个节点（`MiniMaxH3ChainDirector`）自动完成「首段 r2v → 后续段 i2v 首帧锁定接力 → 画面/音频拼接」。
> 画面、剧情、音效等具体内容由提示词自由决定（仓库示例只是其中一种风格）。

---

## 1. 环境要求

- Windows / Linux 均可；ComfyUI ≥ 0.30（推荐 0.31.x）
- Python 3.10+
- 参考显卡：RTX 4080 16G；分段方案同样适配低显存（8G 起）——1080p 直出 10 秒+ 会 OOM，分段后低显存也能跑长视频
- 网络：GitHub + HuggingFace（国内可用 `gh-proxy.com` 镜像和 `hf-mirror.com`）
- Windows 秋叶/整合包环境：Python 是 `ComfyUI/python/python.exe`，所有 `pip install` 都要用它的 `-m pip`（见第 2 节）

## 2. 安装插件（工作流用到以下全部插件，缺一不可）

在 `ComfyUI/custom_nodes/` 下安装：

```bash
# 1) 导演台（链式节点会自动补齐旧版 Director 的连续性接线，见第 3 节）
git clone https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director.git
# 国内镜像：git clone https://gh-proxy.com/https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director.git

# 2) 本仓库（提供 MiniMaxH3ChainDirector 中文版 / MiniMaxH3ChainDirectorEN 英文版节点）
git clone https://github.com/luxu1999/ComfyUI-MiniMaxH3-ChainDirector.git

# 3) 视频保存节点（VHS_VideoCombine，工作流必需）
git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git

# 4) SageAttention 节点（工作流已启用，必须）
git clone https://github.com/kijai/ComfyUI-KJNodes.git
```

安装 Python 依赖（原生版直接 `pip install`；秋叶/整合包请用 `ComfyUI/python/python.exe -m pip install`）：

```bash
# 5) 导演台的依赖（scenedetect / opencv / imageio-ffmpeg 等）
pip install -r ComfyUI_MiniMaxH3_Director/requirements.txt
# 整合包：ComfyUI/python/python.exe -m pip install -r ComfyUI_MiniMaxH3_Director/requirements.txt

# 6) SageAttention（工作流已启用，必须；1.x 与 H3 兼容）
pip install sageattention==1.0.6
# 整合包：ComfyUI/python/python.exe -m pip install sageattention==1.0.6
```

可选加速（不在默认工作流内，装不装都能跑）：

```bash
# 7) TeaCache：ComfyUI-MiniMaxH3-TeaCache（阈值必须 ≤ 0.1，否则画面抽搐）
```

## 3. 导演台补丁（自动处理，无需手动）

链式导演台节点**自带运行时自检**：首次生成时会自动检测 Director 是否缺少「段连续性接线」，缺则直接在内存中补齐，无需手动打补丁、无需重启（已实测未打补丁的旧版 Director 拼接缝依然顺滑）。克隆最新版 Director 时该接线已内置，检测为「已存在」。

以下手动补丁**仅在使用旧版 Director 的 Combine 节点（旧三段拼合工作流，见 https://github.com/luxu1999/ComfyUI-ListUnwrap）时需要**：

| 补丁 | 解决 | 文件 |
|---|---|---|
| 1. Combine autogrow 兼容 | `Director Groups Combine: connect at least one group` | `nodes/director_groups.py` |
| 2. 外部组连续性 | 段间「尾帧→下一段首帧」不生效、衔接硬切/角色消失 | `director/external_groups.py` |

如需手动应用，运行本仓库的自动打补丁脚本

```bash
cd ComfyUI/custom_nodes/ComfyUI-MiniMaxH3-ChainDirector
python patches/apply_patches.py            # 自动定位到 custom_nodes/ComfyUI_MiniMaxH3_Director
# 或显式指定 ComfyUI 根目录：
python patches/apply_patches.py D:/path/to/ComfyUI
```

脚本会做精确字符串替换并打印 `[OK]` / `[SKIP]`。也可以用 `patches/01_*.patch` / `02_*.patch` 手动 `git apply` 或 `patch -p1`。

**打完补丁必须重启 ComfyUI。**

> 版本说明：补丁在 ComfyUI 0.31.x 上验证。0.40+ 新前端可能原生兼容 autogrow，可先只打补丁 2（连续性）试跑，报 Combine 错误再打补丁 1。

## 4. 模型、LoRA 与参考图

### 4.1 模型与 LoRA（放到对应目录）

| 文件 | 目录 |
|---|---|
| `minimax_h3_ref2va_pruned_int8_convrot.safetensors`（第 1 段 r2v 底座） | `models/diffusion_models/` |
| `minimax_h3_fl2va_pruned_int8_convrot.safetensors`（第 2 段起 i2v 底座） | `models/diffusion_models/` |
| `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`（CLIP，CLIPLoader 的 type 选 `minimax`） | `models/text_encoders/`（部分版本为 `models/clip/`，两处都放也行） |
| `minimax_h3_video_vae_fp16.safetensors` | `models/vae/` |
| `minimax_h3_audio_vae_fp32.safetensors` | `models/vae/` |
| `minimax_h3_fl2v_lightx2v_turbo_4step_v0.1_comfy_resized_avg_rank_21_bf16.safetensors`（turbo LoRA，strength 0.75，接在 r2v 和 i2v 两条模型链上） | `models/loras/` |

下载来源：[Kijai/MiniMax-H3_comfy](https://huggingface.co/Kijai/MiniMax-H3_comfy)（国内把链接前缀换成 `https://hf-mirror.com/`）。

> **SageAttention 安装位置**：`pip install sageattention==1.0.6` 装进 ComfyUI 的 Python 环境（秋叶整合包用 `ComfyUI/python/python.exe -m pip install sageattention==1.0.6`）；节点插件在 `custom_nodes/ComfyUI-KJNodes`（节点名 `PathchSageAttentionKJ`，参数 `sage_attention=auto`）。工作流里 r2v / i2v 两条模型链各挂一个 Sage 节点。

### 4.2 参考图（放到 `ComfyUI/input/`）

工作流示例用了 4 张图（可随意增减，最多 9 张）：

| 文件名 | 接入口 | 提示词占位符 |
|---|---|---|
| `桌面.jpg`（场景/主体图） | `image_0` | `<Picture 1>` |
| `正面.png` | `image_1` | `<Picture 2>` |
| `侧面.png` | `image_2` | `<Picture 3>` |
| `背面.png` | `image_3` | `<Picture 4>` |

没有同名图片时，把工作流里 `LoadImage` 的文件名改成你实际的文件名。

## 5. 载入工作流

两种方式任选：

- **人用**：把 `workflows/MiniMax H3 Chain Director｜链式导演台（多段拼接）工作流.png` 直接拖进 ComfyUI 画布（PNG 内嵌工作流），或用菜单 Load 载入同名 `.json`（人工排布版）。
- **Agent 用**：读取 `workflows/MiniMax H3 Chain Director｜链式导演台（多段拼接）工作流_api.json`（API 格式），POST 到 `http://127.0.0.1:8188/prompt`（带 `client_id`），轮询 `/history/{prompt_id}` 直到 `status_str == "success"`；如果响应里有 `node_errors`，逐条读取并按错误信息修复。

节点参数要点：

- **时间轴提示词必填**：每行 `0-5s: 动作描述`（兼容 `-` `‑` `–` `—` `~` 各种连字符与 `s`/`秒`）；留空或格式无法识别会红字报错。
- **总时长必须能被每段秒数整除**：如 30 秒 / 5 秒每段 = 6 段；不整除会红字报错（防止静默丢秒）。时长预设只有 5/10/15/30/45/60/90/120 秒，分段只有 5/10/15 秒。
- 每段上限约 15 秒（362 帧），超出报错。
- 采样步数作用于**每一段**：6 段 × 4 步 = 6 次独立的 4 步采样，总耗时 ≈ 6 × 单段耗时。
- 输出目录：`output/MiniMaxH3/`，文件名带 `filename_prefix` 前缀。

## 6. 运行检查与常见问题

- 队列：`GET /queue` 查看 `queue_running` / `queue_pending`。
- 进度：`GET /history/{prompt_id}`，`executing` 消息里能看到节点 14 的采样进度。
- 爆显存/内存：1080p 直出 10 秒以上会 OOM，改用分段（5 秒每段）或 720p/480p。
- TeaCache 阈值 > 0.1 会导致画面抽搐，固定 ≤ 0.1。
- SageAttention 已启用（`PathchSageAttentionKJ`，`sage_attention=auto`）；必须使用 sageattention 1.x（2.x/3.x 与 H3 不兼容或仅 50 系生效）。
- 报错 `No module named 'ComfyUI_MiniMaxH3_Director'`：说明 Director 没装或加载失败 → 回到第 2 节第 1 步安装并重启。
- 报错 `too many values to unpack (expected 4)`：一般是插件/ComfyUI 核心版本不匹配（尤其 VHS_VideoCombine 等保存节点）→ 按第 8 节把所有插件更新到最新，并用仓库最新工作流重新载入。
- 报错 `时间轴提示词格式无法识别`：时间轴留空或行首不是「秒-秒: 动作」→ 按 `0-5s: 动作` 重写。

## 7. Agent 交付检查清单

- [ ] `custom_nodes/` 下已安装：ComfyUI_MiniMaxH3_Director、ComfyUI-MiniMaxH3-ChainDirector、ComfyUI-VideoHelperSuite、ComfyUI-KJNodes
- [ ] Director 已安装（链式节点会自动内存补齐旧版连续性接线；旧三段拼合工作流才需手动应用补丁），sageattention 1.0.6 已装入 ComfyUI Python 环境
- [ ] 6 个模型/LoRA 文件已放到对应目录
- [ ] 参考图已放入 `input/`，LoadImage 文件名与实际一致
- [ ] 工作流载入成功，节点 `MiniMaxH3ChainDirector` 无红字
- [ ] 提交后 `/history` 返回 `success`，`output/MiniMaxH3/` 出现 mp4

## 8. 如何更新到最新版

给已安装过的机器/用户用（Agent 在维护已有环境时执行）：

```bash
cd ComfyUI/custom_nodes
# 1) 更新本仓库插件（链式导演台节点）
cd ComfyUI-MiniMaxH3-ChainDirector && git pull
# 2) 更新导演台
cd ../ComfyUI_MiniMaxH3_Director && git pull
# 3) 更新保存节点与 Sage 节点
cd ../ComfyUI-VideoHelperSuite && git pull
cd ../ComfyUI-KJNodes && git pull
```

- 若某插件当初是 zip 手动安装的（不是 git 克隆），`git pull` 会报错：删掉该文件夹 → 重新从 GitHub 下载最新版解压。
- 更新后**重启 ComfyUI**；Director 更新后无需重新打补丁（节点会自动检测）。
- **工作流也要更新**：从仓库 `workflows/` 重新下载最新的 `工作流.png / .json / _api.json`，用新版重新载入（旧画布上的旧节点参数可能和新版对不上）。
- `git pull` 报冲突：说明该文件夹被手动改过 → 先备份改动再 `git stash`，或直接删掉重克隆。
- 国内网络拉不动 GitHub：把仓库地址换成 `https://gh-proxy.com/https://github.com/...` 或开启代理。