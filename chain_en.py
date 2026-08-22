"""MiniMax H3 Chain Director (English version) — 纯英文版链式导演台。

Same core as the Chinese node (chain.py MiniMaxH3ChainDirector), but every
label/tooltip/error message is in English. Layout:
  - connection ports on top: model_r2v / model_i2v / video_vae / audio_vae /
    clip / image_0..image_8 (9 image slots → <Picture 1..9>)
  - prompts in the middle: Global Prompt + Timeline Prompt (0-5s: action, required)
  - parameters below (all English)

Requires ComfyUI_MiniMaxH3_Director (apply patches/ in this repo).
"""

from __future__ import annotations

from comfy.samplers import KSampler

from .chain import RES_PRESETS, SPLIT_PRESETS, TIME_PRESETS, run_chain

EN_TIME_PRESETS = ["15s", "30s", "45s", "60s", "90s", "120s", "Custom"]
EN_SPLIT_PRESETS = ["5s per segment (recommended)", "10s per segment", "15s per segment", "Custom"]


class MiniMaxH3ChainDirectorEN:
    """MiniMax H3 Chain Director (pure English)."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                # ---------- connection ports (top, original names) ----------
                "model_r2v": ("MODEL", {"tooltip": "ref2va base model, used for the first r2v segment"}),
                "model_i2v": ("MODEL", {"tooltip": "fl2va base model, used for segment 2+ (i2v handoff)"}),
                "video_vae": ("VAE",),
                "audio_vae": ("VAE",),
                "clip": ("CLIP",),
                "image_0": ("IMAGE", {"tooltip": "Reference image 1 → <Picture 1> (scene / main subject)"}),
                # ---------- prompts (middle) ----------
                "global_prompt": ("STRING", {"multiline": True, "default": "", "tooltip": "Constant settings for the whole video: scene/style/character/camera. You may reference images with <Picture N>."}),
                "timeline_prompt": ("STRING", {"multiline": True, "default": "", "tooltip": "Required. One line per block: 0-5s: action description. Auto-mapped to segments."}),
                # ---------- parameters (below, English) ----------
                "duration_preset": (EN_TIME_PRESETS, {"default": "30s", "tooltip": "Prefer presets (15/30/45/60/90/120s). Use Custom only for non-preset durations like 5/8/33s."}),
                "custom_seconds": ("FLOAT", {"default": 30.0, "min": 5.0, "max": 600.0, "tooltip": "Only used when Duration Preset = Custom"}),
                "split_preset": (EN_SPLIT_PRESETS, {"default": "5s per segment (recommended)", "tooltip": "Presets are only 5s/10s/15s per segment. Use Custom for special cases."}),
                "custom_segment_seconds": ("FLOAT", {"default": 5.0, "min": 5.0, "max": 15.0, "tooltip": "Only used when Split Preset = Custom; max ~15s per segment"}),
                "resolution_preset": (list(RES_PRESETS.keys()), {"default": "0.4MP (480p)", "tooltip": "0.4MP=864x480 (480p) / 0.9MP=1280x736 (720p) / 2.0MP=1920x1088 (1080p)"}),
                "ref_max_size": ("INT", {"default": 864, "min": 256, "max": 2048, "tooltip": "Max edge length for reference image resizing; usually matches the resolution preset"}),
                "auto_anchor": ("BOOLEAN", {"default": True, "tooltip": "Auto-append first-frame lock / body-size / reference consistency anchors"}),
                "steps": ("INT", {"default": 4, "min": 1, "max": 100, "tooltip": "Diffusion steps INSIDE EACH segment. 4 = turbo LoRA recommended; 8 is sharper but ~2x slower."}),
                "sampler": (list(KSampler.SAMPLERS), {"default": "er_sde"}),
                "scheduler": (list(KSampler.SCHEDULERS), {"default": "simple"}),
                "cfg": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "tooltip": "Recommended 1.0 with the turbo LoRA"}),
                "seed": ("INT", {"default": 0}),
                "shift_video": ("FLOAT", {"default": 12.0}),
                "shift_audio": ("FLOAT", {"default": 3.0}),
            },
            "optional": {
                "image_1": ("IMAGE", {"tooltip": "Reference image 2 → <Picture 2>"}),
                "image_2": ("IMAGE", {"tooltip": "Reference image 3 → <Picture 3>"}),
                "image_3": ("IMAGE", {"tooltip": "Reference image 4 → <Picture 4>"}),
                "image_4": ("IMAGE", {"tooltip": "Reference image 5 → <Picture 5>"}),
                "image_5": ("IMAGE", {"tooltip": "Reference image 6 → <Picture 6>"}),
                "image_6": ("IMAGE", {"tooltip": "Reference image 7 → <Picture 7>"}),
                "image_7": ("IMAGE", {"tooltip": "Reference image 8 → <Picture 8>"}),
                "image_8": ("IMAGE", {"tooltip": "Reference image 9 → <Picture 9>"}),
            },
        }

    RETURN_TYPES = ("IMAGE", "AUDIO", "FLOAT", "INT")
    RETURN_NAMES = ("images", "audio", "fps", "frame_count")
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
                "global_prompt": kw["global_prompt"],
                "timeline_prompt": kw["timeline_prompt"],
                "duration_preset": kw["duration_preset"],
                "custom_seconds": kw["custom_seconds"],
                "split_preset": kw["split_preset"],
                "custom_segment_seconds": kw["custom_segment_seconds"],
                "resolution_preset": kw["resolution_preset"],
                "ref_max_size": kw["ref_max_size"],
                "auto_anchor": kw["auto_anchor"],
                "steps": kw["steps"],
                "sampler": kw["sampler"],
                "scheduler": kw["scheduler"],
                "cfg": kw["cfg"],
                "seed": kw["seed"],
                "shift_video": kw["shift_video"],
                "shift_audio": kw["shift_audio"],
            },
            lang="en",
        )