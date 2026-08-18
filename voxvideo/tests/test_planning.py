import json
import tempfile
import unittest
from pathlib import Path

from voxvideo.planning import DesignError, design_fingerprint, make_plan, require_design

from .fakes import design_fixture


class DesignValidationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.path = self.tmp / "design.json"

    def _write(self, design):
        self.path.write_text(json.dumps(design, ensure_ascii=False), encoding="utf-8")

    def test_valid_design(self):
        self._write(design_fixture())
        require_design(self.path)

    def test_missing_narration(self):
        d = design_fixture()
        del d["shots"][0]["narration"]
        self._write(d)
        with self.assertRaises(DesignError) as ctx:
            require_design(self.path)
        self.assertIn("narration", str(ctx.exception))

    def test_empty_video_prompt(self):
        d = design_fixture()
        d["shots"][1]["video_prompt"] = "   "
        self._write(d)
        with self.assertRaises(DesignError) as ctx:
            require_design(self.path)
        self.assertIn("video_prompt", str(ctx.exception))

    def test_image_prompt_missing_is_ok(self):
        d = design_fixture()
        for s in d["shots"]:
            self.assertNotIn("image_prompt", s)
        self._write(d)
        require_design(self.path)

    def test_image_prompt_empty_string_rejected(self):
        d = design_fixture()
        d["shots"][0]["image_prompt"] = ""
        self._write(d)
        with self.assertRaises(DesignError) as ctx:
            require_design(self.path)
        self.assertIn("要么给内容，要么删掉这个字段", str(ctx.exception))

    def test_design_fingerprint_changes(self):
        a = design_fixture()
        b = design_fixture()
        b["shots"][0]["video_prompt"] = "改"
        self.assertNotEqual(design_fingerprint(a), design_fingerprint(b))


class MakePlanTest(unittest.TestCase):
    def test_plan_ids_and_default_duration(self):
        plan = make_plan(design_fixture(), default_seconds=4.0)
        self.assertEqual([s["id"] for s in plan], ["shot-001", "shot-002", "shot-003", "shot-004"])
        self.assertTrue(all(s["duration_seconds"] == 4.0 for s in plan))

    def test_real_duration_preferred(self):
        plan = make_plan(design_fixture(), default_seconds=4.0,
                         durations={"shot-001": 7.5, "shot-002": 3.25})
        self.assertEqual(plan[0]["duration_seconds"], 7.5)
        self.assertEqual(plan[1]["duration_seconds"], 3.25)
        self.assertEqual(plan[2]["duration_seconds"], 4.0)

    def test_image_structure_only_when_prompt_written(self):
        plan = make_plan(design_fixture(image_shots=(1, 3)), default_seconds=4.0)
        with_image = {s["id"] for s in plan if "image" in s}
        self.assertEqual(with_image, {"shot-001", "shot-003"})
        self.assertEqual(plan[0]["image"]["prompt"], "参考图提示词1")
        self.assertNotIn("image", plan[1])


if __name__ == "__main__":
    unittest.main()
