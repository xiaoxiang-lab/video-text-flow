import json
import tempfile
import unittest
from pathlib import Path

from voxvideo.state import (ProjectWorkspace, WorkspaceError, atomic_write,
                            file_hash, stable_hash)

from .fakes import make_project, write_style_fixture


class StateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.ws = ProjectWorkspace(self.tmp / "projects")
        self.ws.projects_dir.mkdir(parents=True, exist_ok=True)

    def test_new_id_generation(self):
        self.assertEqual(self.ws.new_id("why-power", "20260728"), "20260728-why-power")

    def test_new_id_collision_suffix(self):
        first = self.ws.new_id("topic-a", "20260728")
        (self.ws.projects_dir / first).mkdir()
        self.assertEqual(self.ws.new_id("topic-a", "20260728"), "20260728-topic-a-02")
        (self.ws.projects_dir / "20260728-topic-a-02").mkdir()
        self.assertEqual(self.ws.new_id("topic-a", "20260728"), "20260728-topic-a-03")

    def test_kebab_validation(self):
        for bad in ("Topic", "topic_A", "topic a", "主题", "-topic", "topic-"):
            with self.subTest(bad=bad):
                with self.assertRaises(WorkspaceError):
                    self.ws.new_id(bad, "20260728")

    def test_atomic_write_roundtrip(self):
        target = self.tmp / "sub" / "a.json"
        atomic_write(target, json.dumps({"a": 1}))
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"a": 1})

    def test_stable_hash_sort_keys(self):
        self.assertEqual(stable_hash({"b": 1, "a": 2}), stable_hash({"a": 2, "b": 1}))
        self.assertNotEqual(stable_hash({"a": 1}), stable_hash({"a": 2}))

    def test_create_manifest_and_skeleton(self):
        pid = "20260728-topic"
        script = self.tmp / "draft.md"
        script.write_text("# s", encoding="utf-8")
        self.ws.create(pid, script, "vox")
        root = self.ws.root(pid)
        for sub in ("01-script", "02-audio", "03-images/references", "04-prompts",
                    "05-video", ".work/raw-images", ".work/audio-takes"):
            self.assertTrue((root / sub).is_dir())
        self.assertEqual((root / "01-script" / "script.md").read_text(encoding="utf-8"), "# s")
        manifest = self.ws.load_manifest(pid)
        self.assertEqual(manifest["stages"]["design"], "pending")
        self.assertEqual(manifest["style"], "vox")
        self.assertTrue((root / "PROJECT.md").exists())


class HashTest(unittest.TestCase):
    def test_file_hash(self):
        import hashlib
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "f.bin"
            p.write_bytes(b"hello")
            self.assertEqual(file_hash(p), hashlib.sha256(b"hello").hexdigest())
            p.write_bytes(b"hello2")
            self.assertNotEqual(file_hash(p), hashlib.sha256(b"hello").hexdigest())


class StyleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        write_style_fixture(self.tmp)
        self.profiles = self.tmp / "config" / "styles"

    def test_load_style_ok(self):
        from voxvideo.style import load_style
        style = load_style(self.profiles / "vox.json")
        self.assertEqual(style["id"], "vox")

    def test_missing_field(self):
        from voxvideo.style import StyleError, load_style
        p = self.profiles / "broken.json"
        p.write_text(json.dumps({"id": "broken", "name": "x"}), encoding="utf-8")
        with self.assertRaises(StyleError) as ctx:
            load_style(p)
        self.assertIn("guide_files", str(ctx.exception))

    def test_id_mismatch(self):
        from voxvideo.style import StyleError, load_style
        p = self.profiles / "mismatch.json"
        p.write_text(json.dumps({"id": "other", "name": "x", "status": "stable",
                                 "master_prompt_file": "m.txt", "guide_files": []}),
                     encoding="utf-8")
        with self.assertRaises(StyleError) as ctx:
            load_style(p)
        self.assertIn("文件名一致", str(ctx.exception))

    def test_unknown_style_lists_available(self):
        from voxvideo.style import StyleError, get_style
        with self.assertRaises(StyleError) as ctx:
            get_style(self.profiles, "nope")
        self.assertIn("vox", str(ctx.exception))

    def test_guide_files_exist_in_repo(self):
        from voxvideo.style import load_style
        from voxvideo.cli import ROOT
        style = load_style(ROOT / "config" / "styles" / "vox.json")
        for rel in style["guide_files"]:
            self.assertTrue((ROOT / rel).exists(), rel)
        self.assertTrue((ROOT / style["master_prompt_file"]).exists())


if __name__ == "__main__":
    unittest.main()
