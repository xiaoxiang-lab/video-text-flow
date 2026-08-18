"""check_stage2 的测试：05→design.json→handoff→manifest 阶段 2 链。

防假通过原则：违规样例必须检出；合规样例不得误报；产物缺失必须报错。

2026-08-17 第 2 轮新增/重构（srt-vox 差值判据翻译）：
- design.duration_seconds = 配音实测（任意正数），不再是档位值（修复假报）
- 差值 = flow_slot(实测) − 实测；实测 ≥3s ⟹ |差值| ≤ 1.0；短镜（<3s）|差值| ≤ 3.2
- 尾部按差值分档：余量镜尾部含「结尾稳定/保持完全静止/定格」；补差镜含「末帧」+稳定
- handoff「Flow 档位」行 == flow_slot(实测)（修复旧正则静默失效）
- 差值率（解释型 |差值| 合计 ÷ 生成总时长）>20% 进 warnings
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_stage2 import (check_design_internal, check_handoff_vs_design,
                          check_job05_vs_design, check_manifest_files, flow_slot, run)

# ---- 合规样例（4 镜小样，真实项目同构） ----

JOB05_GOOD = """# 05-拆镜作业单（样例）

## 拆镜作业单（4 镜 = H + 3，narration 逐字切分定稿）

| 镜 | 时长档 | 旁白（narration） | 参考图 | 动作要点 |
|---|---|---|---|---|
| H | 4s | 钩子句在这里。 | ✅ | 动作一 |
| 1 | 6s | 这是正文第一句。 | — | 动作二 |
| 2 | 8s | 这是正文第二句，拆了前半。 | ✅ | 动作三 |
| 3 | 4s | 这是正文第二句后半。 | — | 动作四 |

---

## 参考图 image_prompt（2 张）

**H 镜（开场结构镜）**
> 主体：纯白底两枚数字卡。
> 前景：无阴影。
> 背景是纯白底。

**2 镜（核心揭示镜）**
> 主体：天平一枚。
> 前景：无材质。
> 背景是浅灰细网格底。
"""

DESIGN_GOOD = {
    "title": "样例",
    "shots": [
        {"title": "H", "narration": "钩子句在这里。", "duration_seconds": 4.0,
         "video_prompt": "背景是纯白底。\n\n冲击：动作一。\n\n落点。结尾稳定保持 0.8 秒。",
         "image_prompt": "主体：纯白底两枚数字卡。\n前景：无阴影。\n背景是纯白底。"},
        {"title": "1", "narration": "这是正文第一句。", "duration_seconds": 6.0,
         "video_prompt": "背景是浅灰细网格底。\n\n冲击：动作二。\n\n落点。结尾稳定保持 0.8 秒。"},
        {"title": "2", "narration": "这是正文第二句，拆了前半。", "duration_seconds": 8.0,
         "video_prompt": "背景是白底黑虚线。\n\n冲击：动作三。\n\n落点。结尾稳定保持 0.8 秒。",
         "image_prompt": "主体：天平一枚。\n前景：无材质。\n背景是浅灰细网格底。"},
        {"title": "3", "narration": "这是正文第二句后半。", "duration_seconds": 4.0,
         "video_prompt": "背景是浅蓝极淡底。\n\n冲击：动作四。\n\n落点。结尾稳定保持 0.8 秒。"},
    ],
}

MANIFEST_GOOD = {
    "stages": {"images": "completed", "image-review": "completed", "handoff-export": "completed"},
    "master": {"status": "approved"},
    "shots": {
        "shot-001": {"status": "approved"},
        "shot-003": {"status": "approved"},
    },
    "image_failures": {},
}


def make_handoff_good() -> str:
    plan = [{"id": "shot-001", "title": "H", "narration": "钩子句在这里。",
             "duration_seconds": 4.0, "video_prompt": "背景是纯白底。\n\n冲击：动作一。\n\n落点。结尾稳定保持 0.8 秒。"},
            {"id": "shot-002", "title": "1", "narration": "这是正文第一句。",
             "duration_seconds": 6.0, "video_prompt": "背景是浅灰细网格底。\n\n冲击：动作二。\n\n落点。结尾稳定保持 0.8 秒。"},
            {"id": "shot-003", "title": "2", "narration": "这是正文第二句，拆了前半。",
             "duration_seconds": 8.0, "video_prompt": "背景是白底黑虚线。\n\n冲击：动作三。\n\n落点。结尾稳定保持 0.8 秒。"},
            {"id": "shot-004", "title": "3", "narration": "这是正文第二句后半。",
             "duration_seconds": 4.0, "video_prompt": "背景是浅蓝极淡底。\n\n冲击：动作四。\n\n落点。结尾稳定保持 0.8 秒。"}]
    lines = ["# 样例项目 · 逐镜操作单", "", "标题：样例", "", "## 开工前必读", "", "- 模型：**Omni Flash**；比例：**16:9**", ""]
    for s in plan:
        slot = flow_slot(s["duration_seconds"])
        lines += [f"## {s['id']} {s['title']}", "",
                  f"Flow 档位：{slot}s（旁白真实时长 {s['duration_seconds']:.1f}s）", "",
                  "旁白：", "", f"> {s['narration']}", ""]
        if s["id"] in ("shot-001", "shot-003"):
            lines += [f"**参考图：上传 `../03-images\\references\\{s['id']}.png`（image2image 输入）。**", "", f"![参考图](../03-images\\references\\{s['id']}.png)", ""]
        else:
            lines += ["**本镜不上传参考图，直接用下面的提示词生成。**", ""]
        lines += ["提示词：", "", "```text", s["video_prompt"], "```", ""]
    lines += ["---", "", "## 接下来由你完成", "", "1. 逐镜生成并下载视频。"]
    return "\n".join(lines)


class SetupBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "job05.md").write_text(JOB05_GOOD, encoding="utf-8")
        work = self.tmp / ".work"
        work.mkdir()
        (work / "design.json").write_text(json.dumps(DESIGN_GOOD, ensure_ascii=False), encoding="utf-8")
        (work / "manifest.json").write_text(json.dumps(MANIFEST_GOOD, ensure_ascii=False), encoding="utf-8")
        prompts = self.tmp / "04-prompts"
        prompts.mkdir()
        (prompts / "handoff.md").write_text(make_handoff_good(), encoding="utf-8")
        img = self.tmp / "03-images"
        (img / "references").mkdir(parents=True)
        (img / "master.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 2000)
        for sid in ("shot-001", "shot-003"):
            (img / "references" / f"{sid}.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 2000)

    def load_design(self) -> dict:
        return json.loads((self.tmp / ".work" / "design.json").read_text(encoding="utf-8"))


class Job05VsDesignTest(SetupBase):
    def issues_of(self, job05: str | None = None, design: dict | None = None) -> list[str]:
        issues, _stale = check_job05_vs_design(job05 or JOB05_GOOD, design or self.load_design())
        return issues

    def test_good_ok(self):
        self.assertEqual(self.issues_of(), [])

    def test_narration_mismatch_detected(self):
        d = self.load_design()
        d["shots"][1]["narration"] = "这句旁白被改了。"
        issues = self.issues_of(design=d)
        self.assertTrue(any("narration" in i and "1" in i for i in issues))

    def test_hook_mismatch_detected(self):
        d = self.load_design()
        d["shots"][0]["narration"] = "钩子被换了。"
        issues = self.issues_of(design=d)
        self.assertTrue(any("H" in i for i in issues))

    def test_shot_count_mismatch_detected(self):
        d = self.load_design()
        d["shots"].pop()
        issues = self.issues_of(design=d)
        self.assertTrue(any("镜数" in i for i in issues))

    def test_duration_nonpositive_detected(self):
        d = self.load_design()
        d["shots"][2]["duration_seconds"] = 0.0
        issues = self.issues_of(design=d)
        self.assertTrue(any("时长" in i for i in issues))

    def test_stale_slots_in_stats(self):
        # 配音实测与 05 估算档位不符 → stats.stale_slots（不 fail，05 是配音前产物）；
        # handoff 是配音后产物，必须按新实测同步（Flow 档位 4s），补差镜尾部写末帧定格
        d = self.load_design()
        d["shots"][1]["duration_seconds"] = 4.8  # flow_slot = 4（补差 0.8s），05 写 6s
        d["shots"][1]["video_prompt"] = "背景是浅灰细网格底。\n\n冲击：动作二。\n\n落点。末帧保持绝对稳定，这一帧会被定格延长。"
        (self.tmp / ".work" / "design.json").write_text(
            json.dumps(d, ensure_ascii=False), encoding="utf-8")
        handoff = (self.tmp / "04-prompts" / "handoff.md").read_text(encoding="utf-8")
        handoff = handoff.replace("Flow 档位：6s（旁白真实时长 6.0s）",
                                  "Flow 档位：4s（旁白真实时长 4.8s）")
        (self.tmp / "04-prompts" / "handoff.md").write_text(handoff, encoding="utf-8")
        report = run(self.tmp / "job05.md", self.tmp)
        self.assertTrue(report["pass"], report["issues"])
        self.assertTrue(report["stats"]["stale_slots"])

    def test_ref_image_missing_detected(self):
        d = self.load_design()
        d["shots"][2].pop("image_prompt")
        issues = self.issues_of(design=d)
        self.assertTrue(any("参考图" in i and "2" in i for i in issues))

    def test_ref_image_extra_detected(self):
        d = self.load_design()
        d["shots"][1]["image_prompt"] = "多余参考图。"
        issues = self.issues_of(design=d)
        self.assertTrue(any("参考图" in i for i in issues))

    def test_image_prompt_mismatch_detected(self):
        d = self.load_design()
        d["shots"][0]["image_prompt"] = "主体：完全不相关的东西。"
        issues = self.issues_of(design=d)
        self.assertTrue(any("image_prompt" in i and "H" in i for i in issues))

    def test_shot_id_mapping_ok(self):
        # 23 拆 23a/23b：design 顺序与 05 行序一致即合法
        job = JOB05_GOOD.replace("| 3 | 4s | 这是正文第二句后半。", "| 3a | 4s | 这是正文第二句后半。")
        issues = self.issues_of(job05=job)
        self.assertIsNotNone(issues)


class DesignInternalTest(unittest.TestCase):
    def test_missing_narration_detected(self):
        d = {"shots": [{"video_prompt": "x"}]}
        issues = check_design_internal(d)
        self.assertTrue(issues)

    def test_missing_video_prompt_detected(self):
        d = {"shots": [{"narration": "x"}]}
        issues = check_design_internal(d)
        self.assertTrue(issues)

    def test_empty_shots_detected(self):
        issues = check_design_internal({"shots": []})
        self.assertTrue(issues)

    def test_good_ok(self):
        d = {"shots": [{"narration": "x", "duration_seconds": 5.76,
                        "video_prompt": "背景是纯白底。\n\n冲击：1。落点。结尾稳定保持 0.8 秒。"}]}
        self.assertEqual(check_design_internal(d), [])

    def test_adjacent_same_background_detected(self):
        d = {"shots": [
            {"narration": "a", "video_prompt": "背景是纯白底。\n\n冲击：1。落点。结尾稳定保持 0.8 秒。"},
            {"narration": "b", "video_prompt": "背景是纯白底。\n\n冲击：2。落点。结尾稳定保持 0.8 秒。"},
        ]}
        issues = check_design_internal(d)
        self.assertTrue(any("背景" in i for i in issues))

    def test_no_ending_still_detected(self):
        d = {"shots": [{"narration": "x", "duration_seconds": 5.76,
                        "video_prompt": "背景是纯白底。\n\n冲击：1。落点。"}]}
        issues = check_design_internal(d)
        self.assertTrue(any("尾部" in i for i in issues))

    def test_shortfall_shot_needs_stable_tail(self):
        # 补差镜（实测 > 档位，如 10.5s 就近取 10s）：尾部必须物理稳定（末帧会被定格延长）
        good = {"shots": [{"narration": "x", "duration_seconds": 10.5,
                           "video_prompt": "动作完成。末帧保持绝对稳定，这一帧会被定格延长。"}]}
        self.assertEqual(check_design_internal(good), [])
        # 「结尾稳定保持 0.8 秒」物理满足（0.8s ≥ 0.2s 静止）——旧句式不误报
        old = {"shots": [{"narration": "x", "duration_seconds": 10.5,
                          "video_prompt": "动作完成。结尾稳定保持 0.8 秒。"}]}
        self.assertEqual(check_design_internal(old), [])
        # 尾部完全没稳定语义 → 违规
        bad = {"shots": [{"narration": "x", "duration_seconds": 10.5,
                          "video_prompt": "动作完成。收束。"}]}
        issues = check_design_internal(bad)
        self.assertTrue(any("补差" in i for i in issues))

    def test_short_shot_delta_within_3_2(self):
        # 短镜（<3s）：差值可 >1.0，上限 3.2（4s 地板 − 0.8s 下限）
        d = {"shots": [{"narration": "x", "duration_seconds": 2.56,
                        "video_prompt": "动作。结尾稳定保持 0.8 秒。"}]}
        self.assertEqual(check_design_internal(d), [])

    def test_display_shot_text_coverage(self):
        # 展示型（第 3 轮）：上屏文字必须完整覆盖旁白——旁白须为 image_prompt 的子序列
        good = {"shots": [{"narration": "这是一段引文，观众要逐字读完。",
                           "type": "展示", "duration_seconds": 8.0, "image_prompt": "卡片上印：这是一段引文，观众要逐字读完。",
                           "video_prompt": "文字入场。结尾稳定保持 0.8 秒。"}]}
        self.assertEqual(check_design_internal(good), [])
        bad = {"shots": [{"narration": "这是一段引文，观众要逐字读完。",
                          "type": "展示", "duration_seconds": 8.0,
                          "image_prompt": "卡片上只印了标题。",
                          "video_prompt": "文字入场。结尾稳定保持 0.8 秒。"}]}
        issues = check_design_internal(bad)
        self.assertTrue(any("逐字" in i for i in issues))

    def test_explain_shot_ignores_coverage(self):
        # 解释型不做逐字覆盖检查（密度控制，不逐字）
        d = {"shots": [{"narration": "解释型旁白。", "type": "解释", "duration_seconds": 4.0,
                        "video_prompt": "动作。结尾稳定保持 0.8 秒。"}]}
        self.assertEqual(check_design_internal(d), [])

    def test_display_cap_delta_exempt(self):
        # 展示型 >11s 封顶 10s：补差可超 1.0（平台上限，不误报）
        d = {"shots": [{"narration": "x", "type": "展示", "duration_seconds": 13.5,
                        "image_prompt": "x",
                        "video_prompt": "文字入场。结尾稳定保持 0.8 秒。"}]}
        self.assertEqual(check_design_internal(d), [])

    def test_delta_rate_excludes_display(self):
        from check_stage2 import compute_delta_rate
        # 展示型排除后，差值率只看解释型
        shots = [
            {"narration": "a", "type": "解释", "duration_seconds": 3.0,
             "video_prompt": "背景是纯白底。落点。结尾稳定保持 0.8 秒。"},
            {"narration": "b", "type": "展示", "duration_seconds": 13.5,
             "image_prompt": "b", "video_prompt": "文字入场。结尾稳定保持 0.8 秒。"},
        ]
        rate, warns = compute_delta_rate(shots)
        self.assertEqual(rate, 0.25)  # 只剩解释型：1.0/4


class DeltaRateTest(unittest.TestCase):
    def test_rate_in_warnings_when_high(self):
        # 差值率 = 解释型 |差值| 合计 ÷ 生成总时长；>20% 进 warnings 不 fail
        d = {"shots": [{"narration": "a", "duration_seconds": 3.0,
                        "video_prompt": "背景是纯白底。落点。结尾稳定保持 0.8 秒。"},
                       {"narration": "b", "duration_seconds": 3.0,
                        "video_prompt": "背景是浅灰底。落点。结尾稳定保持 0.8 秒。"},
                       {"narration": "c", "duration_seconds": 3.0,
                        "video_prompt": "背景是白底黑虚线。落点。结尾稳定保持 0.8 秒。"}]}
        report = {"warnings": [], "delta_rate": None}
        from check_stage2 import compute_delta_rate
        rate, warns = compute_delta_rate(d["shots"])
        self.assertGreater(rate, 0.20)  # 三镜各 3.0s→4s，差值各 1.0，率 = 3/12 = 25%
        self.assertTrue(warns)


class HandoffVsDesignTest(SetupBase):
    def test_good_ok(self):
        issues = check_handoff_vs_design(self.load_design(), (self.tmp / "04-prompts" / "handoff.md").read_text(encoding="utf-8"))
        self.assertEqual(issues, [])

    def test_narration_mismatch_detected(self):
        d = self.load_design()
        d["shots"][0]["narration"] = "旁白改了。"
        issues = check_handoff_vs_design(d, (self.tmp / "04-prompts" / "handoff.md").read_text(encoding="utf-8"))
        self.assertTrue(any("旁白" in i for i in issues))

    def test_missing_shot_detected(self):
        d = self.load_design()
        d["shots"].pop()
        issues = check_handoff_vs_design(d, (self.tmp / "04-prompts" / "handoff.md").read_text(encoding="utf-8"))
        self.assertTrue(any("镜" in i for i in issues))

    def test_duration_mismatch_detected(self):
        d = self.load_design()
        d["shots"][1]["duration_seconds"] = 10.0
        issues = check_handoff_vs_design(d, (self.tmp / "04-prompts" / "handoff.md").read_text(encoding="utf-8"))
        self.assertTrue(any("时长" in i for i in issues))

    def test_ref_marker_mismatch_detected(self):
        d = self.load_design()
        d["shots"][0].pop("image_prompt")  # handoff 仍标记上传参考图
        issues = check_handoff_vs_design(d, (self.tmp / "04-prompts" / "handoff.md").read_text(encoding="utf-8"))
        self.assertTrue(any("参考图" in i for i in issues))

    def test_flow_slot_mismatch_detected(self):
        # handoff「Flow 档位」行 == flow_slot(实测)——就近吸附规则（防改坏/防旧规则产物）
        text = (self.tmp / "04-prompts" / "handoff.md").read_text(encoding="utf-8")
        text = text.replace("Flow 档位：6s（旁白真实时长 6.0s）", "Flow 档位：8s（旁白真实时长 6.0s）")
        issues = check_handoff_vs_design(self.load_design(), text)
        self.assertTrue(any("档位" in i for i in issues))

    def test_flow_slot_line_parsed(self):
        # 真实产物格式（Flow 档位行）能解析出时长——旧正则「建议时长」静默失效修复
        text = (self.tmp / "04-prompts" / "handoff.md").read_text(encoding="utf-8")
        self.assertIn("Flow 档位", text)
        issues = check_handoff_vs_design(self.load_design(), text)
        self.assertEqual(issues, [])


class ManifestFilesTest(SetupBase):
    def test_good_ok(self):
        issues = check_manifest_files(self.tmp / ".work" / "manifest.json", self.tmp)
        self.assertEqual(issues, [])

    def test_missing_master_detected(self):
        (self.tmp / "03-images" / "master.png").unlink()
        issues = check_manifest_files(self.tmp / ".work" / "manifest.json", self.tmp)
        self.assertTrue(any("master" in i for i in issues))

    def test_missing_ref_detected(self):
        (self.tmp / "03-images" / "references" / "shot-003.png").unlink()
        issues = check_manifest_files(self.tmp / ".work" / "manifest.json", self.tmp)
        self.assertTrue(any("shot-003" in i for i in issues))

    def test_missing_handoff_detected(self):
        (self.tmp / "04-prompts" / "handoff.md").unlink()
        issues = check_manifest_files(self.tmp / ".work" / "manifest.json", self.tmp)
        self.assertTrue(any("handoff" in i for i in issues))

    def test_manifest_missing_raises(self):
        with self.assertRaises(FileNotFoundError):
            check_manifest_files(self.tmp / "nope.json", self.tmp)


class RunTest(SetupBase):
    def test_run_good_passes(self):
        report = run(self.tmp / "job05.md", self.tmp)
        self.assertTrue(report["pass"], report["issues"])

    def test_run_catches_design_bad(self):
        d = self.load_design()
        d["shots"][1]["narration"] = "被改。"
        (self.tmp / ".work" / "design.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        report = run(self.tmp / "job05.md", self.tmp)
        self.assertFalse(report["pass"])

    def test_run_job05_missing_raises(self):
        with self.assertRaises(FileNotFoundError):
            run(self.tmp / "no05.md", self.tmp)


if __name__ == "__main__":
    unittest.main()
