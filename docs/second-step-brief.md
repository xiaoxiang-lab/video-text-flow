# 第二步任务简报 · 21 风格资产自造（Agnes + MiMo 产线）

> 创建：2026-08-17（第一步文字部分完成后）。新对话做第二步前必读本文件 + NEXTSESSION.md + PROGRESS.md + DECISIONS.md。
> 来源：github.com/geeklee/srt-vox-director 的 21 风格体系（vendor/srtvox-director/ 快照）——
> **资产全部自造，不复制上游原图/原提示词**（上游无 LICENSE，用户已定案走 Agnes+MiMo 产线）。

## 目标产物（对齐上游 21 风格，7 行 × 3 列）

| # | 风格（上游方向名） | # | 风格 | # | 风格 |
|---|---|---|---|---|---|
| S01 | 现代纸艺 | S08 | 水墨长卷 | S15 | 皮影机械 |
| S02 | 黏土定格 | S09 | 科学切片 | S16 | 错位拼贴 |
| S03 | 毛毡手工 | S10 | 历史档案 | S17 | 深蓝撕纸 |
| S04 | 矿彩壁画 | S11 | 产品蓝图 | S18 | 马克笔记 |
| S05 | 数据城市 | S12 | 漫画证据 | S19 | 博物模型 |
| S06 | 字体装置 | S13 | 木刻版画 | S20 | 复古波普 |
| S07 | 极简几何 | S14 | 剪纸剧场 | S21 | 美漫风格 |

每风格 4 类资产（参考上游 assets/ 目录结构，见 vendor/srtvox-director/info.txt）：
1. **风格总览图** style-grid.jpg（21 格拼图，同题材同构图同中文 → 可横向比）
2. **风格样图** style-samples/<id>.jpg（给用户选风格用）
3. **六格风格板** style-board/<id>.jpg（给图像模型，出图时上传；六格 = 材质/配色/主体/文字载体/运动/负例 各一格）
4. **风格块提示词**（中文可粘贴）+ 评级表（样图索引 + 实测评级，参考 vendor/srtvox-director/style-gallery.md）

## 产线（全部自造）

```
Agnes 生图（key 在项目 .env AGNES_API_KEY，A1/A2 经验）→ MiMo 看图评级（mimo_vision.ps1 /
  scripts/review-images.ps1 参考图八项）→ 评级表落盘 → 抽帧/拼图（PIL 或 ffmpeg，参考 O2/O3 经验）
```

## 与第一步的匹配约束（不遵守 = 返工，新对话逐条自查）

1. **风格注册体系**：新风格必须注册进 `config/styles/<id>.json` + `ref/<id>/`（guide.zh.md +
   master-prompt.zh.txt）——srt-vox 是独立风格库，我们是注册制（L1：每风格 3 文件）。
   **21 个方向与现有 6 风格（vox/fresh-scrapbook/warm-illustration/ink-scroll/blueprint-craft/
   minimal-motion）重合的，以现有注册为准升级资产，不重复注册**。
2. **guide 结构**（L2）：风格块 A（标准）+ 风格块 B（情绪/揭示）逐字 + 参考图骨架 + 禁止句 +
   文字注意 + 参考图判断规则；**尾部按差值分档写，禁止旧固定尾部句式**（check_docs
   受管数值扫描会报——正典一处，见约束 4）。
3. **无文字母板**：master-prompt.zh.txt 必须无文字（C4 教训：默认母板自带样例文字 → 参考图必抄）；
   明令「所有卡片面必须空白」；生成后审图确认无文字。
4. **受管数值禁区**：风格文档（guide/master/评级表）不得写档位、分界点、差值阈值、短镜上限、
   尾部静止时长、混音比例等受管数值（**完整清单与正典在 checks/check_docs.py MANAGED_PATTERNS**，
   只准引用「按尾部契约选档」式表述）。新增资产后必须跑 `python checks/check_docs.py`。
5. **选型规则登记**：新风格登记进 chupian-vox `style-library.zh.md` 总表（风格 id/名称/底色调性/
   适用题材/强调色），与七维打分（2026-08-17 第一步已加）配合；候选必须解释世界与运动逻辑不同。
6. **验收**：样图/风格板按 `docs/review-checklist.md` 参考图八项验收（画幅/目标构图/主体数量/文字/
   连续性/漂移/无运动模糊/形状完整），MiMo 按维度看图；评级表记录生成难度（七维打分第 6 维）。
7. **文字渲染经验**（LESSONS C 类）：中文短词最稳、英文长词必掉字母（C3）；做旧报纸强先验角落
   必出样例字（C1，判定标准：核心大字正确 + 构图正确即可）；禁带字纸张背景（C2）；禁止「蓝图网格」
   类色系冲突。
8. **风格一致性**：21 风格用**同一个题材、同四件物件、同四处中文**生成（对齐上游 style-grid 的
   横向对比方式）；每风格样图提示词存 sample-prompts.md 类文件（自造版本）。
9. **版权**：自造表达，不逐字复制上游风格块提示词（可参考其结构/维度）；风格方向名沿用（方法论
   认可），资产内容全部原创；产出不开源不公开分发（阶段 4 已取消开源，DECISIONS 2026-08-17）。
10. **校验器联动**：新资产落盘后跑全链——`python -m unittest discover -s checks/tests -t checks`
    + `python checks/run_all.py <产物目录> --project <项目>` + `python checks/check_docs.py`；
    涉及 guide 模板的改动同步项目快照（`python checks/sync_skills.py --apply`，目录级 hash 比较
    会检测 LESSONS/guide 等附属文件变更）。

## 参考材料位置

| 材料 | 位置 |
|---|---|
| 上游 21 风格文件树 | vendor/srtvox-director/info.txt |
| 上游评级表（参考格式） | vendor/srtvox-director/style-gallery.md |
| 上游风格块/样图提示词（参考结构，不复制） | vendor/srtvox-director/style-library.md / sample-prompts.md |
| 21 风格总览图（上游原图，仅参考对比） | vendor/srtvox-director/style-grid.jpg + Temp\opencode\srtvox-assets\style-grid.jpg |
| 单风格样图（上游原图） | Temp\opencode\srtvox-assets\S01.jpg … S21.jpg |
| 第一步落盘的规则 | style-library.zh.md（拆镜定型/七维打分/通用规则）、docs/check-mapping.md、LESSONS.md |

## 建议执行顺序（新对话可调整）

1. 读交接文档 + 跑 sync_skills 确认基线
2. 定 21 风格与现有 6 风格的映射（重合升级 / 新增注册）
3. 建风格注册骨架（config/styles + ref/ 目录）→ 每风格 guide 风格块逐字（先文本后生图，
   文本决定资产一致性）
4. Agnes 产线逐风格出样图（同题材同构图同中文）→ MiMo 八项验收 → 评级表
5. 六格风格板（每风格 1 张，给图像模型）→ 拼 style-grid.jpg
6. 全链校验 + 对抗性检查 + PROGRESS/DECISIONS 落盘
