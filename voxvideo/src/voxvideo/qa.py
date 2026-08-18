"""图片文件技术校验。内容判断不在这里。"""

from __future__ import annotations

from pathlib import Path

EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MIN_SIZE = 1024

MAGIC_PNG = b"\x89PNG\r\n\x1a\n"
MAGIC_JPEG = b"\xff\xd8\xff"
MAGIC_WEBP = b"WEBP"


class QaError(Exception):
    pass


def validate_image_file(path: Path) -> None:
    """后缀、大小 >1KB、文件头魔数（PNG/JPEG/WEBP）。"""
    path = Path(path)
    if not path.exists():
        raise QaError(f"图片不存在：{path}")
    if path.suffix.lower().lstrip(".") not in EXTENSIONS:
        raise QaError(f"图片后缀不在白名单（{sorted(EXTENSIONS)}）：{path.name}")
    size = path.stat().st_size
    if size <= MIN_SIZE:
        raise QaError(f"图片太小（{size} 字节，要求 > {MIN_SIZE}）：{path.name}")
    head = path.read_bytes()[:16]
    if head.startswith(MAGIC_PNG):
        return
    if head.startswith(MAGIC_JPEG):
        return
    if head[8:12] == MAGIC_WEBP and head[:4] == b"RIFF":
        return
    raise QaError(f"文件头魔数不匹配（PNG/JPEG/WEBP）：{path.name}")
