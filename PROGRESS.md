# PROGRESS.md · 进度台账（跨对话持续更新）

> 每个对话结束前必须更新本文件：当前进度、阻塞、下一步。新对话先读本文件。

## 总链路规划（最终目标：跑通 VOX，甚至自动化）

```
阶段 1 ✅ 文案→封面 0-5 关卡机制 + 程序校验器（video-text-flow 项目）
阶段 2 ⏳ 关卡 5 已产出 → 真实 voxvideo 流程打通（init/design.json/门禁/出图/handoff）
阶段 3 🔜 出片链路（2026-08-15 计划已确认，非自动化关卡）：
        ①TTS 配音（synthesize-narration 已有）→ ②Flow 生成（Chrome DevTools MCP + flow-generate skill）
        → ③WSL+ffmpeg 合并脚本（LESSONS H1-H6）→ ④总协调 = 程序脚本 run-video
阶段 4 🔜 GitHub 仓库化 + run-video 一条命令跑全链（含阶段 3）
```

架构判断（DECISIONS.md 2026-08-15）：不需要 cover2/3/4/5 命令——阶段 2 用 voxvideo cli 状态机，阶段 3 全是工具/程序/脚本，总协调是程序不是命令。

## 当前进度（2026-08-15，阶段 3 启动）

| 项 | 状态 |
|---|---|
| 关卡 0 立场确认（宇树 IPO：泡沫悬案） | ✅ |
| 关卡 1 立场重写稿（01） | ✅ 程序+子agent+用户确认 |
| 关卡 2 分镜稿 39 镜 + 标题 C（02） | ✅ 独立风格确认 minimal-motion |
| 关卡 3 配音定稿（03） | ✅ |
| 关卡 4 封面模板结构版（04） | ✅ 用户实测确认 |
| 固化前跨产物对抗性审查 | ✅ 0 内容违规（元信息已修） |
| **关卡 5 拆镜作业单（05）** | ✅ **已确认（2026-08-15）**：41 镜（23 拆 23a/23b）、4分14秒、参考图 4 张（H/4a/17/32）、数字对撞贯穿装置 |
| 关卡 5 对抗性回查（第一性原理） | ✅ 已修 P1-P4：run_all 接入 check_chain / 03 假通过修复 / 03→05 逐字链程序化 / 拆句预警前移 |
| 0-5 关卡全链闭环 | ✅ 01-05 全部三层校验 + 用户确认 |
| **阶段 2：voxvideo 真实流程**（20260815-unitree-ipo） | ✅ **全链打通**：init（minimal-motion）→ design.json（41 镜，narration 逐字 + 4 镜 image_prompt）→ review-design 门禁（子 agent：异常率 7.3% < 20%，3✗+3⚠ 已修）→ generate-images（母板+4 参考图）→ approve-images（用户人工确认，MiMo 欠费）→ export-handoff ✅ |
| **阶段 2 对抗性回查（P5-P8）** | ✅ 已修：P5 05→design.json 无程序校验器 → check_stage2.py 新增；P6 handoff vs design 无校验 → 接入；P7 run_all 不覆盖阶段 2 → --project 参数；P8 manifest vs 文件存在性 → 接入。测试 77→109；子 agent 语义托底 4 处 ⚠（2 修 2 记录） |
| **01-04 明细级重新复核 + P9** | ✅ 4 份核对表落盘（checklist-review-01~04.md）；01 发现 3 处翻案腔（human-writing 硬禁令）→ 用户决策豁免登记 + check_rewrite 补翻案腔检测（P9）+ run_all 豁免机制（exempt 可见可查）；05 时长表笔误修复（21 重复→41 组）；04「柔和阴影」皮肤残留已修。测试 109→121 |
| **阶段 2 项目迁移（2026-08-15）** | ✅ 项目按用户指定位置移到 `C:\Users\xx\Desktop\test\20260815-unitree-ipo\`（voxvideo CLI 新增 `VOXVIDEO_PROJECTS_DIR` 环境变量覆盖项目根，默认仍 ROOT/projects；90 测试全过；全链 run_all 通过） |
| **MiMo token-plan API 接入（2026-08-15）** | ✅ 用户提供小米 token-plan key（.env MIMO_API_KEY），三能力全打通：①识图 mimo-v2.5（mimo_vision.ps1/vision-ask.py/review_images.ps1 URL 固定 token-plan-cn + key 从 .env 读，环境变量残留旧地址是坑已禁）②语音识别 mimo-v2.5-asr（mimo_asr.py 新建，chat/completions + input_audio，whisper 备选）③语音合成 mimo-v2.5-tts（MimoTtsNarrator 加入 narration.py，config.mimo_tts，TTS 限时免费）。voxvideo 测试 90→97 |
| **配音定案 + 真实时长落地（2026-08-15）** | ✅ 用户试听拍板：**MiMo TTS 置顶优先**（语速明快 style），克隆声备选。双后端 41 镜全量合成 → 用户选 MiMo → synthesize-narration 写回真实时长到 design.json（总 190.7s/3:11）→ 档位全 ok 无超档 → handoff 重新导出（真实时长 5.8s/3.4s/7.5s…）。旧 key 全局清理；narration.py 配置段 bug 修复 |

## 阶段 3 进度（2026-08-15）

| 项 | 状态 |
|---|---|
| ① chrome-devtools MCP 配置 | ✅ opencode.jsonc 已加 MCP 配置 + 隔离 Chrome 启动脚本 chrome-flow.bat |
| ② flow-generate skill | ✅ 全局 skill 已建（工作规则 14 条 + 安全边界 + 只读先行/3镜试点/确认兜底），已加白名单 sync 进项目快照；LESSONS.md 沉淀（B1-B5 提示词输入坑） |
| ③ ffmpeg 合并脚本 | ✅ scripts/merge-video.py（裁尾对齐 H3 → 拼接 → 混音 H6/N13 normalize=0，冒烟测试通过） |
| ④ run-video 总协调脚本 | ⏳ 待做 |
| Flow 生成试点（2026-08-15） | ⏸ **已暂停（用户决定停止浏览器自动化）**：MCP 连通/只读/上传/引用/输入流程均验证过；踩坑：type_text 多行=分段提交（剪贴板粘贴解决）、下载依赖 flow-content.google CDN 网络不稳、测试账号点数耗尽、AIX 智能下载器扩展干扰（70+ console 错误）。已删除 chrome-devtools + playwright 两个 MCP 配置（opencode.jsonc 恢复干净）；chrome-flow.bat 保留备用。后续方向（DeepSeek Harness dsh+dsh-playwright-browser / 手动出片 / 其他）**由用户届时自行选择，AI 不代选** |
| **出片链路实测（2026-08-17）** | ✅ 用户手动下载 1-5 镜片段到 05-video → merge-video.py 合并成片（25.52s，1280×720）→ whisper 逐句转写（WSL faster-whisper-large-v3，12.5s）→ ASS 烧录（10 条句级字幕，黑底白字 H2）→ MiMo 抽帧验收 ✅。音效=Flow 原声 0.6 混入（002 镜原声弱属正常） |

## 阶段 3 出片实测记录（2026-08-17，宇树 IPO 5 镜）

```
merge-video.py：1-5.mp4 改名 shot-001~005.mp4 → 裁尾对齐（5.76/3.36/7.52/3.68/5.12s）→ concat → 混音 → final.mp4（25.52s）
字幕：concat 旁白 wav → WSL faster-whisper-large-v3（int8，12.5s）转写 10 段句级时间戳 → 旁白原文替换（whisper 错字：榆树→宇树 等）→ gen-ass.py 生成 subs.ass（H2 样式）→ ffmpeg -vf subtitles 烧录 → final-subs.mp4
验收：ffprobe（h264+aac 720P）+ volumedetect（mean -20dB max -2.5dB）+ MiMo 抽帧 2 处（字幕文字正确无乱码）
坑：ffmpeg 单帧输出要 -update 1；WSL faster_whisper 模型路径要用仓库名（HF 缓存结构）；pip 需 --break-system-packages（PEP 668）
```

## srt-vox-director 分析结论（2026-08-17，待吸纳）

```
来源：github.com/geeklee/srt-vox-director（43★，2026-08-15 更新，Python，无 LICENSE 文件）
定位：SRT 字幕 → Vox 风格视频的分镜+提示词包（21 风格，只出文本不生成媒体）
方法论要点：就近吸附（分界5/7/9，差值≤1.0s 硬规律）· 尾部契约表（差值五档→尾部写法）· 展示/解释两型 ·
  展示型文字逐字覆盖旁白（超14字块拆卡不砍字）· 桥接帧（>11s 拆分+抽帧衔接）· 垫图认知（上传图≠第0帧）·
  check_storyboard/check_prompts/check_state/check_docs 四个校验器 · 正典一处（口径唯一，引用不写数量）·
  state.json 断点续跑 · 七维打分选风格 · 参考图八项/视频六项验收清单 · style-board 六格风格板
本地副本：C:\Users\xx\AppData\Local\Temp\opencode\srtvox-*（readme/skill/storyboard-algorithm/delivery-contract/
  style-selector/check_storyboard.py/examples-e2e + style-library/style-gallery/sample-prompts/prompt-templates/
  prompt-motion/prompt-keywords + style-grid.jpg 21风格总览图）
```

## 吸纳计划（2026-08-17 用户定案，分两步）

```
第一步（文字部分，现在做）：16 条文本规则 + 规则库结构，符合"程序先行 + 子 agent test 托底 +
  对抗性测试 + 不符合返工重做（必须 loop）"原则
第二步（图片部分，之后做）：21 风格资产（样图/风格板/评级表），走 Agnes+MiMo 产线自造

轮次表（第一步）：
  第 0 轮 地基：Flow 实际成片时长统计（差值算术前提，LESSONS 未解决问题）
  第 1 轮 补差：merge-video 补差检测 + 提示词尾部最小改（末帧定格）+ 垫图认知入 LESSONS
  第 2 轮 差值：check_jobcard 差值列/差值率/就近吸附硬规律 + flow_slot 改就近吸附 + 尾部按差值分档
  第 3 轮 两型+七维打分：拆镜定型（解释/展示）+ 展示型文字逐字覆盖 + 载体不撞形 + 选风格 7 维打分
  第 4 轮 桥接：>11s 拆分 + 桥接帧抽帧
  第 5 轮 check_docs 全套：受管数值扫描 + 规则实现覆盖（P6 防复发）+ 断链/引用
  第 6 轮 强制前段试点：每期拆镜后强制先出前 8 镜 + 1 参考图 → 用户确认 → 全量
前置工作：
  ① 版权：无 LICENSE → 先到 repo 开 issue 问授权；期间"结构全收 + 表达重写"
  ② 检查项映射表：16 项 vs check_jobcard/check_stage2/check_chain 对账（已有/新增/冲突）
  ③ 正典一处原则先立（DECISIONS），再上 check_docs
  ④ vendoring 同步机制（复用 sync_skills EXTRA_SOURCES + hash 检测）
  ⑤ 验收清单升级：review-images 按参考图八项/视频六项（MiMo 提示词按维度写）
  ⑥ 强制试点与现有 flow-generate 3 镜试点形成两级（提示词级+生成级）
已评估维持不做：scale 提示（flow-generate 3 镜试点=强制版）、check_state（manifest 门禁已覆盖）
```

## 吸纳 srt-vox 文字部分完成（2026-08-17，轮次 0-6 全部落地）

```
前置：①版权（不开源，VENDOR-NOTICE.md 标注来源）②检查项映射表（docs/check-mapping.md，16 项对账）
  ③正典一处（DECISIONS 已记）④vendoring（vendor/srtvox-director/ 16 文件 + sync_skills EXTRA_SOURCES
  + 目录级 hash 比较——旧待办修复）⑤验收清单升级（docs/review-checklist.md 参考图八项+视频六项 +
  scripts/review-images.ps1 按维度 MiMo 提示词，冒烟通过）⑥校验策略（判据翻译进校验器，不搬脚本）
第 0 轮：Flow 档位整秒假设成立（宇树 5 镜 4/6/8 档 ≈整秒，7.23s 是孤例）；merge-video 自动记录
  档位 vs 实测（.work/flow-duration-log.json）；LESSONS E1-E3
第 1 轮：merge-video 补差检测（视频<旁白 → 警告末帧定格/重生成）；垫图认知入 LESSONS F1-F2
第 2 轮：flow_slot 就近吸附（分界 5/7/9，voxvideo handoff.py + merge-video）；check_jobcard 差值列/
  差值率/短镜；check_stage2 尾部契约分档 + handoff 档位一致性；修复 duration_seconds 假报 41 条
  （synthesize-narration 写回实测后旧校验把实测当档位）+ handoff 正则静默失效（「建议时长」0 匹配）
第 3 轮：拆镜定型（05 型列 + design type 字段：解释/展示）+ 展示型逐字覆盖（image_prompt 子序列）
  + 展示型不拆分/封顶/15s 警告 + 差值率排除展示型 + 七维打分入 style-library.zh.md
第 4 轮：>11s 必拆 + 拆分镜 a/b 成对（桥接 ID）+ 桥接抽帧说明入 flow-generate LESSONS G1-G2
第 5 轮：check_docs.py（受管数值扫描/规则实现覆盖 rule-coverage.json 30 条/断链）+ 接入 run_all
  + 文档 0.8 秒残留清理（style-library 等改引用）
第 6 轮：强制前段试点规则入 chupian-vox SKILL（前 8 镜 + 1 参考图 → 用户确认 → 全量，两级试点）
对抗性测试：宇树 IPO 全链 run_all --project all_pass=True（0 issues，差值率 11.76%，34 stale 提示）；
  测试 121→165（video-text-flow）+ voxvideo 104 全过
```

## 第二步完成（2026-08-17，21 风格资产自造全链落地）

```
产出（42 张图 + 18 风格注册 + 3 升级 + 文档/校验器联动）：
- 映射决策：docs/style-mapping.md——3 重合升级（S07 极简几何→minimal-motion、
  S08 水墨长卷→ink-scroll、S11 产品蓝图→blueprint-craft，补样图引用不重复注册）+
  18 新增注册（modern-paper/clay-stopmotion/felt-craft/mineral-fresco/data-city/
  type-installation/science-slice/historical-archive/comic-evidence/woodcut-print/
  paper-cut-theater/shadow-puppet/offset-collage/deepblue-tear/marker-notes/
  museum-model/retro-pop/comic-style）；vox/fresh-scrapbook/warm-illustration 无重合保持原样
- 样图提示词：docs/style-assets/sample-prompts.md（21 条自造，同题材同构图同中文：
  四物件「旁白稿纸→分镜条→参考图卡→时间线条」+ 四处中文「文字变视频/脚本/参考图/视频提示词」
  + 四类载体嵌入/粘贴/立牌/悬挂 + 底部 8% 留白 + 三层纵深）
- 风格板提示词：docs/style-assets/style-board-prompts.md（21 条，统一框架 + 六格内容表：
  材质/配色/主体/文字载体/运动/负例）
- 产线：Agnes 首张 S01 试出质量达标（MiMo 八项全过）；后续因用户判断 Agnes 平台不稳，
  改 runninghub 用户出图（桌面整份提示词 MD → 用户生成 → 按 1-21 顺序存 → AI 改名）
- 资产：ref/style-assets/（21 样图 + 21 风格板全部 2048×1152=16:9 + style-grid.jpg 21 格拼图
  + README 版权标注）；样图 21/21 中文逐字正确（MiMo 验收：维度 3/5 模板口径不符项已人工复核）
- 注册：18 新风格 config/styles/<id>.json + ref/<id>/（guide.zh.md 风格块 A/B 逐字 +
  参考图骨架 + 禁止句 + 文字注意 + 参考图判断 + 禁止漂移；master-prompt.zh.txt 无文字母板）；
  尾部一律「按尾部契约选档」句式；5 个现有 guide 旧「0.8 秒」句式各 2 处已替换
- 选型规则：chupian-vox style-library.zh.md 总表 24 风格 + 样图展示纪律 + 默认三选 +
  风格板反泄漏追加语；SKILL.md 6→24 风格说明同步；LESSONS Q1-Q7 沉淀
- 评级表：docs/style-assets/style-gallery.md（样图八项评级 + 风格板六项评级 + 分组目录 +
  验收误报说明）
- 校验器联动（对抗性回查发现 2 个空转并修复）：
  ① check_docs MANAGED_DOCS glob docs/*.md 不递归子目录 → docs/style-assets/ 漏扫
    → 改 docs/**/*.md + 测试锁定
  ② 风格文档（Default Project ref/ + config/styles/）不在扫描范围 → 加 EXTRA_STYLE_ROOTS
    外部根扫描 + 路径缺失报 issue 防静默跳过 + 测试锁定
  → 测试 165→167；run_all --project all_pass；check_docs 0 泄漏；sync_skills chupian-vox update；
    voxvideo 104 测试全过（styles 24 个列出验证）
```

## 阶段 3 试点实测记录（2026-08-15，宇树 IPO）

```
环境：MCP 配置后必须重启 opencode 才加载；upload_file 只能传工作区内文件（参考图复制进 Default Project/.tmp-flow）
输入：type_text 多行 = 每段独立提交（灾难，耗点数）→ 剪贴板粘贴 = 完整单段（已验证 350 字）
参考图：输入框 @ 触发媒体选择 → 添加到提示（引用插光标处）；起始/结束帧位是首尾帧，拖拽与 MCP 不兼容
流程：新建项目 → 视频模式（Omni Flash / 16:9 / 6s）→ 输入框 @参考图 + 粘贴提示词 → 创建
点数：测试账号每日 50 点（刷新后 6s 档 4 点/次）；点数耗尽提示「Google Flow 点数已用尽」
遗留：6 个错误生成项（分段提交产物）待清理；「创建」按钮在点数耗尽时状态待确认
```
| ④ run-video 总协调脚本 | ⏳ 待做 |

## 阶段 2 复核记录（20260815-unitree-ipo，2026-08-15）

```
design.json 程序校验：✅ status design_valid=true，41 镜，4 镜带 image_prompt
review-design 门禁（独立子 agent，异常率 7.3% = 3✗/41 < 20%）：
  ✗ 3 处已修：镜 2（610 亿应青蓝-市值口径）、镜 4b（未来青蓝/泡沫墨黑对调）、镜 11a（价格签 150.80 元应青蓝）
  ⚠ 3 处已修：镜 7/9b 删杜撰视觉元素（青蓝圈出/圆点）；8 处相邻同底色→按「每镜换背景」重排（1/5/16/20a/21/28/31 改底色，17/32 被 image_prompt 锁定）
  复核后重新校验：相邻同底 NONE，41 镜全过
generate-images：✅ 母板 + 4 参考图全部 downloaded（Agnes，无失败）
approve-images：✅ 用户人工确认 5 张全部可用（MiMo 402 欠费，跳过 AI 看图，用户看目录确认）
export-handoff：✅ 04-prompts/handoff.md + design-preview.md
【2026-08-15 对抗性回查 P5-P8 后追加】全链重验：run_all + --project 全过；突变测试（篡改 narration）被抓；109 测试全过
```

## 阶段 2 对抗性回查（P5-P8，2026-08-15，第一性原理）

```
P5 05→design.json 无程序校验器：narration 逐字/时长档/参考图集合/image_prompt 逐字全靠子 agent 口头
   （= 关卡 5 P3「口头确认 ≠ 程序化」同类问题在阶段 2 复现）→ 新增 check_stage2.py（程序层，含内部一致性：相邻背景/落点 0.8 秒）
P6 handoff.md vs design.json 一致性无校验（防生成 bug/手动改坏）→ check_handoff_vs_design 接入
P7 run_all 不覆盖阶段 2 产物 → run_all 加 --project 参数（一条命令全链）
P8 manifest 状态机 vs 产物文件无一致性校验（images=completed 但文件丢失检测不到）→ check_manifest_files 接入
测试 77→109；run_all 集成有专门测试（防 P1 复现：宣称接入但代码没跑）
子 agent 语义托底（程序覆盖不到的：动作对齐/颜色口径/handoff 可操作性/风格逐字）：
  4 处 ⚠ 无 ✗ → 修 2：29 镜「219 倍」墨黑（呼应 H 疑问侧）、23 镜「新能源汽车」青蓝（未来读法=答案侧）
  → 记录 2：32 镜（05 内部动作要点 vs image_prompt 不一致被继承，design 忠实 image_prompt 原文）；
    2 镜（三卡全青蓝，150.80/610 与 11a/16 跨镜自洽优先）
  修复后全链重验通过，manifest stages 恢复（design-review/images/image-review/handoff-export = completed，handoff_stale=false）
  留痕：完整核对表落盘 .work/review-design-核对表.md + .work/review-semantic-核对表.md（与关卡 5 核对表-jobcard-review-05.md 同款）
```

## 产物位置

- 当期产物：`C:\Users\xx\Desktop\test\`（01-05 + 素材）
- 项目：`C:\Users\xx\Documents\video-text-flow\`
- 校验器：`checks\`（run_all 一键跑：单文件校验 + check_chain + check_stage2 全链，121 测试）
- 正式项目：`C:\Users\xx\Desktop\test\20260815-unitree-ipo\`（阶段 2 已迁移至此，voxvideo 用 `$env:VOXVIDEO_PROJECTS_DIR` 指向）

## 阻塞 / 待决

- 无阻塞。待决：
  - **待决（用户提出，2026-08-15）**：① ~~项目文件归位~~ ✅ 已解决：阶段 2 项目已移到 `Desktop\test\20260815-unitree-ipo\`（与 01-05 同处）；② 识图 API 配置项化——MiMo 已可用（token-plan key 已配），但「AI 看图 / 问使用者 / 用户自己识别」三选一开关仍未做成配置项；③ 生图配置项化——可选手动生成（不依赖 Agnes API）；④ 生图+识图都可全手动操作
  - 阶段 3 分项（已计划，下一步）：①chrome-devtools MCP 配置（工具层：隔离配置文件 + 只读先行 + 3 镜试点 + 用户确认兜底）②flow-generate skill（工作规则 + 安全边界）③ffmpeg 合并脚本（WSL+ffmpeg，LESSONS H1-H6）④run-video 总协调脚本（程序串全部）
  - 阶段 3 早期项：拆镜作业单→design.json 生成器（05 是 Markdown 表格，需翻译成 design.json shots 结构）
  - 阶段 4 仓库化：voxvideo（Default Project）与 video-text-flow 的关系（独立仓库/子模块/整合）
  - skill 同步纪律：改全局 skill 后必须同步项目副本（skills/README.md 登记）；flow-generate skill 建立后登记

## 成片阶段流程修复（2026-08-18）

```
问题：新对话启用 chupian-vox skill 时，没有先读 LESSONS.md，导致用户要求"合成视频"时简化为单纯视频拼接，
  漏掉裁尾对齐、whisper 转写、ASS 字幕烧录等步骤。
根本原因：SKILL.md 只定义了"到导出 handoff 为止"的流程，没有写"素材包导出后、用户要求出成片"时的标准流程。
  LESSONS.md H1 节是经验记录，不是强制流程，新对话不一定会读。
解决方案：在 SKILL.md 的「边界」部分明确区分「素材包阶段」和「成片阶段」，并新增「成片阶段（强制流程）」章节，
  详细说明完整链路：视频裁尾对齐 → 拼接 → 混音旁白 → Whisper 转写 → ASS 字幕烧录 → 导出 final-subs.mp4。
效果：每次启用 skill 都会读到成片流程，不依赖经验记录，确保用户要求出成片时执行完整链路。
备份：SKILL.md.backup-20260818-HHMMSS 已保存。
同步：python checks/sync_skills.py --apply 已执行，chupian-vox 状态从 same 变为 update。
```
