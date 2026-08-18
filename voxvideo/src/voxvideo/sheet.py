"""04-prompts/design-preview.md 渲染。"""

from __future__ import annotations

from .state import atomic_write


def render_preview(design: dict, plan: list[dict]) -> str:
    lines = [
        "# 拆镜预览",
        "",
        f"- 标题：{design.get('title') or '（未命名）'}",
        f"- 主张：{design.get('topic') or '（未写）'}",
        f"- 镜数：{len(plan)}",
        "",
    ]
    for shot in plan:
        lines.append(f"## {shot['id']} {shot.get('title') or ''}".rstrip())
        lines.append("")
        lines.append(f"- 建议时长：{shot['duration_seconds']:.1f}s")
        if "image" in shot:
            lines.append("- 参考图：需要（已写 image_prompt）")
        else:
            lines.append("- 参考图：不需要")
        lines.append("")
        lines.append("旁白：")
        lines.append("")
        lines.append(f"> {shot['narration']}")
        lines.append("")
        if "audio_notes" in shot:
            lines.append(f"配音备注：{shot['audio_notes']}")
            lines.append("")
        lines.append("视频提示词：")
        lines.append("")
        lines.append("```text")
        lines.append(shot["video_prompt"])
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def write_preview(design: dict, plan: list[dict], path) -> None:
    atomic_write(path, render_preview(design, plan))
