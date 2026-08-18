"""check_cover 的测试：违规样例必须被检出，合规样例不得误报。"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_cover import (extract_prompts, check_layout, check_metaphor,
                         check_forbidden, check_modes)

GOOD = """
## 主图提示词（模式 A）

> 16:9 横版封面。主题转译：极小建筑代表应用层，巨大基座代表底层，核心动作是安放。
> 左侧 55% 为标题区。标题分两行，第一行「甲」，第二行「乙」，「乙」用强调色强调。
> 除标题外无任何其他文字。禁止：赛博朋克、霓虹、蓝紫渐变、芯片、卡通。

## 模式 B（兜底）

> 16:9 横版封面。画面中央是安放装置。画面不含任何文字。禁止：赛博朋克、霓虹。
"""

BAD = """
## 主图提示词（模式 A）

> 一张好看的封面，机器人和芯片放中间，五颜六色。

## 模式 B（兜底）

> 也是封面。
"""


class ExtractTest(unittest.TestCase):
    def test_extract_prompt_blocks(self):
        self.assertEqual(len(extract_prompts(GOOD)), 4)  # 逐行提取：模式 A 3 行 + 模式 B 1 行


class LayoutTest(unittest.TestCase):
    def test_missing_markers_detected(self):
        prompts = extract_prompts(BAD)
        issues = check_layout(prompts)
        self.assertTrue(any(i["type"].startswith("排版参数未内置") for i in issues))

    def test_good_has_layout(self):
        prompts = extract_prompts(GOOD)
        self.assertEqual(check_layout(prompts), [])


class MetaphorTest(unittest.TestCase):
    def test_missing_metaphor_detected(self):
        prompts = extract_prompts(BAD)
        issues = check_metaphor(prompts)
        self.assertTrue(any(i["type"] == "解码动作未内置" for i in issues))

    def test_good_has_metaphor(self):
        prompts = extract_prompts(GOOD)
        self.assertEqual(check_metaphor(prompts), [])


class ForbiddenTest(unittest.TestCase):
    def test_forbidden_in_description_detected(self):
        prompts = extract_prompts(BAD)
        issues = check_forbidden(prompts)
        self.assertTrue(any(i["type"] == "禁止词出现在画面描述" for i in issues))

    def test_forbidden_only_in_ban_sentence_ok(self):
        prompts = extract_prompts(GOOD)
        self.assertEqual(check_forbidden(prompts), [])


class ModesTest(unittest.TestCase):
    def test_missing_mode_detected(self):
        self.assertTrue(any(i["type"] == "模式不齐全" for i in check_modes("## 主图提示词（模式 A）")))

    def test_both_modes_ok(self):
        self.assertEqual(check_modes("模式 A（带字直生）+ 模式 B（纯意象兜底）"), [])


if __name__ == "__main__":
    unittest.main()
