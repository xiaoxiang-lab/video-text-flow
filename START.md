# video-text-flow · 新会话启动引导（START.md）

> 新会话接手本项目时先读本文件 + README.md + PROGRESS.md + DECISIONS.md，即可无缝接上进度。

## 多对话开发协议

**本项目是多对话接力开发**（一整个链路，单对话不够）。每个对话：

```
开始：读 START.md → README.md → PROGRESS.md（进度）→ DECISIONS.md（决策）→ LESSONS 教训
      + 跑一次 `python checks/sync_skills.py`（检查全局 skill 与项目快照差异）
进行：按 PROGRESS.md 的「下一项工作」推进
      ⚠️ 发生时更新（不是结束时）：
        - 每完成一个关卡/决策 → 立即增量更新 PROGRESS.md / DECISIONS.md（几行字，实时落盘）
        - 里程碑后随时可跑 /export 快照（不等到对话结束）
        - 这样即使对话中途崩溃/中断，结论已在文件里，丢失的只有最后几分钟
结束（正常收尾时）：确认文件已是最新 + 跑 `sync_skills.py --apply`（同步 skill 快照）
      + 跑一次 /export 留档
```

**skill 同步程序化**：全局新增/修改/删除 skill 后，跑 `python checks/sync_skills.py --apply` 即同步项目快照（新增/更新/删除全自动，登记表自动追加）——不靠纪律靠程序。

结论在文件（实时），过程在导出（快照兜底）——新对话永远从文件接上，不依赖上一个对话的记忆。

## 最终目的（一句话）

用户每期给出素材（文案/标题/数据），走通 0-5 关卡，产出：立场重写稿 → 分镜稿 → 配音定稿 → 封面提示词 → 拆镜作业单，交付后用户直接拿去生成视频/封面。**质量靠程序校验 + 受约束子 agent，用户只做决策确认**（能程序化就不要大模型）。

## 当前进度（2026-08-15，宇树 IPO 全链 + 阶段 2 完成 + 配音定案）

- ✅ 关卡 0-5 全部完成并验收（01-05 产物在 `C:\Users\xx\Desktop\test\`，全带复核记录；05 为 41 镜拆镜作业单，已确认）
- ✅ 阶段 2 全链打通：项目已按用户指定位置迁移到 **`C:\Users\xx\Desktop\test\20260815-unitree-ipo\`**：init → design.json（41 镜）→ review-design 门禁（异常率 7.3% 修复后通过）→ generate-images（母板+4 参考图）→ approve-images → export-handoff ✅
- ✅ 配音定案（用户试听拍板）：**MiMo TTS 置顶优先**（provider=mimo-tts，style_prompt「明快干脆语速偏快」）→ 克隆声备选 → Fish 兜底。41 镜真实时长已写回 design.json（总 3:10），handoff 已按 Flow 档位（4/6/8/10 向上取整）重新导出
- ✅ MiMo token-plan API 三能力接入：识图 mimo-v2.5 / ASR mimo-v2.5-asr（whisper 备选）/ TTS mimo-v2.5-tts（TTS 限时免费，ASR 按量计费）；key 在 `Default Project\.env`（MIMO_API_KEY），旧 key 已全局清理
- ✅ 对抗性回查 P1-P16 全部完成并固化（翻案腔检测、豁免机制、明细级核对表、check_stage2、MiMo 各坑）；voxvideo 101 测试 + video-text-flow 121 测试全过
- ⏳ 待决（未处理）：识图/生图 API 配置项化（可用时 AI 看图，欠费时问使用者/手动——本轮 MiMo 已可用，配置项化仍待做）
- 封面皮肤方案已实测确认（minimal-motion）；模板固化（visual-cover skill：只填标题+换皮肤）
- 阶段 3 计划已确认（Flow MCP+skill → ffmpeg 合并 → run-video 总协调；知识文件 `docs/flow-knowledge.txt`）；架构判断：不建 cover2/3/4/5 命令，总协调是程序不是命令（见 DECISIONS.md）

## 接续步骤（阶段 3）

1. **阶段 3 分项（按序）**：①chrome-devtools MCP 配置（工具层：隔离配置文件 + 只读先行 + 3 镜试点 + 用户确认兜底）②flow-generate skill（工作规则 + 安全边界，登记进 skills/README + sync_skills）③ffmpeg 合并脚本（WSL+ffmpeg，LESSONS H1-H6 已沉淀）④run-video 总协调脚本（程序串全部）
2. 阶段 3 自动化（可并行）：拆镜作业单 → design.json 生成器（05 表格翻译成 shots 结构）
3. 待决项：识图/生图 API 配置项化（AI 看图/问使用者/手动三选一开关）
4. 阶段 4 仓库化：voxvideo（Default Project）与 video-text-flow 的关系（独立仓库/子模块/整合）

## 关键文件索引

| 文件 | 作用 |
|---|---|
| `README.md` | 信任链/关卡流程/用法/验收状态 |
| `关卡定义.md` | 0-5 关卡 + 决策摘要模式 + 独立风格确认 |
| `校验器设计说明.md` | 判据（程序 vs 子 agent）+ 规则假设来源 |
| `checks/` | 程序校验器（run_all 一键跑，含 check_stage2） |
| `skills/README.md` | 引用的 4 个全局 skill |
| `~/.config/opencode/skills/` | human-writing/杜蕾斯/visual-cover/chupian-vox（说明书） |
| `~/.config/opencode/command/cover.md` | /cover 编排命令 |
| `C:\Users\xx\Desktop\test\` | 当期产物（01-05 + 项目 20260815-unitree-ipo） |
| `C:\Users\xx\Documents\Default Project\` | voxvideo 程序（CLI：`$env:VOXVIDEO_PROJECTS_DIR` 覆盖项目根） |

## 硬规则速记

- 关卡完整性：每关独立交付独立确认，禁止合并跳过
- 决策摘要确认：用户只读 🔴 需决策项，不做全文阅读；AI 判断项必须带判断标准，不裸抛（L6）
- 立场一致性：hook/标题/封面/拆镜 = 关卡 0 确认的立场
- 复核记录：交付物带复核块（无标记 = 未完成）；用户确认 ≠ 规则合规
- **子 agent 复核留痕（规则，2026-08-15 起全关卡通用，新文案/新话题必执行）**：每关子 agent 复核必须落盘**明细级核对表文件**（逐项判定 + 异常处置），放产物同目录或项目 `.work/`（先例：关卡 5 `核对表-jobcard-review-05.md`、阶段 2 `.work/review-design-核对表.md`、`.work/review-semantic-核对表.md`）。摘要级（只在复核块写结论）不是允许的完成形态；01-04 是规则确立前的历史产物不追溯。对话会丢，文件不会
- narration 边界：VOX 逐字切分定稿全文，立场问题在源头解决
- **skill 依赖登记纪律**：项目工作中每引入一个新 skill（调用/新建/测试保留）→ 加白名单 + 跑 `sync_skills.py --apply` 同步进项目快照（详见 skills/README.md）
