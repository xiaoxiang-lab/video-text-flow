"""run_all 的 --project 集成测试：防 P1 复现（宣称接入但代码没跑 = 假接入）。

P1（2026-08-15 对抗性回查）：run_all 从未调用 check_chain，README 宣称含但代码没有。
本测试锁定：run_all --project 必须真正执行 check_stage2 并影响退出码。
"""

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_all
from run_all import exempted_types

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
        from check_stage2 import flow_slot
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


def _write_good_layout(root: Path) -> None:
    """最小合规布局：01-05 占位 + 阶段 2 产物。"""
    (root / "01-立场重写稿.md").write_text("# 01\n正文内容。", encoding="utf-8")
    (root / "02-分镜稿.md").write_text("# 02\n1. 镜一\n", encoding="utf-8")
    (root / "03-配音定稿.md").write_text("# 03\n**hook：**\n> 钩子句。\n\n**正文：**\n\n正文内容。\n", encoding="utf-8")
    (root / "04-封面出图提示词.md").write_text("# 04\n标题\n", encoding="utf-8")
    (root / "05-拆镜作业单.md").write_text(JOB05_GOOD, encoding="utf-8")
    work = root / ".work"
    work.mkdir(exist_ok=True)
    (work / "design.json").write_text(json.dumps(DESIGN_GOOD, ensure_ascii=False), encoding="utf-8")
    (work / "manifest.json").write_text(json.dumps(MANIFEST_GOOD, ensure_ascii=False), encoding="utf-8")
    prompts = root / "04-prompts"
    prompts.mkdir(exist_ok=True)
    (prompts / "handoff.md").write_text(make_handoff_good(), encoding="utf-8")
    img = root / "03-images"
    (img / "references").mkdir(parents=True)
    (img / "master.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 2000)
    for sid in ("shot-001", "shot-003"):
        (img / "references" / f"{sid}.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 2000)


class ExemptTest(unittest.TestCase):
    """豁免登记机制：用户决策落盘为「豁免登记：<检查项>」，run_all 将其从违规降为 exempt。

    防 P1 复现：豁免不能是沉默放行——必须能在产物里查到登记（机器可读），
    且只豁免明确登记的检查项，其他违规照常报。
    """

    def test_extract_exempt_types(self):
        text = "豁免登记：翻案腔（素材原句直引）\n豁免登记：长列举"
        self.assertEqual(exempted_types(text), {"翻案腔", "长列举"})

    def test_no_exempt_clean(self):
        self.assertEqual(exempted_types("正常产物，无豁免"), set())

    def test_check_file_exempts_registered_type(self):
        # 01 稿：3 处翻案腔 + 1 处破折号；只登记豁免翻案腔 → 翻案腔降 exempt，破折号仍违规
        root = Path(tempfile.mkdtemp())
        p = root / "01-立场重写稿.md"
        p.write_text(
            "> 市场买的已经不是过去，而是未来。\n"
            "> 真正的看点不是股价，而是产业。\n"
            "> 结果——降价了。\n"
            "豁免登记：翻案腔（用户决策，2026-08-15）\n",
            encoding="utf-8")
        result = run_all.check_file(p)
        types = {i.get("type") for i in result["report"]["issues"]}
        self.assertEqual(types, {"翻案腔", "破折号"})
        flip = [i for i in result["report"]["issues"] if i["type"] == "翻案腔"]
        dash = [i for i in result["report"]["issues"] if i["type"] == "破折号"]
        self.assertTrue(all(i.get("severity") == "exempt" for i in flip))
        self.assertTrue(all(i.get("severity") != "exempt" for i in dash))
        self.assertFalse(result["report"]["pass"])

    def test_all_registered_exempt_passes(self):
        root = Path(tempfile.mkdtemp())
        p = root / "01-立场重写稿.md"
        p.write_text(
            "> 市场买的已经不是过去，而是未来。\n"
            "豁免登记：翻案腔（用户决策）\n",
            encoding="utf-8")
        result = run_all.check_file(p)
        self.assertTrue(result["report"]["pass"])


class RunAllProjectIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        _write_good_layout(self.root)

    def run_all(self, project: str | None) -> tuple[int, dict]:
        args = ["run_all", str(self.root)]
        if project:
            args += ["--project", str(project)]
        buf = StringIO()
        with redirect_stdout(buf):
            code = run_all.main(args)
        return code, json.loads(buf.getvalue())

    def test_with_project_runs_stage2(self):
        code, report = self.run_all(self.root)
        checkers = [f["checker"] for f in report["files"]]
        self.assertIn("check_stage2", checkers)
        stage2 = [f for f in report["files"] if f["checker"] == "check_stage2"][0]
        self.assertTrue(stage2["report"]["pass"])

    def test_with_project_catches_bad_design(self):
        (self.root / ".work" / "design.json").write_text(
            json.dumps({"shots": []}, ensure_ascii=False), encoding="utf-8")
        code, report = self.run_all(self.root)
        self.assertNotEqual(code, 0)
        stage2 = [f for f in report["files"] if f["checker"] == "check_stage2"][0]
        self.assertFalse(stage2["report"]["pass"])

    def test_without_project_skips_stage2(self):
        code, report = self.run_all(None)
        checkers = [f["checker"] for f in report["files"]]
        self.assertNotIn("check_stage2", checkers)

    def test_project_missing_05_raises_not_pass(self):
        (self.root / "05-拆镜作业单.md").unlink()
        code, report = self.run_all(self.root)
        self.assertNotEqual(code, 0)
        stage2 = [f for f in report["files"] if f["checker"] == "check_stage2"][0]
        self.assertFalse(stage2["report"]["pass"])


if __name__ == "__main__":
    unittest.main()
