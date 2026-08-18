"""拆镜作业单校验：关卡 5 的确定性规则（程序层，0 漂移）。

用法：python checks/check_jobcard.py <05-拆镜作业单.md>
输出：JSON 报告，非零退出码 = 有违规。

校验项：
a. 镜数：头部自称（N 镜 = H + N-1）与作业表行数一致
b. 时长档 ∈ {4,6,8,10}（Flow 档位）
c. 超长句（>36 字）必须 ≥10s 档（读速 ≈4.5 字/s，实测 LESSONS D1）
d. 档位低于字数建议 → warning（读速浮动，不硬拦）
e. 参考图数量：>8 → warning（vox-prompts 典型三到五镜）
f. image_prompt 节镜号集合 == 作业表 ✅ 镜号集合（写了才出图；缺/多都违规）
g. 贯穿装置节存在；复核记录块存在
h. 差值（2026-08-17 第 2 轮，srt-vox 第 5 节翻译）：表格可选「自然时长」列（配音实测）。
   差值 = 时长档 − 自然时长；硬规律：自然 ≥3s ⟹ |差值| ≤ 1.0；短镜（<3s）≤ 3.2；
   差值率 = |差值| 合计 ÷ 生成总时长，>20% → warning（提示三选项，不硬拦）。
i. 拆镜定型（2026-08-17 第 3 轮，srt-vox 第 2 节翻译）：表格可选「型」列（解释/展示）。
   型非法 → error；展示型不拆分（拆出的 1a/1b → error）；展示型自然 >15s → warning
   （按内容分两个展示镜）；展示型超 10s 取 10（补差 ≤1.0 属平台上限）。

规则假设来源：用户硬需求（能程序化就程序化）+ vox-prompts 参考图判断规则
+ LESSONS D1 时长实测 + srt-vox storyboard-algorithm 第 2/5/6 节（两型/吸附表/差值率）。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# ---- 规则参数 ----

# 时长档位（Flow 档位，LESSONS D1：4/6/8/10）
VALID_DURATIONS = (4, 6, 8, 10)
# 字数 → 建议档位（读速 ≈4.5 字/s，来源 LESSONS D1）
DUR_BY_CHARS = ((18, 4), (27, 6), (36, 8), (10**9, 10))
# 参考图数量红线（vox-prompts「典型三到五镜」）
MAX_REFS = 8
# 差值硬规律（srt-vox 第 5 节）：自然 ≥3s ⟹ |差值| ≤ 1.0；短镜（<3s）上限 3.2
DELTA_LIMIT_GE3 = 1.0
DELTA_LIMIT_SHORT = 3.2
DELTA_RATE_WARN = 0.20

# 作业表行：| 镜号 | 时长档 | 旁白 | 参考图 | 动作要点 |（旧 5 列）
TABLE_ROW_RE = re.compile(r"^\s*\|\s*(H|\d+[a-z]?)\s*\|\s*(\d+)s\s*\|\s*(.+?)\s*\|\s*([✅—])\s*\|\s*(.+?)\s*\|\s*$")
# 作业表行（可选 6 列）：| 镜号 | 时长档 | 自然时长 | 旁白 | 参考图 | 动作要点 |
TABLE_ROW6_RE = re.compile(r"^\s*\|\s*(H|\d+[a-z]?)\s*\|\s*(\d+)s\s*\|\s*([\d.]+)?\s*\|\s*(.+?)\s*\|\s*([✅—])\s*\|\s*(.+?)\s*\|\s*$")
# 作业表行（第 3 轮起可选「型」列，第 2 列）：| 镜号 | 型 | 时长档 | [自然时长] | 旁白 | 参考图 | 动作要点 |
TABLE_ROW_TYPE_RE = re.compile(
    r"^\s*\|\s*(H|\d+[a-z]?)\s*\|\s*(解释|展示)\s*\|\s*(\d+)s\s*\|\s*(.+?)\s*\|\s*([✅—])\s*\|\s*(.+?)\s*\|\s*$")
TABLE_ROW_TYPE6_RE = re.compile(
    r"^\s*\|\s*(H|\d+[a-z]?)\s*\|\s*(解释|展示)\s*\|\s*(\d+)s\s*\|\s*([\d.]+)?\s*\|\s*(.+?)\s*\|\s*([✅—])\s*\|\s*(.+?)\s*\|\s*$")
# 头部自称镜数：拆镜作业单（N 镜 = H + N-1）
CLAIMED_RE = re.compile(r"(\d+)\s*镜\s*=\s*H\s*\+\s*(\d+)")
# image_prompt 节标题：**H 镜（…）** 或 **17 镜（…）**
IMAGE_PROMPT_RE = re.compile(r"\*\*(H|\d+[a-z]?)\s*镜")
# 复核记录块
REVIEW_BLOCK_RE = re.compile(r"##\s*复核记录")
# 贯穿装置节
THROUGH_LINE_RE = re.compile(r"##\s*贯穿装置")


def suggested_duration(chars: int) -> int:
    for limit, dur in DUR_BY_CHARS:
        if chars <= limit:
            return dur
    return 10


def parse_table(text: str) -> list[dict]:
    shots = []
    for lineno, line in enumerate(text.splitlines(), 1):
        m = None
        for rx in (TABLE_ROW_TYPE6_RE, TABLE_ROW_TYPE_RE, TABLE_ROW6_RE, TABLE_ROW_RE):
            m = rx.match(line)
            if m:
                break
        if not m:
            continue
        groups = m.groups()
        no = groups[0]
        if m.re is TABLE_ROW_RE:  # 旧 5 列：无型、无自然时长
            shot_type, natural = None, None
            dur, narration, ref, action = groups[1], groups[2], groups[3], groups[4]
        elif m.re is TABLE_ROW6_RE:  # 6 列：自然时长、无型
            shot_type = None
            dur, natural, narration, ref, action = groups[1], groups[2], groups[3], groups[4], groups[5]
        elif m.re is TABLE_ROW_TYPE_RE:  # 型 + 无自然时长
            natural = None
            shot_type, dur, narration, ref, action = groups[1], groups[2], groups[3], groups[4], groups[5]
        else:  # TABLE_ROW_TYPE6_RE：型 + 自然时长
            shot_type, dur, natural, narration, ref, action = groups[1:]
        shots.append({
            "no": no, "lineno": lineno,
            "type": shot_type,
            "dur": int(dur),
            "natural": float(natural) if natural not in (None, "") else None,
            "chars": len(narration),
            "ref": ref == "✅",
            "narration": narration.strip(),
            "action": action.strip(),
        })
    return shots


def check_counts(text: str, shots: list[dict]) -> list[dict]:
    issues = []
    m = CLAIMED_RE.search(text)
    actual = len(shots)
    if m:
        claimed_total = int(m.group(1))
        if claimed_total != actual:
            issues.append({
                "type": "镜数不符",
                "claimed": claimed_total,
                "actual": actual,
                "fix": "头部自称镜数与作业表行数统一",
            })
    elif not shots:
        issues.append({"type": "镜数", "claimed": "—", "actual": actual,
                       "fix": "未找到作业表行（| 镜号 | 时长档 | 旁白 | 参考图 | 动作要点 |）"})
    else:
        issues.append({"type": "镜数", "claimed": "—", "actual": actual,
                       "fix": "头部缺少「（N 镜 = H + N-1）」自称", "severity": "warning"})
    return issues


def check_durations(shots: list[dict]) -> list[dict]:
    issues = []
    for s in shots:
        if s["dur"] not in VALID_DURATIONS:
            issues.append({"type": "时长档非法", "shot": s["no"], "dur": s["dur"],
                           "fix": f"档位 ∈ {list(VALID_DURATIONS)}"})
            continue
        want = suggested_duration(s["chars"])
        if s["dur"] < want:
            if s["chars"] > 36:
                issues.append({"type": "超长句档位不足", "shot": s["no"], "chars": s["chars"],
                               "dur": s["dur"], "fix": f">36 字必须 ≥10s（当前 {s['dur']}s）"})
            else:
                issues.append({"type": "档位建议", "shot": s["no"], "chars": s["chars"],
                               "dur": s["dur"], "suggest": want,
                               "fix": f"建议 {want}s（读速浮动可豁免）", "severity": "warning"})
    return issues


def check_refs(text: str, shots: list[dict]) -> list[dict]:
    issues = []
    ref_shots = {s["no"] for s in shots if s["ref"]}
    prompt_shots = {m.group(1) for m in IMAGE_PROMPT_RE.finditer(text)}
    if len(ref_shots) > MAX_REFS:
        issues.append({"type": "参考图过多", "count": len(ref_shots),
                       "fix": f"vox-prompts 典型三到五镜，最多 {MAX_REFS} 张（再少也要有理由）",
                       "severity": "warning"})
    missing = sorted(ref_shots - prompt_shots)
    extra = sorted(prompt_shots - ref_shots)
    if missing:
        issues.append({"type": "image_prompt 缺失", "shots": missing,
                       "fix": "作业表标 ✅ 的镜必须有 image_prompt 节（写了才出图）"})
    if extra:
        issues.append({"type": "image_prompt 多余", "shots": extra,
                       "fix": "未标 ✅ 的镜不该有 image_prompt 节（不写才不出图）"})
    return issues


def check_structure(text: str) -> list[dict]:
    issues = []
    if not THROUGH_LINE_RE.search(text):
        issues.append({"type": "贯穿装置缺失", "fix": "文件需有「## 贯穿装置」节（决策项，用户要拍板）"})
    if not REVIEW_BLOCK_RE.search(text):
        issues.append({"type": "复核记录缺失", "fix": "文件需有「## 复核记录」块（无标记 = 未完成）"})
    return issues


# 型列非法行：| 镜号 | <非解释/展示> | <时长s> | ...（第 2 列既不是合法型也不是旧格式时长档）
TYPE_INVALID_RE = re.compile(r"^\s*\|\s*(H|\d+[a-z]?)\s*\|\s*([^|]+?)\s*\|\s*(\d+)s\s*\|")
TYPE_VALID = ("解释", "展示")


def check_type(shots: list[dict], text: str) -> list[dict]:
    """拆镜定型校验（2026-08-17 第 3 轮，srt-vox 第 2 节翻译）。

    仅当作业表表头含「型」列时启用——旧 5 列/6 列格式（无型）不启用，
    防误伤汇总时长表等旁表行（宇树 05 的 | H | 24 | 6s |… 汇总行曾误报）。
    """
    issues = []
    has_type_header = bool(re.search(
        r"^\s*\|\s*镜[^|]*\|\s*型\s*\|", text, re.M))
    if not has_type_header:
        return issues
    for line in text.splitlines():
        m = TYPE_INVALID_RE.match(line)
        if m and m.group(2).strip() not in TYPE_VALID:
            issues.append({"type": "型非法", "shot": m.group(1), "value": m.group(2).strip(),
                           "fix": "「型」列 ∈ 解释/展示（srt-vox 第 2 节两型）"})
    for s in shots:
        if s["type"] == "展示":
            # 展示型不拆分（镜号带字母后缀 = 拆分产物）
            if re.search(r"[a-z]$", s["no"]):
                issues.append({"type": "展示型拆分", "shot": s["no"],
                               "fix": "展示型不拆分：超 11s 封顶 10s，靠末帧定格补足"})
            if s["natural"] is not None:
                if s["natural"] > 15.0:
                    issues.append({"type": "展示型超15s", "shot": s["no"], "natural": s["natural"],
                                   "fix": "展示型自然 >15s 按内容分成两个展示镜（每镜展示一部分）",
                                   "severity": "warning"})
                want = 10 if s["natural"] > 10 else min(
                    VALID_DURATIONS, key=lambda c: (abs(c - s["natural"]), c))
                if s["dur"] != want:
                    issues.append({"type": "展示型档位", "shot": s["no"], "dur": s["dur"],
                                   "natural": s["natural"], "want": want,
                                   "fix": f"展示型取最接近档 {want}s（超 10 取 10，不拆分）"})
    return issues


def check_delta(shots: list[dict]) -> list[dict]:
    """差值校验（2026-08-17 第 2 轮，srt-vox 第 5 节翻译）。

    只查提供了「自然时长」列的镜（配音实测）；留空 = 未提供，跳过（旧产物兼容）。
    """
    issues = []
    provided = [s for s in shots if s["natural"] is not None]
    if not provided:
        return issues
    for s in provided:
        delta = s["dur"] - s["natural"]
        # 例外二：展示型自然 >11s 封顶 10s，补差可超 1.0（平台上限）
        is_display_cap = s["type"] == "展示" and s["natural"] > 11.0
        if s["natural"] < 3.0:
            if abs(delta) > DELTA_LIMIT_SHORT + 0.051:
                issues.append({"type": "短镜差值超限", "shot": s["no"], "natural": s["natural"],
                               "dur": s["dur"], "delta": round(delta, 2),
                               "fix": f"短镜（自然 <3s）余量 ≤ {DELTA_LIMIT_SHORT}s（4s 地板 − 0.8s 下限）"})
        elif abs(delta) > DELTA_LIMIT_GE3 + 0.051 and not is_display_cap:
            issues.append({"type": "差值破硬规律", "shot": s["no"], "natural": s["natural"],
                           "dur": s["dur"], "delta": round(delta, 2),
                           "fix": f"自然 ≥3s ⟹ |差值| ≤ {DELTA_LIMIT_GE3}s（就近吸附，分界 5/7/9）"})
    # 差值率只算解释型（srt-vox 定义：解释型 |差值| 合计 ÷ 解释型生成总时长）
    explain = [s for s in provided if s["type"] != "展示"]
    total_gen = sum(s["dur"] for s in explain)
    if total_gen:
        rate = sum(abs(s["dur"] - s["natural"]) for s in explain) / total_gen
        if rate > DELTA_RATE_WARN:
            issues.append({"type": "差值率偏高", "rate": round(rate, 4),
                           "fix": f"差值率 {rate:.1%} > 20%：a. 接受（逐镜写收束动作）"
                                  f"b. 并列短镜合成一镜 c. 回配音稿合并过碎句",
                           "severity": "warning"})
    return issues


def check_split(shots: list[dict]) -> list[dict]:
    """超限拆分 + 桥接（2026-08-17 第 4 轮，srt-vox 第 7 节翻译）。

    - 解释型自然时长 >11s 必须拆（片段号带字母后缀；10-11s 不拆，取 10 档补差）
    - 拆分镜 a/b 成对（有 a 必有 b；前缀相同）——桥接帧 ID 一致性的程序层近似
    """
    issues = []
    has_natural = any(s["natural"] is not None for s in shots)
    split_ids = [s["no"] for s in shots if re.search(r"[a-z]$", s["no"] or "")]
    if split_ids:
        # a/b 成对：统计每个前缀的字母数，缺 b（或字母数不齐）→ error
        from collections import Counter
        seen: dict[str, list[str]] = {}
        for sid in split_ids:
            m = re.match(r"^(H|\d+)([a-z])$", sid)
            if not m:
                continue
            seen.setdefault(m.group(1), []).append(m.group(2))
        for prefix, letters in seen.items():
            if "a" not in letters or "b" not in letters:
                issues.append({"type": "拆分不成对", "shots": sorted(
                    f"{prefix}{c}" for c in letters),
                    "fix": "拆分镜 a/b 必须成对（桥接帧：a 末帧 = b 第 0 帧，抽帧衔接）"})
    if not has_natural:
        return issues
    for s in shots:
        if s["type"] == "展示" or s["natural"] is None:
            continue
        if s["natural"] > 11.0 and not re.search(r"[a-z]$", s["no"]):
            issues.append({"type": "超限未拆分", "shot": s["no"], "natural": s["natural"],
                           "fix": "解释型自然 >11s 必须拆分 + 桥接帧（10-11s 不拆，取 10 档补差）"})
    return issues


def run(text: str) -> dict:
    shots = parse_table(text)
    issues = (
        check_counts(text, shots)
        + check_durations(shots)
        + check_refs(text, shots)
        + check_structure(text)
        + check_delta(shots)
        + check_type(shots, text)
        + check_split(shots)
    )
    errors = [i for i in issues if i.get("severity") != "warning"]
    refs = [s["no"] for s in shots if s["ref"]]
    delta_rows = [s for s in shots if s["natural"] is not None]
    delta_rate = None
    explain = [s for s in delta_rows if s["type"] != "展示"]
    if explain:
        total_gen = sum(s["dur"] for s in explain)
        if total_gen:
            delta_rate = round(
                sum(abs(s["dur"] - s["natural"]) for s in explain) / total_gen, 4)
    return {
        "pass": not errors,
        "issues": issues,
        "stats": {
            "shots": len(shots),
            "refs": len(refs),
            "ref_shots": refs,
            "duration_dist": {d: sum(1 for s in shots if s["dur"] == d) for d in VALID_DURATIONS},
            "total_seconds": sum(s["dur"] for s in shots),
            "total_flow_seconds": int(sum(s["dur"] for s in shots) * 0.9),
            "delta_rate": delta_rate,
        },
    }


def main(argv: list[str]) -> int:
    path = Path(argv[1])
    text = path.read_text(encoding="utf-8")
    report = run(text)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
