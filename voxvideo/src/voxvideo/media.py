"""ffmpeg/ffprobe 包装。只在配音路径上用到。"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


class MediaError(Exception):
    pass


def require_audio_tools() -> None:
    """检查 ffmpeg/ffprobe，缺失时报出还差哪个命令。只在配音入口调用。"""
    missing = [cmd for cmd in ("ffmpeg", "ffprobe") if shutil.which(cmd) is None]
    if missing:
        raise MediaError(
            f"配音需要 {missing}，但没找到。安装 ffmpeg（含 ffprobe）后再运行 synthesize-narration。"
        )


def probe(path: Path) -> dict:
    """ffprobe 取时长/分辨率/有无音轨。"""
    path = Path(path)
    if not path.exists():
        raise MediaError(f"文件不存在：{path}")
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise MediaError(f"ffprobe 失败：{(proc.stderr or '').strip()[:300]}")
    data = json.loads(proc.stdout or "{}")
    duration = None
    try:
        duration = float(data["format"]["duration"])
    except (KeyError, TypeError, ValueError):
        pass
    width = height = None
    has_audio = False
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            width = stream.get("width")
            height = stream.get("height")
        elif stream.get("codec_type") == "audio":
            has_audio = True
    return {"duration": duration, "width": width, "height": height, "has_audio": has_audio}


def concat_audio(take_paths: list[Path], dest: Path) -> Path:
    """concat demuxer 拼接 take。"""
    take_paths = [Path(p) for p in take_paths]
    if not take_paths:
        raise MediaError("没有可拼接的 take")
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"file '{str(p.resolve()).replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'"
             for p in take_paths]
    list_file = dest.with_suffix(".list.txt")
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    proc = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
         "-c", "copy", str(dest)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0 or not dest.exists():
        raise MediaError(f"ffmpeg 拼接失败：{(proc.stderr or '').strip()[:300]}")
    return dest
