"""最终交付 04-prompts/handoff.md —— 给正要去 Google Flow 干活的人的操作单，不是数据转储。"""

from __future__ import annotations

from pathlib import Path

from .state import atomic_write


class HandoffError(Exception):
    pass


def check_export_ready(manifest: dict, image_shots: list[dict], master: dict | None) -> None:
    """导出前置：母板 approved，且有参考图的镜全部 approved。无参考图的镜不参与。"""
    missing = []
    if image_shots and master and master.get("status") != "approved":
        missing.append("母板 master.png 未审核")
    for shot in image_shots:
        status = (manifest["shots"].get(shot["id"]) or {}).get("status")
        if status != "approved":
            missing.append(f"{shot['id']} 参考图未审核（当前 {status}）")
    if missing:
        raise HandoffError(
            "以下图片未审核，不能导出：\n- " + "\n- ".join(missing)
            + "\n请先查看 03-images/ 下的每一张图，确认后运行 approve-images。"
        )


def _image_block(manifest: dict, project_id: str, shot_id: str) -> str:
    info = manifest["shots"].get(shot_id) or {}
    if info.get("status") in ("downloaded", "approved"):
        rel = Path("03-images") / "references" / f"{shot_id}.png"
        return (
            "**参考图：上传 `../" + str(rel) + "`（image2image 输入）。**\n\n"
            f"![参考图](../{str(rel)})\n"
        )
    return "**本镜不上传参考图，直接用下面的提示词生成。**\n"


# Flow 档位（LESSONS D1：Omni Flash 只有 4/6/8/10 秒；第 0 轮实测 4/6/8 档 ≈ 整秒）
FLOW_SLOTS = (4, 6, 8, 10)


def flow_slot(seconds: float) -> int:
    """真实时长就近吸附到最近的 Flow 档位（分界 5/7/9，srt-vox 第 5 节翻译）。

    硬规律：自然时长 ≥ 3 秒时 |差值（档位 − 实测）| ≤ 1.0 秒。
    3 秒以下取 4 秒档（平台地板，差值可 >1.0，属短镜）。
    """
    if seconds < 3.0:
        return 4
    return min(FLOW_SLOTS, key=lambda c: (abs(c - seconds), c))


def render_handoff(design: dict, plan: list[dict], manifest: dict, project_id: str,
                   narration_ready: bool) -> str:
    lines = [
        f"# {project_id} · 逐镜操作单",
        "",
        f"标题：{design.get('title') or '（未命名）'}",
        f"主张：{design.get('topic') or '（未写）'}",
        "",
        "## 开工前必读",
        "",
        "- 模型：**Omni Flash**；比例：**16:9**",
        "- **母板 `03-images/master.png` 不要上传**——它是风格表，不是画面。",
        "- 每镜完整提示词在独立代码块里，一键复制到 Flow。",
        "- 档位说明：Flow 只有 4/6/8/10 秒档，下面「Flow 档位」= 旁白真实时长就近吸附（差值 ≤1.0s，剪辑一步处理）。",
        "",
    ]
    for shot in plan:
        lines.append(f"## {shot['id']} {shot.get('title') or ''}".rstrip())
        lines.append("")
        lines.append(f"Flow 档位：{flow_slot(shot['duration_seconds'])}s"
                     f"（旁白真实时长 {shot['duration_seconds']:.1f}s）")
        lines.append("")
        lines.append("旁白：")
        lines.append("")
        lines.append(f"> {shot['narration']}")
        lines.append("")
        lines.append(_image_block(manifest, project_id, shot["id"]))
        lines.append("提示词：")
        lines.append("")
        lines.append("```text")
        lines.append(shot["video_prompt"])
        lines.append("```")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 接下来由你完成（以下步骤不由 AI 完成）")
    lines.append("")
    lines.append("1. 逐镜生成并下载视频（模型 Omni Flash，比例 16:9，选「Flow 档位」列的时间）。")
    lines.append("2. 按 `shot-001.mp4` 这样重命名，放进 `05-video/`。")
    lines.append("3. 用剪辑软件按镜号顺序拼接。")
    if narration_ready:
        lines.append("4. 混入 `02-audio/narration.wav`。")
        lines.append("5. 加字幕、导出成片。")
    else:
        lines.append("4. 配音未生成：可先运行 synthesize-narration，或自行配一段。")
        lines.append("5. 加字幕、导出成片。")
    lines.append("")
    return "\n".join(lines)


def write_handoff(design: dict, plan: list[dict], manifest: dict, project_id: str,
                  narration_ready: bool, path) -> None:
    atomic_write(path, render_handoff(design, plan, manifest, project_id, narration_ready))
