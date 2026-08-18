@echo off
chcp 65001 >nul
echo ============================================
echo  Flow Agent - 隔离 Chrome 配置文件
echo  调试端口: 9222
echo  配置目录: %USERPROFILE%\.chrome-flow-agent
echo ============================================
echo.
echo 注意事项：
echo   1. 此窗口保持打开，关闭 = 断开 MCP 连接
echo   2. 请在弹出的 Chrome 中手动登录 Google（勿交给 AI）
echo   3. 登录后打开 https://labs.google/fx/tools/flow
echo   4. 完成后在此窗口按 Ctrl+C 关闭
echo.

"%ProgramFiles%\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%USERPROFILE%\.chrome-flow-agent" "https://labs.google/fx/tools/flow"
