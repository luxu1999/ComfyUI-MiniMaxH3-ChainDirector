# ComfyUI-MiniMaxH3-ChainDirector

MiniMax H3 链式导演台（Chain Director）自定义节点：**一个节点自动完成「按总时长分段 → 首段 r2v → 后续段 i2v 首帧锁定接力 → 画面/音频拼接」**，通过分段拼接显著降低显存占用，低显存（8G 起）也能生成 MiniMax H3 长视频。

## 节点

| 节点 | 说明 |
|---|---|
| `MiniMax H3 Chain Director｜链式导演台（多段拼接）` | **中文版**，参数/提示/报错全部中文 |
| `MiniMax H3 Chain Director` | **纯英文版**，参数/提示/报错全部英文（与中文版逻辑一致） |

## 作用与原理

MiniMax H3 单段直出有帧数上限（约 362 帧 ≈ 15 秒），且 16G 显存 1080p 直出 10 秒以上会爆显存。链式导演台把长视频**自动拆成 N 段**：

1. **第 1 段**：r2v（参考图生视频）——`image_0`（场景/主体图）+ `image_1..8`（最多 9 张参考图，对应 `<Picture 1..9>`）；
2. **第 2~N 段**：i2v（图生视频）——以上一段**最后一帧硬锁定**为第一帧，保证角色/场景连续不漂移；
3. 全部段生成后自动拼接画面（`torch.cat`）与音频，输出 `IMAGE + AUDIO + fps + frame_count`，直接接 `VHS_VideoCombine` 保存 mp4。

用户只需填：总时长 + 每段秒数 + 分辨率 + 提示词，剩下全自动。

## 参数说明（中英对照）

### 连接口（提示词上方，两种版本同名）

| 参数 | 类型 | 作用 |
|---|---|---|
| `model_r2v` | MODEL | ref2va 底座，用于第 1 段 r2v 生成 |
| `model_i2v` | MODEL | fl2va 底座，用于第 2 段及以后的 i2v 接力 |
| `video_vae` / `audio_vae` | VAE | 视频 VAE / 音频 VAE |
| `clip` | CLIP | 文本编码器（qwen3vl_32b_minimax_h3） |
| `image_0` ~ `image_8` | IMAGE | 9 个参考图口：`image_0` → `<Picture 1>`，`image_1` → `<Picture 2>`…；只接用得上的，其余留空 |

### 提示词（中间区域）

| 中文版 | 英文版 | 作用 |
|---|---|---|
| 全局提示词 | `global_prompt` | 全片不变的设定：场景/风格/角色/机位等；可用 `<Picture N>` 引用参考图 |
| 时间轴提示词（必填） | `timeline_prompt` | 每行一段：`0-5s: 动作描述`，节点自动按时间段映射到各段；留空红字报错 |

### 参数（提示词下方）

| 中文版 | 英文版 | 作用 / 效果 |
|---|---|---|
| 总时长预设 | `duration_preset` | 5/10/15/30/45/60/90/120 秒可选 |
| 分段方式 | `split_preset` | 每段 5/10/15 秒可选；单段上限约 15 秒（362 帧） |
| 分辨率预设（百万像素） | `resolution_preset` | `0.4MP (480p)`=864×480、`0.9MP (720p)`=1280×736、`2.0MP (1080p)`=1920×1088 |
| 参考图最大边（像素） | `ref_max_size` | 参考图缩放最大边长，一般与分辨率预设一致 |
| 自动锚点 | `auto_anchor` | 自动追加「首帧锁定/体型/参考图一致」锚点句，推荐开启 |
| 采样步数 | `steps` | **每一段内部**的扩散采样步数：4 步 = turbo LoRA 推荐值，8 步更精细但耗时约翻倍（6 段 × 4 步 = 6 次独立 4 步采样） |
| 采样器 / 调度器 | `sampler` / `scheduler` | 推荐 `er_sde` + `simple` |
| 引导强度CFG | `cfg` | turbo LoRA 下推荐 1.0 |
| 随机种子 | `seed` | 固定可复现 |
| 视频时间偏移 | `shift_video` | 推荐 12.0 |
| 音频时间偏移 | `shift_audio` | 推荐 3.0 |

### 注意

- 总时长必须能被每段秒数**整除**（如 60 秒 ÷ 10 秒每段 = 6 段），否则红字报错（防止静默丢秒）。
- 每段超过约 15 秒红字报错。
- 成片时长因 MiniMax 官方帧网格（17k+5）有 ±0.5 秒/段的小误差，属正常。
- 时间轴分隔符兼容 `-` `‑` `–` `—` `~` `－` 等写法（从 Word/微信复制来的特殊连字符也能识别）；时间单位 `s` 或 `秒` 均可。

## 配套工作流

`workflows/` 提供一条 **480p / 30 秒 / 6 段**（5 秒每段）示例工作流（**已启用 SageAttention 加速**），含 `<Picture N>` 提示词写法：

- `workflows/MiniMax_H3_Chain_Director_workflow.png` — 带内嵌工作流，**直接拖进 ComfyUI**
- `workflows/MiniMax_H3_Chain_Director_workflow.json` — UI 格式，ComfyUI 菜单 Load 载入（节点已人工排布，更易读）
- `workflows/MiniMax_H3_Chain_Director_workflow_api.json` — API 格式，适合 AI Agent / 脚本提交

> 通过 Comfy Registry / Manager 安装后，插件目录 `workflows/` 下即以上述英文文件名出现；GitHub 源码里另有同名中文版副本（`MiniMax H3 Chain Director｜链式导演台（多段拼接）工作流.*`），内容完全一致，方便网页浏览。

> 示例参考图：`input/桌面.jpg`、`input/正面.png`、`input/侧面.png`、`input/背面.png`。换成自己的图时改 `LoadImage` 文件名即可，数量随意（最多 9 张）。

## 安装（零配置三步）

1. **装本插件**：ComfyUI-Manager 或 Comfy Registry 里搜「ChainDirector / MiniMax-H3」一键安装；或手动 `git clone https://github.com/luxu1999/ComfyUI-MiniMaxH3-ChainDirector.git` 到 `custom_nodes/`。
2. **自动补齐其余插件与依赖**（一次命令）：
   ```bash
   cd custom_nodes/ComfyUI-MiniMaxH3-ChainDirector
   python scripts/install_all.py        # 自动安装 Director / VideoHelperSuite / KJNodes + 依赖 + sageattention
   ```
3. **下载模型**（约 60GB，一次命令）：
   ```bash
   python scripts/download_models.py    # 默认 hf-mirror.com；加 --mirror hfco 用原生
   ```
4. 重启 ComfyUI，拖入 `workflows/` 的工作流即可跑。

> 模型文件太大无法内置，只能用脚本下载；插件与 Python 依赖已做到一键自动安装。
## 安装与依赖插件

工作流用到的插件（**全部必须安装**）：

1. [ComfyUI_MiniMaxH3_Director](https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director)（导演台。**链式导演台节点会自动检测并补齐旧版 Director 缺少的连续性接线，无需手动打补丁**；旧三段拼合工作流需要的话仍可用 `patches/apply_patches.py`）
2. **ComfyUI-MiniMaxH3-ChainDirector**（本仓库，提供链式导演台节点）
3. [ComfyUI-VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite)（`VHS_VideoCombine` 保存节点）
4. [ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes)（提供 `PathchSageAttentionKJ` SageAttention 节点，工作流已启用）

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director.git
git clone https://github.com/luxu1999/ComfyUI-MiniMaxH3-ChainDirector.git
git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git
git clone https://github.com/kijai/ComfyUI-KJNodes.git
pip install -r ComfyUI_MiniMaxH3_Director/requirements.txt
pip install sageattention==1.0.6
```

补丁说明（可选）：Director 原版两个问题（Combine autogrow 不兼容、段间连续性失效）——链式导演台节点已内置运行时自动补齐，普通使用无需手动打补丁；只有使用旧版 Director 的 Combine 节点（旧三段拼合工作流，见 [ComfyUI-ListUnwrap](https://github.com/luxu1999/ComfyUI-ListUnwrap)）时才需要手动应用：

```bash
cd ComfyUI-MiniMaxH3-ChainDirector
python patches/apply_patches.py            # 自动定位到 custom_nodes/ComfyUI_MiniMaxH3_Director
# 或 python patches/apply_patches.py D:/path/to/ComfyUI
```

打完补丁**必须重启 ComfyUI**。链式节点的运行时自动补齐不需要重启。

### 模型与 LoRA（放到对应目录）

| 文件 | 目录 |
|---|---|
| `minimax_h3_ref2va_pruned_int8_convrot.safetensors`（r2v 底座） | `models/diffusion_models/` |
| `minimax_h3_fl2va_pruned_int8_convrot.safetensors`（i2v 底座） | `models/diffusion_models/` |
| `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`（CLIP） | `models/text_encoders/` |
| `minimax_h3_video_vae_fp16.safetensors` | `models/vae/` |
| `minimax_h3_audio_vae_fp32.safetensors` | `models/vae/` |
| `minimax_h3_fl2v_lightx2v_turbo_4step_v0.1_comfy_resized_avg_rank_21_bf16.safetensors`（turbo LoRA，strength 0.75） | `models/loras/` |

模型来源：[Kijai/MiniMax-H3_comfy](https://huggingface.co/Kijai/MiniMax-H3_comfy)，国内可用 `hf-mirror.com`。

### SageAttention 加速（当前工作流已启用）

- **pip 安装位置**：ComfyUI 的 Python 环境（秋叶整合包即 `ComfyUI/python/python.exe -m pip install sageattention==1.0.6`；原生版即 `pip install sageattention==1.0.6`）。必须 1.x（2.x/3.x 与 H3 不兼容或仅 50 系生效）。
- **节点插件位置**：`custom_nodes/ComfyUI-KJNodes`（`git clone https://github.com/kijai/ComfyUI-KJNodes.git`）。
- **接线方式**：r2v 与 i2v 两条模型链（LoraLoaderModelOnly 之后、链式导演台之前）各挂一个 `PathchSageAttentionKJ`，参数 `sage_attention` 选 `auto`。

可选加速：TeaCache（阈值 **≤ 0.1**，否则画面抽搐），不在默认工作流内。

## 给 AI Agent 的搭建文档

用 Codex / OpenClaw 等 AI Agent 自动复现整套流程？直接把 [docs/AGENT_SETUP_CN.md](docs/AGENT_SETUP_CN.md) 交给 Agent，它会照着下载插件、打补丁、放模型、载入工作流并运行。

提示词写法见 [docs/prompt-writing-guide.md](docs/prompt-writing-guide.md)（通用提示词填写方法）与 [docs/prompt-split-and-consistency-guide.md](docs/prompt-split-and-consistency-guide.md)（总提示词拆分与一致性指南）；仓库内另有对应中文文件名副本，内容一致。

## 兼容性

- ComfyUI ≥ 0.30（推荐 0.31.x）
- 依赖：`torch`（ComfyUI 自带）

## License

MIT

## 致谢

- [ComfyUI_MiniMaxH3_Director](https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director)（AIMixer）
- MiniMax H3 / LightX2V
## 更新记录

- 2026-08-24：新增运行时自动检测/内存补齐 Director 连续性接线，克隆最新 Director 即可用，无需手动打补丁；原 patches/apply_patches.py 手动方式保留。
