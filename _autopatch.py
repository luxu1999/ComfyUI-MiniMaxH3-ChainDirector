"""Runtime self-heal for ComfyUI_MiniMaxH3_Director (no disk writes).

说明：链式导演台节点本身不依赖 Director 的补丁——i2v 首帧锁定是通过组内的
SegmentRef 传递的（已实测未打补丁的旧版 Director 拼接缝依然顺滑）。

本模块提供安全网：
1. 检查 Director 是否安装、核心接口是否存在（缺了就给出明确提示）；
2. 若 Director 版本缺少"段连续性接线"（旧版 02 补丁的等价物），在内存中自动
   补齐，保证 Director 自带的连续性功能对其它工作流也有效；
3. 全程幂等、失败静默，绝不修改磁盘文件、绝不导致 ComfyUI 崩溃。

注意：ComfyUI 加载自定义节点时 custom_nodes 目录不在 sys.path 上，且节点是
逐个注册进 sys.modules 的；因此真正的自检放在「首次运行时」执行（此时所有
插件都已加载完毕）。__init__ 阶段的调用只是温和提示。

原手动补丁方式（patches/apply_patches.py）保留，两者互不影响。
"""

from __future__ import annotations

import json
import os
import sys

_DIRECTOR_PKG = "ComfyUI_MiniMaxH3_Director"

# (子包, 模块, 函数) —— 链式导演台依赖的 Director 接口
_REQUIRED_API = (
    ("director", "external_groups", "pack_i2v_group"),
    ("director", "external_groups", "pack_r2v_group"),
    ("director", "external_groups", "build_plan_from_external_groups"),
    ("director", "executor_core", "execute_director_plan_core"),
    ("nodes", "director_common", "prepare_director_plan"),
    ("nodes", "director_common", "finalize_director_outputs"),
    ("director", "fl2v_timeline", "_duration_to_minimax_frames"),
)

_checked = False


def _find_director_module():
    """优先从 sys.modules 取（运行期必在），否则尝试普通 import。"""
    mod = sys.modules.get(_DIRECTOR_PKG)
    if mod is not None:
        return mod
    try:
        return __import__(_DIRECTOR_PKG)
    except Exception:  # noqa: BLE001
        return None


def _director_dir_exists() -> bool:
    here = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        cand = os.path.join(here, "custom_nodes", _DIRECTOR_PKG)
        if os.path.isdir(cand):
            return True
        parent = os.path.dirname(here)
        if parent == here:
            break
        here = parent
    return False


def _get_member(sub, mod, name):
    try:
        module = __import__(f"{_DIRECTOR_PKG}.{sub}.{mod}", fromlist=[name])
        return getattr(module, name, None), module
    except Exception:  # noqa: BLE001
        return None, None


def _install_continuity_wrapper(ext_mod, original):
    """用包装函数在内存中补齐 build_plan_from_external_groups 的连续性接线。"""
    try:
        from ComfyUI_MiniMaxH3_Director.director.segment_continuity import (
            resolve_continuity_settings,
        )
    except Exception:  # noqa: BLE001
        return False

    def patched(*args, **kwargs):
        plan = original(*args, **kwargs)
        try:
            timeline = json.loads(kwargs.get("timeline_data") or "{}")
            enabled, overlap = resolve_continuity_settings(
                timeline, segment_count=len(getattr(plan, "segments", []) or [])
            )
            plan.continuity_enabled = enabled
            plan.continuity_overlap_frames = overlap
        except Exception:  # noqa: BLE001
            pass
        return plan

    try:
        setattr(ext_mod, original.__name__, patched)
        return True
    except Exception:  # noqa: BLE001
        return False



def director_available() -> bool:
    """Director 是否可用（已加载且可导入）。"""
    return _find_director_module() is not None

def ensure_director_ready() -> str:
    """返回给控制台的可读状态信息（幂等、安全）。运行期调用一次后缓存结果。"""
    global _checked
    if _checked:
        return ""

    mod = _find_director_module()
    if mod is None:
        if _director_dir_exists():
            return (
                "[MiniMaxH3ChainDirector] Director 已安装但尚未加载"
                "（插件加载顺序较早），将在首次生成前自动检测。"
            )
        return (
            "[MiniMaxH3ChainDirector] 未找到 ComfyUI_MiniMaxH3_Director，请先安装："
            "git clone https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director.git"
        )

    _checked = True
    msgs = []

    missing = []
    for sub, mod_name, name in _REQUIRED_API:
        obj, _ = _get_member(sub, mod_name, name)
        if obj is None:
            missing.append(f"{sub}.{mod_name}.{name}")
    if missing:
        msgs.append(
            "[MiniMaxH3ChainDirector] WARN Director 版本过旧/接口缺失：%s。"
            "建议更新 ComfyUI_MiniMaxH3_Director。" % ", ".join(missing)
        )

    fn_obj, ext_mod = _get_member("director", "external_groups", "build_plan_from_external_groups")
    if fn_obj is not None:
        src = getattr(ext_mod, "__file__", "") or ""
        text = ""
        try:
            with open(src, encoding="utf-8") as fh:
                text = fh.read()
        except Exception:  # noqa: BLE001
            pass
        if "continuity_overlap_frames" in text:
            msgs.append("[MiniMaxH3ChainDirector] Director 连续性接线已存在，无需补丁。")
        elif _install_continuity_wrapper(ext_mod, fn_obj):
            msgs.append(
                "[MiniMaxH3ChainDirector] 检测到旧版 Director 缺少连续性接线，"
                "已自动在内存中补齐（无需手动打补丁）。"
            )
        else:
            msgs.append(
                "[MiniMaxH3ChainDirector] WARN 无法自动补齐连续性接线，"
                "可运行 patches/apply_patches.py 手动打补丁。"
            )
    return "\n".join(msgs)