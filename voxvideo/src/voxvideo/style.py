"""风格模板加载与校验。"""

from __future__ import annotations

import json
from pathlib import Path

REQUIRED_FIELDS = ("id", "name", "status", "master_prompt_file", "guide_files")
VALID_STATUS = ("stable", "draft")


class StyleError(Exception):
    pass


def load_style(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED_FIELDS if k not in data]
    if missing:
        raise StyleError(f"{path.name}: 缺少必填字段 {missing}")
    if data["id"] != path.stem:
        raise StyleError(f"{path.name}: id 必须与文件名一致（{data['id']!r} != {path.stem!r}）")
    if data["status"] not in VALID_STATUS:
        raise StyleError(f"{path.name}: status 必须是 {VALID_STATUS} 之一，得到 {data['status']!r}")
    for key, want in (("master_prompt_file", str), ("name", str), ("id", str)):
        if not isinstance(data[key], want):
            raise StyleError(f"{path.name}: {key} 必须是 {want.__name__}")
    if not isinstance(data["guide_files"], list) or not all(isinstance(f, str) for f in data["guide_files"]):
        raise StyleError(f"{path.name}: guide_files 必须是字符串列表")
    if "default_shot_seconds" in data and not isinstance(data["default_shot_seconds"], (int, float)):
        raise StyleError(f"{path.name}: default_shot_seconds 必须是数字")
    return data


def load_styles(profiles_dir: Path) -> list[dict]:
    out = []
    for path in sorted(Path(profiles_dir).glob("*.json")):
        out.append(load_style(path))
    return out


def get_style(profiles_dir: Path, style_id: str) -> dict:
    path = Path(profiles_dir) / f"{style_id}.json"
    if not path.exists():
        available = ", ".join(p.stem for p in sorted(Path(profiles_dir).glob("*.json")))
        raise StyleError(f"未知风格模板 {style_id!r}。可用：{available or '（无）'}")
    return load_style(path)
