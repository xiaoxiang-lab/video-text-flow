"""check_rewrite 的测试：违规样例必须被检出，合规样例不得误报。"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_rewrite import run, check_colons, check_parallels, check_long_lists, check_key_facts, extract_body, check_flip_sentences


class FlipSentenceTest(unittest.TestCase):
    """翻案腔检测（human-writing 成稿禁令：不是A而是B/并非A而是B/不在于A而在于B/表面A实际B/看似A实则B…）。"""

    def test_not_but_detected(self):
        text = "市场买的已经不是宇树过去赚了多少钱，而是未来人形机器人到底能长多大。"
        issues = check_flip_sentences(text)
        self.assertTrue(any(i["type"] == "翻案腔" for i in issues), issues)

    def test_not_but_split_sentence_detected(self):
        text = "真正的看点不是股价涨多少。而是它会不会成为整个产业的估值锚。"
        issues = check_flip_sentences(text)
        self.assertTrue(any(i["type"] == "翻案腔" for i in issues), issues)

    def test_feibing_detected(self):
        text = "它并非没有准备，而是蓄谋已久。"
        issues = check_flip_sentences(text)
        self.assertTrue(any(i["type"] == "翻案腔" for i in issues), issues)

    def test_buzaiyu_detected(self):
        text = "问题不在于价格，而在于信任。"
        issues = check_flip_sentences(text)
        self.assertTrue(any(i["type"] == "翻案腔" for i in issues), issues)

    def test_surface_actual_detected(self):
        text = "表面上看是降价，实际上是清库存。"
        issues = check_flip_sentences(text)
        self.assertTrue(any(i["type"] == "翻案腔" for i in issues), issues)

    def test_no_flip_clean(self):
        self.assertEqual(check_flip_sentences("市场买的是宇树的未来。价格是 150.80 元。"), [])

    def test_not_only_one_side_ok(self):
        # 只有「不是」没有「而是」= 普通否定，不是翻案腔
        self.assertEqual(check_flip_sentences("它不是从工业机器人起家的。"), [])

    def test_run_includes_flip(self):
        text = "> 真正的看点不是股价涨多少，而是它会不会成为估值锚。"
        issues = run(text)["issues"]
        self.assertTrue(any(i["type"] == "翻案腔" for i in issues), issues)


class ColonTest(unittest.TestCase):
    def test_leader_colon_detected(self):
        text = "我为什么说它是底层？因为它没有做成封闭软件，它提出一个激进的设计：一切皆插件。"
        issues = check_colons(text)
        self.assertTrue(any(i["type"] == "提示性冒号" for i in issues), issues)

    def test_quote_colon_allowed(self):
        text = "官方说得很明白，Model 是灵魂。"  # 逗号无冒号，基线
        self.assertEqual(check_colons(text), [])
        text2 = "官方说：Model 是灵魂。"  # 「说」= 引语动词，允许
        self.assertEqual(check_colons(text2), [])

    def test_no_colon_clean(self):
        self.assertEqual(check_colons("今天天气很好。我们走吧。"), [])


class DashTest(unittest.TestCase):
    def test_dash_detected(self):
        text = "结果仅仅过了三个星期——就降价了。"
        issues = run(text)["issues"]
        self.assertTrue(any(i["type"] == "破折号" for i in issues))


class ParallelTest(unittest.TestCase):
    def test_three_items_detected(self):
        text = "模型可以换，工具可以换，Agent Loop 可以换，沙箱可以换。"
        issues = check_parallels(text)
        self.assertTrue(any(i["type"] == "同构排比≥3项" for i in issues))

    def test_two_items_ok(self):
        text = "模型可以换，工具可以换，Agent Loop 和沙箱也都能换。"
        issues = check_parallels(text)
        self.assertEqual([i for i in issues if i["type"] == "同构排比≥3项"], [])


class LongListTest(unittest.TestCase):
    def test_long_list_detected(self):
        text = "读文件、改代码、调终端、搜网页、管上下文、跑任务、检查结果，失败了再继续。"
        issues = check_long_lists(text)
        self.assertTrue(any(i["type"] == "长列举" for i in issues))

    def test_noun_list_ok(self):
        text = "电机、减速器、丝杠、传感器、关节，都会被重新定价。"
        issues = check_long_lists(text)
        self.assertEqual([i for i in issues if i["type"] == "长列举"], [])

    def test_verb_in_word_middle_not_counted(self):
        text = "先把机器人走路做出来，再把运动控制、关节、电机、算法，迁移到人形机器人上。"
        issues = check_long_lists(text)
        self.assertEqual([i for i in issues if i["type"] == "长列举"], [])

    def test_short_ok(self):
        self.assertEqual(check_long_lists("模型是大脑，Harness 是手脚。"), [])


class BodyExtractTest(unittest.TestCase):
    def test_meta_info_ignored(self):
        text = """# 01-立场重写稿

素材立场：悬案——219倍

> 8月10日，宇树正式启动申购。发行价 150.80 元。
> 市场买的已经是未来。
"""
        body = extract_body(text)
        self.assertNotIn("悬案", body)
        self.assertNotIn("——", body)
        self.assertIn("150.80", body)


class KeyFactsTest(unittest.TestCase):
    def test_missing_fact_detected(self):
        issues = check_key_facts("8月13日发布了产品。", ["8月13日", "Star 数万", "Cordis"])
        self.assertEqual(len(issues), 2)  # Star 数万、Cordis 缺失

    def test_all_present_ok(self):
        self.assertEqual(check_key_facts("8月13日，Star 数万，Cordis 都在。", ["8月13日", "Cordis"]), [])


if __name__ == "__main__":
    unittest.main()
