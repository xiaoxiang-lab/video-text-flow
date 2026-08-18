# -*- coding: utf-8 -*-
"""拼 21 格 style-grid.jpg（7 行 × 3 列，同题材同构图同中文横向对比）。"""
from pathlib import Path

from PIL import Image, ImageDraw

ASSETS = Path(r"C:\Users\xx\Documents\Default Project\ref\style-assets")
SAMPLES = ASSETS / "style-samples"

NAMES = [
    "S01-现代纸艺", "S02-黏土定格", "S03-毛毡手工", "S04-矿彩壁画",
    "S05-数据城市", "S06-字体装置", "S07-极简几何", "S08-水墨长卷",
    "S09-科学切片", "S10-历史档案", "S11-产品蓝图", "S12-漫画证据",
    "S13-木刻版画", "S14-剪纸剧场", "S15-皮影机械", "S16-错位拼贴",
    "S17-深蓝撕纸", "S18-马克笔记", "S19-博物模型", "S20-复古波普",
    "S21-美漫风格",
]

COLS, ROWS = 3, 7
CELL_W, CELL_H = 640, 360          # 每格 16:9
GAP = 12                            # 格间距
LABEL_H = 26                        # 每格顶部标签条
MARGIN = 24                         # 外留白

W = MARGIN * 2 + COLS * CELL_W + (COLS - 1) * GAP
H = MARGIN * 2 + ROWS * (CELL_H + LABEL_H) + (ROWS - 1) * GAP

grid = Image.new("RGB", (W, H), "#F0EEE9")
draw = ImageDraw.Draw(grid)

cells = []
for i, name in enumerate(NAMES):
    p = SAMPLES / f"{name}.jpg"
    if not p.exists():
        print(f"缺失 {name}")
        continue
    img = Image.open(p).convert("RGB")
    img = img.resize((CELL_W, CELL_H), Image.LANCZOS)
    r, c = divmod(i, COLS)
    x = MARGIN + c * (CELL_W + GAP)
    y = MARGIN + r * (CELL_H + LABEL_H + GAP)
    grid.paste(img, (x, y + LABEL_H))
    draw.rectangle([x, y, x + CELL_W - 1, y + LABEL_H - 1], fill="#FFFFFF")
    draw.text((x + 8, y + 4), name, fill="#333333")
    cells.append(i)

out = ASSETS / "style-grid.jpg"
grid.save(out, "JPEG", quality=88)
print(f"saved {out}  {grid.size}  格数={len(cells)}")