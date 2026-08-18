# NEXTSESSION.md · 新会话启动（2026-08-17 · 第二步完成，下一步待定）

> 本文件是上一个对话的收尾交接。新会话先读本文件 + PROGRESS.md + DECISIONS.md + README.md。

## 给新会话的开头（可直接复制给 AI）

```
接续 video-text-flow 项目。先读 NEXTSESSION.md → PROGRESS.md → DECISIONS.md → README.md，
跑一次 python checks/sync_skills.py 确认基线，再开工。

第一步（srt-vox 文字部分）与第二步（21 风格资产自造）均已完成：
- 第一步：16 条文本规则 + 规则库结构（轮次 0-6 + 对抗性测试，测试 165 全过）
- 第二步：21 风格资产自造（样图 21 + 风格板 21 + style-grid + 18 新注册 + 3 升级，
  测试 167 全过）
后续方向见下方「下一步候选」，用户未指定前先问。
```

## 第一步已完成（2026-08-17，轮次 0-6 + 对抗性测试）

- ✅ 前置五项：版权标注（VENDOR-NOTICE.md）/ 检查项映射表（docs/check-mapping.md）/ 正典一处 /
  vendoring（vendor/srtvox-director + sync_skills 目录级 hash 比较）/ 验收清单升级
  （docs/review-checklist.md + scripts/review-images.ps1）
- ✅ 轮次 0-6：时长统计 / 补差检测 / 差值+就近吸附 / 两型+七维打分 / 桥接 / check_docs /
  强制前段试点——详见 PROGRESS.md「吸纳 srt-vox 文字部分完成」
- ✅ 对抗性测试：宇树 IPO 全链 all_pass（0 误报）；测试 121→165；voxvideo 104 全过

## 第二步已完成（2026-08-17，21 风格资产自造）

- ✅ 映射：3 重合升级 + 18 新增注册（docs/style-mapping.md）；24 风格 styles 命令列出验证
- ✅ 提示词：docs/style-assets/sample-prompts.md（21 样图）+ style-board-prompts.md（21 风格板）
- ✅ 产线：runninghub 用户出图 + MiMo 验收；42 张全部通过（中文 21/21 逐字正确）
- ✅ 资产：Default Project ref/style-assets/（style-samples/ style-board/ style-grid.jpg + README）
- ✅ 注册：18 新风格 config/styles + ref/（guide A/B 逐字 + 无文字母板 + 尾部按差值分档）
- ✅ 选型：chupian-vox style-library.zh.md 24 风格总表 + 默认三选 + 风格板反泄漏追加语
- ✅ 评级表：docs/style-assets/style-gallery.md
- ✅ 校验联动：check_docs 扫描范围修复（子目录 + 外部根）→ 测试 165→167 全过

## 关键信息速查

| 项 | 位置 |
|---|---|
| 第二步简报（匹配约束 10 条） | docs/second-step-brief.md |
| 21 方向映射决策 | docs/style-mapping.md |
| 样图/风格板提示词（重出用） | docs/style-assets/sample-prompts.md + style-board-prompts.md |
| 评级表/分组/默认三选 | docs/style-assets/style-gallery.md |
| 42 张图片资产 | Default Project ref/style-assets/ |
| 24 风格注册 | Default Project config/styles/ + ref/<id>/ |
| 风格选型总表 | chupian-vox style-library.zh.md（全局 + 项目快照） |
| MiMo 验收脚本 | scripts/review-images.ps1（参考图八项）+ review-style-boards.ps1（风格板六项） |
| 拼图脚本 | scripts/build_style_grid.py |
| 样图批量生成（Agnes，备用） | scripts/generate_style_samples.py |
| 风格注册生成脚本 | scripts/gen_style_regs.py（数据即资产，改后重跑） |

## 下一步候选（用户未指定，勿擅自动手）

- 待定：项目四阶段（阶段 3 出片自动化 / 阶段 4 run-video 总协调）或新需求由用户定方向

## 未决 / 待办

- 用户工作流注意：出图效果不好时不重试，直接告诉用户换 runninghub（LESSONS Q1）
- voxvideo 阶段 4：GitHub 仓库化取消（不开源）；识别/生图配置项化（三选一开关）仍待做
- run-video 总协调脚本（阶段 3 ④）待做
- 风格板/样图如需重出：提示词在 docs/style-assets/，脚本幂等可续跑