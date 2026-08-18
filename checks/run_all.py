"""一键校验：按文件名识别产物，跑对应校验器 + 跨产物链校验，汇总报告。

用法：python checks/run_all.py <产物目录> [--project <vox项目目录>]
识别规则：
  01-*.md → check_rewrite（+关键事实来自 00 素材）
  02-*.md → check_storyboard
  03-*.md → 链层（03 是段落定稿，无镜行格式，check_storyboard 解析 0 镜 = 假通过；
            03 的正确校验 = check_chain 的 02→03 拼接链 + 03→05 逐字链 + 数字链）
  04-*.md → check_cover
  05-*.md → check_jobcard
  全部   → check_chain（跨产物一致性：文本链/数字链/标题/模板结构/03→05 narration 逐字）
  --project <vox项目目录> → check_stage2（05→design.json→handoff→manifest 阶段 2 链）
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_chain
import check_cover
import check_docs
import check_jobcard
import check_rewrite
import check_stage2
import check_storyboard

# 豁免登记：产物文件内「豁免登记：<检查项>」标记（用户决策落盘，机器可读）
# 格式：豁免登记：翻案腔（理由）——检查项名匹配 issue.type 即豁免（不计违规）
EXEMPT_RE = re.compile(r"豁免登记[：:]\s*([^（(；;\n]+)")


def exempted_types(text: str) -> set[str]:
    """从产物文本提取已豁免的检查项集合。"""
    return {m.group(1).strip() for m in EXEMPT_RE.finditer(text)}


def extract_key_facts(source_text: str) -> list[str]:
    """从素材提取关键事实（日期/数字/术语），供重写稿保留核对。"""
    facts = []
    # 日期：7月29日 / 8月13日 等
    facts += re.findall(r"\d{1,2}月\d{1,2}日", source_text)
    # 带单位的数字：0.2美元 / 80% / 2.4万亿 等
    facts += re.findall(r"\d+(?:\.\d+)?(?:万亿|亿|万|%|美元|元|Token|B|GB)", source_text)
    return list(dict.fromkeys(facts))


def check_file(path: Path) -> dict:
    name = path.name
    text = path.read_text(encoding="utf-8")
    exempt = exempted_types(text)
    report: dict | None = None
    if name.startswith("01-"):
        report = check_rewrite.run(text)
    elif name.startswith("02-"):
        report = check_storyboard.run(text)
    elif name.startswith("03-"):
        # 段落定稿：不走 check_storyboard（解析 0 镜 = 假通过），正确校验在 check_chain 链层
        report = {"pass": True, "issues": []}
    elif name.startswith("04-"):
        report = check_cover.run(text)
    elif name.startswith("05-"):
        report = check_jobcard.run(text)
    if report is None:
        return {"file": name, "checker": "skip", "report": {"pass": True, "issues": []}}
    # 豁免登记：用户决策落盘的检查项不计违规（防再犯靠登记可查，不是沉默放行）
    if exempt:
        kept = []
        for i in report["issues"]:
            if i.get("type") in exempt:
                i = dict(i)
                i["severity"] = "exempt"
            kept.append(i)
        report = dict(report)
        report["issues"] = kept
        report["pass"] = not [i for i in kept if i.get("severity") != "exempt"]
    return {"file": name, "checker": {
        "01-": "check_rewrite", "02-": "check_storyboard", "03-": "check_chain（链层）",
        "04-": "check_cover", "05-": "check_jobcard"}.get(name[:3], "skip"),
        "report": report}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="run_all")
    parser.add_argument("directory", help="产物目录（含 01-05 md）")
    parser.add_argument("--project", default=None, help="voxvideo 项目目录（跑阶段 2 链 check_stage2）")
    args = parser.parse_args(argv[1:])
    directory = Path(args.directory)
    results = []
    all_pass = True
    for path in sorted(directory.glob("0[1-5]-*.md")):
        result = check_file(path)
        results.append(result)
        if not result["report"]["pass"]:
            all_pass = False
    # 跨产物链（01→02→03→05 文本链/数字/标题/模板结构）——程序化防漂移的核心
    chain_report = check_chain.run(directory)
    results.append({"file": "check_chain（全链）", "checker": "check_chain",
                    "report": chain_report})
    if not chain_report["pass"]:
        all_pass = False
    # 文档一致性（受管数值/规则覆盖/断链）——2026-08-17 第 5 轮，正典一处
    docs_report = check_docs.run()
    results.append({"file": "check_docs（文档层）", "checker": "check_docs",
                    "report": docs_report})
    if not docs_report["pass"]:
        all_pass = False
    # 阶段 2 链（05→design.json→handoff→manifest）——voxvideo 素材包产物
    if args.project:
        jobs = sorted(directory.glob("05-*.md"))
        if not jobs:
            results.append({"file": "check_stage2", "checker": "check_stage2",
                            "report": {"pass": False, "issues": ["产物目录缺少 05-*.md（check_stage2 输入）"]}})
            all_pass = False
        else:
            try:
                stage2_report = check_stage2.run(jobs[0], Path(args.project))
                results.append({"file": "check_stage2（阶段 2 链）", "checker": "check_stage2",
                                "report": stage2_report})
                if not stage2_report["pass"]:
                    all_pass = False
            except FileNotFoundError as exc:
                results.append({"file": "check_stage2", "checker": "check_stage2",
                                "report": {"pass": False, "issues": [str(exc)]}})
                all_pass = False
    summary = {
        "all_pass": all_pass,
        "files": results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
