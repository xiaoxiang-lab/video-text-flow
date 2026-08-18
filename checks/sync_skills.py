"""全局 skill ↔ 项目快照同步（程序化，白名单制）。

用法：
  python checks/sync_skills.py                 # dry-run：报告差异
  python checks/sync_skills.py --apply         # 执行同步（单向：全局 → 项目）

同步范围：只同步白名单（skills/.sync-whitelist.txt，每行一个 skill 名）内的条目——
本项目用到的才进快照，无关 skill 不复制；项目内白名单外的 skill 目录视为多余并删除。

比较粒度：目录级（递归比所有文件的 sha256），SKILL.md 之外的附属文件
（LESSONS.md 等）变更也能检测到（2026-08-15 旧待办修复，2026-08-17 落地）。

vendoring：EXTRA_SOURCES 里的外部源目录（如 vendor/srtvox-director）同样受
目录级 hash 检测——上游更新/本地改动会报 update，防静默漂移。

规则假设来源：用户决策（2026-08-15：GitHub 仓库须自包含，但只含本项目相关 skill；
2026-08-17：srt-vox 副本纳入 EXTRA_SOURCES + hash 检测）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

GLOBAL_SKILLS = Path.home() / ".config" / "opencode" / "skills"
GLOBAL_COMMAND = Path.home() / ".config" / "opencode" / "command" / "cover.md"
PROJECT_SKILLS = Path(__file__).resolve().parents[1] / "skills"
PROJECT_COMMAND = PROJECT_SKILLS / "command" / "cover.md"
WHITELIST_FILE = PROJECT_SKILLS / ".sync-whitelist.txt"
EXCLUDED_PROJECT_ENTRIES = {"command", "README.md", ".sync-whitelist.txt"}

# 附加源：不在全局 skills/ 的项目外目录。
# 两类：
#   a. 外部 skill（如 chupian-vox 依赖的 vox-prompts，位于 voxvideo 项目）——目录须含 SKILL.md
#   b. vendoring 副本（如 vendor/srtvox-director，上游无 LICENSE、结构非 skill）——不要求 SKILL.md
# 共同点：按白名单同步进项目 skills/ 快照，目录级 hash 检测。
EXTRA_SOURCES: dict[str, Path] = {
    "vox-prompts": Path(r"C:\Users\xx\Documents\Default Project\.claude\vox-prompts"),
    "srtvox-director": Path(__file__).resolve().parents[1] / "vendor" / "srtvox-director",
}


def load_whitelist() -> list[str]:
    if not WHITELIST_FILE.exists():
        return []
    return [line.strip() for line in WHITELIST_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")]


def src_of(name: str, src_root: Path) -> Path | None:
    """条目的源目录：优先全局 skills/，其次附加源。

    全局 skills/ 下的必须是标准 skill（含 SKILL.md）；EXTRA_SOURCES 不要求
    SKILL.md（vendoring 副本可能不是 skill 结构）。
    """
    p = src_root / name
    if p.exists() and (p / "SKILL.md").exists():
        return p
    extra = EXTRA_SOURCES.get(name)
    if extra is not None and extra.exists():
        return extra
    return None


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def iter_files(root: Path) -> list[Path]:
    """递归收集目录下所有普通文件（相对路径排序）。"""
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file())


def dir_fingerprint(root: Path) -> dict[str, str]:
    """目录级指纹：相对路径 → sha256。任一文件缺失/变更都会改变指纹。"""
    fp: dict[str, str] = {}
    for p in iter_files(root):
        rel = p.relative_to(root).as_posix()
        fp[rel] = file_sha256(p)
    return fp


def iter_skill_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [p for p in sorted(root.iterdir())
            if p.is_dir() and (p / "SKILL.md").exists()]


def iter_snapshot_dirs(root: Path) -> list[Path]:
    """快照目录：标准 skill 或 vendoring 副本（EXTRA_SOURCES 名）都算。"""
    if not root.exists():
        return []
    return [p for p in sorted(root.iterdir())
            if p.is_dir() and (p / "SKILL.md").exists() or p.name in EXTRA_SOURCES]


def compare(src_root: Path, dst_root: Path, whitelist: list[str]) -> dict:
    """返回 {name: 'add'|'update'|'remove'|'same'}（仅白名单内，源含附加源）。

    目录级比较：递归比所有文件 hash（不只是 SKILL.md）——附属文件（LESSONS.md 等）
    变更也会报 update（旧待办修复，2026-08-17）。
    """
    src = {}
    for name in whitelist:
        sp = src_of(name, src_root)
        if sp is not None:
            src[name] = sp
    dst = {p.name: p for p in iter_skill_dirs(dst_root)}
    # 白名单内的 vendoring 副本即使不含 SKILL.md，也在 dst 里
    for name in whitelist:
        if name in EXTRA_SOURCES and name not in dst and (dst_root / name).is_dir():
            dst[name] = dst_root / name
    result: dict[str, str] = {}
    for name, sp in src.items():
        dp = dst.get(name)
        if dp is None:
            result[name] = "add"
        else:
            src_fp = dir_fingerprint(sp)
            dst_fp = dir_fingerprint(dp)
            result[name] = "same" if src_fp == dst_fp else "update"
    # 项目内白名单外的 skill 目录 = 多余，标记 remove
    for name in dst:
        if name in whitelist:
            continue
        if name not in src:
            result[name] = "remove"
    return result


def sync_one(src: Path, dst: Path, action: str) -> None:
    if action == "remove":
        shutil.rmtree(dst, ignore_errors=True)
    else:
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)


def sync_cover(apply: bool) -> str:
    if not GLOBAL_COMMAND.exists():
        return "skip（全局 cover.md 不存在）"
    if PROJECT_COMMAND.exists() and file_sha256(GLOBAL_COMMAND) == file_sha256(PROJECT_COMMAND):
        return "same"
    if apply:
        PROJECT_COMMAND.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(GLOBAL_COMMAND, PROJECT_COMMAND)
        return "updated"
    return "update"


def append_sync_record(changes: dict[str, str], cover_status: str) -> None:
    """同步后自动在 skills/README.md 登记（追加一行）。"""
    readme = PROJECT_SKILLS / "README.md"
    if not readme.exists():
        return
    date = datetime.now().strftime("%Y-%m-%d")
    summary = "、".join(f"{k}({v})" for k, v in changes.items() if v != "same") or "无变化"
    line = f"| {date} | 自动同步：{summary}；cover.md {cover_status} |"
    text = readme.read_text(encoding="utf-8")
    if line not in text:
        readme.write_text(text.rstrip() + "\n" + line + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="sync_skills")
    parser.add_argument("--apply", action="store_true", help="执行同步（默认 dry-run）")
    args = parser.parse_args(argv)

    whitelist = load_whitelist()
    changes = compare(GLOBAL_SKILLS, PROJECT_SKILLS, whitelist)
    cover_status = sync_cover(apply=args.apply)

    if args.apply:
        for name, action in changes.items():
            sp = src_of(name, GLOBAL_SKILLS)
            if action == "remove":
                sync_one(GLOBAL_SKILLS / name, PROJECT_SKILLS / name, "remove")
            elif action in ("add", "update") and sp is not None:
                sync_one(sp, PROJECT_SKILLS / name, "add")
        append_sync_record(changes, cover_status)
        report = {"applied": True, "changes": changes, "cover.md": cover_status}
    else:
        report = {"applied": False, "changes": changes, "cover.md": cover_status,
                  "hint": "加 --apply 执行同步"}

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not any(v in ("add", "update", "remove") for v in changes.values()) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
