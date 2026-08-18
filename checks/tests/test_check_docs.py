"""check_docs 的测试：受管数值扫描 / 规则实现覆盖 / 断链（2026-08-17 第 5 轮）。

防假通过原则：违规样例必须检出；合规样例不得误报。
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_docs import (check_links, check_rule_coverage, scan_managed_values)


class ManagedValuesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.docs = self.tmp / "docs"
        self.docs.mkdir()

    def write(self, name: str, content: str) -> Path:
        p = self.docs / name
        p.write_text(content, encoding="utf-8")
        return p

    def test_leak_detected(self):
        self.write("a.md", "档位是 4/6/8/10 秒，就近吸附分界点 5/7/9。")
        issues = scan_managed_values(self.tmp, ["docs/*.md"], set())
        self.assertTrue(any("档位" in i for i in issues))
        self.assertTrue(any("分界" in i for i in issues))

    def test_old_tail_constant_detected(self):
        self.write("a.md", "落点收尾后写「结尾稳定保持 0.8 秒」。")
        issues = scan_managed_values(self.tmp, ["docs/*.md"], set())
        self.assertTrue(any("0.8 秒" in i for i in issues))

    def test_clean_doc_passes(self):
        self.write("a.md", "落点收尾后按尾部契约选档；档位与差值见校验器。")
        self.assertEqual(scan_managed_values(self.tmp, ["docs/*.md"], set()), [])

    def test_exempt_marker_allows(self):
        # 显式「受管数值豁免」行 = 决策留痕，允许出现
        self.write("a.md", "受管数值豁免：本处记录历史句式「结尾稳定保持 0.8 秒」。")
        self.assertEqual(scan_managed_values(self.tmp, ["docs/*.md"], set()), [])

    def test_subdir_scanned(self):
        # 2026-08-17 第二步：风格资产在 docs/style-assets/ 子目录，必须被扫到
        # （旧 glob docs/*.md 漏扫子目录 = 联动空转，P6 同类）
        sub = self.docs / "style-assets"
        sub.mkdir()
        (sub / "gallery.md").write_text("落点收尾后写「结尾稳定保持 0.8 秒」。", encoding="utf-8")
        issues = scan_managed_values(self.tmp, ["docs/**/*.md"], set())
        self.assertTrue(any("0.8 秒" in i for i in issues))
        # 锁定正典默认扫描范围包含子目录
        from check_docs import MANAGED_DOCS
        self.assertIn("docs/**/*.md", MANAGED_DOCS)

    def test_external_style_roots_scanned(self):
        # 外部风格文档根（voxvideo ref/ + config/styles/）也被扫：guide/master 泄受管数值必须报
        extra = Path(tempfile.mkdtemp())
        (extra / "guide.zh.md").write_text("落点收尾后写「结尾稳定保持 0.8 秒」。", encoding="utf-8")
        issues = scan_managed_values(self.tmp, ["docs/**/*.md"], set(), extra_roots=[str(extra)])
        self.assertTrue(any("guide.zh.md" in i and "0.8 秒" in i for i in issues))
        # 干净的外部根不报
        extra2 = Path(tempfile.mkdtemp())
        (extra2 / "guide.zh.md").write_text("结尾按尾部契约选档。", encoding="utf-8")
        self.assertEqual(
            scan_managed_values(self.tmp, ["docs/**/*.md"], set(), extra_roots=[str(extra2)]), [])


class RuleCoverageTest(unittest.TestCase):
    def test_missing_coverage_file_reported(self):
        issues = check_rule_coverage(Path(tempfile.mkdtemp()) / "nope.json", Path(tempfile.mkdtemp()))
        self.assertTrue(any("rule-coverage" in i for i in issues))

    def test_missing_module_reported(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "coverage.json").write_text(
            json.dumps({"rules": [{"id": "r1", "rule": "x", "source": "no_such_mod.func",
                                   "test": "t", "keyword": "k"}]}, ensure_ascii=False),
            encoding="utf-8")
        issues = check_rule_coverage(tmp / "coverage.json", tmp)
        self.assertTrue(any("no_such_mod" in i for i in issues))

    def test_missing_symbol_reported(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "mod.py").write_text("def other(): pass", encoding="utf-8")
        (tmp / "coverage.json").write_text(
            json.dumps({"rules": [{"id": "r1", "rule": "x", "source": "mod.no_such_sym",
                                   "test": "t", "keyword": "k"}]}, ensure_ascii=False),
            encoding="utf-8")
        issues = check_rule_coverage(tmp / "coverage.json", tmp)
        self.assertTrue(any("no_such_sym" in i for i in issues))

    def test_missing_test_keyword_reported(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "mod.py").write_text("def func(): pass", encoding="utf-8")
        (tmp / "tests").mkdir()
        (tmp / "tests" / "t.py").write_text("def test_x(): pass", encoding="utf-8")
        (tmp / "coverage.json").write_text(
            json.dumps({"rules": [{"id": "r1", "rule": "x", "source": "mod.func",
                                   "test": "t", "keyword": "不存在的关键词"}]}, ensure_ascii=False),
            encoding="utf-8")
        issues = check_rule_coverage(tmp / "coverage.json", tmp)
        self.assertTrue(any("关键词" in i for i in issues))

    def test_real_coverage_passes(self):
        from check_docs import COVERAGE_FILE, CHECKS_DIR
        self.assertEqual(check_rule_coverage(COVERAGE_FILE, CHECKS_DIR), [])


class LinksTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "checks").mkdir()
        (self.tmp / "checks" / "real.py").write_text("x", encoding="utf-8")

    def test_broken_link_detected(self):
        (self.tmp / "a.md").write_text("[不存在](../nope.md)", encoding="utf-8")
        issues = check_links(self.tmp, ["*.md"], set())
        self.assertTrue(any("断链" in i for i in issues))

    def test_missing_code_ref_detected(self):
        (self.tmp / "a.md").write_text("跑 `checks/missing.py`", encoding="utf-8")
        issues = check_links(self.tmp, ["*.md"], set())
        self.assertTrue(any("引用不存在" in i for i in issues))

    def test_existing_refs_pass(self):
        (self.tmp / "a.md").write_text("跑 `checks/real.py`，见 [说明](a.md)", encoding="utf-8")
        self.assertEqual(check_links(self.tmp, ["*.md"], set()), [])

    def test_external_and_glob_skipped(self):
        (self.tmp / "a.md").write_text(
            "见 https://example.com/x 与 `checks/*.py`", encoding="utf-8")
        self.assertEqual(check_links(self.tmp, ["*.md"], set()), [])


if __name__ == "__main__":
    unittest.main()
