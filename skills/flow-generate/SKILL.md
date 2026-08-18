---
name: flow-generate
description: Flow 视频生成：用 chrome-devtools MCP 操作 Google Flow，按项目 handoff.md 逐镜生成视频（chupian-vox 导出的素材包 → 成片镜头）。触发场景：用户要求「用 Flow 生成视频」「开始 Flow 生成」「Flow 出片」「生成镜头视频」「用 chrome-devtools 操作 Flow」，或 chupian-vox 走到 handoff 后用户要自动化出片。只做 Flow 浏览器生成环节；拼接/配音/字幕归阶段 3 后续的 ffmpeg 合并脚本（run-video），不在此处理。核心纪律：隔离配置 + 只读先行 + 3 镜试点 + 用户确认兜底。
---

# flow-generate（Flow 视频生成）

本 skill 是 chupian-vox 导出 `handoff.md` 之后的**出片环节**（阶段 3），首次突破原「AI 不碰浏览器」边界——安全规则必须逐条遵守，不得简化。

依赖：chrome-devtools MCP（`~/.config/opencode/opencode.jsonc` 已配）+ 隔离 Chrome（`C:\Users\xx\Documents\video-text-flow\scripts\chrome-flow.bat` 启动，端口 9222，配置目录 `~\.chrome-flow-agent`）。

## 前置条件检查（缺一即停）

1. chrome-devtools MCP 已连接（`list_pages` 等工具可用）
2. 隔离 Chrome 已启动（用户运行 chrome-flow.bat，或 PowerShell 执行：
   `& "$env:ProgramFiles\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="$env:USERPROFILE\.chrome-flow-agent" "https://labs.google/fx/tools/flow"`）
3. 用户已在 Chrome 手动登录 Google（AI 绝不碰密码/验证码）
4. Flow 页面 `https://labs.google/fx/tools/flow` 已打开

## 只读先行（强制，第一步）

不点生成、不传文件、不下载、不登录、不改页面。先：

1. `list_pages` 列页面
2. 找 URL 含 `labs.google/fx/tools/flow` 的页
3. 读该页标题 / URL / 主要可见文字
4. `take_screenshot` 截图
5. 确认具备工具：`list_pages` / `select_page` / `take_snapshot` / `take_screenshot` / `click` / `fill`（或 type_text）/ `upload_file`

找不到 Flow 页面或缺工具 → 停止并说明缺什么，**不绕过登录、不重配浏览器**。

第二步只读确认：

1. 选中页确实是 Flow
2. 无登录弹窗 / 验证码 / 权限弹窗
3. Chrome 只开 Flow 相关页
4. 页面有：新建项目 / 文本生成视频 / 上传参考图 / 模型选择 / 画幅比例 / 生成按钮

仍不点生成、不传文件、不下载。汇报页面状态。

## 读取项目（不改写）

1. 完整读 `handoff.md`，不修改
2. 汇总所有镜头：编号 / 旁白 / Flow 档位 / 模型 / 画幅 / 参考图要求

## 工作规则（硬约束）

1. 严格按 `shot-NNN` 顺序，从 shot-001 到最后一镜
2. 模型与画幅以 handoff.md「开工前必读」为准（默认 Omni Flash / 16:9）
3. 每镜用 handoff 对应代码块里的**完整提示词**，不改写文案 / 旁白 / 镜头意图
4. **不上传 `master.png`**——它是风格表不是画面
5. 只上传 handoff 明确要求的参考图（对应镜号）；未要求的不传
6. 生成视频不加旁白 / 音乐 / 歌词（旁白与音频后期合成）
7. 每次操作前先读页面状态，不凭猜测点击
8. 生成后检查：乱码 / 错误品牌 / 人物变形 / 错误画幅 / 镜头内部乱切 / 风格漂移
9. 已有文件不覆盖、不删除
10. 新文件按 `05-video\shot-NNN.mp4` 保存
11. Flow 下载按钮无法存到指定目录时，报告下载位置，不擅自删除覆盖
12. 不读其他标签页（邮箱 / 网盘 / 密码管理器）
13. 不输入密码 / 验证码 / 支付信息 / 安全密钥
14. 出现 CAPTCHA / 登录确认 / 付款 / 权限请求 → 暂停通知用户

## 3 镜试点（强制）

第一阶段只处理 3 镜（shot-001/002/003），验证方向后再批量。原因：Flow 页面可能改版、生成耗额度、风格/纸张/文字/品牌标志依赖前几镜验证方向。3 镜成功后用户确认，再继续剩余镜头。

## 用户确认兜底（强制）

真正**点击生成 / 上传参考图 / 下载视频之前**，先汇报即将执行的动作 + 涉及文件，等用户确认。

## 失败处理

- 连续 2 次生成失败 → 暂停并说明具体原因
- 失败镜头只重试必要镜，不重复生成合格镜
- 每完成 5 镜汇报：已完成编号 / 失败编号 / 剩余额度 / 页面错误

## 安全边界

- 只用隔离配置 `~\.chrome-flow-agent`，不动日常 Chrome
- 调试端口用 `127.0.0.1`，不外露到 `0.0.0.0`
- 不用 `--auto` 全自动批准模式
- 出现验证码 / 支付 / 二次登录时**用户手动完成**
- 完成后关闭专用 Chrome，`opencode mcp list` 确认状态，再从配置禁用或删除 chrome-devtools
