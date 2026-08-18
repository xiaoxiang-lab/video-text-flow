import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voxvideo.adapter import AdapterError
from voxvideo.handoff import HandoffError
from voxvideo.media import MediaError
from voxvideo.narration import NarrationError
from voxvideo.pipeline import Pipeline, PipelineError
from voxvideo.qa import QaError
from voxvideo.state import ProjectWorkspace, atomic_write

from .fakes import FakeAdapter, FakeNarrator, design_fixture, load_manifest, make_config, make_project


def make_pipeline(root: Path) -> Pipeline:
    return Pipeline(ProjectWorkspace(root / "projects"), make_config(), root)


class NarrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.pid = make_project(self.tmp, design_fixture())
        self.pipe = make_pipeline(self.tmp)

    def _synthesize(self, fake=None, probe=None):
        with patch("voxvideo.media.require_audio_tools"):
            return self.pipe.synthesize_narration(
                self.pid, narrator=fake or FakeNarrator(),
                patch_probe=probe or (lambda p: {"duration": 6.25, "has_audio": True}),
                patch_concat=lambda takes, dest: dest.write_bytes(b"RIFF-concat"),
            )

    def test_synth_writes_takes_and_updates_durations(self):
        result = self._synthesize()
        self.assertEqual(result["status"], "completed")
        wav = self.tmp / "projects" / self.pid / "02-audio" / "narration.wav"
        self.assertTrue(wav.exists())
        design = json.loads((self.tmp / "projects" / self.pid / ".work" / "design.json").read_text(encoding="utf-8"))
        self.assertTrue(all(s["duration_seconds"] == 6.25 for s in design["shots"]))
        manifest = load_manifest(self.tmp, self.pid)
        self.assertEqual(manifest["stages"]["narration"], "completed")
        self.assertNotIn("api_key", manifest["narration"])

    def test_manifest_never_contains_key(self):
        self._synthesize()
        raw = (self.tmp / "projects" / self.pid / ".work" / "manifest.json").read_text(encoding="utf-8")
        self.assertNotIn("FISH_API_KEY", raw)
        self.assertNotIn("secret", raw)

    def test_idempotent_rerun(self):
        fake = FakeNarrator()
        self._synthesize(fake)
        self.assertEqual(len(fake.calls), 4)
        self._synthesize(fake)
        self.assertEqual(len(fake.calls), 4)

    def test_voice_change_retriggers(self):
        fake = FakeNarrator()
        self._synthesize(fake)
        fake2 = FakeNarrator(voice_id="v-999")
        self._synthesize(fake2)
        manifest = load_manifest(self.tmp, self.pid)
        self.assertEqual(manifest["narration"]["voice_id"], "v-999")

    def test_missing_ffmpeg_blocks_only_narration(self):
        with patch("voxvideo.media.require_audio_tools", side_effect=MediaError("配音需要 ffmpeg/ffprobe")):
            with self.assertRaises(MediaError) as ctx:
                self.pipe.synthesize_narration(self.pid, narrator=FakeNarrator())
        self.assertIn("ffmpeg", str(ctx.exception))

    def test_missing_credentials_error_has_way_out(self):
        with patch("voxvideo.media.require_audio_tools"):
            with self.assertRaises(NarrationError) as ctx:
                self.pipe.synthesize_narration(self.pid, narrator=None)
        self.assertIn(".env", str(ctx.exception))


class DesignReviewGateTest(unittest.TestCase):
    """design 未复核时 generate-images 必须拒绝；复核通过后放行。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.pid = make_project(self.tmp, design_fixture(image_shots=(1, 3)))
        self.pipe = make_pipeline(self.tmp)
        manifest = load_manifest(self.tmp, self.pid)
        manifest["stages"]["design-review"] = "pending"
        atomic_write(self.tmp / "projects" / self.pid / ".work" / "manifest.json",
                     json.dumps(manifest, ensure_ascii=False, indent=2))

    def test_generate_images_refused_before_review(self):
        with self.assertRaises(PipelineError):
            self.pipe.generate_images(self.pid, adapter=FakeAdapter())

    def test_review_design_then_generate_ok(self):
        result = self.pipe.review_design(self.pid)
        self.assertEqual(result["design_review"], "completed")
        fake = FakeAdapter()
        self.pipe.generate_images(self.pid, adapter=fake)
        self.assertIn(("text2image", "MASTER PROMPT 风格表"), fake.calls)

    def test_design_change_invalidates_review(self):
        self.pipe.review_design(self.pid)
        design = design_fixture(image_shots=(1, 3))
        design["shots"][0]["narration"] = "改了旁白"
        atomic_write(self.tmp / "projects" / self.pid / ".work" / "design.json",
                     json.dumps(design, ensure_ascii=False, indent=2))
        self.pipe._require_design(self.pid)  # 指纹变化触发下游重置
        manifest = load_manifest(self.tmp, self.pid)
        self.assertEqual(manifest["stages"]["design-review"], "pending")
        with self.assertRaises(PipelineError):
            self.pipe.generate_images(self.pid, adapter=FakeAdapter())


class GenerateImagesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.pid = make_project(self.tmp, design_fixture(image_shots=(1, 3)))
        self.pipe = make_pipeline(self.tmp)

    def test_only_submits_image_shots_plus_master(self):
        fake = FakeAdapter()
        self.pipe.generate_images(self.pid, adapter=fake)
        self.assertEqual(len(fake.calls), 3)
        self.assertEqual(fake.calls[0][0], "text2image")
        self.assertEqual(fake.calls[1][0], "image2image")
        master = self.tmp / "projects" / self.pid / "03-images" / "master.png"
        self.assertTrue(master.exists())
        ref1 = self.tmp / "projects" / self.pid / "03-images" / "references" / "shot-001.png"
        self.assertTrue(ref1.exists())
        manifest = load_manifest(self.tmp, self.pid)
        self.assertEqual(manifest["stages"]["images"], "completed")
        self.assertEqual(manifest["stages"]["image-review"], "needs-review")
        self.assertEqual(manifest["shots"]["shot-001"]["status"], "downloaded")

    def test_idempotent_no_resubmit(self):
        fake = FakeAdapter()
        self.pipe.generate_images(self.pid, adapter=fake)
        first = len(fake.calls)
        self.pipe.generate_images(self.pid, adapter=fake)
        self.assertEqual(len(fake.calls), first)

    def test_deleted_file_regenerates(self):
        fake = FakeAdapter()
        self.pipe.generate_images(self.pid, adapter=fake)
        ref = self.tmp / "projects" / self.pid / "03-images" / "references" / "shot-001.png"
        ref.unlink()
        self.pipe.generate_images(self.pid, adapter=fake)
        self.assertEqual(len(fake.calls), 4)
        self.assertTrue(ref.exists())

    def test_timeout_keeps_submit_id_and_rerun_recovers(self):
        fake = FakeAdapter(timeout_waits={"sid-1"})
        with self.assertRaises(AdapterError):
            self.pipe.generate_images(self.pid, adapter=fake)
        manifest = load_manifest(self.tmp, self.pid)
        self.assertIn("master", manifest["image_failures"])
        self.assertEqual(manifest["master"]["status"], "submitted")
        self.assertEqual(manifest["master"]["submit_id"], "sid-1")

        fake.timeout_waits = set()
        self.pipe.generate_images(self.pid, adapter=fake)
        manifest = load_manifest(self.tmp, self.pid)
        self.assertEqual(manifest["master"]["status"], "downloaded")
        self.assertNotIn("submit_id", manifest["master"])
        self.assertEqual(manifest["stages"]["images"], "completed")

    def test_failure_isolated_per_shot(self):
        fake = FakeAdapter(fail_waits={2})
        with self.assertRaises(AdapterError):
            self.pipe.generate_images(self.pid, adapter=fake)
        manifest = load_manifest(self.tmp, self.pid)
        self.assertIn("shot-001", manifest["image_failures"])
        self.assertEqual(manifest["shots"]["shot-001"]["status"], "failed")
        self.assertEqual(manifest["shots"]["shot-003"]["status"], "downloaded")
        self.assertNotIn("submit_id", manifest["shots"]["shot-001"])

    def test_shot_id_without_image_errors(self):
        fake = FakeAdapter()
        with self.assertRaises(PipelineError) as ctx:
            self.pipe.generate_images(self.pid, adapter=fake, shot_ids=["shot-002"])
        self.assertIn("没有 image_prompt", str(ctx.exception))
        self.assertEqual(len(fake.calls), 0)

    def test_shot_id_partial_generation(self):
        fake = FakeAdapter()
        self.pipe.generate_images(self.pid, adapter=fake, shot_ids=["shot-003"])
        ref3 = self.tmp / "projects" / self.pid / "03-images" / "references" / "shot-003.png"
        ref1 = self.tmp / "projects" / self.pid / "03-images" / "references" / "shot-001.png"
        self.assertTrue(ref3.exists())
        self.assertFalse(ref1.exists())
        self.assertEqual(len(fake.calls), 2)


class NoImageProjectTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.pid = make_project(self.tmp, design_fixture())
        self.pipe = make_pipeline(self.tmp)

    def test_no_image_project_runs_through_without_tool(self):
        fake = FakeAdapter(available=False)
        result = self.pipe.generate_images(self.pid, adapter=fake)
        self.assertEqual(result["images_needed"], 0)
        self.assertEqual(len(fake.calls), 0)
        self.pipe.approve_images(self.pid)
        exported = self.pipe.export_handoff(self.pid)
        self.assertTrue(Path(exported["handoff"]).exists())

    def test_handoff_renders_no_upload_note(self):
        fake = FakeAdapter(available=False)
        self.pipe.generate_images(self.pid, adapter=fake)
        self.pipe.approve_images(self.pid)
        exported = self.pipe.export_handoff(self.pid)
        content = Path(exported["handoff"]).read_text(encoding="utf-8")
        self.assertIn("本镜不上传参考图", content)
        self.assertIn("提示词1", content)
        self.assertNotIn("母板：尚未生成", content)

    def test_master_not_generated_without_images(self):
        fake = FakeAdapter(available=False)
        self.pipe.generate_images(self.pid, adapter=fake)
        master = self.tmp / "projects" / self.pid / "03-images" / "master.png"
        self.assertFalse(master.exists())
        manifest = load_manifest(self.tmp, self.pid)
        self.assertEqual(manifest["stages"]["images"], "completed")
        self.assertEqual(manifest["stages"]["image-review"], "completed")


class ToolUnavailableTest(unittest.TestCase):
    def test_errors_with_way_out(self):
        tmp = Path(tempfile.mkdtemp())
        pid = make_project(tmp, design_fixture(image_shots=(1,)))
        pipe = make_pipeline(tmp)
        fake = FakeAdapter(available=False)
        with self.assertRaises(AdapterError) as ctx:
            pipe.generate_images(pid, adapter=fake)
        msg = str(ctx.exception)
        self.assertIn("IMAGE_ADAPTER=kling", msg)
        self.assertIn("image_prompt 从 design.json 全部去掉", msg)
        self.assertEqual(len(fake.calls), 0)


class ApprovalGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.pid = make_project(self.tmp, design_fixture(image_shots=(1,)))
        self.pipe = make_pipeline(self.tmp)
        self.pipe.generate_images(self.pid, adapter=FakeAdapter())

    def test_export_refused_before_approval(self):
        with self.assertRaises(HandoffError) as ctx:
            self.pipe.export_handoff(self.pid)
        self.assertIn("未审核", str(ctx.exception))

    def test_approve_then_export(self):
        self.pipe.approve_images(self.pid)
        self.pipe.export_handoff(self.pid)
        manifest = load_manifest(self.tmp, self.pid)
        self.assertEqual(manifest["stages"]["image-review"], "completed")
        self.assertEqual(manifest["master"]["status"], "approved")

    def test_approve_rejects_corrupted_file(self):
        ref = self.tmp / "projects" / self.pid / "03-images" / "references" / "shot-001.png"
        ref.write_bytes(b"garbage data not an image")
        with self.assertRaises(QaError):
            self.pipe.approve_images(self.pid)
        manifest = load_manifest(self.tmp, self.pid)
        self.assertEqual(manifest["stages"]["image-review"], "needs-review")

    def test_retry_image_requires_reapproval(self):
        self.pipe.approve_images(self.pid)
        prompt = self.tmp / "new-prompt.txt"
        prompt.write_text("新提示词", encoding="utf-8")
        self.pipe.retry_image(self.pid, "shot-001", prompt, adapter=FakeAdapter())
        manifest = load_manifest(self.tmp, self.pid)
        self.assertEqual(manifest["stages"]["image-review"], "pending")
        self.assertEqual(manifest["stages"]["handoff-export"], "pending")

    def test_retry_image_without_prompt_errors(self):
        with self.assertRaises(PipelineError) as ctx:
            self.pipe.retry_image(self.pid, "shot-002", self.tmp / "x.txt", adapter=FakeAdapter())
        self.assertIn("没有 image_prompt", str(ctx.exception))


class StatusTest(unittest.TestCase):
    def test_image_count_denominator(self):
        tmp = Path(tempfile.mkdtemp())
        pid = make_project(tmp, design_fixture(image_shots=(1, 3)))
        pipe = make_pipeline(tmp)
        status = pipe.status(pid)
        self.assertEqual(status["image_counts"], {"total_with_images": 2, "approved": 0})
        pipe.generate_images(pid, adapter=FakeAdapter())
        pipe.approve_images(pid)
        status = pipe.status(pid)
        self.assertEqual(status["image_counts"], {"total_with_images": 2, "approved": 2})


class ResumeTest(unittest.TestCase):
    def test_resume_stops_when_images_unreviewed(self):
        tmp = Path(tempfile.mkdtemp())
        pid = make_project(tmp, design_fixture(image_shots=(1,)))
        pipe = make_pipeline(tmp)
        pipe.generate_images(pid, adapter=FakeAdapter())
        result = pipe.resume(pid)
        self.assertTrue(result["stopped"])
        self.assertFalse(pipe.ws.handoff_path(pid).exists())

    def test_resume_exports_when_all_approved(self):
        tmp = Path(tempfile.mkdtemp())
        pid = make_project(tmp, design_fixture(image_shots=(1,)))
        pipe = make_pipeline(tmp)
        pipe.generate_images(pid, adapter=FakeAdapter())
        pipe.approve_images(pid)
        result = pipe.resume(pid)
        self.assertFalse(result["stopped"])
        self.assertTrue(pipe.ws.handoff_path(pid).exists())


class DesignChangeTest(unittest.TestCase):
    def test_design_change_resets_downstream(self):
        tmp = Path(tempfile.mkdtemp())
        pid = make_project(tmp, design_fixture(image_shots=(1,)))
        pipe = make_pipeline(tmp)
        pipe.generate_images(pid, adapter=FakeAdapter())
        pipe.approve_images(pid)
        pipe.export_handoff(pid)
        design_path = pipe.ws.design_path(pid)
        design = json.loads(design_path.read_text(encoding="utf-8"))
        design["shots"][0]["video_prompt"] = "改成这样"
        atomic_write(design_path, json.dumps(design, ensure_ascii=False, indent=2))
        pipe.status(pid)
        manifest = load_manifest(tmp, pid)
        self.assertEqual(manifest["stages"]["handoff-export"], "pending")
        self.assertTrue(manifest["handoff_stale"])
        self.assertFalse(manifest["stages"]["image-review"] == "completed")


if __name__ == "__main__":
    unittest.main()
