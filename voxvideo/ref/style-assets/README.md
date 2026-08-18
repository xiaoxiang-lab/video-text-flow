# 21 风格资产库（自造，2026-08-17 第二步）

> 本目录下所有图片资产均为**自造**：提示词由本项目原创撰写
> （video-text-flow `docs/style-assets/`），生成走 Agnes/runninghub 产线，
> **不复制上游原图、不逐字复制上游提示词**。上游仅作方法论与方向名参考，
> 来源：github.com/geeklee/srt-vox-director（无 LICENSE，见
> video-text-flow `vendor/srtvox-director/VENDOR-NOTICE.md`）。
>
> **版权**：项目已定案不开源不公开分发（DECISIONS 2026-08-17），本资产库随项目私有。

## 目录

| 路径 | 内容 | 读者 |
|---|---|---|
| `style-samples/SNN-风格名.jpg` | 21 张风格样图（同题材同构图同中文） | 用户选风格 |
| `style-board/SNN-风格名.jpg` | 21 张六格风格板（材质/配色/主体/载体/运动/负例） | 图像模型（出图上传，配反泄漏追加语） |
| `style-grid.jpg` | 21 格总览图（7 行 × 3 列） | 用户横比 |
| `work/` | 验收中间产物（list/评审结果） | 维护用 |

## 重出

- 样图提示词：video-text-flow `docs/style-assets/sample-prompts.md`
- 风格板提示词：video-text-flow `docs/style-assets/style-board-prompts.md`
- 评级表与验收记录：video-text-flow `docs/style-assets/style-gallery.md`
- 拼图脚本：video-text-flow `scripts/build_style_grid.py`

## 验收

2026-08-17 runninghub 版全部通过：样图按参考图八项（21/21，中文逐字正确；
维度 3/5 在样图场景按「四件齐全无多余」判定，模板口径不符项已复核）；
风格板按六项（21/21，六格结构/标签/载体空白/材质统一）。
