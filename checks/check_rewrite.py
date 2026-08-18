"""立场重写稿校验：human-writing 成稿禁令的确定性规则（程序层，0 漂移）。

用法：python checks/check_rewrite.py <重写稿.md>
输出：JSON 报告（pass/issues/stats），非零退出码 = 有违规。
规则假设来源标注：偏好（human-writing 成稿禁令）/ 实测（长列举 20s 可念线）。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# ---- 规则参数（假设来源：偏好 = human-writing 成稿禁令） ----

# 提示性冒号：冒号前分句尾部命中这些词 = 提示性（违规）。
# 例外：冒号前分句含「说/写道/表示/回应」等引语动词 = 引语冒号（允许）。
COLON_LEADERS = (
    "说明", "思考", "执行", "设计", "意味着", "很明确", "总结", "核心", "问题",
    "答案", "做法", "逻辑", "判断", "结论", "信号", "提醒", "告诉", "看法",
    "目标", "定义", "方式", "方案", "建议", "原理", "道理", "关键", "重点",
    "情况", "事实", "道理", "好处", "坏处", "理由", "原因",
)
QUOTE_VERBS = ("说", "写道", "表示", "回应", "写着", "写道")

# 破折号（假设来源：偏好）
DASHES = ("——", "—", "–")

# 同构排比（假设来源：偏好，≤2 项为限）：连续的「X 可以换/Y 能换/…」结构
# (?<!都) 排除「也都能换」的误匹配（「能换」前是「都」不是并列项）
PARALLEL_PATTERNS = r"([^，。；：！？]{1,12})(?<!都)(?:可以换|能换|可换|可以拆|可以改|能改|可以组合)"

# 长列举：单句逗号分隔 ≥6 项且 >20 字，且**含动词的项占比 ≥50%**（假设来源：实测口播可念线）
# 名词列举（电机、减速器、丝杠…）念起来不累，不算长列举；短语列举（读文件、改代码…）才算
LONG_LIST_ITEMS = 6
LONG_LIST_MIN_LEN = 20
LONG_LIST_VERB_RATIO = 0.5
VERBS = (
    "读", "改", "调", "搜", "管", "跑", "检查", "写", "看", "做", "拿", "放",
    "买", "卖", "算", "记", "找", "开", "关", "接", "拆", "装", "推", "拉",
    "提", "举", "切", "合", "拼", "排", "转", "移", "换", "量", "测", "试",
    "生成", "处理", "执行", "管理", "搜索", "调用", "运行", "提交", "发布",
    "下载", "上传", "迁移", "规划", "分析", "跟踪", "调试", "部署", "维护",
)

# 翻案腔（假设来源：human-writing 成稿禁令——先立一个读者没有的误解再推翻）
# 已知外衣（举例不是边界，但程序只查确定性句式；变形靠语义层子 agent）：
# 「不是A，而是B」「并非A，而是B」「不在于A，而在于B」「表面A，实际B」「看似A，实则B」
FLIP_PATTERNS = (
    r"不是[^。；\n]{1,30}，而是",
    r"不是[^。；\n]{1,30}。\s*而是",
    r"并非[^。；\n]{1,30}，而是",
    r"不在于[^。；\n]{1,30}，而在于",
    r"表面[^。；\n]{1,30}，实际[上是]?",
    r"看似[^。；\n]{1,30}，实则",
)

# 正文提取：只查「> 」引用块（口播正文），跳过 frontmatter 与元信息区
# 注意：[ \t]? 不能用 \s?——\s 匹配换行，会导致跨行匹配吞掉下一行的「> 」（实测 bug）
BODY_LINE_RE = re.compile(r"^>[ \t]?(.+)$", re.MULTILINE)


def extract_body(text: str) -> str:
    lines = [m.group(1) for m in BODY_LINE_RE.finditer(text)]
    if lines:
        return "\n".join(lines)
    # 无引用块时兜底：跳过 --- 之间的 frontmatter 与「## 」标题区
    parts = re.split(r"^---\s*$", text, flags=re.MULTILINE)
    body = parts[-1] if len(parts) > 1 else text
    body = "\n".join(l for l in body.splitlines() if not l.startswith("#") and not l.startswith("- ") and l.strip())
    return body

# ---- 检测实现 ----

def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"[。！？\n]", text) if s.strip()]


def check_colons(text: str) -> list[dict]:
    """提示性冒号检测：违规 = 冒号前分句尾部命中引导词，且无引语动词。"""
    issues = []
    for m in re.finditer("：", text):
        start = m.start()
        before = text[:start]
        # 取冒号前最近的分句（按句末标点切）
        clause = re.split(r"[。！？\n]", before)[-1]
        tail = clause.strip()
        if not tail:
            continue
        has_quote_verb = any(tail.endswith(v) for v in QUOTE_VERBS)
        is_leader = any(tail.endswith(w) for w in COLON_LEADERS)
        if is_leader and not has_quote_verb:
            issues.append({
                "type": "提示性冒号",
                "pos": start,
                "evidence": tail + "：",
                "fix": "改句号或逗号断句",
            })
    return issues


def check_dashes(text: str) -> list[dict]:
    issues = []
    for d in DASHES:
        for m in re.finditer(re.escape(d), text):
            issues.append({"type": "破折号", "pos": m.start(), "evidence": d, "fix": "删除或改标点"})
    return issues


def check_parallels(text: str) -> list[dict]:
    """同构排比：同一句内同构模式命中 ≥3 次 = 违规（允许 2 项）。"""
    issues = []
    for sent in _split_sentences(text):
        hits = list(re.finditer(PARALLEL_PATTERNS, sent))
        if len(hits) >= 3:
            issues.append({
                "type": "同构排比≥3项",
                "evidence": sent[:60],
                "fix": "压缩到 2 项，其余换说法",
            })
    return issues


def check_long_lists(text: str) -> list[dict]:
    issues = []
    for sent in _split_sentences(text):
        parts = [p for p in re.split(r"[，,、]", sent) if p]
        if len(parts) >= LONG_LIST_ITEMS and len(sent) > LONG_LIST_MIN_LEN:
            # 动宾项判据：以动词开头且 ≥3 字（「关节」「算法」这类 2 字名词以动词字开头，排除）
            verb_items = sum(1 for p in parts
                             if any(p.startswith(v) and len(p) >= 3 for v in VERBS))
            if verb_items / len(parts) >= LONG_LIST_VERB_RATIO:
                issues.append({
                    "type": "长列举",
                    "evidence": sent[:60],
                    "fix": "按语义拆成两句（单口气 >20s 不可念）",
                })
    return issues


def check_flip_sentences(text: str) -> list[dict]:
    """翻案腔检测：命中已知外衣句式 = 违规（human-writing 硬禁令）。"""
    issues = []
    for pat in FLIP_PATTERNS:
        for m in re.finditer(pat, text):
            issues.append({
                "type": "翻案腔",
                "evidence": m.group(0)[:60],
                "fix": "正面直陈：先给判断再给依据，不立误解再推翻",
            })
    return issues


def check_key_facts(text: str, key_facts: list[str]) -> list[dict]:
    """关键事实保留核对（假设来源：立场重写规则——事实不丢）。
    key_facts 由调用方传入（素材关键数字/术语）。"""
    issues = []
    for fact in key_facts:
        if fact and fact not in text:
            issues.append({"type": "关键事实缺失", "evidence": fact, "fix": "补回原文事实"})
    return issues


def run(text: str, key_facts: list[str] | None = None) -> dict:
    body = extract_body(text)
    issues = (
        check_colons(body)
        + check_dashes(body)
        + check_parallels(body)
        + check_long_lists(body)
        + check_flip_sentences(body)
        + check_key_facts(body, key_facts or [])
    )
    return {
        "pass": not issues,
        "issues": issues,
        "stats": {
            "sentences": len(_split_sentences(body)),
            "chars": len(body),
            "colons": body.count("："),
            "dashes": sum(body.count(d) for d in DASHES),
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
