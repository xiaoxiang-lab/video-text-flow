# VENDOR-NOTICE · 来源与使用标注

> **来源**：github.com/geeklee/srt-vox-director（2026-08-15 更新，43★，Python）
> **版权状态**：上游仓库**无 LICENSE**（默认保留权利）。
> **用户决策（2026-08-17，DECISIONS.md）**：本项目**阶段 4 不开源**（GitHub 公开仓库化取消，
> 改私有/本地归档）——本副本仅本地使用，不公开分发、不并入开源产物；无需开 issue 问授权。
>
> 本副本 = 上游文件结构全收 + 敏感处表达略改（不逐字复制可辨识整段）。用途：
> ① 吸纳时对照正典（结构/公式/判据）；② sync_skills vendoring 的 hash 检测基线（上游更新时提示）。
> 上游更新时：重新抓取覆盖本目录，跑 `python checks/sync_skills.py` 看差异，再决定是否吸纳新规则。

## 文件清单（2026-08-17 快照）

| 文件 | 上游路径 | 用途 |
|---|---|---|
| README.upstream.md | README.md | 项目总览（上游原样） |
| SKILL.md | SKILL.md | 路由与判定规则 |
| storyboard-algorithm.md | references/storyboard-algorithm.md | 分镜算法/吸附表/差值/尾部契约/校验器（正典） |
| delivery-contract.md | references/delivery-contract.md | 输出契约/state.json/用户自检表 |
| style-selector.md | references/style-selector.md | 七维打分/自定义风格 DNA |
| prompt-keywords.md | references/prompt-keywords.md | 计字口径/密度三档/渲染路线（正典） |
| prompt-templates.md | references/prompt-templates.md | 提示词模板正典 |
| prompt-motion.md | references/prompt-motion.md | 参考图角色/桥接帧/收束动作 |
| style-gallery.md | references/style-gallery.md | 样图评级/默认三选 |
| style-library.md | references/style-library.md | 21 条风格块（图片部分，第二步用） |
| sample-prompts.md | assets/sample-prompts.md | 21 风格样图提示词（图片部分） |
| check_storyboard.py | scripts/check_storyboard.py | 上游分镜校验器（参考其判据，不搬代码） |
| examples-e2e.md | examples/end-to-end.md | 端到端范例 |
| info.txt | （抓取时 repo 元信息） | 上游文件树/README 快照 |
| style-grid.jpg | assets/style-grid.jpg | 21 风格总览图（图片部分，MiMo 可看图） |

> 说明：上游其余资产（style-board/、style-highlight/、style-samples/、troubleshooting.md、
> storyboard-blueprints.md、delivery-handoff.md、check_prompts.py、check_state.py、check_docs.py、
> _lint_rules.py、tests/）未入快照——图片类走第二步自造产线，脚本类只翻译判据不搬代码，
> 文档类按需再抓。缺失时从上一次 Temp 副本（srtvox-*）或上游直接补。
