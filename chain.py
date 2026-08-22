"""MiniMaxH3ChainDirector（链式导演台 / Chain Director）— 共享核心 + 中文节点。

一个节点自动完成「按总时长分段 → 首段 r2v → 后续段 i2v 首帧锁定接力 → 画面/音频合并」。

布局约定：
- 提示词上方只放连接口（模型/VAE/CLIP/图片），命名保留英文原名：model_r2v / model_i2v /
  video_vae / audio_vae / clip / image_0..image_8（9 个图片口，对应 MiniMax H3 的 9 图输入）
- 中间是 2 个提示词框：全局提示词（全片设定）+ 时间轴提示词（每行 0-5s: 动作，必填）
- 提示词下方是全部参数（中文名）
- 分辨率用百万像素预设（0.4MP/0.9MP/2.0MP）

纯英文版节点见 chain_en.py（MiniMaxH3ChainDirectorEN）。

依赖：ComfyUI_MiniMaxH3_Director（需应用 patches/ 的两个补丁）。
"""

from __future__ import annotations

import json
import re

import torch
from comfy.samplers import KSampler

TIME_PRESETS = ["15秒", "30秒", "45秒", "60秒", "90秒", "120秒", "自定义"]
SPLIT_PRESETS = ["5秒每段 (推荐)", "10秒每段", "15秒每段", "自定义"]
RES_PRESETS = {
    "0.4MP (480p)": (864, 480, 864),
    "0.9MP (720p)": (1280, 736, 1280),
    "2.0MP (1080p)": (1920, 1088, 1920),
}

_EN = {
    "timeline_empty": "Please fill the Timeline Prompt (one line per block, e.g. 0-5s: action description).",
    "timeline_bad": "Timeline prompt format was not recognized. Use one line per block: 0-5s: action description.",
    "too_long": "Segment frame count %d exceeds the model limit of 362 (keep one segment under ~15s).",
    "too_short": "Total duration %.1fs is smaller than segment duration %.1fs. Increase total or reduce segment.",
    "not_divisible": "Total %.1fs is not divisible by segment %.1fs: it would generate %d segment(s) totaling %.1fs, which does not match the requested duration. Prefer preset durations and preset segments (5/10/15s only).",
}


def _parse_timeline(text):
    blocks = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(
            r"^\s*(\d+(?:\.\d+)?)\s*[-~–—至]+\s*(\d+(?:\.\d+)?)\s*[s秒]?\s*[:：]?\s*(.+)$",
            line,
        )
        if m:
            blocks.append((float(m.group(1)), float(m.group(2)), m.group(3).strip()))
    return blocks


def _anchor_i2v(text, auto):
    t = text
    lock = "视频第一帧必须与给定首帧画面完全一致，角色必须始终在场、不能消失。"
    if auto and "首帧" not in t:
        t = lock + t
    if auto and "不能变大" not in t:
        t = t + "全程保持与参考图一致的小巧体型，不能变大。"
    return t


def _anchor_r2v(text, auto):
    t = text
    if auto and "参考图" not in t:
        t = "角色外观完全以参考图（正面/侧面/背面等）为准。" + t
    if auto and "不能变大" not in t:
        t = t + "全程保持小巧体型，不能变大。"
    return t


def _to_seconds(token, fallback):
    t = str(token or "").strip()
    if t in ("自定义", "Custom", "custom"):
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", t)
    return float(m.group(1)) if m else float(fallback)


def run_chain(p, lang="zh"):
    """执行链式导演台核心逻辑。

    p 的键（中英文节点统一在此归一化）：
      model_r2v, model_i2v, video_vae, audio_vae, clip
      images: dict {0..8: torch.Tensor}（只包含已连接的槽位）
      global_prompt, timeline_prompt
      duration_preset, custom_seconds, split_preset, custom_segment_seconds
      resolution_preset, ref_max_size, auto_anchor
      steps, sampler, scheduler, cfg, seed, shift_video, shift_audio
    """
    from ComfyUI_MiniMaxH3_Director.nodes.director_common import (  # noqa: PLC0415
        finalize_director_outputs,
        prepare_director_plan,
    )
    from ComfyUI_MiniMaxH3_Director.director.executor_core import (  # noqa: PLC0415
        execute_director_plan_core,
    )
    from ComfyUI_MiniMaxH3_Director.director.external_groups import (  # noqa: PLC0415
        pack_i2v_group,
        pack_r2v_group,
    )
    from ComfyUI_MiniMaxH3_Director.director.fl2v_timeline import (  # noqa: PLC0415
        _duration_to_minimax_frames,
    )

    model_r2v = p["model_r2v"]
    model_i2v = p["model_i2v"]
    video_vae = p["video_vae"]
    audio_vae = p["audio_vae"]
    clip = p["clip"]
    images = p.get("images") or {}

    total_seconds = _to_seconds(p["duration_preset"], p["custom_seconds"])
    if total_seconds is None:
        total_seconds = float(p["custom_seconds"])
    segment_seconds = _to_seconds(p["split_preset"], p["custom_segment_seconds"])
    if segment_seconds is None:
        segment_seconds = float(p["custom_segment_seconds"])
    width, height, ref_max_size = RES_PRESETS[p["resolution_preset"]]
    ref_max_size = int(p.get("ref_max_size") or ref_max_size)

    ratio = total_seconds / segment_seconds
    if total_seconds < segment_seconds - 1e-6:
        if lang == "en":
            raise ValueError(_EN["too_short"] % (total_seconds, segment_seconds))
        raise ValueError(
            "总时长 %.1f 秒小于每段 %.1f 秒：请增大总时长或减小每段秒数。"
            "推荐优先使用预设总时长与预设分段（每段仅 5/10/15 秒）。" % (total_seconds, segment_seconds)
        )
    if abs(ratio - round(ratio)) > 1e-6:
        seg_count_actual = int(round(ratio))
        if lang == "en":
            raise ValueError(_EN["not_divisible"] % (total_seconds, segment_seconds, seg_count_actual, seg_count_actual * segment_seconds))
        raise ValueError(
            "总时长 %.1f 秒无法被每段 %.1f 秒整除：实际将生成 %d 段共 %.1f 秒，与目标时长不符。"
            "推荐优先使用预设总时长与预设分段（每段仅 5/10/15 秒）。" % (
                total_seconds, segment_seconds, seg_count_actual, seg_count_actual * segment_seconds
            )
        )
    seg_count = max(1, int(round(ratio)))
    fc = _duration_to_minimax_frames(segment_seconds, 24.0)
    if fc > 362:
        if lang == "en":
            raise ValueError(_EN["too_long"] % fc)
        raise ValueError("每段帧数 %d 超过模型上限 362（单段请控制在约 15 秒内）" % fc)

    timeline_prompt = p.get("timeline_prompt") or ""
    if not timeline_prompt.strip():
        if lang == "en":
            raise ValueError(_EN["timeline_empty"])
        raise ValueError("请填写「时间轴提示词」（每行格式：0-5s: 动作描述）。")
    blocks = _parse_timeline(timeline_prompt)
    if not blocks:
        if lang == "en":
            raise ValueError(_EN["timeline_bad"])
        raise ValueError("时间轴提示词格式无法识别，请按每行「0-5s: 动作描述」的格式填写。")
    seg_prompts = []
    for i in range(seg_count):
        s0 = i * segment_seconds
        s1 = (i + 1) * segment_seconds
        hits = [b[2] for b in blocks if b[1] > s0 and b[0] < s1]
        if not hits:
            nearest = min(blocks, key=lambda b: min(abs(b[0] - s0), abs(b[1] - s1)))
            hits = [nearest[2]]
        seg_prompts.append("；".join(hits))

    r2v_refs = {0: images[0]}
    for idx in sorted(k for k in images if k != 0):
        if len(r2v_refs) < 9:
            r2v_refs[len(r2v_refs)] = images[idx]

    auto_anchor = bool(p.get("auto_anchor", True))
    global_prompt = p.get("global_prompt") or ""

    def make_timeline(task_type):
        return json.dumps(
            {
                "timelineMode": "prompt_batch",
                "totalFrames": fc,
                "frameRate": 24,
                "width": width,
                "height": height,
                "refMaxSize": ref_max_size,
                "output": {
                    "mode": "fixed",
                    "longEdge": ref_max_size,
                    "width": width,
                    "height": height,
                    "maxExportFrames": 0,
                    "exportMode": "all",
                    "continuityEnabled": False,
                },
                "global": {"taskType": task_type, "prompt": global_prompt},
                "segments": [
                    {
                        "id": "s0",
                        "start": 0,
                        "length": fc,
                        "frameCount": fc,
                        "durationSec": segment_seconds,
                        "prompt": "",
                        "taskType": "",
                        "refs": [],
                        "negativePrompt": "",
                    }
                ],
                "gen": {"defaultFrameCount": fc},
                "runSelectEnabled": False,
                "runSelection": [],
            },
            ensure_ascii=False,
        )

    all_images = []
    all_audios = []
    prev_last = None

    for i in range(seg_count):
        if i == 0:
            prompt = _anchor_r2v(seg_prompts[0], auto_anchor)
            groups = [
                pack_r2v_group(
                    prompt=prompt,
                    duration_sec=segment_seconds,
                    ref_images=r2v_refs,
                )
            ]
            task_type = "r2v — 参考主体生视频(Reference to Video)"
            kwargs_groups = {"r2v_groups": groups}
        else:
            prompt = _anchor_i2v(seg_prompts[i], auto_anchor)
            groups = [
                pack_i2v_group(
                    prompt=prompt,
                    duration_sec=segment_seconds,
                    first_frame=prev_last,
                    last_frame=None,
                )
            ]
            task_type = "i2v — 图生视频(Image to Video)"
            kwargs_groups = {"i2v_groups": groups}

        node_id = "chain_%d" % i
        plan = prepare_director_plan(
            timeline_data=make_timeline(task_type),
            task_type=task_type,
            global_prompt=global_prompt,
            total_frames=fc,
            frame_rate=24,
            width=width,
            height=height,
            ref_max_size=ref_max_size,
            unique_id=node_id,
            **kwargs_groups,
        )
        combined, seg_outputs, seg_audios, report = execute_director_plan_core(
            plan,
            node_id=node_id,
            model=(model_r2v if i == 0 else model_i2v),
            vae=video_vae,
            audio_vae=audio_vae,
            clip=clip,
            cfg=float(p.get("cfg", 1.0)),
            seed=int(p.get("seed", 0)),
            steps=int(p.get("steps", 4)),
            sampler=p.get("sampler", "er_sde"),
            scheduler=p.get("scheduler", "simple"),
            shift_video=float(p.get("shift_video", 12.0)),
            shift_audio=float(p.get("shift_audio", 3.0)),
            clear_vram_between_segments=True,
        )
        images_out, audio_out, _fps, _fc, _src, _rep = finalize_director_outputs(
            plan,
            combined,
            seg_outputs,
            report,
            export_source_images=False,
            segment_audios=seg_audios,
        )

        batch = images_out[0]
        all_images.append(batch)
        if audio_out and audio_out[0] is not None:
            all_audios.append(audio_out[0])
        prev_last = batch[-1:].clone()
        print(
            "[MiniMaxH3ChainDirector] segment %d/%d done (%d frames)" % (i + 1, seg_count, int(batch.shape[0])),
            flush=True,
        )

    final_images = torch.cat(all_images, dim=0)
    if all_audios:
        sr = int(all_audios[0].get("sample_rate", 32000))
        final_audio = {
            "waveform": torch.cat([a["waveform"] for a in all_audios], dim=-1),
            "sample_rate": sr,
        }
    else:
        final_audio = {"waveform": torch.zeros(1, 1, 0), "sample_rate": 32000}

    return (final_images, final_audio, 24.0, int(final_images.shape[0]))


class MiniMaxH3ChainDirector:
    """链式导演台（多段拼接）中文版。"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                # ---------- 连接口（提示词上方，保留英文原名） ----------
                "model_r2v": ("MODEL", {"tooltip": "ref2va 底座，用于第一段 r2v 生成"}),
                "model_i2v": ("MODEL", {"tooltip": "fl2va 底座，用于第2段及以后的 i2v 接力"}),
                "video_vae": ("VAE",),
                "audio_vae": ("VAE",),
                "clip": ("CLIP",),
                "image_0": ("IMAGE", {"tooltip": "第1张参考图 → <Picture 1>（场景/主体图）"}),
                # ---------- 提示词（中间区域） ----------
                "全局提示词": ("STRING", {"multiline": True, "default": "", "tooltip": "全片不变的设定：场景/风格/角色/机位等；可用 <Picture N> 引用参考图"}),
                "时间轴提示词": ("STRING", {"multiline": True, "default": "", "tooltip": "必填。每行格式：0-5s: 动作描述，节点自动按分段映射"}),
                # ---------- 参数（提示词下方，中文名） ----------
                "总时长预设": (TIME_PRESETS, {"default": "30秒", "tooltip": "推荐优先使用预设（15/30/45/60/90/120秒）；只有需要 5/8/33 秒等非预设时长时才选「自定义」"}),
                "自定义总时长（秒）": ("FLOAT", {"default": 30.0, "min": 5.0, "max": 600.0, "tooltip": "仅当「总时长预设」选「自定义」时生效"}),
                "分段方式": (SPLIT_PRESETS, {"default": "5秒每段 (推荐)", "tooltip": "预设每段只有 5秒/10秒/15秒 三类；特殊需求才选「自定义」"}),
                "自定义每段秒数": ("FLOAT", {"default": 5.0, "min": 5.0, "max": 15.0, "tooltip": "仅当「分段方式」选「自定义」时生效；单段上限约 15 秒"}),
                "分辨率预设（百万像素）": (list(RES_PRESETS.keys()), {"default": "0.4MP (480p)", "tooltip": "0.4MP=864×480(480p) / 0.9MP=1280×736(720p) / 2.0MP=1920×1088(1080p)"}),
                "参考图最大边（像素）": ("INT", {"default": 864, "min": 256, "max": 2048, "tooltip": "参考图缩放的最大边长，一般与分辨率预设一致"}),
                "自动锚点": ("BOOLEAN", {"default": True, "tooltip": "自动追加锁帧句/体型/参考图一致性锚点"}),
                "采样步数": ("INT", {"default": 4, "min": 1, "max": 100, "tooltip": "每一段内部的扩散采样步数；4步=加速LoRA推荐值，8步画质更细但耗时约翻倍"}),
                "采样器": (list(KSampler.SAMPLERS), {"default": "er_sde"}),
                "调度器": (list(KSampler.SCHEDULERS), {"default": "simple"}),
                "引导强度CFG": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "tooltip": "Turbo LoRA 下推荐 1.0"}),
                "随机种子": ("INT", {"default": 0}),
                "视频时间偏移": ("FLOAT", {"default": 12.0}),
                "音频时间偏移": ("FLOAT", {"default": 3.0}),
            },
            "optional": {
                "image_1": ("IMAGE", {"tooltip": "第2张参考图 → <Picture 2>"}),
                "image_2": ("IMAGE", {"tooltip": "第3张参考图 → <Picture 3>"}),
                "image_3": ("IMAGE", {"tooltip": "第4张参考图 → <Picture 4>"}),
                "image_4": ("IMAGE", {"tooltip": "第5张参考图 → <Picture 5>"}),
                "image_5": ("IMAGE", {"tooltip": "第6张参考图 → <Picture 6>"}),
                "image_6": ("IMAGE", {"tooltip": "第7张参考图 → <Picture 7>"}),
                "image_7": ("IMAGE", {"tooltip": "第8张参考图 → <Picture 8>"}),
                "image_8": ("IMAGE", {"tooltip": "第9张参考图 → <Picture 9>"}),
            },
        }

    RETURN_TYPES = ("IMAGE", "AUDIO", "FLOAT", "INT")
    RETURN_NAMES = ("画面帧", "音频", "帧率", "总帧数")
    FUNCTION = "run"
    CATEGORY = "utils/MiniMaxH3"

    def run(self, **kw):
        images = {0: kw["image_0"]}
        for i in range(1, 9):
            if kw.get(f"image_{i}") is not None:
                images[i] = kw[f"image_{i}"]
        return run_chain(
            {
                "model_r2v": kw["model_r2v"],
                "model_i2v": kw["model_i2v"],
                "video_vae": kw["video_vae"],
                "audio_vae": kw["audio_vae"],
                "clip": kw["clip"],
                "images": images,
                "global_prompt": kw["全局提示词"],
                "timeline_prompt": kw["时间轴提示词"],
                "duration_preset": kw["总时长预设"],
                "custom_seconds": kw["自定义总时长（秒）"],
                "split_preset": kw["分段方式"],
                "custom_segment_seconds": kw["自定义每段秒数"],
                "resolution_preset": kw["分辨率预设（百万像素）"],
                "ref_max_size": kw["参考图最大边（像素）"],
                "auto_anchor": kw["自动锚点"],
                "steps": kw["采样步数"],
                "sampler": kw["采样器"],
                "scheduler": kw["调度器"],
                "cfg": kw["引导强度CFG"],
                "seed": kw["随机种子"],
                "shift_video": kw["视频时间偏移"],
                "shift_audio": kw["音频时间偏移"],
            },
            lang="zh",
        )