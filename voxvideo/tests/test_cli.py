import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import voxvideo.cli as cli

from .fakes import write_style_fixture
from voxvideo.state import today_shanghai


def make_repo(tmp: Path) -> dict:
    write_style_fixture(tmp)
    guide = tmp / ".claude" / "skills" / "vox-prompts" / "SKILL.md"
    guide.parent.mkdir(parents=True, exist_ok=True)
    guide.write_text("# vox-prompts\n", encoding="utf-8")
    config = {
        "jimeng": {"binary": "dreamina", "session": 0, "model": "5.0", "resolution": "2k",
                   "poll_seconds": 30, "timeout_seconds": 1800},
        "style": {"default": "vox", "profiles_dir": "config/styles"},
        "workflow": {"default_shot_seconds": 4},
        "narration": {"provider": "fish-audio", "endpoint": "https://api.fish.audio/v1/tts",
                      "api_key_env": "FISH_API_KEY", "voice_env": "FISH_VOICE_ID",
                      "model_env": "FISH_MODEL", "default_model": "s2-pro",
                      "format": "wav", "speed": 1.0, "timeout_seconds": 180},
    }
    (tmp / "config" / "default.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    return config


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.config = make_repo(self.tmp)
        patchers = [
            patch.object(cli, "ROOT", self.tmp),
            patch.object(cli, "CONFIG_PATH", self.tmp / "config" / "default.json"),
        ]
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    def _run(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_styles_lists_vox(self):
        code, out, _ = self._run(["styles"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["styles"][0]["id"], "vox")

    def test_init_creates_project(self):
        script = self.tmp / "draft.md"
        script.write_text("# 脚本", encoding="utf-8")
        code, out, _ = self._run(["init", "--topic", "my-topic", "--script-file", str(script)])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["project_id"], f"{today_shanghai()}-my-topic")
        self.assertTrue((self.tmp / "projects" / data["project_id"] / "PROJECT.md").exists())
        for f in data["style_guide_files"]:
            self.assertTrue(Path(f).exists())

    def test_init_missing_script_fails_with_code_1(self):
        code, _, err = self._run(["init", "--topic", "my-topic", "--script-file", str(self.tmp / "nope.md")])
        self.assertEqual(code, 1)
        self.assertIn("脚本文件不存在", err)

    def test_init_bad_topic_fails(self):
        script = self.tmp / "draft.md"
        script.write_text("# 脚本", encoding="utf-8")
        code, _, err = self._run(["init", "--topic", "Bad Topic", "--script-file", str(script)])
        self.assertEqual(code, 1)
        self.assertIn("kebab-case", err)

    def test_status_unknown_project(self):
        code, _, err = self._run(["status", "--project", "20260101-nope"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
