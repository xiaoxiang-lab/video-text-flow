"""批量从 sample-prompts.md 提取 21 条提示词，调用 Agnes 生成样图。

用法：
  python scripts/generate_style_samples.py            # 全量
  python scripts/generate_style_samples.py --id S01   # 单个

输出：Default Project/ref/style-assets/style-samples/<存为名>
幂等：目标文件已存在且非空则跳过。
失败：偶发连接重置/SSL EOF 直接重试（A1 经验），重试 3 次。
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(r"C:\Users\xx\Documents\Default Project")
ASSETS_DIR = PROJECT_ROOT / "ref" / "style-assets" / "style-samples"
PROMPTS_FILE = Path(__file__).resolve().parents[1] / "docs" / "style-assets" / "sample-prompts.md"
ENDPOINT = "https://apihub.agnes-ai.com/v1/images/generations"
MODEL = "agnes-image-2.1-flash"
SIZE = "2K"
RATIO = "16:9"
RETRY = 3
PROXY_PORTS = (7892, 18725)


def load_env_key() -> str:
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("AGNES_API_KEY="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("AGNES_API_KEY", "")


def parse_prompts() -> list[dict]:
    text = PROMPTS_FILE.read_text(encoding="utf-8")
    blocks = []
    # 段落标题 ## S01 现代纸艺 ... 到下一个 ## 或文件尾
    pattern = re.compile(r"^## (S\d+)\s+(\S.*?)$\n\n存为 `([^`]+)`[^\n]*\n\n```text\n(.*?)\n```", re.M | re.S)
    for m in pattern.finditer(text):
        blocks.append({"id": m.group(1), "name": m.group(2).strip(),
                       "filename": m.group(3), "prompt": m.group(4)})
    return blocks


def make_opener():
    handlers = []
    for port in PROXY_PORTS:
        try:
            import socket
            with socket.create_connection(("127.0.0.1", port), timeout=0.8):
                pass
            handlers.append(urllib.request.ProxyHandler(
                {"http": f"http://127.0.0.1:{port}", "https": f"http://127.0.0.1:{port}"}))
            break
        except OSError:
            continue
    return urllib.request.build_opener(*handlers)


def generate(key: str, prompt: str, dest: Path) -> None:
    payload = json.dumps({"model": MODEL, "prompt": prompt, "size": SIZE, "ratio": RATIO}).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT, data=payload, method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    # 递归找第一个 http URL
    def first_url(obj):
        if isinstance(obj, dict):
            for v in obj.values():
                u = first_url(v)
                if u:
                    return u
        elif isinstance(obj, list):
            for v in obj:
                u = first_url(v)
                if u:
                    return u
        elif isinstance(obj, str) and obj.startswith("http"):
            return obj
        return None
    url = first_url(data)
    if not url:
        raise RuntimeError(f"响应里找不到图片 URL: {json.dumps(data, ensure_ascii=False)[:400]}")
    opener = make_opener()
    req2 = urllib.request.Request(url, headers={"User-Agent": "voxvideo/0.1"})
    try:
        with opener.open(req2, timeout=180) as resp:
            blob = resp.read()
    except urllib.error.URLError as exc:
        raise RuntimeError(f"下载失败: {exc.reason}") from exc
    if not blob:
        raise RuntimeError("下载为空")
    dest.write_bytes(blob)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", default=None, help="只生成某个 S01..S21")
    args = parser.parse_args(argv)
    key = load_env_key()
    if not key:
        print("AGNES_API_KEY 未配置")
        return 1
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    blocks = parse_prompts()
    if len(blocks) != 21:
        print(f"警告：解析到 {len(blocks)} 条提示词（应为 21）")
    ok, fail = [], []
    for b in blocks:
        if args.id and b["id"] != args.id:
            continue
        dest = ASSETS_DIR / b["filename"]
        if dest.exists() and dest.stat().st_size > 0:
            print(f"[skip] {b['id']} {b['filename']} 已存在")
            ok.append(b["id"])
            continue
        print(f"[gen ] {b['id']} {b['filename']} ...")
        last_err = None
        for attempt in range(1, RETRY + 1):
            try:
                generate(key, b["prompt"], dest)
                print(f"  ok ({dest.stat().st_size // 1024} KB)")
                ok.append(b["id"])
                break
            except Exception as exc:
                last_err = exc
                print(f"  attempt {attempt} 失败: {exc}")
                time.sleep(3 * attempt)
        else:
            print(f"  FAIL: {last_err}")
            fail.append(b["id"])
        time.sleep(1)
    print(json.dumps({"ok": ok, "fail": fail, "total": len(blocks)}, ensure_ascii=False))
    return 0 if not fail else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))