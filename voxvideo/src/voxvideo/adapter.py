"""图片后端适配器。

当前默认后端：Agnes AI（OpenAI 兼容 API）。预留可灵（Kling）切换接口。
换后端只需要改 config/default.json 的 image_adapter 字段或环境变量 IMAGE_ADAPTER，
不需要改 pipeline / cli / 测试。

统一接口：
- available() -> bool：工具是否可用（不保证成功，只做快速检查）
- generate(prompt, output_path, fingerprint=None) -> dict：文生图，返回 {"submit_id": str}
- generate_with_reference(prompt, reference_image, output_path, fingerprint=None) -> dict：图生图
- wait_and_download(submit_id, output_path) -> Path：等结果并下载落地
- name -> str：适配器标识（用于报错文案）
"""

from __future__ import annotations

import base64
import json
import os
import socket
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path


class AdapterError(Exception):
    pass


def _walk(obj, key: str):
    """递归查找所有匹配 key 的值。"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                yield v
            yield from _walk(v, key)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk(item, key)


def _first_http_url(obj) -> str | None:
    """递归找第一个以 http 开头的字符串（Agnes 响应里通常只有图片 URL）。"""
    if isinstance(obj, dict):
        for v in obj.values():
            found = _first_http_url(v)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _first_http_url(item)
            if found:
                return found
    elif isinstance(obj, str) and obj.startswith("http"):
        return obj
    return None


class ImageAdapter(ABC):
    name = "abstract"

    @abstractmethod
    def available(self) -> bool:
        ...

    @abstractmethod
    def generate(self, prompt: str, output_path, fingerprint=None) -> dict:
        ...

    @abstractmethod
    def generate_with_reference(self, prompt: str, reference_image, output_path, fingerprint=None) -> dict:
        ...

    @abstractmethod
    def wait_and_download(self, submit_id: str, output_path) -> Path:
        ...


class AgnesImageAdapter(ImageAdapter):
    """Agnes AI 图片后端（OpenAI 兼容）。

    Agnes 是同步返回图片 URL 的；为了兼容项目的幂等/轮询设计，
    把 URL 编码进 submit_id（"agnes_sync:<url>"），wait_and_download 解析后直接下载。
    """

    name = "agnes"
    SYNC_PREFIX = "agnes_sync:"
    PROXY_PORTS = (7892, 18725)  # 自游猫 / v2rayN 常见本机端口

    def __init__(self, endpoint: str = "https://apihub.agnes-ai.com/v1/images/generations",
                 api_key: str = "", model: str = "agnes-image-2.1-flash",
                 size: str = "2K", ratio: str = "16:9", timeout_seconds: int = 180,
                 download_proxy: str = "", auto_detect_proxy: bool = True):
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model
        self.size = size
        self.ratio = ratio
        self.timeout_seconds = timeout_seconds
        self.download_proxy = download_proxy
        self.auto_detect_proxy = auto_detect_proxy

    def available(self) -> bool:
        return bool(self.api_key)

    def _post(self, payload: dict) -> dict:
        """POST 生成任务。HTTPError 时只回显 response body，不打印整个 request（防 key 泄露）。"""
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint, data=body, method="POST",
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                detail = f"HTTP {exc.code}"
            raise AdapterError(f"Agnes 返回 HTTP {exc.code}：{detail}") from exc
        except urllib.error.URLError as exc:
            raise AdapterError(f"Agnes 请求失败：{exc.reason}") from exc
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise AdapterError(f"Agnes 响应不是 JSON：{raw[:400]!r}")

    def _submit(self, payload: dict) -> str:
        data = self._post(payload)
        url = _first_http_url(data)
        if not url:
            raise AdapterError(f"Agnes 响应里找不到图片 URL：{json.dumps(data, ensure_ascii=False)[:400]}")
        return f"{self.SYNC_PREFIX}{url}"

    def generate(self, prompt: str, output_path, fingerprint=None) -> dict:
        payload = {"model": self.model, "prompt": prompt,
                   "size": self.size, "ratio": self.ratio}
        return {"submit_id": self._submit(payload), "fingerprint": fingerprint}

    def generate_with_reference(self, prompt: str, reference_image, output_path, fingerprint=None) -> dict:
        ref = Path(reference_image)
        if not ref.exists():
            raise AdapterError(f"参考输入不存在：{ref}")
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "webp": "image/webp"}.get(ref.suffix.lower().lstrip("."), "image/png")
        data_uri = f"data:{mime};base64,{base64.b64encode(ref.read_bytes()).decode('ascii')}"
        payload = {"model": self.model, "prompt": prompt,
                   "size": self.size, "ratio": self.ratio,
                   "image": [data_uri]}  # OpenAI 兼容扩展字段（extra_body）
        return {"submit_id": self._submit(payload), "fingerprint": fingerprint}

    @classmethod
    def decode_sync_id(cls, submit_id: str) -> str:
        """解析 "agnes_sync:<url>" → url。"""
        if not submit_id.startswith(cls.SYNC_PREFIX):
            raise AdapterError(f"不是 Agnes 同步 submit_id：{submit_id[:40]}")
        return submit_id[len(cls.SYNC_PREFIX):]

    def _detect_proxy(self) -> str | None:
        """显式配置的下载代理优先；否则快速探测本机常见代理端口（通就用）。"""
        if self.download_proxy:
            return self.download_proxy
        if self.auto_detect_proxy:
            for port in self.PROXY_PORTS:
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.8):
                        pass
                    return f"http://127.0.0.1:{port}"
                except OSError:
                    continue
        return None

    def _make_opener(self):
        handlers = []
        proxy = self._detect_proxy()
        if proxy:
            handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
        return urllib.request.build_opener(*handlers)

    def _download(self, url: str) -> bytes:
        req = urllib.request.Request(url, headers={"User-Agent": "voxvideo/0.1"})
        opener = self._make_opener()
        try:
            with opener.open(req, timeout=self.timeout_seconds) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            raise AdapterError(f"下载图片失败 HTTP {exc.code}：{url[:120]}") from exc
        except urllib.error.URLError as exc:
            raise AdapterError(f"下载图片失败：{exc.reason}") from exc

    def wait_and_download(self, submit_id: str, output_path) -> Path:
        dest = Path(output_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        url = self.decode_sync_id(submit_id)
        blob = self._download(url)
        if not blob:
            raise AdapterError(f"下载为空：{url[:120]}")
        dest.write_bytes(blob)
        return dest


class KlingImageAdapter(ImageAdapter):
    """可灵（Kling）开放平台占位。接口已就位，实现后即可切换。

    接入参数（以官方文档 https://klingai.com/document-api 为准，以下为公开约定）：
    - 端点（按账号所属区域二选一）：
        国内：https://api.klingai.com
        国际：https://api-singapore.klingai.com
    - 鉴权：请求头 Authorization: Bearer {KLING_API_KEY}
    - 文生图：POST /v1/images/generations
        body: {"model": "<图片模型名>", "prompt": "...",
               "n": 1, "aspect_ratio": "16:9", "image_size": "2k", "response_format": "url"}
    - 图生图：POST /v1/images/edits
        body 同上，加 "image": "base64 图片内容"
    - 异步轮询：提交返回 {"data": {"task_id": "..."}}；
        轮询 GET /v1/images/generations/{task_id}（或 /v1/tasks/{task_id}），
        task_status ∈ pending / running / succeed / failed；succeed 后取
        task_result.images[].url 下载。
    - 计费：按张数扣积分；具体价格见开放平台定价页。
    - 建议实现：generate 提交返回 {"submit_id": task_id}，
        wait_and_download 轮询到 succeed 后下载 URL 落地。
    """

    name = "kling"

    def available(self) -> bool:
        return False

    def generate(self, prompt: str, output_path, fingerprint=None) -> dict:
        raise NotImplementedError("KlingImageAdapter 尚未实现：先填官方接入参数再启用（见类注释）")

    def generate_with_reference(self, prompt: str, reference_image, output_path, fingerprint=None) -> dict:
        raise NotImplementedError("KlingImageAdapter 尚未实现：先填官方接入参数再启用（见类注释）")

    def wait_and_download(self, submit_id: str, output_path) -> Path:
        raise NotImplementedError("KlingImageAdapter 尚未实现：先填官方接入参数再启用（见类注释）")


def get_image_adapter(config: dict, env: dict | None = None) -> ImageAdapter:
    """工厂：config/default.json 的 image_adapter 字段 > 环境变量 IMAGE_ADAPTER > 默认 "agnes"。"""
    env = dict(os.environ if env is None else env)
    choice = (config.get("image_adapter") or "").strip() or env.get("IMAGE_ADAPTER", "").strip() or "agnes"
    if choice == "agnes":
        key = env.get("AGNES_API_KEY", "")
        conf = config.get("agnes") or {}
        return AgnesImageAdapter(
            endpoint=conf.get("endpoint", "https://apihub.agnes-ai.com/v1/images/generations"),
            api_key=key,
            model=conf.get("model", "agnes-image-2.1-flash"),
            size=conf.get("size", "2K"),
            ratio=conf.get("ratio", "16:9"),
            timeout_seconds=int(conf.get("timeout_seconds", 180)),
            download_proxy=conf.get("download_proxy", ""),
            auto_detect_proxy=bool(conf.get("auto_detect_proxy", True)),
        )
    if choice == "kling":
        return KlingImageAdapter()
    raise AdapterError(f"未知图片后端 {choice!r}：支持 agnes / kling（IMAGE_ADAPTER 或 config.image_adapter 配置）")
