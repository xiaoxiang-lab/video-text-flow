# video-text-flow · 视频文本生产流水线（私有仓库）

> 中文说明在下，English: [README.EN.md](README.EN.md)

**一句话**：素材（文案/标题/数据）→ 立场对齐 → 分镜稿 → 配音定稿 → 封面 → 拆镜作业单 →
voxvideo 素材包（逐镜提示词 + 参考图 + 配音）→ 人手工出片。

质量保障：**程序校验（确定性）+ 受约束子 agent（语义）+ 用户决策**，三层防漂移。
能程序化就不要大模型；LLM 执行规则 = 概率性重新解释，程序 = 翻译一次执行 N 次。

## 信任链（第一性原理）

```
规则层：假设，标注来源（实测/偏好/硬件）
  ↓ 一次性翻译
程序层：checks/ 确定性执行，自身被测试覆盖（防假通过）
  ↓ 只兜底不可形式化的
子 agent 层：独立上下文 + 约束，输出被程序验证
  ↓ 只留下主观判断
用户层：决策（立场/风格/标题选择）——主观不可程序化
```

## 关卡流程

| 关卡 | 产物 | 程序校验 | 子 agent 语义 | 用户决策 |
|---|---|---|---|---|
| 0 | 立场确认（对话） | — | 复述素材立场 | ✅ 认同/换立场 |
| 1 | `01-立场重写稿.md` | check_rewrite | 立场/事实/可念 | ✅ 确认立场稿 |
| 2 | `02-分镜稿.md` | check_storyboard | 知识点/视觉落点/类型裁决 | ✅ 确认+选标题+选风格 |
| 3 | `03-配音定稿.md` | check_storyboard | hook 一致性 | ✅ 确认定稿 |
| 4 | `04-封面出图提示词.md` | check_cover | 意象-议题推导验证 | ✅ 确认封面 |
| 5 | `05-拆镜作业单.md` | check_jobcard | 核对表（narration↔video_prompt） | ✅ 确认 |

## 使用

```
# 1. 校验单个产物
python checks/check_rewrite.py    <01-立场重写稿.md>
python checks/check_storyboard.py <02-分镜稿.md>
python checks/check_cover.py      <04-封面出图提示词.md>

# 2. 一键校验目录（按 01-05 文件名识别；03 走链层校验，check_chain 全链必跑）
python checks/run_all.py <产物目录>

# 3. 阶段 2 链校验（05→design.json→handoff→manifest；voxvideo 素材包产物）
python checks/check_stage2.py <05-拆镜作业单.md> <项目目录>

# 4. 一键全链（01-05 + check_chain + check_stage2 阶段 2 链）
python checks/run_all.py <产物目录> --project <项目目录>

# 5. 校验器自身测试（防假通过——校验器也要被校验）
python -m unittest discover -s checks/tests -t checks
```

## 校验器自身被测试覆盖

`checks/tests/`：167 个测试（违规样例必须检出、合规样例不得误报；含防假通过：
0 镜解析必须报错、run_all --project 必须真跑 check_stage2、豁免登记必须可查非沉默放行、
check_docs 子目录与外部风格文档根必须被扫到）。
校验器改参数/加规则 → 先加测试 → 再改代码（TDD）。

## 豁免机制（用户决策落盘）

程序报错 → 用户决策豁免时，在产物复核块写一行 `豁免登记：<检查项>（理由）`，
run_all 将该检查项降为 exempt（报告仍列出，severity=exempt 可见可查），
其他违规照常报。只豁免明确登记的项；新产物原则上不豁免。

## 仓库内容

| 目录 | 是什么 | 运行时位置（本机） |
|---|---|---|
| `checks/` | 程序校验器（run_all 一键；167 测试） | `C:\Users\xx\Documents\video-text-flow\checks\` |
| `docs/` | 规则文档、21 风格映射/提示词/评级表、验收清单 | 同上 |
| `scripts/` | merge-video、review-images（MiMo 八项）、风格板验收、拼图、Agnes 批量出图等 | 同上 |
| `skills/` | skill 快照（白名单同步自全局，**不含字体**） | 项目自包含，运行时以全局为准 |
| `vendor/` | srtvox-director 上游快照（参考源，VENDOR-NOTICE 标注） | 同上 |
| `voxvideo/` | VOX 素材包程序（src/config/ref/tests + CLAUDE.md + .claude/vox-prompts） | 运行时在 `C:\Users\xx\Documents\Default Project\` |

## 新 agent 上手（同一台电脑，clone 即用）

1. `git clone <仓库地址>` 到任意位置（建议 `C:\Users\xx\Documents\video-text-flow`）。
2. 本项目依赖的外部件**本机已装好，无需重复安装**：
   - 全局 skills：`C:\Users\xx\.config\opencode\skills\`（运行时以全局为准，
     仓库 `skills/` 只是快照；改全局后跑 `python checks/sync_skills.py --apply` 同步）
   - 运行时程序：`C:\Users\xx\Documents\Default Project\`（voxvideo 本机已有部署；
     仓库 `voxvideo/` 是完整副本，供恢复或参考）
   - Python + PIL、7-Zip、git、ffmpeg、WSL（faster-whisper / Qwen3-TTS）均已装
3. 密钥：见下节，最多问用户要一次。
4. 验证基线：`python -m unittest discover -s checks/tests -t checks`（167 全过）+
   `python checks/check_docs.py`（0 issues）+ `python checks/sync_skills.py`（全 same）。

## 密钥与模型（不在仓库，用户自填）

- `.env` 密钥（在 `Default Project\.env`，**绝不入库**）：
  - `AGNES_API_KEY`（Agnes 生图）
  - `MIMO_API_KEY`（MiMo 识图/ASR/TTS，token-plan）
  - `FISH_API_KEY` / `FISH_VOICE_ID`（Fish Audio 兜底配音）
- 本地模型（WSL 内，**大文件不传 GitHub**）：
  - Qwen3-TTS（`/root/models/qwen3tts`，克隆声）
  - faster-whisper-large-v3（字幕转写）
- 字体（**131MB 不传**）：`skills/杜蕾斯文案skill/assets/fonts/cjk/` 的思源黑体、
  霞鹜文楷等开源字体——同一台电脑上全局 skill 目录已有，跑
  `python checks/sync_skills.py --apply` 即从全局恢复；换新电脑时按官方源下载
  （Noto Sans/Serif SC、LXGW WenKai、ZCOOL 系列）。

## 生成产线备忘（Agnes 出图不稳时）

- 样图/风格板提示词在 `docs/style-assets/`（sample-prompts.md / style-board-prompts.md）。
- **Agnes 效果不好时不重试**：直接把这些提示词交给用户，让用户在 runninghub
  等平台自行生成，AI 负责后续验收/评级/改名（LESSONS Q1）。
- 42 张风格资产在 `voxvideo/ref/style-assets/`（21 样图 + 21 六格风格板 + style-grid）。

## 目录速查

```
checks/                 程序校验层（run_all 一键；167 测试防假通过）
docs/
  second-step-brief.md  第二步任务简报（匹配约束 10 条）
  style-mapping.md      21 方向 ↔ 6 现有风格映射
  check-mapping.md      srt-vox 16 项 ↔ 校验器对账
  review-checklist.md   参考图八项 + 视频六项
  style-assets/         样图/风格板提示词 + 评级表
scripts/                出图/验收/拼图/合并脚本
skills/                 说明书快照（白名单制）
vendor/srtvox-director/ 上游参考快照（不开源分发）
voxvideo/               VOX 素材包程序（24 风格注册 + 42 张资产 + 104 测试）
NEXTSESSION.md          会话交接（新对话先读）
PROGRESS.md             进度台账
DECISIONS.md            决策记录
关卡定义.md             关卡与分工详表
```

## 版权

私有仓库，不开源不公开分发（DECISIONS 2026-08-17）。上游 srt-vox-director 无 LICENSE，
本项目仅吸收方法论（结构全收、表达重写），21 风格资产全部自造，来源标注见
`vendor/srtvox-director/VENDOR-NOTICE.md`。
