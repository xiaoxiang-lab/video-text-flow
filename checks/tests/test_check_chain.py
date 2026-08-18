"""check_chain 的测试：文本链/数字/标题/模板结构各检查项。"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_chain import (chain_01_02, chain_02_03, chain_03_05, check_numbers,
                         check_title_consistency, check_template_structure,
                         extract_03_body, is_subsequence, strip_punct,
                         shot_narrations)

BODY01 = "今天发布了产品。价格是 1 元。销量涨了。"
SHOTS = ["今天发布了产品。", "价格是 1 元。", "销量涨了。"]

# 05 作业单样例：表格行旁白 == 03 正文（23 拆 23a/23b 可拼接还原）
JOB05_GOOD = """# 05-拆镜作业单（样例）

## 拆镜作业单（4 镜 = H + 3，narration 逐字切分定稿）

| 镜 | 时长档 | 旁白（narration） | 参考图 | 动作要点 |
|---|---|---|---|---|
| H | 4s | 钩子句在这里。 | — | 动作 |
| 1 | 4s | 这是正文第一句。 | — | 动作 |
| 2 | 4s | 这是正文第二句，拆了前半。 | — | 动作 |
| 3 | 4s | 这是正文第二句后半。 | — | 动作 |
"""
JOB05_SPLIT = """# 05-拆镜作业单（样例）

## 拆镜作业单（4 镜 = H + 3，narration 逐字切分定稿）

| 镜 | 时长档 | 旁白（narration） | 参考图 | 动作要点 |
|---|---|---|---|---|
| H | 4s | 钩子句在这里。 | — | 动作 |
| 1 | 4s | 这是正文第一句。 | — | 动作 |
| 2 | 4s | 这是正文第二句，拆了前半。 | — | 动作 |
| 3 | 4s | 这段旁白和上面那句完全对不上。 | — | 动作 |
"""


class SubsequenceTest(unittest.TestCase):
    def test_subsequence_ok(self):
        self.assertTrue(is_subsequence("abc", "xaybzc"))
        self.assertFalse(is_subsequence("abc", "abx"))


class ChainTest(unittest.TestCase):
    def test_chain_01_02_ok(self):
        self.assertEqual(chain_01_02(BODY01, SHOTS, ""), [])

    def test_chain_01_02_missing(self):
        self.assertTrue(chain_01_02("今天发布了产品。价格是 1 元。销量涨了。还有一句。",
                                    SHOTS, ""))

    def test_chain_01_02_deleted_ok(self):
        # 删除记录里的句子不参与比对
        sb = "- 「先看背景。」→ 删（过渡）\n"
        body = "先看背景。今天发布了产品。价格是 1 元。销量涨了。"
        self.assertEqual(chain_01_02(body, SHOTS, sb), [])

    def test_chain_02_03_ok(self):
        body03 = "今天发布了产品。价格是 1 元。销量涨了。"
        self.assertEqual(chain_02_03(SHOTS, body03), [])

    def test_chain_02_03_mismatch(self):
        self.assertTrue(chain_02_03(SHOTS, "完全不同的内容。"))


class Chain03_05Test(unittest.TestCase):
    BODY03 = "这是正文第一句。这是正文第二句，拆了前半。这是正文第二句后半。"

    def test_chain_03_05_ok(self):
        self.assertEqual(chain_03_05(self.BODY03, JOB05_GOOD, hook03="钩子句在这里。"), [])

    def test_chain_03_05_mismatch(self):
        issues = chain_03_05(self.BODY03, JOB05_SPLIT, hook03="钩子句在这里。")
        self.assertTrue(issues)
        self.assertTrue(any("03→05" in i for i in issues))

    def test_chain_03_05_hook_mismatch(self):
        issues = chain_03_05(self.BODY03, JOB05_GOOD, hook03="完全不同的钩子。")
        self.assertTrue(any("H 行" in i for i in issues))

    def test_chain_03_05_empty_jobcard(self):
        self.assertTrue(chain_03_05(self.BODY03, "## 没有表格", hook03="钩子句在这里。"))


class NumbersTest(unittest.TestCase):
    def test_missing_detected(self):
        texts = {"01": "今天发布了产品。", "02": "今天发布了产品。", "03": "今天发布了产品。"}
        issues = check_numbers("价格 150.80 元，销量 2.78 亿。", texts)
        self.assertEqual(len(issues), 6)  # 3 文件 × 2 数字

    def test_all_present(self):
        texts = {"01": "价格 150.80 元，销量 2.78 亿。", "02": "价格 150.80 元。销量 2.78 亿。",
                 "03": "价格 150.80 元，销量 2.78 亿。"}
        self.assertEqual(check_numbers("价格 150.80 元，销量 2.78 亿。", texts), [])


class TitleTest(unittest.TestCase):
    def test_title_missing_in_04(self):
        issues = check_title_consistency("- **标题**：我的标题（强调词：x）", "别的文件")
        self.assertTrue(issues)

    def test_title_present(self):
        self.assertEqual(check_title_consistency("- **标题**：我的标题（强调词：x）",
                                                 "这里有我的标题，也有排版"), [])


class TemplateTest(unittest.TestCase):
    def test_template_rewritten_detected(self):
        bad = "【核心创作任务】随便写点别的。\n【固定视觉语言】"
        self.assertTrue(check_template_structure(bad))

    def test_template_intact(self):
        from check_chain import TEMPLATE_CORE_TASK
        good = f"【核心创作任务】\n{TEMPLATE_CORE_TASK}\n【固定视觉语言】"
        self.assertEqual(check_template_structure(good), [])


class Extract03Test(unittest.TestCase):
    def test_extract_body_after_marker(self):
        text = "**hook：**\n> 钩子句。\n\n**正文：**\n\n这是正文内容。\n\n---\n## 五件套"
        self.assertEqual(extract_03_body(text), "这是正文内容。")


if __name__ == "__main__":
    unittest.main()
