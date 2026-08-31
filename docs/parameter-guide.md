# Parameter Guide & Recommended Settings (MiniMax H3 Chain Director)

The Chain Director splits long videos into N segments and generates them one by one, so **the sampling parameters below apply per segment**, not to the whole video. Example: 60s / 10s per segment = 6 segments; with steps = 4, each segment runs its own 4-step sampling.

## Quick Reference

| Parameter | Recommended | What it does |
|---|---|---|
| `ref_video_fps` | `0` | Only matters when `ref_video` is connected: `0` = auto proportional slicing; real fps = exact per-second slicing |
| `auto_anchor` | True | Automatically appends consistency anchor sentences (first-frame lock / body & costume consistency / reference-image consistency) to every segment |
| `steps` | `4` (turbo LoRA) / `8` (quality first) | Diffusion sampling steps **per segment** |
| `sampler` | `er_sde` | Standard sampler for MiniMax H3 + turbo LoRA |
| `scheduler` | `simple` | Standard scheduler paired with er_sde / turbo LoRA |
| `cfg` | `1.0` (turbo LoRA) | How strongly the prompt controls the output |

## 1. ref_video_fps

- Type: INT, range `0-240`, default `0`.
- Purpose: only relevant when a `ref_video` is connected. It controls how the reference video is sliced per segment:
  - `0` = auto proportional slicing by frame count (most generic, recommended).
  - Real fps (e.g. `30`) = exact per-second slicing (`segment_seconds x fps` frames per segment).
- Tip: keep `0` when no reference video is connected; it does not affect generation.

## 2. auto_anchor

- Type: BOOLEAN, default True.
- Purpose: appends consistency anchor sentences to each segment prompt (first frame must match previous segment's last frame; character proportions/costume/hair follow the reference image; scene objects do not drift).
- Tip: keep enabled. Disable only if you write your own complete anchors and want full control. If characters feel "too locked" (stiff motion), try disabling and writing anchors yourself.

## 3. steps

- Type: INT, range `1-100`, default `4`.
- Meaning: sampling steps **per segment**. Total sampling = segments x steps.
- Tip:
  - `4`: recommended with the turbo LoRA (lightx2v 4step); fast and close to the LoRA's advertised quality.
  - `8`: better quality/stability, roughly 1.8-2x the time of 4 steps.
  - Without turbo LoRA (stock model), use `10-30` steps. Using `4` without the LoRA under-samples (blurry / blocky output).

## 4. sampler

- Type: combo (44 options), default `er_sde`.
- Purpose: numerical solver for diffusion denoising; different samplers converge differently.
- Tip: use **er_sde** for MiniMax H3 + turbo LoRA. Without the LoRA you can try `dpmpp_2m_sde` / `euler_ancestral`.
- If `er_sde` is missing from the dropdown, upgrade ComfyUI to >= 0.30.

## 5. scheduler

- Type: combo, default `simple`.
- Purpose: noise schedule curve for each step.
- Tip: keep **simple** with er_sde + turbo LoRA. If output looks overexposed/gray, try `karras` / `exponential`.

## 6. cfg

- Type: FLOAT, range `0.0-10.0`, default `1.0`.
- Meaning: prompt control strength. Higher = more obedient to the prompt, but too high causes saturation and artifacts.
- Tip:
  - turbo LoRA: `1.0` (tune within `0.8-1.5`).
  - Stock model without LoRA: `3-6`.
- Common issues: CFG too high + 4 steps = blurry / oversaturated / flickering; CFG too low = output ignores the prompt.

## Recommended Configurations

| Use case | Resolution | Split | Steps | Sampler/Scheduler | CFG |
|---|---|---|---|---|---|
| Quick test | 480p | 5s per segment | 4 | er_sde + simple | 1.0 |
| Export (speed first) | 720p | 5s per segment | 4 | er_sde + simple | 1.0 |
| Export (quality first) | 720p | 5s per segment | 8 | er_sde + simple | 1.0 |
| 1080p long video | 1080p | 5s per segment | 4-8 | er_sde + simple | 1.0 |

## Troubleshooting

### "Input out of range / Invalid input / Wrong input type" when loading an old workflow

- Cause: the workflow was saved with an **older node version**. Newer nodes added the `ref_video_fps` widget, shifting all parameter positions in old workflows (typical symptom: the steps box shows `er_sde`, the CFG box shows a huge number).
- Fix: set the values back to the recommendations and re-save: `ref_video_fps=0`, auto_anchor=True, steps=`4`, sampler=`er_sde`, scheduler=`simple`, cfg=`1.0`.

### ModuleNotFoundError: No module named 'sageattention'

- Cause: the workflow includes two `Patch Sage Attention (KJ)` nodes, but `sageattention` is not installed in the current ComfyUI environment.
- Fix: right-click both SageAttention nodes and choose **Bypass**, or install `sageattention==1.0.6` per the README.