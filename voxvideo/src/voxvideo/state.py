"""路径与持久状态的唯一接口。"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
except Exception:  # Windows 无 tzdata 时兜底：Asia/Shanghai 是固定 UTC+8，无夏令时
    SHANGHAI_TZ = timezone(timedelta(hours=8), "Asia/Shanghai")

KB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SHOT_ID_RE = re.compile(r"^shot-\d{3}$")

MANIFEST_SCHEMA_VERSION = 3
STAGE_KEYS = ("design", "design-review", "images", "image-review", "handoff-export", "narration")
STAGE_VALUES = ("pending", "completed", "needs-review", "optional")


class WorkspaceError(Exception):
    pass


def check_kebab(value: str, what: str) -> None:
    if not KB_RE.match(value):
        raise WorkspaceError(f"{what} 必须是 kebab-case（小写字母、数字、连字符）：{value!r}")


def check_shot_id(value: str) -> None:
    if not SHOT_ID_RE.match(value):
        raise WorkspaceError(f"镜头 ID 必须是 shot-001 形式：{value!r}")


def stable_hash(payload: object) -> str:
    """排序键的 JSON SHA256。"""
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write(path: Path, data: str | bytes) -> None:
    """写临时文件再 replace，避免写一半留下损坏文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "wb" if isinstance(data, bytes) else "w"
    encoding = None if isinstance(data, bytes) else "utf-8"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".tmp")
    try:
        with os.fdopen(fd, mode, encoding=encoding) as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def today_shanghai() -> str:
    return datetime.now(SHANGHAI_TZ).strftime("%Y%m%d")


class ProjectWorkspace:
    """项目路径与状态文件的唯一入口。"""

    def __init__(self, projects_dir: Path):
        self.projects_dir = Path(projects_dir)

    # ---------- 项目 ID 与骨架 ----------

    def new_id(self, topic: str, date: str | None = None) -> str:
        check_kebab(topic, "topic")
        day = date or today_shanghai()
        base = f"{day}-{topic}"
        if not self.projects_dir.joinpath(base).exists():
            return base
        n = 2
        while self.projects_dir.joinpath(f"{base}-{n:02d}").exists():
            n += 1
        return f"{base}-{n:02d}"

    def root(self, project_id: str) -> Path:
        return self.projects_dir / project_id

    def create(self, project_id: str, script_file: Path, style_id: str) -> dict:
        root = self.root(project_id)
        for sub in (
            "01-script",
            "02-audio",
            "03-images/references",
            "04-prompts",
            "05-video",
            ".work/raw-images",
            ".work/audio-takes",
        ):
            (root / sub).mkdir(parents=True, exist_ok=True)
        script_dst = root / "01-script" / "script.md"
        if not script_dst.exists():
            script_dst.write_bytes(Path(script_file).read_bytes())
        manifest = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "project_id": project_id,
            "created_at": datetime.now(SHANGHAI_TZ).isoformat(timespec="seconds"),
            "style": style_id,
            "script_file": "01-script/script.md",
            "stages": {k: "pending" for k in STAGE_KEYS},
            "narration": {"status": "pending"},
            "master": {"status": "pending"},
            "shots": {},
            "image_failures": {},
            "design_fingerprint": None,
            "handoff_stale": False,
        }
        self.write_manifest(project_id, manifest)
        self.write_project_md(project_id)
        return manifest

    # ---------- manifest ----------

    def manifest_path(self, project_id: str) -> Path:
        return self.root(project_id) / ".work" / "manifest.json"

    def load_manifest(self, project_id: str) -> dict:
        return json.loads(self.manifest_path(project_id).read_text(encoding="utf-8"))

    def write_manifest(self, project_id: str, manifest: dict) -> None:
        atomic_write(self.manifest_path(project_id), json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

    # ---------- 项目内路径 ----------

    def design_path(self, project_id: str) -> Path:
        return self.root(project_id) / ".work" / "design.json"

    def master_prompt_path(self, project_id: str) -> Path:
        return self.root(project_id) / ".work" / "master-prompt.txt"

    def master_path(self, project_id: str) -> Path:
        return self.root(project_id) / "03-images" / "master.png"

    def reference_path(self, project_id: str, shot_id: str) -> Path:
        return self.root(project_id) / "03-images" / "references" / f"{shot_id}.png"

    def raw_image_path(self, project_id: str, shot_id: str) -> Path:
        return self.root(project_id) / ".work" / "raw-images" / f"{shot_id}.png"

    def take_path(self, project_id: str, shot_id: str) -> Path:
        return self.root(project_id) / ".work" / "audio-takes" / f"{shot_id}.wav"

    def narration_path(self, project_id: str) -> Path:
        return self.root(project_id) / "02-audio" / "narration.wav"

    def handoff_path(self, project_id: str) -> Path:
        return self.root(project_id) / "04-prompts" / "handoff.md"

    def preview_path(self, project_id: str) -> Path:
        return self.root(project_id) / "04-prompts" / "design-preview.md"

    # ---------- PROJECT.md ----------

    def write_project_md(self, project_id: str) -> None:
        root = self.root(project_id)
        manifest = self.load_manifest(project_id)
        design_path = self.design_path(project_id)
        needs_images = False
        if design_path.exists():
            try:
                design = load_json(design_path)
                needs_images = any("image_prompt" in s for s in design.get("shots", []))
            except Exception:
                needs_images = False
        if needs_images:
            master_line = "- `03-images/master.png`：风格母板（只用于生成参考图，交付时不上传）"
        else:
            master_line = "- 母板：本项目不需要（母板只用于生成参考图）"
        lines = [
            f"# {project_id}",
            "",
            f"- 风格模板：{manifest['style']}",
            f"- 脚本：`01-script/script.md`",
            "",
            "## 交付物",
            "",
            "- `04-prompts/handoff.md`：逐镜操作单（必出）",
            "- `04-prompts/design-preview.md`：拆镜预览",
            "- `02-audio/narration.wav`：整条配音（本地 Qwen3-TTS 克隆人声 + ffmpeg）",
            master_line,
            "- `03-images/references/`：按需参考图（需要 Agnes API）",
            "",
            "## 工作流",
            "",
            "```",
            "python -m voxvideo synthesize-narration --project <id>",
            "python -m voxvideo generate-images --project <id>",
            "python -m voxvideo approve-images --project <id>",
            "python -m voxvideo export-handoff --project <id>",
            "```",
            "",
            "生成视频、下载、合成、字幕由人手工完成，AI 在导出 handoff.md 后收工。",
            "",
        ]
        atomic_write(root / "PROJECT.md", "\n".join(lines))
