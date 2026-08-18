"""分镜稿校验：分镜稿模式的确定性规则（程序层，0 漂移）。

用法：python checks/check_storyboard.py <分镜稿.md>
输出：JSON 报告，非零退出码 = 有违规。
规则假设来源：实测（9s/12 字残句线，子 agent 复核案例）/ 偏好（类型红线）。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# ---- 规则参数 ----

MAX_CHARS = 60          # 单句 ≤60 字 ≈9s（实测：模型单段上限 10s，vox-director 蒸馏）
SPLIT_WARN_CHARS = 45   # 45-60 字：Flow 档位不足预警（拆句提示，>45 字必超 8s 档）
MIN_SHOT_CHARS = 12     # 残句线：<12 字（衔接词起头超短残句必须合回，实测）
# 条件从句残句：条件词开头且【无逗号主句】= 话没说完（「如果 X，主句。」是完整复句，不算）
# 「当」已移除（「当然」误报）；「说它…」是宾语从句非条件从句
CLAUSE_STARTERS = ("如果", "因为", "只要", "假如", "虽然", "尽管")
SHORT_SHOT_ALLOWLIST = ("便宜", "为什么", "没错", "正是", "停")  # 刻意短镜豁免（程序标 warning）

# 分镜行格式：【来源标注】旁白文本（或 编号. 【标注】文本）
SHOT_LINE_RE = re.compile(r"^\s*\d+[a-z]?\.?\s*【([^】]+)】(.+)$")

# 自称镜数：文件头「分镜稿（N 镜…）」或「（N 镜」
COUNT_RE = re.compile(r"(\d+)\s*镜")


def parse_shots(text: str) -> list[dict]:
    shots = []
    for lineno, line in enumerate(text.splitlines(), 1):
        m = SHOT_LINE_RE.match(line)
        if not m:
            continue
        label, body = m.group(1), m.group(2)
        # 去掉行内编号（如 18a. 前缀已在正则外）与尾部注记
        narration = body.strip()
        shots.append({
            "no": len(shots) + 1,
            "lineno": lineno,
            "label": label.strip(),
            "narration": narration,
            "chars": len(narration),
        })
    return shots


def check_counts(text: str, shots: list[dict]) -> list[dict]:
    issues = []
    m = COUNT_RE.search(text.split("\n\n")[0])  # 头部自称镜数
    if m and int(m.group(1)) != len(shots):
        issues.append({
            "type": "镜数不符",
            "claimed": int(m.group(1)),
            "actual": len(shots),
            "fix": "统一为实际镜数",
        })
    if not shots:
        issues.append({
            "type": "镜数",
            "claimed": m.group(1) if m else "—",
            "actual": 0,
            "fix": "解析到 0 镜：该文件不是分镜格式（03 定稿是段落文本，走 check_chain 链层校验），防假通过",
        })
    return issues


def check_lengths(shots: list[dict]) -> list[dict]:
    issues = []
    for s in shots:
        if s["chars"] > MAX_CHARS:
            issues.append({"type": "超时镜>60字", "shot": s["no"], "chars": s["chars"],
                           "evidence": s["narration"][:40], "fix": "拆分"})
        elif s["chars"] > SPLIT_WARN_CHARS:
            issues.append({"type": "建议拆句>45字", "shot": s["no"], "chars": s["chars"],
                           "evidence": s["narration"][:30],
                           "fix": ">45 字必超 Flow 8s 档（拆镜时需 10s 或拆句），建议分镜阶段提前拆",
                           "severity": "warning"})
        elif s["chars"] < MIN_SHOT_CHARS and not any(w in s["narration"] for w in SHORT_SHOT_ALLOWLIST):
            issues.append({"type": "超短残句<12字", "shot": s["no"], "chars": s["chars"],
                           "evidence": s["narration"], "fix": "合回相邻镜", "severity": "warning"})
    return issues


def check_clause_starts(shots: list[dict]) -> list[dict]:
    issues = []
    for s in shots:
        head = s["narration"].lstrip("，,、 ")
        if any(head.startswith(starter) for starter in CLAUSE_STARTERS):
            # 无逗号 = 没有主句部分 = 残句；有逗号（如「如果 X，主句。」）= 完整复句
            if "，" not in head and "," not in head:
                issues.append({"type": "条件从句独立成镜", "shot": s["no"],
                               "evidence": head[:30], "fix": "合回主句或改直陈"})
    return issues


def check_labels(shots: list[dict]) -> list[dict]:
    issues = []
    for s in shots:
        if not re.search(r"(第\d+句|拆自|合并|原文|v\d)", s["label"]):
            issues.append({"type": "来源标注格式异常", "shot": s["no"], "evidence": s["label"],
                           "fix": "标注为【第X句】/【拆自 第X句…】", "severity": "warning"})
    return issues


def check_question_runs(shots: list[dict]) -> list[dict]:
    """设问镜连续 ≥3 = 红线（修辞型连续；定义/论证链由子 agent 裁决，程序只报告）。"""
    runs = []
    cur = []
    for s in shots:
        if "？" in s["narration"] or "?" in s["narration"]:
            cur.append(s["no"])
        else:
            if len(cur) >= 3:
                runs.append(cur[:])
            cur = []
    if len(cur) >= 3:
        runs.append(cur[:])
    issues = []
    for r in runs:
        issues.append({"type": "设问镜连续≥3", "shots": r,
                       "fix": "插入非设问镜；若属定义/论证链请在复核记录注明豁免口径",
                       "severity": "warning"})
    return issues


def run(text: str) -> dict:
    shots = parse_shots(text)
    issues = (
        check_counts(text, shots)
        + check_lengths(shots)
        + check_clause_starts(shots)
        + check_labels(shots)
        + check_question_runs(shots)
    )
    errors = [i for i in issues if i.get("severity") != "warning"]
    return {
        "pass": not errors,
        "issues": issues,
        "stats": {"shots": len(shots),
                  "max_chars": max((s["chars"] for s in shots), default=0),
                  "question_shots": sum(1 for s in shots if "？" in s["narration"])},
    }


def main(argv: list[str]) -> int:
    path = Path(argv[1])
    text = path.read_text(encoding="utf-8")
    report = run(text)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
