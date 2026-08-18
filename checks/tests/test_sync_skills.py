"""sync_skills 的测试：新增/更新/删除/cover 检测。"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sync_skills import compare, file_sha256, iter_skill_dirs, src_of


def make_skill(root: Path, name: str, content: str = "# x") -> None:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(content, encoding="utf-8")


class CompareTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.src = self.tmp / "src"
        self.dst = self.tmp / "dst"
        self.src.mkdir()
        self.dst.mkdir()

    def test_add_detected(self):
        make_skill(self.src, "new-skill")
        changes = compare(self.src, self.dst, ["new-skill"])
        self.assertEqual(changes.get("new-skill"), "add")

    def test_not_in_whitelist_ignored(self):
        make_skill(self.src, "unrelated")
        changes = compare(self.src, self.dst, ["only-this"])
        self.assertNotIn("unrelated", changes)

    def test_update_detected(self):
        make_skill(self.src, "a", "v1")
        make_skill(self.dst, "a", "v2")
        changes = compare(self.src, self.dst, ["a"])
        self.assertEqual(changes.get("a"), "update")

    def test_remove_detected(self):
        make_skill(self.src, "gone")
        make_skill(self.dst, "gone")
        make_skill(self.dst, "only-dst")
        changes = compare(self.src, self.dst, ["gone"])
        self.assertEqual(changes.get("only-dst"), "remove")

    def test_whitelisted_extra_in_dst_kept(self):
        make_skill(self.src, "a")
        make_skill(self.dst, "a")
        make_skill(self.dst, "b")
        changes = compare(self.src, self.dst, ["a", "b"])
        self.assertNotEqual(changes.get("b"), "remove")  # 白名单内的项目存在 → 保持不删

    def test_same(self):
        make_skill(self.src, "a", "v1")
        make_skill(self.dst, "a", "v1")
        changes = compare(self.src, self.dst, ["a"])
        self.assertEqual(changes.get("a"), "same")

    def test_non_skill_dir_ignored(self):
        (self.src / "command").mkdir()
        (self.src / "README.md").write_text("x", encoding="utf-8")
        self.assertEqual(iter_skill_dirs(self.src), [])

    def test_extra_file_change_detected(self):
        """目录级比较：非 SKILL.md 附属文件（LESSONS.md 等）变更也要报 update（旧待办修复）。"""
        make_skill(self.src, "a", "v1")
        make_skill(self.dst, "a", "v1")
        (self.src / "a" / "LESSONS.md").write_text("l1", encoding="utf-8")
        (self.dst / "a" / "LESSONS.md").write_text("l2", encoding="utf-8")
        changes = compare(self.src, self.dst, ["a"])
        self.assertEqual(changes.get("a"), "update")

    def test_extra_file_added_in_dst_ignored(self):
        """目录级比较：同一文件两边都没有 → same；只在目标多文件 → update。"""
        make_skill(self.src, "a", "v1")
        make_skill(self.dst, "a", "v1")
        (self.src / "a" / "LESSONS.md").write_text("l1", encoding="utf-8")
        changes = compare(self.src, self.dst, ["a"])
        self.assertEqual(changes.get("a"), "update")

    def test_same_with_full_dir(self):
        """目录级比较：多文件全部一致 → same。"""
        make_skill(self.src, "a", "v1")
        make_skill(self.dst, "a", "v1")
        for d in ("a", "b"):
            (self.src / "a" / f"{d}.md").write_text(d, encoding="utf-8")
            (self.dst / "a" / f"{d}.md").write_text(d, encoding="utf-8")
        changes = compare(self.src, self.dst, ["a"])
        self.assertEqual(changes.get("a"), "same")


class ExtraSourceTest(unittest.TestCase):
    """vendoring：EXTRA_SOURCES 目录不需要 SKILL.md（非 skill 结构副本）。"""

    def test_extra_source_without_skill_detected(self):
        tmp = Path(tempfile.mkdtemp())
        src = tmp / "src"
        dst = tmp / "dst"
        src.mkdir()
        dst.mkdir()
        (src / "vendor-x").mkdir()
        (src / "vendor-x" / "notes.md").write_text("n", encoding="utf-8")
        import sync_skills as ss
        old = ss.EXTRA_SOURCES
        try:
            ss.EXTRA_SOURCES = {"vendor-x": src / "vendor-x"}
            self.assertEqual(src_of("vendor-x", src), src / "vendor-x")
        finally:
            ss.EXTRA_SOURCES = old

    def test_src_of_prefers_global_skill(self):
        tmp = Path(tempfile.mkdtemp())
        src = tmp / "src"
        src.mkdir()
        make_skill(src, "a", "global")
        self.assertEqual(src_of("a", src), src / "a")


if __name__ == "__main__":
    unittest.main()
