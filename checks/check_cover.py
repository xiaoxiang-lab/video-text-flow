"""封面提示词校验：visual-cover 硬规则（程序层，0 漂移）。

用法：python checks/check_cover.py <封面出图提示词.md>
输出：JSON 报告，非零退出码 = 有违规。
规则假设来源：实测（排版/解码动作不内置 = 生图丢参数，用户实测）/ 偏好（禁止清单）。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# ---- 规则参数 ----

# 排版参数必须内置（实测教训：生图模型只看提示词正文）——按类别必需，各类至少命中一个
LAYOUT_CATEGORIES = {
    "画幅": ("16:9", "5:2", "4:5", "1:1"),
    "占比": ("%", "55", "45", "占比"),
    "断行": ("两行", "断行", "第一行", "第二行"),
    "强调": ("强调", "青蓝", "高饱和红", "墨绿", "强调色"),
    "无其他文字": ("除标题外", "无任何其他文字", "不含任何文字"),
}
# 解码动作/隐喻说明必须内置（实测教训：模型不理解「为什么这么设计」）
METAPHOR_MARKERS = ("隐喻", "转译", "代表", "意味着", "表达", "核心动作")
# 禁止清单（偏好：模板禁止项）
FORBIDDEN_WORDS = ("赛博朋克", "霓虹", "蓝紫渐变", "机器人", "芯片", "科幻城市",
                   "仪表盘", "满屏", "卡通", "家居", "廉价3D", "夸张光效")
# 模式 A/B 必须齐全
MODE_RE = re.compile(r"模式\s*[AB]")

# 提取提示词正文（> 开头的引用块）
PROMPT_BLOCK_RE = re.compile(r"^>\s?(.+)$", re.MULTILINE)


def extract_prompts(text: str) -> list[str]:
    return [m.group(1) for m in PROMPT_BLOCK_RE.finditer(text)]


def check_layout(prompts: list[str]) -> list[dict]:
    issues = []
    if not prompts:
        return [{"type": "无提示词块", "fix": "模式 A 提示词必须存在"}]
    body = "\n".join(prompts)
    for category, markers in LAYOUT_CATEGORIES.items():
        if not any(m in body for m in markers):
            issues.append({"type": f"排版参数未内置（{category}）",
                           "fix": f"提示词正文必须包含 {category} 类参数（{'/'.join(markers[:3])}…）"})
    return issues


def check_metaphor(prompts: list[str]) -> list[dict]:
    body = "\n".join(prompts)
    if not any(m in body for m in METAPHOR_MARKERS):
        return [{"type": "解码动作未内置", "fix": "提示词开头必须有隐喻说明句（转译/隐喻/代表）"}]
    return []


def check_forbidden(prompts: list[str]) -> list[dict]:
    """禁止词只能出现在「禁止/避免」句里，不得出现在画面描述。"""
    issues = []
    for prompt in prompts:
        # 去掉禁止句（禁止/避免 之后的部分）再查
        cleaned = re.split(r"(禁止|避免|不要)", prompt)[0]
        for w in FORBIDDEN_WORDS:
            if w in cleaned:
                issues.append({"type": "禁止词出现在画面描述", "word": w,
                               "evidence": cleaned[:60], "fix": "移到禁止清单句"})
    return issues


def check_modes(text: str) -> list[dict]:
    modes = MODE_RE.findall(text)
    a, b = any("A" in m for m in modes), any("B" in m for m in modes)
    if not (a and b):
        return [{"type": "模式不齐全", "fix": "模式 A（带字直生）+ 模式 B（纯意象兜底）都要有"}]
    return []


def run(text: str) -> dict:
    prompts = extract_prompts(text)
    issues = (
        check_layout(prompts)
        + check_metaphor(prompts)
        + check_forbidden(prompts)
        + check_modes(text)
    )
    return {
        "pass": not issues,
        "issues": issues,
        "stats": {"prompt_blocks": len(prompts),
                  "has_mode_a": "模式 A" in text or "模式A" in text,
                  "has_mode_b": "模式 B" in text or "模式B" in text},
    }


def main(argv: list[str]) -> int:
    path = Path(argv[1])
    text = path.read_text(encoding="utf-8")
    report = run(text)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
