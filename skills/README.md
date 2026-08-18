# skills（说明书层 · vendored 副本）

**本项目不是全新 skill，是以下全局 skill 的版本快照（vendored 副本）**——clone 仓库后项目自包含，但运行时仍以全局为准。

## 副本清单

| skill | 来源 | 用途 |
|---|---|---|
| human-writing（文案-长文写作） | ~/.config/opencode/skills/human-writing/ | 写正文/立场重写/分镜稿模式 |
| 杜蕾斯文案skill（文案-标题入口） | ~/.config/opencode/skills/杜蕾斯文案skill/ | 标题/hook/关键词/冲突理论 |
| visual-cover（视觉-封面生成） | ~/.config/opencode/skills/visual-cover/ | 封面模板/皮肤表 |
| chupian-vox | ~/.config/opencode/skills/chupian-vox/ | VOX 拆镜/风格库/复核机制 |
| vox-prompts | Default Project/.claude/vox-prompts/（附加源） | chupian-vox 依赖的提示词规范 |
| flow-generate | ~/.config/opencode/skills/flow-generate/ | Flow 视频生成（chrome-devtools MCP，阶段 3） |
| command/cover.md | ~/.config/opencode/command/cover.md | /cover 编排命令 |

**依赖全景（chupian-vox）**：chupian-vox → vox-prompts（✅ 已快照）→ voxvideo 项目本体（config/styles 6 风格、ref/、src/——阶段 4 仓库化时解决：独立仓库/子模块/整合，见 PROGRESS.md 待决）

## 同步约定（重要）

**全局 = 运行时源（当前机器干活用）；项目 = 版本快照（GitHub 可复现）。**

- **白名单制**：只同步 `skills/.sync-whitelist.txt` 内的 skill（本项目用到的）；无关 skill 不复制；项目内白名单外的 skill 目录自动删除
- 新增项目依赖的 skill → 加进白名单 → 跑 `python checks/sync_skills.py --apply`
- 修改全局 skill 后 → 跑 `sync_skills.py --apply` 同步项目副本（hash 检测差异）
- 删除 skill → 同步时自动从项目删除
- 每次同步自动登记下方记录表

**依赖登记纪律（长期）**：在 video-text-flow 项目工作中，**每引入一个新 skill（你调用的 / 新建后保留的 / 测试通过的），都必须**：
1. 加进 `.sync-whitelist.txt`（源在全局 skills/ 的直接加名；源在别处（如 vox-prompts）的加 sync_skills.py 的 EXTRA_SOURCES）
2. 跑 `python checks/sync_skills.py --apply` 同步进项目快照
3. skills/README.md 登记表自动追加

「调用过但项目不需要」的 skill 不进白名单；「项目需要」的标准 = 在 video-text-flow 工作流中被实际引用（skill 的 description/流程引用，或你在项目会话中明确指定）。

## 同步记录

| 日期 | 同步内容 |
|---|---|
| 2026-08-15 | 首次快照：4 skill + cover.md 复制入库（含全部 rules/lessons/references） |
| 2026-08-15 | 自动同步：chupian-dh(add)、docx-gov-format(add)、grill-me(add)、local-talking-head-edit(add)、ppt-master(add)、yt-dlp(add)；cover.md same |
| 2026-08-15 | 自动同步：chupian-dh(remove)、docx-gov-format(remove)、grill-me(remove)、local-talking-head-edit(remove)、ppt-master(remove)、yt-dlp(remove)；cover.md same |
| 2026-08-15 | 自动同步：vox-prompts(add)；cover.md same |
| 2026-08-15 | 自动同步：无变化；cover.md same |
| 2026-08-15 | 自动同步：chupian-vox(update)；cover.md same |
| 2026-08-15 | 自动同步：flow-generate(add)；cover.md same |
| 2026-08-17 | 自动同步：srtvox-director(add)；cover.md same |
| 2026-08-17 | 自动同步：flow-generate(update)；cover.md same |
| 2026-08-17 | 自动同步：chupian-vox(update)、flow-generate(update)；cover.md same |
| 2026-08-17 | 自动同步：chupian-vox(update)；cover.md same |
| 2026-08-18 | 自动同步：chupian-vox(update)；cover.md same |
