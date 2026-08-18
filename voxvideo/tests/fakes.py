import json
from pathlib import Path

from voxvideo.adapter import AdapterError
from voxvideo.planning import DesignError, design_fingerprint
from voxvideo.state import ProjectWorkspace, atomic_write

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 1500
WAV = b"RIFF" + b"\x00" * 200 + b"WAVE"


class FakeAdapter:
    """记录调用；wait 可配置失败/超时。测试里绝不发真实网络请求。"""

    name = "fake"

    def __init__(self, available=True, fail_waits=None, timeout_waits=None):
        self.available_ = available
        self.fail_waits = set(fail_waits or [])
        self.timeout_waits = set(timeout_waits or [])
        self.calls = []
        self.waits = []
        self._seq = 0

    def available(self) -> bool:
        return self.available_

    def generate(self, prompt, output_path, fingerprint=None):
        self.calls.append(("text2image", prompt))
        return {"submit_id": self._next()}

    def generate_with_reference(self, prompt, reference_image, output_path, fingerprint=None):
        self.calls.append(("image2image", prompt))
        return {"submit_id": self._next()}

    def _next(self):
        self._seq += 1
        return f"sid-{self._seq}"

    def wait_and_download(self, submit_id, dest):
        self.waits.append(submit_id)
        n = len(self.waits)
        if submit_id in self.timeout_waits:
            raise TimeoutError("poll timeout")
        if n in self.fail_waits:
            raise AdapterError("boom")
        Path(dest).write_bytes(PNG)


class FakeNarrator:
    def __init__(self, voice_id="v-123"):
        self.voice_id = voice_id
        self.calls = []

    def describe(self):
        return {"provider": "fish-audio", "voice_id": self.voice_id,
                "model": "s2-pro", "format": "wav", "speed": 1.0}

    def synthesize(self, text, dest):
        self.calls.append(text)
        Path(dest).write_bytes(WAV)


def design_fixture(image_shots=(), n=4):
    shots = []
    for i in range(1, n + 1):
        s = {"title": f"镜{i}", "narration": f"旁白{i}", "video_prompt": f"提示词{i}"}
        if i in image_shots:
            s["image_prompt"] = f"参考图提示词{i}"
        shots.append(s)
    return {"title": "测试片", "topic": "一句话主张", "shots": shots}


def write_style_fixture(root: Path) -> None:
    styles = root / "config" / "styles"
    styles.mkdir(parents=True, exist_ok=True)
    (styles / "vox.json").write_text(json.dumps({
        "schema_version": 1,
        "id": "vox",
        "name": "Vox Editorial Collage",
        "summary": "s",
        "status": "stable",
        "master_prompt_file": "ref/vox-style/master-prompt.zh.txt",
        "guide_files": [".claude/skills/vox-prompts/SKILL.md"],
        "default_shot_seconds": 4,
    }, ensure_ascii=False), encoding="utf-8")
    ref = root / "ref" / "vox-style"
    ref.mkdir(parents=True, exist_ok=True)
    (ref / "master-prompt.zh.txt").write_text("MASTER PROMPT 风格表", encoding="utf-8")


def make_config() -> dict:
    return {
        "jimeng": {"binary": "dreamina", "session": 0, "model": "5.0", "resolution": "2k",
                   "poll_seconds": 0, "timeout_seconds": 60},
        "style": {"default": "vox", "profiles_dir": "config/styles"},
        "workflow": {"default_shot_seconds": 4},
        "narration": {
            "provider": "fish-audio",
            "endpoint": "https://api.fish.audio/v1/tts",
            "api_key_env": "FISH_API_KEY",
            "voice_env": "FISH_VOICE_ID",
            "model_env": "FISH_MODEL",
            "default_model": "s2-pro",
            "format": "wav",
            "speed": 1.0,
            "timeout_seconds": 180,
        },
    }


def make_project(root: Path, design: dict, topic="test-topic") -> str:
    write_style_fixture(root)
    ws = ProjectWorkspace(root / "projects")
    pid = ws.new_id(topic)
    script = root / "draft.md"
    script.write_text("# script", encoding="utf-8")
    ws.create(pid, script, "vox")
    atomic_write(ws.design_path(pid), json.dumps(design, ensure_ascii=False, indent=2))
    manifest = ws.load_manifest(pid)
    manifest["stages"]["design"] = "completed"
    manifest["design_fingerprint"] = design_fingerprint(design)  # 指纹同步，避免首次调用触发重置
    manifest["stages"]["design-review"] = "completed"  # 测试 fixture 默认已复核；门禁测试单独改回
    ws.write_manifest(pid, manifest)
    return pid


def load_manifest(root: Path, pid: str) -> dict:
    return json.loads((root / "projects" / pid / ".work" / "manifest.json").read_text(encoding="utf-8"))
