"""跨产物一致性校验（程序化：文本链/数字链/标题/模板结构——确定性检查不做给模型）。

用法：python checks/check_chain.py <产物目录>
输出：JSON 报告，非零退出码 = 有违规。

校验项：
a. 01→02 文本链：02 每镜文本按序拼接 == 01 正文（删除记录除外）
b. 02→03 文本链：03 定稿正文 == hook + 02 镜文本按序拼接
c. 数字链：素材关键数字必须保留在 01/02/03 正文（标题等取整位置不查）
d. 标题一致性：03 五件套标题 == 04 标题（及断行中的标题）
e. 04 模板结构：【核心创作任务】原文未被改写（对照模板骨架逐字）

规则假设来源：用户硬需求（2026-08-15：能程序化就程序化，需要语义理解的才用模型）
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_rewrite import extract_body
from check_storyboard import SHOT_LINE_RE

# 素材关键数字提取（日期/带单位数字/百分比，允许数字与单位间空格）
FACT_RE = re.compile(r"\d{1,2}月\d{1,2}日|\d+(?:\.\d+)?\s*(?:万亿|亿|万|%|美元|元|Token|倍|B|GB)")

# 封面模板【核心创作任务】原文（visual-cover 固化模板，逐字比对防改写）
TEMPLATE_CORE_TASK = """先理解标题背后真正要表达的关系、变化、动作或结果。
然后，把这个主题转译成右侧一个「可读但不直白」的抽象实体意象：
- 它必须由一个清晰的核心动作构成，例如连接、汇聚、对齐、推进、拆解、穿透、折叠、平衡、转化、生长或跨越。
- 画面中的物体需要有明确的隐喻关系，让观众即使不看标题，也能感到它在表达「某件事正在发生」。
- 右侧只讲一个视觉故事，使用少量精确的物体，不堆砌概念。
- 不要把主题直接画成图标、插画说明书或字面场景；要把它做成一个有材质、有结构、有动作的抽象小型装置。
- 可加入一位小比例、真实感的人物。人物负责与装置发生关键动作，例如调整、连接、推进、观察或完成最后一步。人物只作为尺度和行动感，不抢走主题。
- 如果人物会让主题变得多余或俗套，可以省略。"""


def strip_punct(text: str) -> str:
    """归一化：去空白/标点（文本链比对用，允许标点差异）。"""
    return re.sub(r"[\s，。！？、：；「」『』“”‘’\u3000,.!?;:]", "", text)


def extract_03_body(text: str) -> str:
    """03 定稿正文：在「**正文：**」标记之后（正文不是 > 引用块）。"""
    m = re.search(r"\*\*正文[：:]\*\*\s*(.+?)(?=\n---|\n##)", text, re.S)
    if m:
        return m.group(1).strip()
    return ""


def is_subsequence(seq: str, text: str) -> bool:
    """seq 是否按序出现在 text 中（子序列匹配，允许 text 缺失 seq 的删除句）。"""
    it = iter(text)
    return all(c in it for c in seq)


def shot_narrations(storyboard_text: str) -> list[str]:
    """02 分镜稿：按镜序提取旁白文本（去标注/编号）。"""
    texts = []
    for line in storyboard_text.splitlines():
        m = SHOT_LINE_RE.match(line)
        if m:
            texts.append(m.group(2).strip())
    return texts


def remove_deleted_sentences(body01: str, storyboard_text: str) -> str:
    """按 02 的删除记录，从 01 正文剔除被删句（子序列比对前）。"""
    deleted = []
    for m in re.finditer(r"「([^」]+)」→\s*删", storyboard_text):
        deleted.append(m.group(1))
    out = body01
    for d in deleted:
        out = out.replace(d, "")
    return out


def chain_01_02(body01: str, narrations: list[str], storyboard_text: str) -> list[str]:
    """02 镜文本拼接（归一化）应为 01 正文剔除删除句后的子序列。"""
    joined = "".join(strip_punct(t) for t in narrations)
    body = strip_punct(remove_deleted_sentences(body01, storyboard_text))
    if not is_subsequence(body, joined):
        i = 0
        while i < len(body) and i < len(joined) and body[i] == joined[i]:
            i += 1
        return [f"01→02 文本链失配于第 {i} 字：01[{body[max(0,i-10):i+10]}] vs 02[{joined[max(0,i-10):i+10]}]"]
    return []


def chain_02_03(narrations: list[str], body03: str) -> list[str]:
    """03 正文区块 == 02 镜拼接（hook 是独立区块，单独验证存在）。"""
    expected_n = strip_punct("".join(narrations))
    body_n = strip_punct(body03)
    if expected_n != body_n:
        return ["02→03 文本链不一致（03 正文 ≠ 02 镜拼接）"]
    return []


def chain_03_05(body03: str, text05: str, hook03: str = "") -> list[str]:
    """05 作业单 narration 逐字切分 == 03 定稿（VOX 硬约束：不改写不删句）。

    05 的 H 行 = 03 hook 区块；其余行按序拼接 = 03 正文。
    05 允许拆句（23 → 23a/23b），按序拼接后仍须与 03 逐字一致。
    确定性检查：程序做，不交给子 agent 口头确认。
    """
    narrations = []
    for line in text05.splitlines():
        m = SHOT_LINE_RE.match(line)
        if m:
            narrations.append(m.group(2).strip())
    if not narrations:
        import check_jobcard
        for s in check_jobcard.parse_table(text05):
            narrations.append(s["narration"])
    if not narrations:
        return ["03→05 文本链失败：05 未解析到任何 narration（不是作业单格式）"]
    issues = []
    # H 行 == hook（归一化标点后严格比对）
    first = strip_punct(narrations[0])
    hook_n = strip_punct(hook03)
    if hook_n and first != hook_n:
        issues.append(f"03→05 文本链失配（H 行 vs 03 hook）：05[{first}] != 03[{hook_n}]")
    # 其余行 == 03 正文
    joined = strip_punct("".join(narrations[1:]))
    body_n = strip_punct(body03)
    if joined != body_n:
        i = 0
        while i < len(body_n) and i < len(joined) and body_n[i] == joined[i]:
            i += 1
        issues.append(f"03→05 文本链失配于第 {i} 字：03[{body_n[max(0, i-10):i+10]}] vs 05[{joined[max(0, i-10):i+10]}]")
    return issues


def check_numbers(source_text: str, texts: dict[str, str]) -> list[str]:
    """素材数字（归一化去空格）必须出现在 01/02/03 正文。"""
    facts = list(dict.fromkeys(FACT_RE.findall(source_text)))
    issues = []
    for fact in facts:
        fact_n = strip_punct(fact)
        for name, text in texts.items():
            if name == "04":
                continue  # 04 允许取整（219 倍）
            if fact_n not in strip_punct(text):
                issues.append(f"数字「{fact}」缺失于 {name}")
    return issues


def check_title_consistency(text03: str, text04: str) -> list[str]:
    """03 五件套标题 == 04 标题（及断行中的标题）。"""
    m = re.search(r"- \*\*标题\*\*[：:]\s*([^（\n|]+)", text03)
    if not m:
        return ["03 未找到五件套标题"]
    title = m.group(1).strip()
    if title not in text04:
        return [f"04 未包含 03 标题「{title}」"]
    return []


def check_template_structure(text04: str) -> list[str]:
    """04 的【核心创作任务】必须与模板原文一致（防改写）。"""
    m = re.search(r"【核心创作任务】\s*(.*?)(?=【固定视觉语言】)", text04, re.S)
    if not m:
        return ["04 缺少【核心创作任务】段"]
    got = re.sub(r"^>\s?", "", m.group(1), flags=re.M).strip()
    if strip_punct(got) != strip_punct(TEMPLATE_CORE_TASK):
        return ["04 的【核心创作任务】被改写（对照模板原文）"]
    return []


def load(dir_path: Path) -> dict[str, str]:
    files = {}
    for p in sorted(dir_path.glob("0[1-5]-*.md")):
        files[p.name[:2]] = p.read_text(encoding="utf-8")
    return files


def run(dir_path: Path) -> dict:
    files = load(dir_path)
    issues: list[str] = []

    if "01" in files and "02" in files:
        body01 = extract_body(files["01"])
        narrations = shot_narrations(files["02"])
        issues += chain_01_02(body01, narrations, files["02"])
    if "02" in files and "03" in files:
        narrations = shot_narrations(files["02"])
        body03 = extract_03_body(files["03"])
        hook = re.search(r"hook[：:]\*\*\s*\n>\s*(.+)", files["03"])
        if hook is None:
            issues.append("03 缺少 hook 区块")
        issues += chain_02_03(narrations, body03)
    if "03" in files and "05" in files:
        hook_text = ""
        m = re.search(r"hook[：:]\*\*\s*\n>\s*(.+)", files["03"])
        if m:
            hook_text = m.group(1).strip()
        issues += chain_03_05(extract_03_body(files["03"]), files["05"], hook03=hook_text)
    source = ""
    for p in dir_path.glob("原始文案.txt"):
        source = p.read_text(encoding="utf-8")
    if source:
        texts = {"01": extract_body(files.get("01", "")),
                 "02": files.get("02", ""),
                 "03": extract_03_body(files.get("03", ""))}
        issues += check_numbers(source, texts)
    if "03" in files and "04" in files:
        issues += check_title_consistency(files["03"], files["04"])
    if "04" in files:
        issues += check_template_structure(files["04"])

    return {"pass": not issues, "issues": issues,
            "files": sorted(files.keys())}


def main(argv: list[str]) -> int:
    report = run(Path(argv[1]))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
