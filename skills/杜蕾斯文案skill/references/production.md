# 出图管线：AI 出图层，代码做排版

## 为什么不让 AI 直接把字写进图里

实测结论：AI 图像模型渲染中文仍会**错字、缺笔画、字形崩坏、标点乱码**，且不可控。

而杜蕾斯这套视觉的命门恰恰是**精确排版**：
- 关键词放大 1.8–2.5 倍并染品牌色 → 需要精确字号比
- 按意群手动断行 → 需要精确控制换行位置
- Logo 恒定位置、永不放大 → 需要像素级定位
- 留白率 ≥ 50% → 需要精确边距

这些全都是**排版引擎的活，不是生成模型的活**。

## 分层管线

```
① AI 图像模型 → 只出【背景质感 / 道具 / 图形元素】
   提示词里必须明确写：NO text, NO letters, NO numbers, NO logos
   推荐 GPT Image 2（便宜、快）或 Nano Banana Pro（质感更好）

② 代码排版 → 承担全部文字
   按 visual-system.md 的字号/配色/留白规范

③ 精确截图 → 按 ratios.md 输出五种画幅
```

**额外好处**：改文案只改一行代码，不用重新烧钱出图；五个比例复用同一套变量。

---

## 排版方案怎么选

| 方案 | 优势 | 劣势 | 何时用 |
|---|---|---|---|
| **HTML/CSS + Playwright** ⭐ | CSS 全家桶、中文断行/字距最省心、所见即所得、迭代最快 | 依赖浏览器二进制 | **默认首选** |
| **Satori + resvg** | JSX→SVG→PNG，**无需浏览器**、确定性、快（Vercel OG 图方案） | 仅支持 CSS 子集（flex，无 grid）、CJK 需手动挂字体 | 服务端批量集成 |
| **Canvas**（skia-canvas / node-canvas） | 程序化绘图强、无浏览器、性能好 | **要自己写换行和文本测量**，无布局引擎 | **图标阵列**（撕历体那种满屏小汽车/购物袋）、数据驱动图形 |
| **SVG 模板 + resvg** | 矢量可无限放大、确定性 | 换行要手写 `tspan`、字体嵌入麻烦 | 需要矢量交付 |
| **Pillow / ImageMagick** | 零依赖 | 排版质量差，无字距控制 | 只适合水印、批量贴图 |
| **Figma API** | 设计师协作、可交付源文件 | 需要 token + 现成设计稿 | 有设计团队时 |

**规律**：文字为主 → HTML；**图形阵列为主 → Canvas**。杜蕾斯的「撕历体」（满屏图标 vs 单个图标的对比）用 Canvas 程序化生成远比手摆强。

---

## HTML/CSS 参考实现

关键点在注释里。完整可跑版本见本目录同级的 `assets/compose_example.py`（如无则按下方骨架自建）。

```python
from playwright.sync_api import sync_playwright
import base64, pathlib

RED = "#E2001A"      # 品牌强调色，全图唯一
INK = "#E8ECF2"      # 正文
# (画幅, 宽, 高, 正文px, 强调px)  —— 正文 ≈ 画面高度的 2.5%–3.5%
SPECS = [("3x4",1200,1600,44,92), ("1x1",1200,1200,74,118),
         ("4x3",1600,1200,52,96), ("9x16",1080,1920,62,104),
         ("16x9",1920,1080,60,104)]

def plate(tag):  # AI 生成的背景层，转 base64 内联，避免路径问题
    b = pathlib.Path(f"plates/{tag}.png").read_bytes()
    return "data:image/png;base64," + base64.b64encode(b).decode()

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{
  width:%(w)spx;height:%(h)spx;overflow:hidden;
  background:#0E1A2E url('%(plate)s') center/cover no-repeat;
  font-family:"PingFang SC","Source Han Sans SC",sans-serif;
  color:%(ink)s;-webkit-font-smoothing:antialiased;
}
.copy{line-height:1.62;letter-spacing:.02em;font-size:%(body)spx}
.hl{color:%(red)s;font-weight:600;font-size:%(hl)spx;letter-spacing:0}
/* 道具主体：文本光标。纯 CSS = 像素精确，比 AI 生成可靠 */
.caret{width:%(cw)spx;height:%(ch)spx;background:%(red)s;
       box-shadow:0 0 24px rgba(226,0,26,.45),0 0 72px rgba(226,0,26,.18)}
.sig{position:absolute;bottom:5.8%%;left:0;right:0;text-align:center;
     font-size:%(sig)spx;letter-spacing:.42em;color:rgba(232,236,242,.34)}
"""

with sync_playwright() as p:
    br = p.chromium.launch()
    for tag, w, h, body, hl in SPECS:
        page = br.new_page(viewport={"width": w, "height": h},
                           device_scale_factor=2)   # 2x = 文字锐利
        page.set_content(build_html(tag, w, h, body, hl))
        page.wait_for_timeout(400)                   # 等字体加载
        page.screenshot(path=f"final/{tag}.png")
        page.close()
    br.close()
```

### 五种画幅的版式分支（骨架）

```
vertical (3:4)  ── 上文 / 中主体 / 下留白，文案 4 行内
square   (1:1)  ── 大字居中即主体，文案砍到 2 行，字号反而更大
split    (4:3)  ── 左 46% 文案（垂直居中）/ 右 54% 主体
stack    (9:16) ── 上下各留安全区（顶 15% / 底 20%），短句堆叠
hero     (16:9) ── 左 62% 单行标题 + 副标 / 右 38% 主体
```

---

## AI 背景层提示词模板

```
An abstract minimalist background plate for a premium graphic poster.
Absolutely NO text, NO letters, NO numbers, NO characters, NO logos, NO objects, NO people.
Pure atmospheric field only.
<配色描述：例 Deep midnight navy gradient from #16233F to #0A1220>
A very soft diffuse light falloff from the upper area, fading into darkness at the edges.
Fine cinematic film grain and delicate paper-like texture.
Subtle vignette on all four corners.
Calm, restrained, expensive, editorial.
Completely empty and clean — this is only a background texture,
the entire surface must remain unobstructed with nothing placed on it.
```

**必写的三条否定**：`NO text` / `NO objects`（除非道具就是要 AI 生成）/ `NO people`。

做 AI 主题时额外加一句否定：
```
No sci-fi blue glow, no circuit boards, no robots, no brains, no globes, no neural network graphics.
```
——这些是 AI 题材的视觉陈词滥调，出现即降级。

---

## 质检

出图后逐条核对（同 `visual-system.md` 清单），另加两条：

- [ ] 中文有没有错字/缺笔画？（HTML 管线下应为零，若出现说明字体缺字，换字体）
- [ ] 关键词的放大倍率是不是落在 1.8–2.5 之间？（超出会失衡）
