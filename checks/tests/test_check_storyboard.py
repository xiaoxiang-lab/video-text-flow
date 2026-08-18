"""check_storyboard 的测试：违规样例必须被检出，合规样例不得误报。"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_storyboard import (parse_shots, check_counts, check_lengths,
                              check_clause_starts, check_labels, check_question_runs)


class ParseTest(unittest.TestCase):
    def test_parse_shots(self):
        text = """# 分镜稿（46 镜）

1. 【01 第1句】DeepSeek Harness 发布之后，评论区吵翻了。
2. 【拆自 01 第2句前半】有人说它是国产版 Claude Code。
18a. 【拆自 01 第18句前半】模型可以换。
"""
        shots = parse_shots(text)
        self.assertEqual(len(shots), 3)
        self.assertEqual(shots[0]["chars"], 29)  # 全字符（含字母/空格/标点），朗读时长口径
        self.assertEqual(shots[2]["no"], 3)


class CountTest(unittest.TestCase):
    def test_count_mismatch(self):
        text = "# 分镜稿（47 镜）\n\n1. 【第1句】甲。\n2. 【第2句】乙。\n"
        shots = parse_shots(text)
        issues = check_counts(text, shots)
        self.assertTrue(any(i["type"] == "镜数不符" for i in issues))

    def test_count_match(self):
        text = "# 分镜稿（2 镜）\n\n1. 【第1句】甲。\n2. 【第2句】乙。\n"
        shots = parse_shots(text)
        self.assertEqual(check_counts(text, shots), [])


class LengthTest(unittest.TestCase):
    def test_short_clause_detected(self):
        shots = [{"no": 1, "chars": 8, "narration": "而是它的框架。"}]
        issues = check_lengths(shots)
        self.assertTrue(any(i["type"] == "超短残句<12字" for i in issues))

    def test_long_shot_detected(self):
        shots = [{"no": 1, "chars": 65, "narration": "长" * 65}]
        issues = check_lengths(shots)
        self.assertTrue(any(i["type"] == "超时镜>60字" for i in issues))

    def test_allowlist_short_ok(self):
        shots = [{"no": 1, "chars": 2, "narration": "便宜。"}]
        issues = check_lengths(shots)
        self.assertEqual([i for i in issues if i["type"] == "超短残句<12字"], [])

    def test_45_to_60_chars_warns_split(self):
        # 45-60 字：Flow 档位不足提示（拆句预警，不硬拦）
        shots = [{"no": 1, "chars": 48, "narration": "长" * 48}]
        issues = check_lengths(shots)
        self.assertTrue(any(i["type"] == "建议拆句>45字" for i in issues))
        self.assertTrue(all(i.get("severity") == "warning"
                            for i in issues if i["type"] == "建议拆句>45字"))

    def test_under_45_no_warning(self):
        shots = [{"no": 1, "chars": 44, "narration": "长" * 44}]
        issues = check_lengths(shots)
        self.assertEqual([i for i in issues if i["type"] == "建议拆句>45字"], [])


class ZeroShotTest(unittest.TestCase):
    def test_zero_shots_is_error(self):
        from check_storyboard import run
        # 段落文本（如 03 定稿）没有镜行格式——解析 0 镜必须报错，防假通过
        text = "# 03-配音定稿\n\n**正文：**\n\n这是第一句。这是第二句。"
        report = run(text)
        self.assertFalse(report["pass"])
        self.assertTrue(any(i["type"] == "镜数" for i in report["issues"]))

    def test_zero_shots_claimed_zero_allowed(self):
        # 无自称镜数且无表格 = 该文件不该用本校验器（run_all 不再把 03 送进来）
        from check_storyboard import run
        report = run("# 随便一个文档\n\n没有镜行。")
        self.assertFalse(report["pass"])


class ClauseStartTest(unittest.TestCase):
    def test_condition_clause_detected(self):
        shots = [{"no": 1, "narration": "如果它真的把模型全部开放给开发者。"}]
        issues = check_clause_starts(shots)
        self.assertTrue(any(i["type"] == "条件从句独立成镜" for i in issues))

    def test_full_conditional_ok(self):
        shots = [{"no": 1, "narration": "如果它上市后表现强势，资本市场会重新给整个产业链定价。"}]
        self.assertEqual(check_clause_starts(shots), [])

    def test_dangran_not_matched(self):
        shots = [{"no": 1, "narration": "当然，说它纯是泡沫，也不公平。"}]
        self.assertEqual(check_clause_starts(shots), [])

    def test_normal_ok(self):
        shots = [{"no": 1, "narration": "DeepSeek 开放了全部能力。"}]
        self.assertEqual(check_clause_starts(shots), [])


class LabelTest(unittest.TestCase):
    def test_bad_label_warns(self):
        shots = [{"no": 1, "label": "随便写的", "narration": "文本。"}]
        issues = check_labels(shots)
        self.assertTrue(any(i["type"] == "来源标注格式异常" for i in issues))

    def test_good_label_ok(self):
        shots = [{"no": 1, "label": "拆自 01 第2句前半", "narration": "文本。"}]
        self.assertEqual(check_labels(shots), [])


class QuestionRunTest(unittest.TestCase):
    def test_three_questions_warns(self):
        shots = [{"no": i, "narration": "为什么？" if i % 2 else "为什么？"} for i in range(1, 4)]
        issues = check_question_runs(shots)
        self.assertTrue(any(i["type"] == "设问镜连续≥3" for i in issues))

    def test_two_questions_ok(self):
        shots = [{"no": 1, "narration": "为什么？"}, {"no": 2, "narration": "为什么？"},
                 {"no": 3, "narration": "这是事实。"}]
        self.assertEqual(check_question_runs(shots), [])


if __name__ == "__main__":
    unittest.main()
