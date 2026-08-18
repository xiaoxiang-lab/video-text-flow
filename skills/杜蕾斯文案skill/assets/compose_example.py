#!/usr/bin/env python3
"""杜蕾斯式海报合成器：AI 出背景层，HTML/CSS 排版文字，无头浏览器截图。"""
import os, base64, pathlib
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).parent
OUT = HERE / "final"; OUT.mkdir(exist_ok=True)

RED = "#E2001A"
INK = "#E8ECF2"
DIM = "rgba(232,236,242,.55)"

def plate(tag):
    b = (HERE / "plates" / f"{tag}.png").read_bytes()
    return "data:image/png;base64," + base64.b64encode(b).decode()

# (tag, 宽, 高, 正文px, 强调px, 版式)
SPECS = [
    ("3x4",  1200, 1600, 44,  92,  "vertical"),
    ("1x1",  1200, 1200, 74,  118, "square"),
    ("4x3",  1600, 1200, 52,  96,  "split"),
    ("9x16", 1080, 1920, 62,  104, "stack"),
    ("16x9", 1920, 1080, 60,  104, "hero"),
]

BASE_CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:%(w)spx;height:%(h)spx;overflow:hidden}
body{
  background:#0E1A2E url('%(plate)s') center/cover no-repeat;
  font-family:"PingFang SC","Hiragino Sans GB","Source Han Sans SC",-apple-system,sans-serif;
  color:%(ink)s; position:relative;
  -webkit-font-smoothing:antialiased;
}
.wrap{position:absolute;inset:0;display:flex}
.copy{line-height:1.62;letter-spacing:.02em;font-weight:400}
.hl{color:%(red)s;font-weight:600;letter-spacing:0}
/* 主体：文本光标（道具主体，纯 CSS，像素精确） */
.caret{
  width:%(cw)spx;height:%(ch)spx;background:%(red)s;border-radius:1px;
  box-shadow:0 0 %(cg)spx rgba(226,0,26,.45), 0 0 %(cg2)spx rgba(226,0,26,.18);
}
.sig{
  position:absolute;font-size:%(sig)spx;letter-spacing:.42em;
  color:rgba(232,236,242,.34);font-weight:300;
}
.sub{font-size:%(sub)spx;color:%(dim)s;line-height:1.7;letter-spacing:.04em;font-weight:300}
"""

def build(tag, w, h, body, hl, layout):
    cw = max(6, round(w * 0.0075))
    ch = round(h * (0.075 if layout in ("vertical", "stack") else 0.10))
    css = BASE_CSS % dict(w=w, h=h, plate=plate(tag), ink=INK, red=RED, dim=DIM,
                          cw=cw, ch=ch, cg=round(w*0.02), cg2=round(w*0.06),
                          sig=round(w*0.0115), sub=round(body*0.52))

    if layout == "vertical":      # 3:4 主视觉：上文 / 中主体 / 下留白
        css += f"""
        .wrap{{flex-direction:column;padding:{round(h*0.105)}px {round(w*0.115)}px}}
        .copy{{font-size:{body}px}} .hl{{font-size:{hl}px}}
        .mid{{flex:1;display:flex;align-items:center;justify-content:center;padding-bottom:{round(h*0.10)}px}}
        .sig{{bottom:{round(h*0.058)}px;left:0;right:0;text-align:center}}"""
        html = f"""<div class="wrap">
          <div class="copy"><span class="hl">会提问</span>的人，<br>不需要更好的模型。</div>
          <div class="mid"><div class="caret"></div></div>
        </div><div class="sig">AI COURSE</div>"""

    elif layout == "square":      # 1:1 封面：大字为主体，文案砍到 2 行
        css += f"""
        .wrap{{flex-direction:column;align-items:center;justify-content:center;padding:0 {round(w*0.085)}px}}
        .copy{{font-size:{body}px;text-align:center;line-height:1.5}} .hl{{font-size:{hl}px}}
        .caret{{margin-top:{round(h*0.085)}px}}
        .sig{{bottom:{round(h*0.062)}px;left:0;right:0;text-align:center}}"""
        html = f"""<div class="wrap">
          <div class="copy"><span class="hl">会提问</span>的人<br>不需要更好的模型</div>
          <div class="caret"></div>
        </div><div class="sig">AI COURSE</div>"""

    elif layout == "split":       # 4:3 横版：左文右图
        css += f"""
        .wrap{{align-items:center}}
        .L{{width:46%;padding-left:{round(w*0.085)}px}}
        .R{{width:54%;display:flex;align-items:center;justify-content:center}}
        .copy{{font-size:{body}px}} .hl{{font-size:{hl}px}}
        .sig{{bottom:{round(h*0.072)}px;left:{round(w*0.085)}px}}"""
        html = f"""<div class="wrap">
          <div class="L"><div class="copy"><span class="hl">会提问</span>的人，<br>不需要更好的模型。</div></div>
          <div class="R"><div class="caret"></div></div>
        </div><div class="sig">AI COURSE</div>"""

    elif layout == "stack":       # 9:16 竖屏：短句堆叠 + 上下安全区
        css += f"""
        .wrap{{flex-direction:column;align-items:center;
               padding:{round(h*0.20)}px {round(w*0.09)}px {round(h*0.20)}px}}
        .copy{{font-size:{body}px;text-align:center;line-height:1.5}} .hl{{font-size:{hl}px}}
        .mid{{flex:1;display:flex;align-items:center;justify-content:center}}
        .sig{{bottom:{round(h*0.093)}px;left:0;right:0;text-align:center}}"""
        html = f"""<div class="wrap">
          <div class="copy"><span class="hl">会提问</span>的人<br>不需要<br>更好的模型</div>
          <div class="mid"><div class="caret"></div></div>
        </div><div class="sig">AI COURSE</div>"""

    else:                          # 16:9 Hero：单行标题 + 副标 + 右侧主体
        css += f"""
        .wrap{{align-items:center}}
        .L{{width:62%;padding-left:{round(w*0.072)}px}}
        .R{{width:38%;display:flex;align-items:center;justify-content:center}}
        .copy{{font-size:{body}px;white-space:nowrap}} .hl{{font-size:{hl}px}}
        .sub{{margin-top:{round(h*0.045)}px}}
        .sig{{bottom:{round(h*0.082)}px;left:{round(w*0.072)}px}}"""
        html = f"""<div class="wrap">
          <div class="L">
            <div class="copy"><span class="hl">会提问</span>的人，不需要更好的模型。</div>
            <div class="sub">三小时，换回你未来三年的加班。</div>
          </div>
          <div class="R"><div class="caret"></div></div>
        </div><div class="sig">AI COURSE</div>"""

    return f"<!doctype html><meta charset='utf-8'><style>{css}</style>{html}"


with sync_playwright() as p:
    br = p.chromium.launch()
    for tag, w, h, body, hl, layout in SPECS:
        page = br.new_page(viewport={"width": w, "height": h}, device_scale_factor=2)
        page.set_content(build(tag, w, h, body, hl, layout))
        page.wait_for_timeout(400)
        fp = OUT / f"ai-course_{tag}.png"
        page.screenshot(path=str(fp))
        page.close()
        print("OK", fp)
    br.close()
