---
name: chupian-vox
description: VOX素材包（主程序）：肖翔出片-VOX 系列。仅当用户说完整品牌名「肖翔出片-VOX」或使用 /chupian 命令时启用；只说「肖翔出片」不带后缀时先问是哪个系列。「肖翔出片-数字人」是另一个 skill（数字人出片），不要在此处理。泛词（拆镜、素材包、逐镜提示词、参考图、配音、做视频、出片）不自动触发。流程：脚本→AI 拆镜→逐镜视频提示词→按需参考图与配音→handoff.md，人手工出片。
---

# 肖翔出片-VOX

用户调用本 skill = 启用整套「肖翔出片-VOX」程序（voxvideo，位于 `C:\Users\xx\Documents\Default Project`）。
目标：输入脚本 → AI 拆镜 → 产出素材包（逐镜视频提示词必出、按需参考图与母板、配音）→ 人手工出片。

## 启用后的固定动作

1. 工作目录切到 `C:\Users\xx\Documents\Default Project`，所有命令在那里跑。
2. 先读项目规则 `CLAUDE.md` 和风格指南 `config/styles/vox.json` 里 `guide_files` 列的三个文件
   （`.claude/vox-prompts/SKILL.md`、`ref/vox-style/image-prompts.zh.md`、`ref/vox-style/video-prompts.zh.md`）。
3. 与用户确认脚本的主张后开工，不要急着跑流程。

## 命令写法（Windows）

```powershell
$env:PYTHONPATH = "src"
python -m voxvideo styles                        # 列出风格
python -m voxvideo init --topic <kebab-case> --script-file <path>   # 建项目
python -m voxvideo synthesize-narration --project <id>              # 配音（需 Fish Audio+ffmpeg）
python -m voxvideo generate-images --project <id>                   # 母板+参考图（需即梦）
python -m voxvideo approve-images --project <id>                    # AI 真实看图后确认
python -m voxvideo export-handoff --project <id>                    # 导出操作单
python -m voxvideo resume --project <id> / status --project <id>    # 续跑 / 看状态
```

## 流程要点（详细规则以项目 CLAUDE.md 为准）

- init 之后，AI 读风格指南拆镜，把结果写进 `.work/design.json`：每镜必须有
  `narration` 和 `video_prompt`；`image_prompt` 按需写——写了才出参考图，没写就不出。
- 拆镜时必须主动告诉用户：哪几镜给参考图、为什么（典型三到五镜，不是每镜）。
- **narration 边界（硬约束）**：narration 必须逐字切分用户定稿文案的原文句子——不改写、不润色、不新增、不删句。开头钩子由「文案-标题入口」skill 在文案定稿阶段产出（已拼入正文第一句的文案才算定稿）；用户文案没有钩子时提示先走 /cover 或「文案-标题入口」定稿，本 skill 不擅自写钩子。
- **拆镜前可拆性自检（强制关卡）**：拿到定稿文案先按 human-writing「视频分镜稿模式」的 5 条标准自查（单句≤9s、一句一知识点、相邻3镜不连续同类型、无纯过渡句、有视觉落点）。不达标必须先出分镜稿，禁止跳过直进拆镜；达标才拆。
- **强制前段试点（每期必做，2026-08-17 第 6 轮）**：拆镜完成后**不直接全量**——先出**前 8 镜**（H + 前 7 镜）+ 其中 1 张参考图，给用户确认方向（画面语言/文字载体/参考图风格），确认后才全量拆完剩余镜。不按 >40 镜触发，方向验证与规模无关；与 flow-generate 的 3 镜试点（生成级）形成两级：提示词级试点在本关，生成级试点在 Flow。
- **拆镜定型（每镜必标，2026-08-17 第 3 轮）**：拆镜时给每一镜定型「解释/展示」（判据与规则见 style-library.zh.md「拆镜定型」节）：解释型就近吸附档位；展示型不拆分、封顶 10s、上屏文字逐字覆盖旁白（拆卡不砍字）。型列写进作业表，check_jobcard 校验。
- **拆镜复核（强制关卡，防语义漂移）**：design.json 拆镜完成、generate-images 之前，**必须用 task 工具新起独立子 agent 做语义复核，禁止主 agent 自查代替**（自写自审有确认偏误，实测教训：镜 14「便宜四倍」曾画反成「划掉一块」，应为划掉三块留一块）。
  - 子 agent 全量复核 32 镜，逐镜判定「narration 信息点 ↔ video_prompt ↔ image_prompt」，**明细级核对表落盘项目 `.work/`**（每镜必须有判定，无判定 = 复核未完成；摘要级不是允许的完成形态——全关卡通用规则，先例：`.work/review-design-核对表.md`）
  - **确定性错误**（禁止词、narration 逐字切分、单句>9s、风格块漏写/改字）→ 子 agent 直接修正 design.json，修正记录写入核对表
  - **语义问题**（漂移/画反/缺信息/视觉理解争议）→ 挑出来，出「异常报告」给用户：只列异常项 + 每条带修正建议，用户 1-2 分钟拍板「改/不改」；0 异常时报告一句话「复核通过」
  - **返工决策树（异常率 = 质量信号）**：
    1. 语义异常 < 20% → 打补丁，出异常报告
    2. 语义异常 ≥ 20% → 不修补，派**新子 agent 重新拆镜**（不用主 agent，避免被上次结果锚定）
    3. 异常 ≥3 镜且集中在同一段落 → 只重做该段对应节点（回到分镜稿改那段或局部重拆）
    4. 重新拆镜后二次复核仍 ≥20% → 升级：报告用户，回到定稿/分镜稿节点（异常源可能在更早环节）
  - 硬规则：阈值写死不凭感觉；**返工上限 2 次**，超过必有人工介入；确定性错误不计入重拆阈值；返工成本 ≈ 一次拆镜，远低于带病出片后的重生成，是全场最便宜的修正点。
- **制作细节（patrick 实践）**：点掉每段开头约 1/4 秒模型发呆时间；每镜时长优先 4/6 秒档；最终质检就一句话——「嘴里正在说的，画面里是不是也正在发生」。
- **参考图数量判断**：按 vox-prompts「哪几镜需要参考图」规则（贯穿主体 / 多具名元素空间关系 / 必须准确的英文大字 / 结构性镜头）。「必须准确的文字镜」（如 LUNA -80%、$1.00/$0.20、-80%）必须配参考图钉住，文字是生图最容易崩的部分。
- 顺序：拆镜确认 → 配音（可选）→ 出图（可选）→ 审图 → 导出 handoff.md。
- **输入双入口**：① 用户已有素材（文案/标题/数据——立场必须经关卡0对齐，素材立场≠用户立场时先由 human-writing 立场重写）；② 用户只有立场/标题（human-writing 按立场写正文后再进入本流程）。立场一致性在源头解决，VOX 不补。
- **风格必须用户确认**：拆镜前给 2-3 个风格候选（见 style-library.zh.md），说明气质差异，用户定了才 init，不默认选 vox。
- 工具缺失只影响对应交付件：即梦缺失 = 不出图（不阻塞提示词导出）；
  Fish Audio 缺失 = 不出配音（不阻塞图片与提示词）。
- 提示词写作硬约束在 `.claude/vox-prompts/SKILL.md`，逐条遵守（一镜一运镜、
  动作放「冲击」拍、落点收尾、深度至少两层、不写镜号时码等）。

## 边界（很重要）

- AI 在导出 `04-prompts/handoff.md` 那一刻收工。逐镜生成视频、下载、拼接、
  混入 `02-audio/narration.wav`、加字幕、导出成片——全部由用户手工完成，
  AI 不参与，也不要替用户下载视频或调用浏览器自动化。
- 项目目录 `projects/YYYYMMDD-topic/` 按 01-script … 05-video 分类，
  技术状态放 `.work/`，不与交付混放。

## 用户环境注意

- 生成图片用 Agnes API（`AGNES_API_KEY` 在 `.env`）；下载图片建议开着自游猫代理（自动探测 7892）。
- 配音用本地 Qwen3-TTS（WSL 内 faster-qwen3-tts，克隆 `/root/s2s/ref.wav` 的人声，免费，
  需 NVIDIA 显卡）；Fish Audio 是备选（`.env` 填 FISH_API_KEY / FISH_VOICE_ID）。
- 最终出片用 Google Flow（Omni Flash、16:9），由用户自己操作。

## 成长机制（重要）

本 skill 带实战经验库，与 SKILL.md 同目录的 **`LESSONS.md`** 是成长日志，**`vox-director-method.zh.md`** 是从教程视频蒸馏的 VOX 导演方法论（拆镜定性、参考图提示词模板、时间轴动作写法、题材视觉库、风格切换锚点），**`style-library.zh.md`** 是风格库选型速查与工作流（6 风格总表 + 选型规则 + 用户流程）。

## 风格库与选型工作流（用户只给文案，AI 定风格）

- 24 个已注册风格：`vox`（档案做旧，严肃/科技/商业）、`fresh-scrapbook`（清新手账，生活/美食/旅行）、`warm-illustration`（温暖插画，情感/心理/人文）、`ink-scroll`（水墨国风，文化/历史/文学）、`blueprint-craft`（蓝晒手工，DIY/工程/拆解）、`minimal-motion`（极简动态，效率/方法论/干货），以及 2026-08-17 第二步新增的 18 个（modern-paper/clay-stopmotion/felt-craft/mineral-fresco/data-city/type-installation/science-slice/historical-archive/comic-evidence/woodcut-print/paper-cut-theater/shadow-puppet/offset-collage/deepblue-tear/marker-notes/museum-model/retro-pop/comic-style）——全表与选型规则见 `style-library.zh.md`。
- 选型规则与工作流详见 `style-library.zh.md`：题材匹配 + 语气匹配 → 拿不准给用户 2-3 候选 → 用户确认 → `init --style <id>` → 读该风格 guide.zh.md 拆镜。
- **样图展示**：给用户看 `ref/style-assets/style-samples/` 的样图（附文字描述，不一次抛全部）；一次看全给 `style-grid.jpg`。
- **风格板上传**：出图时把 `ref/style-assets/style-board/<id>.jpg` 与参考图提示词一起上传，配反泄漏追加语（只学材质配色，不学分区布局）。
- 用户只负责文案时：AI 主动推荐风格（说明气质差异），不默认选 vox。
- 同一项目中途不得静默换风格；换风格 = 重新拆镜。

1. **启用时**：先读 `LESSONS.md`，其中已验证的经验条目与 SKILL.md 冲突时，以日期更新在后者为准。
2. **实战后**：每次完整任务收尾时，把本次踩过的坑、验证过的模型行为、流程优化沉淀成
   `[日期] 类别：现象 → 原因 → 解法/规则` 条目追加进 `LESSONS.md`（不重复已有条目，只补增量）。
3. 沉淀标准：下次实战能直接照做的才算有价值；一次性的偶发问题（如临时网络抖动）不记。
4. 环境相关重大变化（如换图片后端、Flow 档位变化）必须追加条目，防止新会话重复踩坑。
