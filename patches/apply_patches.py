"""Apply the two required patches to ComfyUI_MiniMaxH3_Director.

Usage:
    python apply_patches.py [<comfyui_root>]

Default <comfyui_root> is derived from this file's location if the plugin was
cloned inside custom_nodes, otherwise pass the ComfyUI root explicitly.
"""

import io
import os
import sys


def patch_file(path: str, old: str, new: str, label: str) -> bool:
    content = io.open(path, encoding="utf-8").read()
    n = content.count(old)
    if n != 1:
        print("[SKIP] %s: match count = %d (already applied or path wrong)" % (label, n))
        return False
    io.open(path, "w", encoding="utf-8").write(content.replace(old, new))
    print("[OK]   %s patched" % label)
    return True


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    if len(sys.argv) > 1:
        root = sys.argv[1]
    else:
        root = os.path.abspath(os.path.join(here, "..", "..", "ComfyUI_MiniMaxH3_Director"))

    groups_py = os.path.join(root, "nodes", "director_groups.py")
    external_py = os.path.join(root, "director", "external_groups.py")

    ok = True

    ok &= patch_file(
        groups_py,
        (
            "        def execute(cls, groups=None) -> comfy_io.NodeOutput:\n"
            "            return comfy_io.NodeOutput(_combine_groups(groups))"
        ),
        (
            "        def execute(cls, groups=None, **kwargs) -> comfy_io.NodeOutput:\n"
            "            if groups is None:\n"
            "                groups = {k: v for k, v in kwargs.items() if k.startswith('group_')}\n"
            "            return comfy_io.NodeOutput(_combine_groups(groups))"
        ),
        "Combine autogrow compat",
    )

    old_head = "    return DirectorPlan(\n        frame_rate=fps,"
    new_head = (
        "    from .segment_continuity import resolve_continuity_settings\n\n"
        "    continuity_enabled, continuity_overlap = resolve_continuity_settings(\n"
        "        timeline, segment_count=len(segments)\n"
        "    )\n\n"
        "    return DirectorPlan(\n        frame_rate=fps,"
    )
    old_tail = "        run_indices=None,  # already filtered\n    )"
    new_tail = (
        "        run_indices=None,  # already filtered\n"
        "        continuity_enabled=continuity_enabled,\n"
        "        continuity_overlap_frames=continuity_overlap,\n"
        "    )"
    )
    content = io.open(external_py, encoding="utf-8").read()
    n1, n2 = content.count(old_head), content.count(old_tail)
    if n1 == 1 and n2 == 1:
        io.open(external_py, "w", encoding="utf-8").write(
            content.replace(old_head, new_head).replace(old_tail, new_tail)
        )
        print("[OK]   External-groups continuity patched")
    else:
        print("[SKIP] External-groups continuity: head=%d tail=%d (already applied or path wrong)" % (n1, n2))
        ok = False

    print("done. Restart ComfyUI after patching." if ok else "some patches skipped - check paths.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
