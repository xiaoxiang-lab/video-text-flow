// 杜蕾斯式海报合成：GPT Image 2 出静物主体 + Canvas 按真海报排版规律叠字
const { createCanvas, loadImage, GlobalFonts } = require('@napi-rs/canvas')
const fs = require('fs')

// 字体：优先用可免费商用的思源全家桶 / 得意黑；系统字体只作兜底。
// ⚠️ 苹方、微软雅黑、方正、汉仪等需商业授权，不要用于对外物料 —— 见 references/typography.md
for (const dir of [`${process.env.HOME}/Library/Fonts`, '/Library/Fonts',
                   '/usr/share/fonts', `${process.env.HOME}/.local/share/fonts`]) {
  try { GlobalFonts.loadFontsFromDir(dir) } catch (e) {}
}
;['/System/Library/Fonts/Hiragino Sans GB.ttc',
  '/System/Library/Fonts/Supplemental/Songti.ttc'].forEach(p => { try { GlobalFonts.registerFromPath(p) } catch (e) {} })

const has = n => GlobalFonts.families.some(f => f.family === n)
const pick = (cands, fb) => cands.find(has) || fb
const SANS  = `"${pick(['Source Han Sans SC','Noto Sans CJK SC','Alibaba PuHuiTi 3.0',
                        'HarmonyOS Sans SC','OPPOSans'], 'Hiragino Sans GB')}"`
const SERIF = `"${pick(['Source Han Serif SC','Noto Serif CJK SC','KingHwa_OldSong'], 'Songti SC')}"`
if (process.env.DUREX_FONT_DEBUG) console.error('fonts →', { SANS, SERIF })

// 从真海报抠出的参数
const INK   = '#2B2724'          // 正文
const DIM   = 'rgba(43,39,36,.52)' // 眉题
const RED   = '#C8102E'          // 品牌强调色（唯一）
const LOGO_W = 0.086             // logo 宽 ≈ 画面宽 8.6%

// 版式：tag, w, h, 文案锚点(x%,y%), 正文字号(占宽%), 强调倍率, 行距, 对齐
const SPECS = [
  ['3x4',  1200, 1600, .105, .105, .0385, 1.72, 1.95, 'left'],
  ['1x1',  1200, 1200, .095, .120, .0455, 1.68, 1.85, 'left'],
  ['4x3',  1600, 1200, .075, .215, .0385, 1.70, 1.95, 'left'],
  ['9x16', 1080, 1920, .105, .115, .0520, 1.65, 1.85, 'left'],
  ['16x9', 1920, 1080, .062, .235, .0345, 1.72, 2.00, 'left'],
]

// 文案：段 = [{t:文字, hl:是否强调}]
const EYEBROW = '2026 · AI COURSE'
const LINES = [
  [{ t: '会提问', hl: true }, { t: '的人，', hl: false }],
  [{ t: '不需要更好的模型。', hl: false }],
]
const SUB = '试一百把钥匙，不如问对一次。'

// 签名块：椭圆宽度由文字实测宽度决定，永不溢出
function drawLogo (ctx, cx, baseY, unit) {
  const tag = 'AI COURSE'
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
  // 上层超小字
  ctx.fillStyle = 'rgba(43,39,36,.50)'
  ctx.font = `${Math.round(unit * 0.115)}px ${SANS}`
  ctx.letterSpacing = `${unit * 0.05}px`
  ctx.fillText('学 会 提 问', cx, baseY)
  ctx.letterSpacing = '0px'
  // 下层椭圆框：按实测文字宽度 + 内边距
  const fs = Math.round(unit * 0.205)
  ctx.font = `600 ${fs}px ${SANS}`
  const tw = ctx.measureText(tag).width
  const padX = fs * 0.78, padY = fs * 0.46
  const bw = tw + padX * 2, bh = fs + padY * 2
  const by = baseY + unit * 0.20
  ctx.strokeStyle = INK; ctx.lineWidth = Math.max(1.4, unit * 0.018)
  ctx.beginPath(); ctx.roundRect(cx - bw / 2, by, bw, bh, bh / 2); ctx.stroke()
  ctx.fillStyle = INK
  ctx.fillText(tag, cx, by + bh / 2 + fs * 0.04)
  return by + bh
}

async function build (tag, w, h, ax, ay, bodyR, hlMul, lh) {
  const cv = createCanvas(w, h), ctx = cv.getContext('2d')
  const img = await loadImage(`hero5/${tag}.png`)

  // 取底图角落的纸色，铺满整幅 —— 底部签名带才有干净底
  const probe = createCanvas(1, 1); const pc = probe.getContext('2d')
  pc.drawImage(img, 4, 4, 1, 1, 0, 0, 1, 1)
  const [r, g, b] = pc.getImageData(0, 0, 1, 1).data
  ctx.fillStyle = `rgb(${r},${g},${b})`; ctx.fillRect(0, 0, w, h)

  // 主体图只占到签名带以上，保证 logo 落在空白纸面（真海报的铁律）
  const band = h * 0.135
  const rh = h - band
  const s = Math.max(w / img.width, rh / img.height)
  ctx.drawImage(img, (w - img.width * s) / 2, (rh - img.height * s) / 2, img.width * s, img.height * s)

  const body = Math.round(w * bodyR)
  const hl = Math.round(body * hlMul)
  const x = w * ax
  let y = h * ay

  // 眉题
  ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic'
  ctx.fillStyle = DIM
  ctx.font = `${Math.round(body * 0.60)}px ${SANS}`
  ctx.letterSpacing = `${body * 0.10}px`
  ctx.fillText(EYEBROW, x, y)
  ctx.letterSpacing = '0px'
  y += body * 1.85

  // 主文案：逐段绘制，强调段放大染色
  for (const line of LINES) {
    let cx = x
    const maxSize = line.some(p => p.hl) ? hl : body
    for (const p of line) {
      ctx.font = p.hl ? `600 ${hl}px ${SANS}` : `${body}px ${SANS}`
      ctx.fillStyle = p.hl ? RED : INK
      ctx.fillText(p.t, cx, y)
      cx += ctx.measureText(p.t).width
    }
    y += maxSize * (lh * 0.62) + body * 0.55
  }

  // 副标
  y += body * 0.55
  ctx.font = `${Math.round(body * 0.62)}px ${SANS}`
  ctx.fillStyle = 'rgba(43,39,36,.62)'
  ctx.fillText(SUB, x, y)

  // 底部签名，居中
  drawLogo(ctx, w / 2, h - h * 0.072, w * LOGO_W)
  return cv
}

;(async () => {
  fs.mkdirSync('final_v2', { recursive: true })
  for (const [tag, w, h, ax, ay, br, hm, lh] of SPECS) {
    const cv = await build(tag, w, h, ax, ay, br, hm, lh)
    const fp = `final_v2/keys_${tag}.png`
    fs.writeFileSync(fp, cv.toBuffer('image/png'))
    console.log('OK', fp)
  }
})()
