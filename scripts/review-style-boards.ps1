param(
  [string]$ListFile,
  [string]$OutDir
)

# 风格板专用 MiMo 验收（六格结构/标签/载体空白/材质统一）
$key = $env:MIMO_API_KEY
if (-not $key) { Write-Error "MIMO_API_KEY not set"; exit 1 }
if (-not (Test-Path $ListFile)) { Write-Error "list file not found"; exit 1 }
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

Add-Type -AssemblyName System.Drawing

$TEMPLATE = @"
请按 6 个维度逐项检查这张六格风格板参考图。每个维度输出一行「维度名：通过/不通过 + 一句说明」，
最后单独一行「不合格汇总：维度号列表（无则写无）」。严格按维度回答。

1. 画幅：是否为 16:9 横版构图？
2. 六格结构：画面是否清晰地分成 2 行 × 3 列共 6 个方格（格子上方有标签字：材质/配色/主体/载体/运动/负例）？格子是否齐全、排列规整？
3. 标签文字：六个格子的标签字是否都存在且书写正确（材质、配色、主体、载体、运动、负例）？
4. 无多余文字：除格子标签字外，画面里有没有出现任何多余的文字、字母、数字、乱码？（载体格里的卡/牌/标签应全部空白）
5. 风格统一：六个格子的材质、配色是否统一为同一种风格（不是六种不同风格混拼）？
6. 形状完整：物体有无残缺边缘、断裂轮廓、运动模糊或拖影？

本风格补充说明：
{extra}
"@

$jobs = Get-Content $ListFile -Encoding UTF8
foreach ($line in $jobs) {
  if (-not $line.Trim()) { continue }
  $parts = $line -split "`t"
  $imgPath = $parts[0]
  $extra = if ($parts.Count -gt 1) { $parts[1] } else { "无" }
  $name = [System.IO.Path]::GetFileNameWithoutExtension($imgPath)
  $out = Join-Path $OutDir "review-board-$name.txt"
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
  Write-Host ("{0}: {1} KB" -f $name, [math]::Round($bytes.Length/1KB,0))

  $prompt = $TEMPLATE.Replace("{extra}", $extra)
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