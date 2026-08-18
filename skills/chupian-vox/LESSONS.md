# 肖翔出片-VOX · 实战经验库（成长日志）

本文件是本 skill 的成长机制：每次完整实战后，把这次任务中验证过的经验沉淀到这里。
新会话启用 skill 时，AI 必须先读本文件，并遵守其中已验证的条目（冲突时以本条更新日期在后者为准）。

条目格式：`[日期] 类别：现象 → 原因 → 解法/规则`

---

## 2026-08-11 首次沉淀（项目：20260810-openai-deepseek-price-war）

### A. 环境与工具

- [A1] Agnes 图片 API：key 在项目 `.env` 的 `AGNES_API_KEY`。POST 生成偶发 `WinError 10054`（连接被重置）和 `SSL: UNEXPECTED_EOF`——重跑即可（幂等，submit_id 保留可续传；失败 entry 自动标 failed 再跑会重新提交）。
- [A2] 图片下载走本机代理（adapter 自动探测 7892/18725）；生成请求本身直连，慢/断时重试。
- [A3] 审图必须真实看图：默认入口模型（deepseek-v4-flash）无视觉，用 MiMo API 脚本
  `C:\Users\xx\.config\opencode\scripts\mimo_vision.ps1`。该脚本已修两处：① Invoke-RestMethod 会把 UTF-8 中文双重编码（→改用 Invoke-WebRequest + RawContentStream 后 UTF8 解码）；② max_tokens=1500 会被 reasoning 吃光导致 content 为空（→改 4000）。批量审图用临时脚本（参考 `Temp/opencode/review_images.ps1`：list 文件 每行 `路径<TAB>问题`，结果写 UTF-8 文件逐个 read）。
- [A4] 控制台中文输出乱码（GBK）：一切中文结果写文件（UTF-8）再 read，不要看控制台。

### B. 代码缺陷（已修）

- [B1] `src/voxvideo/pipeline.py` 的 `_adapter()` 原本 `env=None` 直接读 os.environ，`.env` 里的 AGNES_API_KEY 读不到 → 图片生成报「未配置」；已修为 `load_env_file(self.root / ".env")`。改代码后跑 `python -m unittest discover -s tests -t .`（87 个用例）。

### C. Agnes 模型行为（关键，影响出图策略）

- [C1] **「做旧报纸拼贴」强先验**：无论文字禁止句怎么写，画面角落必然出现 THE DEAL / $123 / Fig. 3 – Trade Route / 红色地图针 / 色卡色块（风格训练样本自带）。禁止句只能减少、不能根除。**判定标准**：核心大字拼写正确 + 主体构图正确即可接受，角落元素在 4 秒镜头中不可见；每张最多重抽 3-4 轮，不要无限重抽。
- [C2] 参考图背景禁用带字纸张（报纸头版/护照印章田/账本页/索引卡墙/货运清单）——直接诱导样例文字；改用纯图形纹理（等高线地形图/电路走线/股票曲线雕版）。**禁用「蓝图网格」**：蓝图是蓝色系，会破坏「每镜换背景、配色不变」的棕黄档案调统一。
- [C3] 英文长词必掉字母（`NOT AVAILABLE` 两次抽成 `NOT AVILABLE`）；**换短词**（`CLOSED`）一次成功。拆镜时优先给参考图镜设计短英文大字。
- [C4] 默认风格母板提示词（`ref/vox-style/master-prompt.zh.txt`）自带样例文字（THE DEAL/$123 是它的字体样本面板）→ 参考图图生图必抄；**项目级 `.work/master-prompt.txt` 覆盖为「无文字母板」**（只写材质/配色/图形组件，明令「所有卡片面必须空白」）。生成后审图确认无文字再继续。
- [C5] 真实品牌标志可点名（OpenAI 花环、DeepSeek 鲸鱼），必须写「扁平、不变形」；参考视频（Kimi K3 片）同款用法。提示词里有「不要臆造品牌标志」AVOID 句，不冲突。

### D. 拆镜与结构（Flow 时长约束）

- [D1] **Google Flow（Omni Flash）档位只有 4/6/8/10 秒，且实际成片 ≈ 档位 × 0.90**（8s 档实测 7.23s）。结论：旁白 >9s 的镜必须**拆镜**（一句一镜，按逗号/句号自然断点），保证每镜单段生成；否则要拆两段拼接，节奏重复。
- [D2] 拆镜时长控制：每镜旁白 ≤9s 为目标；拆完用 `synthesize-narration` 拿真实时长复核。
- [D3] **重新拆镜后参考图归属**：manifest `shots` entry 按镜 id 存储，新镜 id 无 entry 时 `generate-images` 会误以为要重新生成 → 请求 Agnes（慢/卡）。图文件未变时不要重生成：复制参考图文件为新镜号 + 把 manifest entry 的 key 重映射（Python 改 manifest.json 一次秒做），再 approve。
- [D4] `generate-images` 幂等跳过依赖 entry.`input_fingerprint` 匹配；design fingerprint 变化只重置 stages（images/image-review/handoff-export → pending），不动 entries。参考图文本没变时重跑全 skipped。

### E. 配音

- [E1] faster-qwen3-tts `serve` **不支持 speed 参数**（TTS 时长由文本韵律决定，无法指定目标时长）。「按最终时长重新配音」= 逐镜重新合成（文本不变）+ 实测偏差用音频变速（ffmpeg atempo）≤5% 兜底；>10% 变速不自然。
- [E2] `synthesize-narration` 会自动把每镜真实时长写回 design.json `duration_seconds`——选档表以此为准。
- [E3] 效果优先原则（用户确认）：重新配音（韵律自然）优于大比例音频变速；变速只做 ≤5% 收尾。

### F. 交付规范

- [F1] 用户要求交付到指定文件夹（如桌面）时：复制副本。**handoff.md 里参考图路径是项目相对路径**（`../03-images\references\...`），副本必须替换为副本内实际路径（`references\...`）。
- [F2] 交付组合：`handoff.md`（完整操作单：旁白+时长+参考图标记+提示词）+ `提示词.md`（纯提示词逐镜代码块，脚本从 design.json 生成）+ `narration.wav` + 参考图 + 母板（可选，说明「不要上传」）。用户说「完整操作单和提示词」= 只要两个 MD，其余按需。
- [F3] 参考图对应表要随拆镜更新（镜号变化后文件改名 + handoff 同步）。

### G. 流程与风格借鉴

- [G1] 先拆镜 → 配音（拿真实时长）→ 出图 → 审图 → 导出；配音时长决定 Flow 选档，别先出图。
- [G2] 参考视频（Kimi K3 解说片）风格要素，可直接写进 video_prompt：做旧地图+黑色地标剪影开场、真实品牌纸牌、实物小模型混合（闹钟/闸机/标签机/地球仪/金币/丝带/照片剪报）、**底部黑底白字字幕条**（写「画面底部是一条黑色字幕条，白色简体中文『XXX』（label）」，Flow 能渲染中文短句）。
- [G3] 字幕策略：**句级字幕**（whisper 转逐句时间戳，2-3s 切换）优于镜级（长镜字幕整段不动）；参考图内不要加字幕条（加剧 C1 文字污染）。
- [G4] 长旁白镜拆镜后的字幕短句：按句提炼 ≤8 字要点，与旁白同步。

---

### H. 字幕与合成链路（2026-08-11 已实测跑通）

- [H1] **后期句级字幕链路**：视频裁尾对齐旁白 → 拼接 → 旁白 TTS 重配（克隆声）→ 拼接音频 → whisper 转逐句时间戳 → 生成 ASS → ffmpeg 烧录。whisper 转写中文会错字（Replit→Rayplate），**用旁白原文替换转写文本，时间戳保留**（按 segments 顺序对应原文句）。
- [H2] ASS 黑底白字条样式（仿参考视频）：`BorderStyle=3`（不透明背景框）+ `BackColour=&H64000000`（60% 透明黑）+ 白字 + `Alignment=2`（底部居中）+ `MarginV=26`；字体 `Microsoft YaHei`。本机 ffmpeg 带 libass，`-vf subtitles=subs.ass` 即可，directwrite 自动找到中文字体（**不要加 fontsdir 参数**，Windows 路径转义会解析失败）。
- [H3] 视频裁尾对齐：视频时长 > 旁白时长时 `ffmpeg -t <旁白时长>` 裁前段（落点定格后裁剪，比大比例变速自然）；变速（atempo）只做 ≤5% 收尾。
- [H4] **烧录字幕 vs 后期字幕不能混**：提示词里写字幕条（Flow 烧录）就必须删掉后期 ASS，反之亦然；两版提示词要严格区分，拆镜重写时容易漏删（本次踩坑：31 镜重写时沿用旧烧录字幕句，导致成片双字幕重叠）。判定：凡是定了「后期句级字幕」，video_prompt 里绝不能出现「字幕条」字样。
- [H5] Flow 生成结果色差：同一提示词多次生成色调不一致（随机 seed）。对策：固定 seed（若支持）/ 同镜多生成挑一致 / 提示词加色板锚定（参考视频蒸馏后）。
- [H6] **混音是独立步骤，极易漏**（本次踩坑：烧字幕用 `-c:a copy` 把视频原声带过、旁白 wav 没混入，用户听不到配音）。正确做法：`-filter_complex "[0:v]subtitles=subs.ass[v];[0:a]volume=0.6[a0];[1:a]volume=1.5[a1];[a0][a1]amix=inputs=2:duration=first[aout]"`（Flow 音效原声 0.6 + 旁白 1.5，比例按听感调）。**验证**：合成后用 whisper 转写成片音轨，能转出旁白文字 = 混入成功；只转出零碎音效 = 漏混。

### I. VOX 导演方法论蒸馏（2026-08-11，两个教程视频 93 帧密采样）

- [I1] 完整方法论已写入同目录 **`vox-director-method.zh.md`**（拆镜定性、参考图结构化模板、时间轴动作写法、题材视觉库、风格切换锚点、剪辑建议）。拆镜与写提示词前必须读它。
- [I2] 参考图提示词最有价值的升级：**主体「数量唯一+位置+占比%」+ 材质/色板独立成句 + 左上暖光 + 允许文字点名 + 负面只写四项（重复主体/额外元素/文字乱码/材质飘移）+ 标签摘要收尾**。
- [I3] 视频提示词：**时间轴分段写动作**（0-Xs 推进 → Xs-Ys 绕行 → 结尾稳定 0.8s），主体动作与镜头轨迹分开描述（「镜头不能代替主体运动」）。
- [I4] 拆镜时给每句旁白定性（提出问题/解释原理/给出证据），一镜一知识点，主体数量明确，右下留字幕安全区。
- [I5] 风格切换一致性靠「关键词+配色+转场锚点」三固定；跨镜统一锚点元素（如红色纸飞机）是强一致性手段。
- [I6] 音效三件套直接写进提示词：纸张摩擦、快速掠过、低频环境音；模型原声保留，后期混音分层。

### J. 方法论落地实践（2026-08-11，当前项目应用）

- [J1] 「结尾稳定保持 0.8 秒」批量追加到全部镜的落点句后（re.sub 落点句），31 镜一次完成；视频未生成阶段改 video_prompt 零成本，务必在用户开生成前做完。
- [J2] **video_prompt 可改、image_prompt 不可改**：改 video_prompt 只重置 stages（approve 一次恢复）；改 image_prompt 会变 fingerprint → 参考图全部重抽（已生成的图作废）。方法论升级参考图时，只影响未出图的新项目。
- [J3] handoff.md 是程序生成的，export 会覆盖；档位标注/节奏建议等人工增量要在 **export 之后**处理（复制 → 打标注 → 插建议），顺序反了会被冲掉（本次踩坑）。
- [J4] 出片节奏建议（已写入当前 handoff）：以旁白为时间轴、关键情绪镜多停半秒、动作偏慢轻微变速、0.8s 结尾便于裁尾对齐。
- [J5] 方法论对「商业数据」题材的强化点：价格/数据对比镜可实物化为微缩城市/道路/标签机等具象模型（当前项目镜 9 已用标签机+硬币，符合）。

### K. 特殊形象锁定（名人/机构/特殊物件，2026-08-11 已验证）

- [K1] **名人/特殊物件形象必须用参考图锁定**：通用元素（太阳、箭头、纸箱、剪影）文字提示即可；真实人物（Replit 总裁 Amjad Masad 等）、机构吉祥物、特殊设备（研究所的 3D 模型等）必须提供形象参考图，否则模型自由发挥性别/形象（本片镜 2/8 曾有此风险）。
- [K2] **获取路径**：Wikimedia Commons API（`action=query&generator=search&gsrnamespace=6&gsrsearch=人名`，香港中转 curl）；维基百科页面常无主图，Commons 是合影（用 MiMo 看图定位人物位置与占比 → PIL 裁剪单人区域 → Agnes 图生图风格化）。
- [K3] **风格化 prompt**（已验证出图质量高）：「将这张人物照片转成 Vox 风格黑白半调剪影：保留可辨识轮廓特征（光头、络腮胡、肩部），黑白半调网点、粗白描边、背后一道错位红色笔触、做旧报纸印刷颗粒、米黄档案纸底，只保留这一个人物，不要其他人/文字/标签/色卡/水印/背景杂物」。
- [K4] 处理后的参考图放 `references/person-<名字>.png`，handoff/提示词.md 手动标注上传镜（export 会覆盖，标注在 export 后补）。审图确认：性别/特征可辨识 + 风格统一 + 无文字污染。
- [K5] 该方法可扩展到机构标志（真实品牌标已在 C5）、特殊设备（如研究所装置：找官方照片 → 剪影化 → 参考图）。

### L. 风格库扩展（2026-08-11）

- [L1] 注册 5 个新风格（`config/styles/` + `ref/<id>/`，每风格 3 文件：json 注册 + guide.zh.md 提示词指南 + master-prompt.zh.txt 无文字母板）：fresh-scrapbook / warm-illustration / ink-scroll / blueprint-craft / minimal-motion。总表与选型规则见 `style-library.zh.md`。
- [L2] 新风格 guide 结构：风格块 A（标准）+ 风格块 B（情绪/揭示）逐字文本、参考图骨架 + 禁止句、文字注意、参考图判断规则；统一带「结尾稳定保持 0.8 秒」。
- [L3] 风格选型工作流：用户只给文案 → AI 按题材+语气推荐（拿不准给 2-3 候选）→ 用户确认 → init --style <id> → 读该风格 guide 拆镜。同一项目中途不换风格。
- [L4] 新风格暂无风格样张图（reference_files 为空）：参考图母板由 master-prompt.zh.txt 运行时文生图生成（vox 的教训：母板提示词必须无文字）。后续可给每个风格生成样张图补进 reference_files。
- [L5] 每个风格「一句一镜、一镜一知识点、右下字幕安全区、名人/特殊物件锁参考图、后期句级字幕」等通用规则不变（见 style-library 通用规则节）。

### M. 配音双轨（Fish Audio 新 API + 用户克隆声，2026-08-12 已验证）

- [M1] **Fish Audio 官方新端点（旧端点已废弃 401）**：`POST https://fishaudio.org/api/open/v1/speech/tts`，Header `Authorization: Bearer <key>`，body `{"text": "...", "voiceId": "<音色ID>"}`，返回 audio/mpeg（mp3）。注意：① 旧文档的 `api.fish.audio/v1/tts` + `reference_id` 会 401；② urllib 需带浏览器 UA 否则 403；③ 系统测试音色 `00a1b221-6137-4b73-ad62-b0cbce134167` 可用。
- [M2] 用户已提供 Fish key（已存入对话，未落盘代码；需要时写入项目 `.env` 的 FISH_API_KEY/FISH_VOICE_ID——注意 narrator_from_config 走的是旧端点，新端点需更新 narration.py 或直接脚本调用）。
- [M3] 用户偏好：Fish API 可用且音质 OK；具体音色待用户后面挑选（选好再固化 voiceId）。当前项目配音默认用**用户克隆声**（Qwen3-TTS，ref=`声音/2.wav`，ref_text=whisper 转写文本）。
- [M4] 用户声音样本 2.wav（13.76s）= 用户本人念的镜 1-3 旁白；克隆声版本合成后 12.56s，比用户原声快约 1s（TTS 语速差异，用户反馈后再调）。
- [M5] 测试素材：`testsucai/1-5.mp4` = 镜 001-005 生成视频（用户实际生成的档位与建议档位有出入，如镜 2 用 4s、镜 3 用 6s——以实测时长为准，不纠档位）。

### N. GitHub 开源调研（2026-08-12，三个高星 VOX 项目方法论）

- [N1] 调研对象：`Alisa0808/vox-director`（1273★，全自动端到端）、`cyberlesterr/paper-collage-video`（189★，Remotion 本地引擎）、`louchi1984-coder/voxeasy`（70★，Flow 提示词导演，与我们流程最贴）。
- [N2] **图片提示词 5 段结构**（vox-director，与教程蒸馏的模板互补）：①STYLE BLOCK 每镜逐字复用（这是全片统一的关键）②SCENE 描述为独立剪贴件（每个元素有清晰边缘+投影→视频模型才能分层视差）③BACKGROUND 单一大胆平色 ④HEADLINE 短粗 2-3 词烤进图里（图片模型渲染文字远好于视频模型）⑤TECH（比例/2k）。
- [N3] **视频提示词 5 轴 + 稳定性三轴**（vox-director）：GOAL + CAMERA + MOVEMENT + AESTHETIC + FEEL + COLOR + CONSTRAINTS；稳定性三轴（⭐最重要的反崩手段）：Motion amplitude（`very subtle ~5%`，避免 intense 靠近文字）、Dimensional lock（`flat 2D, camera parallel to the poster, no 3D rotation; paper layers parallax only`）、Stability anchors（`headline/logo/layout stay sharp and perfectly stable — do not redraw`）。
- [N4] **Omni 措辞规则**：Omni/Veo/Runway 对 `no/don't` 负面词会反噬（"may result in the opposite"），画面描述应正面措辞；Kling/Seedance 才支持负面提示词。我们的 AVOID 块在 Flow 上对「不要音乐旁白」类仍有效，但画面类否定（不要 3D 等）建议改写正面（"flat 2D paper"）。
- [N5] **⚠ Omni/Seedance 拒绝真人+品牌标志**（vox-director 实测）：名人脸与品牌 logo 进图生视频会 block（"prohibited contents"），改 JPG/去名字/剪影都无效，是图像内容检测；**Kling O3 pro 允许**；本地逐帧引擎无此限制。本项目镜 2/8（Replit 真人参考图）、镜 1/8/15/16（OpenAI/DeepSeek 标志）有被拒风险——被拒时去掉标志/真人描述重试，或换 Kling。
- [N6] **表达方式路由**（voxeasy，拆镜时用）：每镜只选一种：①`direct` 直接呈现（有真实主体/过程/数据就直给）②`story` 故事场景（有具体人物事件）③`metaphor` 视觉隐喻（抽象关系/不可见机制才用）。**能用真实主体讲清就不强行隐喻**；隐喻映射从首帧到末帧不变。
- [N7] **时间轴规则**（voxeasy）：语义优先合并/拆分（不机械一行一镜）；**可长不可短**：选完整覆盖实际时长的最小档位（≤4→4、>4≤6→6、>6≤8→8、>8≤10→10），素材尾部裁短不选短档；字幕间停顿与开场空白必须保留；中文 220-240 字/分钟估时。
- [N8] **输出合同**（voxeasy）：Prompt 前两句写风格+比例+时长（`Vox style paper-cut collage art, 16:9. 6-second duration.`）；4/6/8s 最多两个动作阶段、10s 最多三个；Hex 色值只作不可见控制（写"Never render Hex codes as visible text"）；动作时间戳必须与档位一致。
- [N9] **转场意图表**（paper-collage-video，用户剪辑时参考）：continuity→slide 0.45s、location-change→wipe 0.5s、time-passage→page-turn 0.7s、focus-reveal→iris 0.55s、chapter-reset→shutters 0.65s、impact→cut 0s（纸边转场风格）。
- [N10] **visual-sfx 拟声词**：画面可带 1-8 字拟声词（咚！砰！嗖—，stamp/shake/drop-impact 动画），必须绑定对应音效、不与字幕重叠；环境音只走音频不走画面文字。
- [N11] **主题预设表**（vox-director 的 10 个）：american-retro / swiss-modern / punk-zine / soviet-constructivist / wpa-propaganda / 70s-groovy / chinese-ink / atomic-age / newsprint-editorial / gilded-deco——作为 vox 内部色板变体备选（比另建风格轻量）。
- [N12] 模型选型（Atlas 价格参考）：海报图 nano-banana-2（~$0.08，CN/EN 文字渲染最好）、动画 gemini-omni-flash i2v（~$0.13，文字稳定+分层视差）、真人/品牌 Kling o3 pro（~$0.095）、配音 xai/tts（~$0.015）、音乐 minimax/music-2.6（~$0.11）。~30s 片成本约 $0.8-1.0。
- [N13] ffmpeg 教训：慢放用 setpts 不冻结；关键文字后期叠加（不靠视频模型渲染）；最终 timing 从实际音频 ASR 推导不用脚本预估（我们已在做）；amix 默认归一化会减半音量（已踩过，normalize=0 修复）。

### O. 封面与发布信息（2026-08-12，杜蕾斯文案 skill 联动）

- [O1] 出片收尾时主动问用户要不要「发布信息」：标题/简介/封面文案/转发语（杜蕾斯式双层语义：表层事件、里层主张，一跳可达、点破即死；3-5 方案不同公式让用户选）+ 封面图（多渠道版式骨架必须不同，不许换皮）。
- [O2] **封面图管线：AI 只出无文字底图 + PIL 代码排版文字**（杜蕾斯 skill 原则：中文永不出错）。Agnes 底图**必带乱字**（"仅剩10席名额"等）——对策：① 提示词避开「报纸头版」类描述（必出字）用「纯纸纹理」；② PIL 后处理覆盖乱字区（顶部横幅涂红条、底部涂采样纸色）；③ 最后 MiMo 审图确认无乱字。
- [O3] 中文字体：思源黑体 `C:\Windows\Fonts\NotoSansSC-VF.ttf`（SIL OFL 免费可商用），PIL `set_variation_by_axes([wght])` 调字重；关键词放大 ~1.6-1.7 倍染品牌色（Vox 红 #D62E1F），其余同字号墨黑。
- [O4] 交付结构：图是图（`封面/` 目录）、文字是文字（handoff「发布信息」区块）；handoff 是程序生成，发布信息区块在 export 后手动补（同档位标注）。

## 未解决的问题（下次实战验证）

- generate-images 在「结构变化但图未变」时仍会因缺 entry 发起网络请求（已用 D3 绕过）；是否在 CLI 层加「--map-shots 旧:新」参数待定。
- Flow 10s 档实际时长的准确分布（8s 档测了 7.23s，本次测试 10/6/4 档实际 10.0/6.0/4.0s，与 7.23s 个例矛盾）——每次实战请用户记录实际时长，统计真实规律。

## 2026-08-15 流程与制作细节

- [P1] **可拆性自检是拆镜前强制关卡**：定稿文案先按 human-writing「视频分镜稿模式」5 条标准自查（单句≤9s、一句一知识点、相邻3镜不连续同类型、无纯过渡句、有视觉落点）。不达标必须先出分镜稿，禁止直进拆镜——否则拆出连续数据镜/氛围镜，能生成但效果闷。
- [P2] **分镜稿三操作防漂移**：拆长句（标来源）/ 删过渡（标来源）/ 【新增】评点句。无来源标注的句子=擅自重写，禁止。
- [P3] 制作细节（源自 patrick 教程逐字稿，待实测）：点掉每段开头约 1/4 秒模型发呆时间；每镜时长优先 4/6 秒档；最终质检就一句话——「嘴里正在说的，画面里是不是也正在发生」。
- [P4] hook 重叠处理：hook 与正文第一句信息重叠时只改 hook 不动正文（正文在分镜稿阶段已冻结）。
- [P5] **hook 不杜撰细节**（实测 2026-08-15 抓到的堵点）：hook 只基于正文已有信息，不得写正文没有的数字/事件/概念（如「价格战打了三个回合」——正文无此内容）。出 hook 后对照正文逐项核对，找不到出处就改。
- [P6] **建校验器必须对照规则全文逐条翻译，不能凭记忆挑几条**（实测 2026-08-15）：check_rewrite 只翻译了冒号/破折号/排比/长列举四项，human-writing 成稿禁令的**翻案腔**（不是…而是…/并非…而是…/表面…实际…等 6 种外衣）漏译 → 01 稿 3 处翻案腔过了关卡 1 程序校验 + 子 agent 复核（子 agent 清单也没列翻案腔维度）直到 2026-08-15 全量重查才抓到。教训：① 建校验器时把上游 skill（human-writing 等）成稿禁令**全文**过一遍，每条禁令要么程序化、要么写进子 agent 固定清单，不留空白；② 子 agent 清单维度 = 程序未覆盖的禁令集合，清单要照 skill 原文逐条抄，不凭记忆。
- [P7] **豁免机制（2026-08-15 确立）**：程序报错 → 用户决策豁免 → 产物复核块写「豁免登记：<检查项>（理由）」，run_all 将该检查项降为 exempt（报告仍列出 severity=exempt，可见可查，非沉默放行）。只豁免明确登记的项；新产物原则上不豁免（规则确立后按规则走）。历史产物（规则确立前）允许豁免，靠程序补漏防未来复犯。
- [P8] **子 agent 复核明细级留痕 = 全关卡规则（2026-08-15）**：每关子 agent 复核必须落盘明细级核对表文件（逐项判定 + 异常处置），放产物同目录或项目 `.work/`。摘要级（只在复核块写结论）不是允许的完成形态——对话会丢，文件不会。先例：关卡 5 `核对表-jobcard-review-05.md`、阶段 2 `.work/review-design-核对表.md`、01-04 重查 `.work/checklist-review-01~04.md`。
- [P9] **MiMo token-plan API（2026-08-15 实测，三能力）**：baseURL `https://token-plan-cn.xiaomimimo.com/v1`，key 存 `Default Project/.env` 的 MIMO_API_KEY（**.env 优先于环境变量**——shell 残留旧 key/旧 URL 是 401 主因，URL 一律硬编码新地址，别用 MIMO_BASE_URL）。①识图 mimo-v2.5：标准 image_url base64；②ASR mimo-v2.5-asr：user content 只放 input_audio（`data:audio/wav;base64,` 前缀或纯 base64+format），**不能带 text 部分**（网关注入提示词，带 = 400），顶层 `asr_options.language`（auto/zh/en），wav/mp3 ≤10MB，**按量计费**；③TTS mimo-v2.5-tts：chat/completions，待合成文本放 **assistant** 消息、user 消息 = 风格指令（voicedesign 必填），顶层 `audio:{"format":"wav","voice":"mimo_default"}`（预置音色 8 个），响应 `choices[0].message.audio.data` base64 wav，**限时免费**；voicedesign 用文本设计音色、voiceclone 用 `data:audio/mpeg;base64,样本` 克隆。
- [P10] **配音/字幕链路顺序（2026-08-15 用户定）**：配音 **MiMo TTS 置顶优先**（provider=mimo-tts，style_prompt「明快干脆语速偏快」）→ 本地 Qwen3-TTS 克隆声备选 → Fish 兜底；字幕 whisper 转写（WSL）→ MiMo ASR 备选（按量计费注意余额）。
- [P11] **MiMo TTS style_prompt 陷阱（2026-08-15 实测）**：中文 prompt 里的「沉稳/专业/适中」会被模型理解为放慢语速（44 字 8.64s vs 无 style 7.04s），「明快/干脆/偏快」最快（5.76s）。调语速用对词，别用模糊的「适中」。
- [P12] **MIMO 旧 key 全局清理（2026-08-15）**：旧 key（sk-cw70tbt…）在用户级环境变量持久残留，每个新 shell 都带上 → 新 key 401/402 反复。彻底清：`[Environment]::SetEnvironmentVariable('MIMO_API_KEY',$null,'User')` + MIMO_BASE_URL/MIMO_MODEL 同删；.env 只留新 key（tp-ci9lmx…）。脚本读 key 规则：.env 优先、环境变量次之（2026-08-15 起）。
- [P13] **双后端配音对比流程（2026-08-15 验证）**：两套 TTS（本地克隆声 + MiMo）各合成 41 镜 → durations.json 逐镜时长 → 各自合并整片 → 桌面交付试听 → 用户选定后端 → synthesize-narration 写回真实时长到 design.json → 档位复核 → export-handoff。踩坑：中途中断/换样本后重跑必须清空 takes 再全量（`if not dest.exists()` 会跳过旧产物）；probe 在 GBK 控制台读 ffprobe 输出会 UnicodeDecodeError，用 encoding='utf-8' 或换 subprocess 读法。
- [P14] **handoff 档位取整（2026-08-15）**：Flow 只有 4/6/8/10 秒档，handoff 不能写真实旁白时长（5.8s 用户没法选）→ `flow_slot(seconds)` 向上取整到念得完的最小档，显示「Flow 档位：6s（旁白真实时长 5.8s）」。test_handoff_flow.py 覆盖（97→101 测试）。
- [P15] **narration.py 配置段 bug（2026-08-15）**：`narrator_from_config` 的 mimo-tts 分支读 `nar.get("mimo_tts")`（narration 段），但 mimo_tts 配置在 **config 顶层** → 取到空配置、style_prompt 变空 → 单测与全量行为不一致。修：`config.get("mimo_tts") or nar.get("mimo_tts") or {}`。教训：配置键放哪层，读的时候必须同一层，加测试锁定。
- [P16] **项目位置可迁移（2026-08-15）**：voxvideo CLI 新增 `VOXVIDEO_PROJECTS_DIR` 环境变量覆盖项目根（默认 ROOT/projects）；项目移到 Desktop\test 后命令：`$env:VOXVIDEO_PROJECTS_DIR="C:\Users\xx\Desktop\test"; python -m voxvideo <cmd> --project <id>`。handoff 内相对路径（../03-images/...）随项目整体移动仍有效。

## 2026-08-17 第二步：21 风格资产自造（Q 类）

- [Q1] **样图/风格板产线（用户 runninghub 出图 + AI 验收）**：Agnes 出图质量不稳时，改由用户在自己选的平台（runninghub）生成，AI 出完整提示词（每张一条、可整体复制，存桌面 MD 供复制）、用户按 1-21 顺序存图、AI 改名（Python `Path.rename`，PS 中文乱码别用 PowerShell 改名）。效果不好**不重试**，直接让用户换平台生。
- [Q2] **参考图八项模板在「样图」场景的误报**：维度 3（主体数量）与维度 5（连续性）是为**单镜参考图**设计的——样图本就设计为四件物件、静态无转场锚点，MiMo 按模板口径报「主体不唯一/无锚点」是口径不符不是图的问题。判定改按「四件齐全无多余」；画幅项个别误报（实测 2048×1152=16:9），用 PIL/System.Drawing 读实际像素复核，别信 MiMo 目测比例。
- [Q3] **风格板专用验收六项**：六格结构（2×3 齐全）/标签字（材质配色主体载体运动负例）/载体空白（除标签外零文字）/材质统一/形状完整/画幅。与参考图八项不同，别混用模板。风格板上传必须配**反泄漏追加语**（只学材质配色，不学分区布局，不画格子标签条色卡）。
- [Q4] **PS1 脚本中文必崩（再犯）**：新写 review-style-boards.ps1 忘了 BOM → 语法错误满屏。规律重申：.ps1 必须 UTF-8 with BOM（`[System.IO.File]::WriteAllText($f,$c,[System.Text.UTF8Encoding]::new($true))` 一行修复）。
- [Q5] **check_docs 扫描范围坑（P6 同类）**：MANAGED_DOCS 用 `docs/*.md` **不递归子目录** → docs/style-assets/ 里的评级表/提示词全漏扫（约束 4 联动空转）。修：glob 改 `docs/**/*.md` + 加测试锁定；外部风格文档根（Default Project ref/ + config/styles/）加 EXTRA_STYLE_ROOTS 扫描，路径不存在时报 issue 防静默跳过。教训：校验器扫描范围改完必须加"违规样例必须检出"测试，宣称扫了但代码没扫 = 假通过。
- [Q6] **风格注册 3 文件 + 资产 4 件套**：每新风格 = config/styles/<id>.json + ref/<id>/guide.zh.md + ref/<id>/master-prompt.zh.txt（母板一律无文字）；21 方向资产 = 样图 + 六格风格板 + 总览图（PIL 拼 7×3）+ 提示词/评级表文档。重合方向（S07 极简几何→minimal-motion、S08 水墨长卷→ink-scroll、S11 产品蓝图→blueprint-craft）只升级资产不重复注册。
- [Q7] **母板无文字纪律扩展**：C4 教训升级——所有新风格 master-prompt 统一「画面中绝对不允许出现任何字母、单词、数字、文字」+「所有卡片与牌面必须空白」句式；样图提示词（含上屏中文）与风格板提示词（载体全空白）分开写，不混用。
