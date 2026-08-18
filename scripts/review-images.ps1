param(
  [string]$ListFile,
  [string]$OutDir
)

# 批量 MiMo 看图（验收清单升级版，2026-08-17）
# list 文件每行：路径<TAB>类型<TAB>本镜补充说明（可选）
#   类型 reference = 参考图八项 | video = 视频片段六项
# 提示词模板正典在本文件（docs/review-checklist.md 只列清单本体）。

$key = $env:MIMO_API_KEY
if (-not $key) { Write-Error "MIMO_API_KEY not set"; exit 1 }
if (-not (Test-Path $ListFile)) { Write-Error "list file not found"; exit 1 }
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

Add-Type -AssemblyName System.Drawing

$TEMPLATE_REFERENCE = @"
请按 8 个维度逐项检查这张参考图。每个维度输出一行「维度名：通过/不通过 + 一句说明」，
最后单独一行「不合格汇总：维度号列表（无则写无）」。严格按维度回答，不要泛泛而谈。

1. 画幅：是否为 16:9 横版构图？
2. 目标构图：画面是否为完整成立的构图（主体、前后层次完整），而不是待填文字的空白底板或未完成的草图？
3. 主体数量：画面中主体数量是否唯一且与描述一致？有没有重复、多余、多出来的主体？
4. 文字：画面上所有文字是否逐字正确、清晰可读？有没有乱码、错字、笔画残缺、或出现描述里没有的文字？
5. 连续性：画面上是否有明确的转场锚点元素（可供相邻镜衔接的位置/颜色/形状）？
6. 漂移：材质、配色、光照是否统一协调？有没有风格板格子、色卡、标签条、样张边框混入画面？
7. 无运动模糊：画面里有没有拖影、运动模糊、重影？
8. 形状完整：物体有没有残缺边缘、断裂轮廓、融化变形？

本镜补充说明（含预期主体数量与构图要点）：
{extra}
"@

$TEMPLATE_VIDEO = @"
请按 6 个维度逐项检查这条视频片段。每个维度输出一行「维度名：通过/不通过 + 一句说明」，
最后单独一行「不合格汇总：维度号列表（无则写无）」。严格按维度回答，不要泛泛而谈。

1. 开场状态：视频第 0 帧（前 0.5 秒内）各部件的位置是否符合预期开场构图（不必与上传图逐像素一致）？
2. 位移：是否至少有三个主要部件有可见的物理位移（移动/旋转/入场），而不是只有光效或纯推镜？
3. 文字：文字是否作为完整载体整块移动？字符有没有被逐字重绘、改写、闪烁、凭空长出新的字？
4. 终帧：视频末尾各元素是否已到达最终位置并稳定（末段无明显漂移）？终态是否符合预期？
5. 数量：全程物体数量有没有增减（不该出现的物体进出画面）？
6. 桥接：片段末尾画面是否稳定清晰（若是拆分镜的下游片段，首帧应与上游末帧一致）？

本镜补充说明（含预期动作与终态）：
{extra}
"@

$jobs = Get-Content $ListFile -Encoding UTF8
foreach ($line in $jobs) {
  if (-not $line.Trim()) { continue }
  $parts = $line -split "`t"
  $imgPath = $parts[0]
  $kind = if ($parts.Count -gt 1) { $parts[1].Trim().ToLower() } else { "reference" }
  $extra = if ($parts.Count -gt 2) { $parts[2] } else { "无" }
  $name = [System.IO.Path]::GetFileNameWithoutExtension($imgPath)
  $out = Join-Path $OutDir "review-$name.txt"
  if (-not (Test-Path $imgPath)) { [System.IO.File]::WriteAllText($out, "IMAGE NOT FOUND", (New-Object System.Text.UTF8Encoding($false))); continue }

  $img = [System.Drawing.Image]::FromFile($imgPath)
  $maxW = 1024
  if ($img.Width -gt $maxW) {
    $h = [int]($img.Height * $maxW / $img.Width)
    $bmp = New-Object System.Drawing.Bitmap($maxW, $h)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.DrawImage($img, 0, 0, $maxW, $h)
    $g.Dispose(); $img.Dispose()
    $ms = New-Object System.IO.MemoryStream
    $bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Jpeg)
    $bytes = $ms.ToArray(); $ms.Dispose(); $bmp.Dispose()
  } else {
    $bytes = [System.IO.File]::ReadAllBytes($imgPath)
  }
  $b64 = [Convert]::ToBase64String($bytes)
  Write-Host ("{0} ({1}): {2} KB" -f $name, $kind, [math]::Round($bytes.Length/1KB,0))

  if ($kind -eq "video") { $prompt = $TEMPLATE_VIDEO } else { $prompt = $TEMPLATE_REFERENCE }
  $prompt = $prompt.Replace("{extra}", $extra)

  $payload = @{
    model = "mimo-v2.5"
    messages = @(
      @{
        role = "user"
        content = @(
          @{ type = "text"; text = $prompt },
          @{ type = "image_url"; image_url = @{ url = "data:image/jpeg;base64,$b64" } }
        )
      }
    )
    max_tokens = 4000
  } | ConvertTo-Json -Depth 8
  $body = [System.Text.Encoding]::UTF8.GetBytes($payload)
  try {
    $resp = Invoke-WebRequest -Uri "https://token-plan-cn.xiaomimimo.com/v1/chat/completions" `
      -Method Post -Headers @{ Authorization = "Bearer $key" } `
      -ContentType "application/json; charset=utf-8" -Body $body -TimeoutSec 120 -UseBasicParsing
    $rawBytes = $resp.RawContentStream.ToArray()
    $json = [System.Text.Encoding]::UTF8.GetString($rawBytes) | ConvertFrom-Json
    $answer = $json.choices[0].message.content
    if (-not $answer) { $answer = "(empty content)" }
    [System.IO.File]::WriteAllText($out, $answer, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "saved $out"
  } catch {
    [System.IO.File]::WriteAllText($out, "API FAIL: $($_.Exception.Message)", (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "FAIL: $($_.Exception.Message)"
  }
}
