"""design.json 校验与镜头计划生成。"""

from __future__ import annotations

import json
from pathlib import Path

from .state import stable_hash


class DesignError(Exception):
    pass


def require_design(design_path: Path) -> dict:
    """校验 design.json：每镜必须有非空 narration 和 video_prompt。

    image_prompt 可选——写了就代表这镜要参考图，没写就跳过。
    不接受空字符串占位：要么有内容，要么整个字段不存在。
    """
    path = Path(design_path)
    if not path.exists():
        raise DesignError(f"design.json 不存在：{path}")
    try:
        design = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DesignError(f"design.json 不是合法 JSON：{exc}") from exc
    if not isinstance(design, dict) or "shots" not in design:
        raise DesignError("design.json 必须包含 shots 列表")
    shots = design["shots"]
    if not isinstance(shots, list) or not shots:
        raise DesignError("design.json 的 shots 不能为空")
    for i, shot in enumerate(shots, 1):
        if not isinstance(shot, dict):
            raise DesignError(f"第 {i} 镜不是对象")
        for field in ("narration", "video_prompt"):
            if field not in shot:
                raise DesignError(f"第 {i} 镜缺少 {field!r} 字段")
            if not isinstance(shot[field], str) or not shot[field].strip():
                raise DesignError(f"第 {i} 镜的 {field!r} 必须是非空字符串")
        if "image_prompt" in shot:
            if not isinstance(shot["image_prompt"], str) or not shot["image_prompt"].strip():
                raise DesignError(
                    f"第 {i} 镜的 image_prompt 是空字符串：要么给内容，要么删掉这个字段（不写就表示这镜不需要参考图）"
                )
        for field, kind in (("title", str), ("audio_notes", str)):
            if field in shot and not isinstance(shot[field], kind):
                raise DesignError(f"第 {i} 镜的 {field!r} 必须是字符串")
        if "duration_seconds" in shot:
            if not isinstance(shot["duration_seconds"], (int, float)) or shot["duration_seconds"] <= 0:
                raise DesignError(f"第 {i} 镜的 duration_seconds 必须是正数")
    return design


def design_fingerprint(design: dict) -> str:
    return stable_hash(design)


def make_plan(design: dict, default_seconds: float = 4.0, durations: dict | None = None) -> list[dict]:
    """生成镜头计划：分配 shot-001 式 ID 与时长。

    有真实配音时长时优先用它，否则用模板的 default_shot_seconds。
    没写 image_prompt 的镜不给它建 image 结构——判定只有一处：
    shot["image"] 存在即需要参考图。
    """
    durations = durations or {}
    plan = []
    for i, shot in enumerate(design["shots"], 1):
        shot_id = f"shot-{i:03d}"
        dur = durations.get(shot_id)
        if not dur:
            dur = shot.get("duration_seconds") or default_seconds
        entry = {
            "id": shot_id,
            "index": i,
            "title": shot.get("title", ""),
            "narration": shot["narration"],
            "video_prompt": shot["video_prompt"],
            "duration_seconds": float(dur),
        }
        if "audio_notes" in shot:
            entry["audio_notes"] = shot["audio_notes"]
        if "image_prompt" in shot:
            entry["image"] = {"prompt": shot["image_prompt"], "status": "pending"}
        plan.append(entry)
    return plan
