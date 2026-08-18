"""check_docs：文档一致性校验（2026-08-17 第 5 轮，srt-vox check_docs 判据翻译）。

用法：python checks/check_docs.py
输出：JSON 报告，非零退出码 = 有违规。

校验项：
a. 受管数值扫描（正典一处，DECISIONS 2026-08-17）：档位 4/6/8/10、分界 5/7/9、
   差值阈值 1.0/3.2、拆分线 11s、尾部静止 0.2/0.6/0.8 秒、混音 0.6/1.5——
   只允许出现在正典代码文件；文档（docs/skills/README 等）只准引用不写数值。
b. 规则实现覆盖（P6 防复发）：checks/rule-coverage.json 每条规则 →
   校验器 source 符号存在 + 对应测试文件含 keyword。
c. 断链/引用：md 文档的相对链接（[x](path)、![x](path)、`checks/xxx`、`scripts/xxx`）
   目标必须存在（排除 vendor/ 与外部 URL）。

规则假设来源：DECISIONS 2026-08-17 正典一处原则 + LESSONS P6（建校验器必须对照规则
全文逐条翻译，不留空白）。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
CHECKS_DIR = Path(__file__).resolve().parent
COVERAGE_FILE = CHECKS_DIR / "rule-coverage.json"
# 受管数值的正典文件（允许出现这些数值的代码文件）
CANON_FILES = {
    "check_jobcard.py": {"4, 6, 8, 10", "1.0", "3.2", "5/7/9", "0.2", "0.6", "0.8", "1.5"},
    "check_stage2.py": {"4, 6, 8, 10", "1.0", "3.2", "0.2", "0.6", "0.8", "1.5"},
    "check_docs.py": set(),
    "handoff.py": {"4, 6, 8, 10"},
    "merge-video.py": {"4, 6, 8, 10", "0.6", "1.5"},
    "flow_slot": {"5/7/9"},
}
# 受管数值模式（规则性表述，非实测记录）——文档里出现即违规
MANAGED_PATTERNS = [
    (r"档位\s*[∈=:：]?\s*[{\[]?\s*4\s*[,，/、]\s*6\s*[,，/、]\s*8\s*[,，/、]\s*10", "档位列举 4/6/8/10"),
    (r"分界(?:点)?\s*[=:：]?\s*5\s*[,，/、]\s*7\s*[,，/、]\s*9", "分界点 5/7/9"),
    (r"差值[^。\n]{0,12}1\.0\s*秒", "差值阈值 1.0 秒"),
    (r"短镜[^。\n]{0,12}3\.2\s*秒", "短镜上限 3.2 秒"),
    (r"结尾稳定保持 0\.8 秒", "旧尾部常量 0.8 秒（已退役，按差值分档）"),
    (r"(?:音效|bgm)[^。\n]{0,10}0\.6", "混音比例 0.6（音效）"),
    (r"旁白[^。\n]{0,10}1\.5", "混音比例 1.5（旁白）"),
]
# 受管数值扫描范围（会被当规则引用的文档）——排除 vendored 快照（skills/srtvox-director/）、
# 台账（PROGRESS/DECISIONS/NEXTSESSION）与实测日志（LESSONS.md，记录历史事实不算规则引用）
MANAGED_DOCS = [
    "README.md", "START.md", "关卡定义.md", "校验器设计说明.md",
    "docs/**/*.md",
    "skills/chupian-vox/SKILL.md", "skills/chupian-vox/style-library.zh.md",
    "skills/flow-generate/SKILL.md",
]
# 断链扫描范围（我们的文档；skill 快照链接外部是常态，不扫）
LINK_GLOBS = [
    "README.md", "START.md", "关卡定义.md", "校验器设计说明.md",
    "docs/**/*.md", "skills/README.md",
]
LINK_EXCLUDE = {"vendor", "projects", "outputs", "srtvox-director"}

# 外部文档根（2026-08-17 第二步）：voxvideo 项目的风格文档（guide/master/注册 json）
# 也遵守正典一处（约束 4：风格文档不得写受管数值）。路径可注入（测试用）。
EXTRA_STYLE_ROOTS = [
    str(Path(r"C:\Users\xx\Documents\Default Project\ref")),
    str(Path(r"C:\Users\xx\Documents\Default Project\config\styles")),
]


def scan_managed_values(root: Path | None = None, doc_globs: list[str] | None = None,
                        exclude: set[str] | None = None,
                        extra_roots: list[str] | None = None) -> list[str]:
    """扫描文档里的受管数值表述（正典一处）。root/doc_globs 可注入（测试用）。"""
    issues = []
    root = root or ROOT
    doc_globs = doc_globs if doc_globs is not None else MANAGED_DOCS
    exclude = exclude or LINK_EXCLUDE
    extra_roots = extra_roots if extra_roots is not None else EXTRA_STYLE_ROOTS
    # 项目内文档
    for glob in doc_globs:
        for path in root.glob(glob):
            if not path.is_file() or any(part in exclude for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                for pattern, label in MANAGED_PATTERNS:
                    if re.search(pattern, line) and "受管数值豁免" not in line:
                        issues.append(
                            f"{path.relative_to(root)}:{lineno} 受管数值外泄（{label}）："
                            f"「{line.strip()[:60]}」——正典一处：数值只出现在正典文件，"
                            f"此处改引用不写数值")
    # 外部风格文档根（guide/master/注册 json 与评级表同纪律）
    for extra in extra_roots:
        eroot = Path(extra)
        if not eroot.exists():
            issues.append(
                f"外部风格文档根不存在：{extra}——正典一处扫描漏扫，检查路径配置或恢复目录")
            continue
        for path in sorted(eroot.rglob("*.md")) + sorted(eroot.rglob("*.txt")) + sorted(eroot.rglob("*.json")):
            if "style-assets/work" in str(path):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                for pattern, label in MANAGED_PATTERNS:
                    if re.search(pattern, line) and "受管数值豁免" not in line:
                        issues.append(
                            f"{path}:{lineno} 受管数值外泄（{label}）："
                            f"「{line.strip()[:60]}」——正典一处：数值只出现在正典文件，"
                            f"此处改引用不写数值")
    return issues


def check_rule_coverage(coverage_file: Path | None = None,
                        checks_dir: Path | None = None) -> list[str]:
    """规则实现覆盖（P6 防复发）：映射表每条规则 source 符号存在 + 测试含 keyword。"""
    issues = []
    coverage_file = coverage_file or COVERAGE_FILE
    checks_dir = checks_dir or CHECKS_DIR
    if not coverage_file.exists():
        return [f"rule-coverage.json 不存在（{coverage_file}）——规则映射表是 check_docs 的输入"]
    try:
        data = json.loads(coverage_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"rule-coverage.json 解析失败：{exc}"]
    for rule in data.get("rules", []):
        rid, source, test = rule.get("id"), rule.get("source", ""), rule.get("test", "")
        keyword = rule.get("keyword", "")
        if not (rid and source and test):
            issues.append(f"规则 {rid} 映射表缺字段（id/source/test 必填）")
            continue
        # source: module.symbol → checks/<module>.py 含 symbol；或 module → 文件存在
        mod, _, sym = source.partition(".")
        mod_path = checks_dir / f"{mod}.py"
        if not mod_path.exists():
            issues.append(f"规则 {rid}（{rule.get('rule','')}）：校验器模块 {mod}.py 不存在")
            continue
        if sym:
            text = mod_path.read_text(encoding="utf-8")
            if sym not in text:
                issues.append(f"规则 {rid}（{rule.get('rule','')}）：{mod}.py 中找不到符号 {sym}")
        # 测试文件含 keyword
        test_path = checks_dir / "tests" / f"{test}.py"
        if not test_path.exists():
            issues.append(f"规则 {rid}：测试文件 {test}.py 不存在")
            continue
        if keyword and keyword not in test_path.read_text(encoding="utf-8"):
            issues.append(f"规则 {rid}（{rule.get('rule','')}）：{test}.py 中找不到关键词「{keyword}」")
    return issues


def check_links(root: Path | None = None, link_globs: list[str] | None = None,
                exclude: set[str] | None = None) -> list[str]:
    """断链/引用：md 相对链接与代码路径引用必须存在。"""
    issues = []
    root = root or ROOT
    link_globs = link_globs if link_globs is not None else LINK_GLOBS
    exclude = exclude or LINK_EXCLUDE
    link_re = re.compile(r"\[[^\]]*\]\(([^)#]+?)(?:#[^)]*)?\)|!\[[^\]]*\]\(([^)#]+?)\)")
    code_ref_re = re.compile(r"`((?:checks|scripts|vendor)/[^`]+)`")
    for glob in link_globs:
        for path in root.glob(glob):
            if not path.is_file() or any(part in exclude for part in path.parts):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), 1):
                for m in link_re.finditer(line):
                    target = m.group(1) or m.group(2)
                    if not target or "://" in target or target.startswith(("#", "mailto:")):
                        continue
                    if "*" in target or "?" in target:
                        continue  # glob 模式（如 checks/checklist-*.md）不判存在
                    # 相对链接从文档所在目录解析
                    rel = (path.parent / target).resolve()
                    if not rel.exists():
                        issues.append(f"{path.relative_to(root)}:{lineno} 断链：{target}")
                for m in code_ref_re.finditer(line):
                    target = m.group(1)
                    if "*" in target or "?" in target:
                        continue
                    rel = (root / target).resolve()
                    if not rel.exists():
                        issues.append(f"{path.relative_to(root)}:{lineno} 引用不存在：{target}")
    return issues


def run() -> dict:
    issues = scan_managed_values() + check_rule_coverage() + check_links()
    return {"pass": not issues, "issues": issues,
            "stats": {"managed": len(scan_managed_values()),
                      "coverage_rules": len(json.loads(COVERAGE_FILE.read_text(encoding="utf-8")).get("rules", []))}}


def main(argv: list[str]) -> int:
    report = run()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
