# -*- coding: utf-8 -*-
"""更新现有 5 个 guide 的尾部句式：旧「结尾稳定保持 0.8 秒」→ 差值分档（正典一处）。
并给 3 个重合风格 json 加样图 reference_files。"""
import json
import re
from pathlib import Path

ROOT = Path(r"C:\Users\xx\Documents\Default Project")
GUIDES = [
    "ref/blueprint-craft/guide.zh.md",
    "ref/fresh-scrapbook/guide.zh.md",
    "ref/ink-scroll/guide.zh.md",
    "ref/minimal-motion/guide.zh.md",
    "ref/warm-illustration/guide.zh.md",
]

for rel in GUIDES:
    p = ROOT / rel
    text = p.read_text(encoding="utf-8")
    new = text.replace(
        "落点停在[元素定格]的那一刻。结尾稳定保持 0.8 秒。",
        "落点停在[元素定格]的那一刻。结尾按尾部契约选档（余量档静止收束/补差档末帧定格，见通用规则）。",
    ).replace(
        "落点停在[定格]。结尾稳定保持 0.8 秒。",
        "落点停在[定格]。结尾按尾部契约选档。",
    )
    n = new.count("尾部契约选档")
    p.write_text(new, encoding="utf-8")
    print(f"{rel}: 尾部契约 {n} 处")

# 3 个重合风格加样图引用（升级资产）
UPGRADES = {
    "minimal-motion": "ref/style-assets/style-samples/S07-极简几何.jpg",
    "ink-scroll": "ref/style-assets/style-samples/S08-水墨长卷.jpg",
    "blueprint-craft": "ref/style-assets/style-samples/S11-产品蓝图.jpg",
}
for sid, sample in UPGRADES.items():
    p = ROOT / "config" / "styles" / f"{sid}.json"
    reg = json.loads(p.read_text(encoding="utf-8"))
    refs = reg.setdefault("reference_files", [])
    if sample not in refs:
        refs.append(sample)
    p.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{sid}.json: reference_files={refs}")