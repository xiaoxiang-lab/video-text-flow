"""argparse 分发，输出 JSON。异常打到 stderr 并以 1 退出。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .adapter import AdapterError
from .handoff import HandoffError
from .media import MediaError
from .narration import NarrationError
from .pipeline import Pipeline, PipelineError
from .planning import DesignError
from .qa import QaError
from .state import WorkspaceError, check_shot_id, load_json
from .style import StyleError, load_styles

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "default.json"

KNOWN_ERRORS = (
    WorkspaceError, StyleError, DesignError, PipelineError, AdapterError,
    NarrationError, MediaError, QaError, HandoffError,
)


def _load_config() -> dict:
    return load_json(CONFIG_PATH)


def _out(payload: object) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_styles(config: dict) -> int:
    profiles = ROOT / config["style"]["profiles_dir"]
    styles = []
    for s in load_styles(profiles):
        styles.append({
            "id": s["id"], "name": s["name"], "summary": s["summary"],
            "status": s["status"], "guide_files": s["guide_files"],
            "reference_files": s.get("reference_files", []),
            "default_shot_seconds": s.get("default_shot_seconds", 4),
        })
    return _out({"styles": styles})


def cmd_init(config: dict, args) -> int:
    script = Path(args.script_file)
    if not script.exists():
        raise WorkspaceError(f"脚本文件不存在：{script}")
    from .style import get_style
    profiles = ROOT / config["style"]["profiles_dir"]
    style = get_style(profiles, args.style)
    ws = config["_ws"]
    project_id = ws.new_id(args.topic)
    ws.create(project_id, script, style["id"])
    guide_files = [str((ROOT / f).resolve()) for f in style["guide_files"]]
    return _out({
        "project_id": project_id,
        "style": style["id"],
        "style_guide_files": guide_files,
        "script": "01-script/script.md",
    })


def _require_pipeline(config: dict, project_id: str) -> Pipeline:
    return Pipeline(config["_ws"], config, ROOT)


def cmd_synthesize(config: dict, args) -> int:
    result = _require_pipeline(config, args.project).synthesize_narration(args.project)
    return _out(result)


def cmd_review_design(config: dict, args) -> int:
    return _out(_require_pipeline(config, args.project).review_design(args.project))


def cmd_generate_images(config: dict, args) -> int:
    shot_ids = args.shot_id or None
    if shot_ids:
        for sid in shot_ids:
            check_shot_id(sid)
    result = _require_pipeline(config, args.project).generate_images(args.project, shot_ids=shot_ids)
    return _out(result)


def cmd_approve(config: dict, args) -> int:
    return _out(_require_pipeline(config, args.project).approve_images(args.project))


def cmd_retry(config: dict, args) -> int:
    check_shot_id(args.shot_id)
    result = _require_pipeline(config, args.project).retry_image(args.project, args.shot_id, args.prompt_file)
    return _out(result)


def cmd_export(config: dict, args) -> int:
    return _out(_require_pipeline(config, args.project).export_handoff(args.project))


def cmd_resume(config: dict, args) -> int:
    return _out(_require_pipeline(config, args.project).resume(args.project))


def cmd_status(config: dict, args) -> int:
    return _out(_require_pipeline(config, args.project).status(args.project))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="voxvideo", description="脚本 → 素材包 → 人手工出片")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("styles", help="列出可用风格模板及其必读指南文件")

    p_init = sub.add_parser("init", help="建项目")
    p_init.add_argument("--topic", required=True, help="kebab-case 主题")
    p_init.add_argument("--script-file", required=True, help="脚本路径")
    p_init.add_argument("--style", default=None, help="风格模板 id（缺省用 config 默认）")

    p_syn = sub.add_parser("synthesize-narration", help="合成逐镜配音（Qwen3-TTS/Fish Audio）并拼接")
    p_syn.add_argument("--project", required=True)

    p_gen = sub.add_parser("generate-images", help="先生成母板，再生成写了 image_prompt 的镜的参考图（design 必须已复核）")
    p_gen.add_argument("--project", required=True)
    p_gen.add_argument("--shot-id", nargs="+", help="只生成指定镜（可多个）")

    p_rev = sub.add_parser("review-design", help="独立子 agent 复核通过后标记 design-review=completed")
    p_rev.add_argument("--project", required=True)

    p_app = sub.add_parser("approve-images", help="AI 真实看图后调用，推进到已审核")
    p_app.add_argument("--project", required=True)

    p_ret = sub.add_parser("retry-image", help="换提示词只重抽一张")
    p_ret.add_argument("--project", required=True)
    p_ret.add_argument("--shot-id", required=True)
    p_ret.add_argument("--prompt-file", required=True)

    p_exp = sub.add_parser("export-handoff", help="导出最终素材包操作单")
    p_exp.add_argument("--project", required=True)

    p_res = sub.add_parser("resume", help="从未完成的步骤继续；图片没审就停下")
    p_res.add_argument("--project", required=True)

    p_sta = sub.add_parser("status", help="当前状态")
    p_sta.add_argument("--project", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = _load_config()
        from .state import ProjectWorkspace
        # 项目根可经环境变量覆盖（默认 ROOT/projects）
        projects_env = os.environ.get("VOXVIDEO_PROJECTS_DIR", "").strip()
        if projects_env:
            projects_dir = Path(projects_env)
            if not projects_dir.is_absolute():
                projects_dir = ROOT / projects_dir
        else:
            projects_dir = ROOT / config.get("projects_dir", "projects")
        config["_ws"] = ProjectWorkspace(projects_dir)
        if args.command == "styles":
            return cmd_styles(config)
        if args.command == "init":
            if args.style is None:
                args.style = config["style"]["default"]
            return cmd_init(config, args)
        if args.command == "synthesize-narration":
            return cmd_synthesize(config, args)
        if args.command == "review-design":
            return cmd_review_design(config, args)
        if args.command == "generate-images":
            return cmd_generate_images(config, args)
        if args.command == "approve-images":
            return cmd_approve(config, args)
        if args.command == "retry-image":
            return cmd_retry(config, args)
        if args.command == "export-handoff":
            return cmd_export(config, args)
        if args.command == "resume":
            return cmd_resume(config, args)
        if args.command == "status":
            return cmd_status(config, args)
        parser.error(f"未知命令：{args.command}")
        return 1
    except KNOWN_ERRORS as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"error: 文件不存在：{exc}", file=sys.stderr)
        return 1
