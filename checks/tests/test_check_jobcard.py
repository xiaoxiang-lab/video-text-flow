"""check_jobcard 测试：05-拆镜作业单 校验器（TDD）。

判据（来自 vox-prompts / LESSONS D1，规则假设来源见 校验器设计说明.md）：
- 镜数：头部自称（N 镜 = H + N-1）与实际表格行一致
- 时长档 ∈ {4,6,8,10}（Flow 档位）
- 档位必须覆盖朗读时长：>36 字必须 ≥10s（读速 ≈4.5 字/s，实测 LESSONS D1）
- 档位低于字数应取档 → warning（读速有浮动，不硬拦）
- 参考图：典型 3-5 张（vox-prompts「典型三到五镜」）；>8 → warning；0 → 提示（可能用户跳过图片工具）
- image_prompt 节标题镜号集合 == 表格标 ✅ 的镜号集合（写了才出图，漏写/多写都违规）
- 贯穿装置节存在；复核记录块存在
"""

import unittest

import check_jobcard as m


def make_compliant() -> str:
    """合规样例：5 镜（H + 4），参考图 2 张对应 H/2，档位全覆盖。"""
    return """# 05-拆镜作业单（样例 · 关卡5交付）

立场：样例立场 | 风格：minimal-motion | 日期：2026-08-15

## 贯穿装置：巨型数字对撞

两枚巨型扁平数字相向推进、对撞、弹开。

## 拆镜作业单（5 镜 = H + 4，narration 逐字切分定稿）

| 镜 | 时长档 | 旁白（narration） | 参考图 | 动作要点 |
|---|---|---|---|---|
| H | 6s | 这是样例的第一句话。 | ✅ | 数字对撞，问号落定 |
| 1 | 4s | 第二句话很短。 | — | 日期卡弹出 |
| 2 | 6s | 第三句话稍微长一些，念起来大概需要六秒钟时间。 | ✅ | 数字对撞，天平倾斜 |
| 3 | 8s | 第四句话有三十个字左右，需要八秒才能念完。 | — | 时间轴快进 |
| 4 | 10s | 第五句话超过三十六个字必须给足十秒档位不然根本念不完这一整句这是超长句测试。 | — | 柱状图生长 |

## video_prompt 示范（2 镜完整版）

### H 镜（6s，风格块 A）

> 极简动态舞台：纯白底。

### 2 镜（6s，风格块 B）

> 纯白底上的巨型数字与结论卡。

## 参考图 image_prompt（2 张）

**H 镜（贯穿装置首秀）**
> 主体：纯白底上两枚巨型扁平数字卡。

**2 镜（数字对撞钉住）**
> 主体：纯白底上两枚巨型扁平数字卡。

## 复核记录（先程序，后子 agent）

```
程序校验（check_jobcard.py）：✅ 通过
子 agent 核对表：✅ 通过
用户确认：✅ 已确认
```

## 确认项（关卡5）

1. 镜头划分：H + 4 镜。
"""


class TestJobcardCompliant(unittest.TestCase):
    def test_compliant_passes(self):
        report = m.run(make_compliant())
        self.assertTrue(report["pass"], msg=str(report["issues"]))
        self.assertEqual(report["stats"]["shots"], 5)
        self.assertEqual(report["stats"]["refs"], 2)
        self.assertEqual(report["stats"]["total_seconds"], 6 + 4 + 6 + 8 + 10)


class TestJobcardCounts(unittest.TestCase):
    def test_claimed_mismatch(self):
        text = make_compliant().replace("5 镜 = H + 4", "6 镜 = H + 5")
        report = m.run(text)
        self.assertFalse(report["pass"])
        self.assertTrue(any("镜数" in i["type"] for i in report["issues"]))

    def test_missing_table(self):
        text = make_compliant()
        text = "\n".join(line for line in text.splitlines()
                         if not line.strip().startswith("|"))
        report = m.run(text)
        self.assertFalse(report["pass"])
        self.assertTrue(any("镜数" in i["type"] for i in report["issues"]))


class TestJobcardDurations(unittest.TestCase):
    def test_illegal_duration(self):
        text = make_compliant().replace("| 1 | 4s |", "| 1 | 7s |")
        report = m.run(text)
        self.assertFalse(report["pass"])
        self.assertTrue(any("时长档" in i["type"] for i in report["issues"]))

    def test_long_shot_under_duration(self):
        text = make_compliant().replace("| 4 | 10s |", "| 4 | 8s |")
        report = m.run(text)
        self.assertFalse(report["pass"])
        self.assertTrue(any("超长句" in i["type"] for i in report["issues"]))

    def test_short_shot_under_duration_warns(self):
        text = make_compliant().replace("| 2 | 6s |", "| 2 | 4s |")
        report = m.run(text)
        self.assertTrue(report["pass"], msg="档位低于字数建议只 warning，不硬拦")
        self.assertTrue(any(i["type"] == "档位建议" for i in report["issues"]))

    def test_no_duration_column(self):
        text = make_compliant().replace("| 1 | 4s |", "| 1 | — |")
        report = m.run(text)
        self.assertFalse(report["pass"])
        self.assertTrue(any("镜数" in i["type"] or "时长档" in i["type"] for i in report["issues"]))


class TestJobcardRefs(unittest.TestCase):
    def test_too_many_refs_warns(self):
        text = make_compliant()
        extra = "\n".join(f"| {i} | 4s | 补充镜 {i} 的旁白文本。 | ✅ | 动作 |" for i in range(5, 13))
        prompts = "\n\n" + "\n\n".join(f"**{i} 镜（补图）**\n> 主体：补图。" for i in range(5, 13))
        text = text.replace("## video_prompt 示范", extra + "\n\n## video_prompt 示范")
        text = text.replace("## 确认项（关卡5）", prompts + "\n\n## 确认项（关卡5）")
        text = text.replace("5 镜 = H + 4", "13 镜 = H + 12")
        report = m.run(text)
        self.assertTrue(report["pass"], msg="参考图多只 warning，不硬拦")
        self.assertTrue(any("参考图" in i["type"] for i in report["issues"]))

    def test_ref_missing_image_prompt(self):
        text = make_compliant()
        text = text.replace("**H 镜（贯穿装置首秀）**", "**X 镜（缺图）**")
        report = m.run(text)
        self.assertFalse(report["pass"])
        self.assertTrue(any("image_prompt" in i["type"] for i in report["issues"]))

    def test_image_prompt_for_non_ref_shot(self):
        text = make_compliant()
        text = text.replace("**2 镜（数字对撞钉住）**", "**3 镜（多余图）**")
        report = m.run(text)
        self.assertFalse(report["pass"])
        self.assertTrue(any("image_prompt" in i["type"] for i in report["issues"]))

    def test_zero_refs_ok_with_note(self):
        text = make_compliant()
        text = text.replace("| ✅ |", "| — |")
        text = text.replace("参考图 image_prompt（2 张）", "参考图 image_prompt（0 张，跳过图片工具）")
        text = text.replace("**H 镜（贯穿装置首秀）**", "~~H~~")
        text = text.replace("**2 镜（数字对撞钉住）**", "~~2~~")
        report = m.run(text)
        self.assertTrue(report["pass"], msg=str(report["issues"]))


class TestJobcardStructure(unittest.TestCase):
    def test_missing_through_line(self):
        text = make_compliant().replace("## 贯穿装置：巨型数字对撞", "## 内容")
        report = m.run(text)
        self.assertFalse(report["pass"])
        self.assertTrue(any("贯穿装置" in i["type"] for i in report["issues"]))

    def test_missing_review_block(self):
        text = make_compliant().replace("## 复核记录", "## 记录")
        report = m.run(text)
        self.assertFalse(report["pass"])
        self.assertTrue(any("复核记录" in i["type"] for i in report["issues"]))


class TestJobcardDelta(unittest.TestCase):
    """2026-08-17 第 2 轮：差值列/就近吸附硬规律/短镜/差值率（srt-vox 第 5 节翻译）。

    05 表格可选第 3 列「自然时长」（配音实测秒数）；留空 = 未提供（旧产物兼容，跳过）。
    """

    DELTA_HEADER = """# 05-拆镜作业单（差值样例）

## 贯穿装置：数字对撞

## 拆镜作业单（4 镜 = H + 3，narration 逐字切分定稿）

| 镜 | 时长档 | 自然时长 | 旁白（narration） | 参考图 | 动作要点 |
|---|---|---|---|---|---|
| H | 6s | 5.76 | 旁白一。 | — | 动作一 |
| 1 | 4s | 3.36 | 旁白二。 | — | 动作二 |
| 2 | 8s | 7.52 | 旁白三。 | — | 动作三 |
| 3 | 4s | 2.56 | 短镜旁白。 | — | 动作四 |

## 复核记录
"""

    def test_delta_rows_ok(self):
        report = m.run(self.DELTA_HEADER)
        self.assertTrue(report["pass"], msg=str(report["issues"]))
        self.assertEqual(report["stats"]["delta_rate"], round((0.24 + 0.64 + 0.48 + 1.44) / (6 + 4 + 8 + 4), 4))

    def test_delta_math_violation(self):
        # 差值 = 时长档 − 自然时长；硬规律：自然 ≥3s ⟹ |差值| ≤ 1.0
        text = self.DELTA_HEADER.replace("| 1 | 4s | 3.36 |", "| 1 | 6s | 3.36 |")
        report = m.run(text)
        self.assertFalse(report["pass"])
        self.assertTrue(any("差值" in i["type"] for i in report["issues"]))

    def test_short_shot_delta_cap_3_2(self):
        # 短镜（自然 <3s）：余量可 >1.0，上限 3.2
        text = self.DELTA_HEADER.replace("| 3 | 4s | 2.56 |", "| 3 | 4s | 0.5 |")
        report = m.run(text)
        self.assertFalse(report["pass"])
        self.assertTrue(any("短镜" in i["type"] for i in report["issues"]))

    def test_short_shot_ok_within_cap(self):
        report = m.run(self.DELTA_HEADER)
        self.assertTrue(report["pass"])

    def test_delta_rate_high_warns(self):
        # 差值率 >20% → warning（srt-vox：向用户提示三选项，不硬拦）
        text = """# 05
## 贯穿装置：数字对撞
| 镜 | 时长档 | 自然时长 | 旁白 | 参考图 | 动作要点 |
|---|---|---|---|---|---|
| H | 4s | 3.0 | 甲。 | — | 一 |
| 1 | 4s | 3.0 | 乙。 | — | 二 |
| 2 | 4s | 3.0 | 丙。 | — | 三 |

## 复核记录
"""
        report = m.run(text)
        self.assertTrue(report["pass"], msg="差值率超 20% 只 warning")
        self.assertTrue(any("差值率" in i["type"] for i in report["issues"]))

    def test_old_5col_table_still_ok(self):
        # 旧 5 列格式无自然时长列 → 跳过差值校验，不误报
        report = m.run(make_compliant())
        self.assertTrue(report["pass"])


class TestJobcardType(unittest.TestCase):
    """2026-08-17 第 3 轮：拆镜定型（解释/展示，srt-vox 第 2 节翻译）。

    05 表格可选「型」列（第 2 列，紧邻镜号）；不填 = 旧格式兼容。
    """

    TYPED_HEADER = """# 05-拆镜作业单（定型样例）

## 贯穿装置：数字对撞

## 拆镜作业单（3 镜 = H + 2，narration 逐字切分定稿）

| 镜 | 型 | 时长档 | 旁白（narration） | 参考图 | 动作要点 |
|---|---|---|---|---|---|
| H | 解释 | 6s | 旁白一。 | — | 动作一 |
| 1 | 展示 | 4s | 引文内容要完整。 | — | 动作二 |
| 2 | 解释 | 8s | 旁白三。 | — | 动作三 |

## 复核记录
"""

    def test_typed_rows_ok(self):
        report = m.run(self.TYPED_HEADER)
        self.assertTrue(report["pass"], msg=str(report["issues"]))

    def test_invalid_type_detected(self):
        text = self.TYPED_HEADER.replace("| 1 | 展示 |", "| 1 | 演示 |")
        report = m.run(text)
        self.assertFalse(report["pass"])
        self.assertTrue(any("型" in i["type"] for i in report["issues"]))

    def test_display_shot_split_detected(self):
        # 展示型不拆分（srt-vox：展示型超 11s 封顶 10s，不拆）
        text = self.TYPED_HEADER.replace("| 1 | 展示 | 4s |", "| 1a | 展示 | 4s |")
        report = m.run(text)
        self.assertFalse(report["pass"])
        self.assertTrue(any("展示" in i["type"] for i in report["issues"]))

    def test_display_shot_over_15s_warns(self):
        # 展示型自然时长 >15s → warning（按内容分两个展示镜）
        text = """# 05
## 贯穿装置：数字对撞
| 镜 | 型 | 时长档 | 自然时长 | 旁白 | 参考图 | 动作要点 |
|---|---|---|---|---|---|---|
| H | 展示 | 10s | 16.5 | 一段很长的引文内容需要逐字展示。 | — | 一 |

## 复核记录
"""
        report = m.run(text)
        self.assertTrue(report["pass"], msg=">15s 展示型只 warning")
        self.assertTrue(any("展示" in i["type"] and "15" in i["fix"] for i in report["issues"]))

    def test_display_shot_caps_at_10(self):
        # 展示型自然时长 (10,11] 取 10 档（补差 ≤1.0）；超 10 取 10
        text = """# 05
## 贯穿装置：数字对撞
| 镜 | 型 | 时长档 | 自然时长 | 旁白 | 参考图 | 动作要点 |
|---|---|---|---|---|---|---|
| H | 展示 | 10s | 10.4 | 一段引文内容。 | — | 一 |

## 复核记录
"""
        report = m.run(text)
        self.assertTrue(report["pass"], msg=str(report["issues"]))

    def test_old_5col_no_type_ok(self):
        report = m.run(make_compliant())
        self.assertTrue(report["pass"])


class TestJobcardSplit(unittest.TestCase):
    """2026-08-17 第 4 轮：超限拆分 + 桥接（srt-vox 第 7 节翻译）。

    解释型自然时长 >11s 必须拆（拆出的片段号带字母后缀）；拆分镜 a/b 成对。
    """

    SPLIT_HEADER = """# 05-拆镜作业单（拆分样例）

## 贯穿装置：数字对撞

## 拆镜作业单（3 镜 = H + 2，narration 逐字切分定稿）

| 镜 | 型 | 时长档 | 自然时长 | 旁白（narration） | 参考图 | 动作要点 |
|---|---|---|---|---|---|---|
| H | 解释 | 6s | 5.6 | 旁白一。 | — | 动作一 |
| 1a | 解释 | 6s | 5.8 | 前半句内容。 | — | 动作二 |
| 1b | 解释 | 6s | 5.9 | 后半句内容。 | — | 动作三 |

## 复核记录
"""

    def test_split_pair_ok(self):
        report = m.run(self.SPLIT_HEADER)
        self.assertTrue(report["pass"], msg=str(report["issues"]))

    def test_over_11s_not_split_detected(self):
        # 解释型自然 >11s 未拆 → error（超限必须拆，片段号带字母后缀）
        text = self.SPLIT_HEADER.replace(
            "| H | 解释 | 6s | 5.6 |", "| H | 解释 | 10s | 11.5 |")
        report = m.run(text)
        self.assertFalse(report["pass"])
        self.assertTrue(any("拆分" in i["type"] for i in report["issues"]))

    def test_split_pair_incomplete_detected(self):
        # 拆分成对：有 a 无 b → error
        text = self.SPLIT_HEADER.replace("| 1b | 解释 | 6s | 5.9 |", "| 2 | 解释 | 6s | 5.9 |")
        report = m.run(text)
        self.assertFalse(report["pass"])
        self.assertTrue(any("桥接" in i["type"] or "成对" in i["type"] for i in report["issues"]))

    def test_split_without_natural_skips(self):
        # 无自然时长列 → 拆分检查跳过（配音前无法判超限）
        text = self.SPLIT_HEADER.replace("| 镜 | 型 | 时长档 | 自然时长 | 旁白（narration） | 参考图 | 动作要点 |",
                                         "| 镜 | 型 | 时长档 | 旁白（narration） | 参考图 | 动作要点 |")
        text = text.replace("| H | 解释 | 6s | 5.6 |", "| H | 解释 | 6s |")
        text = text.replace("| 1a | 解释 | 6s | 5.8 |", "| 1a | 解释 | 6s |")
        text = text.replace("| 1b | 解释 | 6s | 5.9 |", "| 1b | 解释 | 6s |")
        report = m.run(text)
        self.assertTrue(report["pass"], msg=str(report["issues"]))


if __name__ == "__main__":
    unittest.main()
