"""配音后端。

- qwen3-tts（默认）：本地 Qwen3-TTS，WSL 里 faster-qwen3-tts serve clone 模式，
  克隆用户自己的声音（ref.wav），模型常驻、逐行输入、批量出 wav。
- mimo-tts（备选）：小米 MiMo token-plan 语音合成 API（OpenAI 兼容 chat/completions）。
  实测要点（2026-08-15，官方文档 + 真实调用）：
  - 端点 POST https://token-plan-cn.xiaomimimo.com/v1/chat/completions
  - 待合成文本放在 role=assistant 的 content；role=user 是风格指令（可选，voicedesign 必填）
  - 顶层参数 audio: {"format": "wav", "voice": "mimo_default"}（预置音色 8 个：
    mimo_default/冰糖/茉莉/苏打/白桦/Mia/Chloe/Milo/Dean）
  - 响应取 choices[0].message.audio.data（base64 wav）；流式时 format 用 pcm16
  - 模型：mimo-v2.5-tts（预置音色）/ mimo-v2.5-tts-voicedesign（文本设计音色）/
    mimo-v2.5-tts-voiceclone（音频克隆，audio.voice 传 data:audio/mpeg;base64,<样本>）
  - TTS 计费：限时免费（官方文档 2026-07-15）
- fish-audio（备选）：Fish Audio TTS API。契约要点（都是实测踩过的坑）：
  - 端点 POST https://api.fish.audio/v1/tts
  - model 是请求头，不是 body 字段。写进 body 不会报错，但模型不会切换。
  - 响应体直接是二进制音频流，不是 JSON。
  - 捕获 HTTPError 回显错误时，只回显 response body——key 在请求头里，
    不会出现在 body 中；不要图省事把整个 request 对象打出来。
"""

from __future__ import annotations

import base64
import json
import os
import shlex
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

WAV_MAGIC = b"RIFF"


class NarrationError(Exception):
    pass


def load_env_file(env_path: Path | None, environ: dict | None = None) -> dict:
    """补齐缺失环境变量，真实环境变量永远优先。返回合并后的视图。"""
    env = dict(os.environ if environ is None else environ)
    if env_path and Path(env_path).exists():
        for line in Path(env_path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and key not in env:
                env[key] = value
    return env


class FishAudioNarrator:
    def __init__(self, endpoint: str, api_key: str, voice_id: str, model: str = "s2-pro",
                 format: str = "wav", speed: float = 1.0, timeout_seconds: int = 180):
        self.endpoint = endpoint
        self.api_key = api_key
        self.voice_id = voice_id
        self.model = model
        self.format = format
        self.speed = speed
        self.timeout_seconds = timeout_seconds

    def describe(self) -> dict:
        """可复现事实，刻意不含 key。"""
        return {
            "provider": "fish-audio",
            "voice_id": self.voice_id,
            "model": self.model,
            "format": self.format,
            "speed": self.speed,
        }

    def synthesize(self, text: str, dest: Path) -> Path:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps(
            {
                "text": text,
                "reference_id": self.voice_id,
                "format": self.format,
                "prosody": {"speed": self.speed},
            }
        ).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "model": self.model,
        }
        req = urllib.request.Request(self.endpoint, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                blob = resp.read()
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                detail = f"HTTP {exc.code}"
            raise NarrationError(f"Fish Audio 返回 HTTP {exc.code}：{detail}") from exc
        except urllib.error.URLError as exc:
            raise NarrationError(f"Fish Audio 请求失败：{exc.reason}") from exc
        if not blob or not blob.startswith(WAV_MAGIC):
            raise NarrationError(f"Fish Audio 返回的不是 wav 音频流（{len(blob)} 字节）")
        dest.write_bytes(blob)
        return dest


class MimoTtsNarrator:
    """小米 MiMo token-plan 语音合成（OpenAI 兼容 chat/completions）。

    文本放 assistant 消息，风格指令放 user 消息，顶层 audio 参数指定格式与音色。
    """

    def __init__(self, endpoint: str, api_key: str, voice: str = "mimo_default",
                 model: str = "mimo-v2.5-tts", style_prompt: str = "",
                 format: str = "wav", timeout_seconds: int = 300):
        self.endpoint = endpoint
        self.api_key = api_key
        self.voice = voice
        self.model = model
        self.style_prompt = style_prompt
        self.format = format
        self.timeout_seconds = timeout_seconds

    def describe(self) -> dict:
        return {
            "provider": "mimo-tts",
            "model": self.model,
            "voice": self.voice,
            "format": self.format,
        }

    def synthesize(self, text: str, dest: Path) -> Path:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        messages = []
        if self.style_prompt:
            messages.append({"role": "user", "content": self.style_prompt})
        messages.append({"role": "assistant", "content": text})
        payload = {
            "model": self.model,
            "messages": messages,
            "audio": {"format": self.format, "voice": self.voice},
        }
        req = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = resp.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise NarrationError(f"MiMo TTS 返回 HTTP {exc.code}：{detail}") from exc
        except urllib.error.URLError as exc:
            raise NarrationError(f"MiMo TTS 请求失败：{exc.reason}") from exc
        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise NarrationError(f"MiMo TTS 响应不是 JSON（{len(body)} 字节）") from exc
        audio = (data.get("choices") or [{}])[0].get("message", {}).get("audio")
        if not audio or not audio.get("data"):
            raise NarrationError(f"MiMo TTS 响应缺 audio.data：{str(data)[:300]}")
        b64 = audio["data"]
        if "," in b64 and b64.startswith("data:"):
            b64 = b64.split(",", 1)[1]
        blob = base64.b64decode(b64)
        if not blob.startswith(WAV_MAGIC):
            raise NarrationError(f"MiMo TTS 返回的不是 wav（{len(blob)} 字节，前 4 字节 {blob[:4]!r}）")
        dest.write_bytes(blob)
        return dest


def narrator_from_config(config: dict, env: dict) -> FishAudioNarrator | Qwen3TtsNarrator | MimoTtsNarrator:
    """按 config/narration.provider 选择配音后端。

    - qwen3-tts（默认）：本地 Qwen3-TTS（WSL serve clone），无需凭证
    - mimo-tts：小米 MiMo token-plan TTS，需要 MIMO_API_KEY
    - fish-audio：Fish Audio，需要 FISH_API_KEY / FISH_VOICE_ID
    """
    nar = config["narration"]
    provider = nar.get("provider", "fish-audio")
    if provider == "qwen3-tts":
        q = nar.get("qwen3_tts") or {}
        return Qwen3TtsNarrator(
            wsl_distro=q.get("wsl_distro", "Ubuntu-24.04"),
            cli=q.get("cli", "/root/s2s/.venv/bin/faster-qwen3-tts"),
            model=q.get("model", "/root/models/qwen3tts"),
            ref_audio=q.get("ref_audio", "/root/s2s/ref.wav"),
            ref_text=q.get("ref_text", ""),
            language=q.get("language", "Chinese"),
            device=q.get("device", "cuda"),
            output_dir=q.get("output_dir", "/tmp/voxvideo-tts"),
            startup_timeout_seconds=int(q.get("startup_timeout_seconds", 120)),
            gen_timeout_seconds=int(q.get("gen_timeout_seconds", 120)),
        )
    if provider == "mimo-tts":
        # 注意：mimo_tts 配置段在 config 顶层（不在 narration 段内）
        m = config.get("mimo_tts") or nar.get("mimo_tts") or {}
        api_key = env.get(m.get("api_key_env", "MIMO_API_KEY"), "")
        if not api_key:
            raise NarrationError(
                "缺少 MIMO_API_KEY。在项目根 .env 里填小米 token-plan 的 API key，再重试。"
            )
        return MimoTtsNarrator(
            endpoint=m.get("endpoint", "https://token-plan-cn.xiaomimimo.com/v1/chat/completions"),
            api_key=api_key,
            voice=m.get("voice", "mimo_default"),
            model=m.get("model", "mimo-v2.5-tts"),
            style_prompt=m.get("style_prompt", ""),
            format=m.get("format", "wav"),
            timeout_seconds=int(m.get("timeout_seconds", 300)),
        )
    api_key = env.get(nar["api_key_env"], "")
    voice_id = env.get(nar["voice_env"], "")
    if not api_key or not voice_id:
        missing = [name for name, val in ((nar["api_key_env"], api_key), (nar["voice_env"], voice_id)) if not val]
        raise NarrationError(
            f"缺少环境变量 {missing}。在项目根 .env 里填 FISH_API_KEY 与 FISH_VOICE_ID "
            "（注册 fish.audio → API Keys 建 key → 音色页 URL 取 reference_id），再重试。"
        )
    model = env.get(nar["model_env"], nar.get("default_model", "s2-pro"))
    return FishAudioNarrator(
        endpoint=nar["endpoint"],
        api_key=api_key,
        voice_id=voice_id,
        model=model,
        format=nar.get("format", "wav"),
        speed=float(nar.get("speed", 1.0)),
        timeout_seconds=int(nar.get("timeout_seconds", 180)),
    )


class Qwen3TtsNarrator:
    """本地 Qwen3-TTS 配音（WSL 内 faster-qwen3-tts serve clone 模式）。

    serve 常驻模型，stdin 每行一段文本，输出到 output-dir 的 out_0001.wav 递增文件。
    输出文件命名按进程内递增序号；每次启动清空 output-dir，序号从 1 重计。
    """

    READY_MARK = "captured"

    def __init__(self, wsl_distro: str = "Ubuntu-24.04", cli: str = "/root/s2s/.venv/bin/faster-qwen3-tts",
                 model: str = "/root/models/qwen3tts", ref_audio: str = "/root/s2s/ref.wav",
                 ref_text: str = "", language: str = "Chinese", device: str = "cuda",
                 output_dir: str = "/tmp/voxvideo-tts", startup_timeout_seconds: int = 120,
                 gen_timeout_seconds: int = 120, proc_factory=None):
        self.wsl_distro = wsl_distro
        self.cli = cli
        self.model = model
        self.ref_audio = ref_audio
        self.ref_text = ref_text
        self.language = language
        self.device = device
        self.output_dir = output_dir
        self.startup_timeout_seconds = startup_timeout_seconds
        self.gen_timeout_seconds = gen_timeout_seconds
        self._proc_factory = proc_factory or subprocess.Popen
        self._proc = None
        self._count = 0
        self._log_lines = []
        self._log_lock = threading.Lock()

    def describe(self) -> dict:
        return {"provider": "qwen3-tts-local", "model": self.model,
                "voice": "clone", "language": self.language,
                "ref_audio": self.ref_audio}

    def close(self) -> None:
        if self._proc is not None:
            try:
                self._proc.stdin.close()
            except Exception:
                pass
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None

    def _start(self) -> None:
        cmd = (
            f"export PYTHONUNBUFFERED=1; "
            f"rm -rf {shlex.quote(self.output_dir)} && mkdir -p {shlex.quote(self.output_dir)} && "
            f"exec {self.cli} --device {self.device} serve --mode clone "
            f"--model {shlex.quote(self.model)} "
            f"--ref-audio {shlex.quote(self.ref_audio)} "
            f"--ref-text {shlex.quote(self.ref_text)} "
            f"--language {shlex.quote(self.language)} "
            f"--output-dir {shlex.quote(self.output_dir)}"
        )
        self._proc = self._proc_factory(
            ["wsl", "-d", self.wsl_distro, "-e", "bash", "-c", cmd],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        self._log_lines = []

        def reader():
            assert self._proc is not None and self._proc.stdout is not None
            for line in self._proc.stdout:
                with self._log_lock:
                    self._log_lines.append(line.decode("utf-8", errors="replace").rstrip())

        threading.Thread(target=reader, daemon=True).start()
        # serve 在加载/warmup 阶段就会阻塞读取 stdin 首行：不能等 ready 标记，
        # 进程起来后直接喂文本即可（stdin 管道会缓冲，serve 加载完自然读到）。
        time.sleep(2.0)
        if self._proc.poll() is not None:
            raise NarrationError(f"Qwen3-TTS serve 启动即退出：{self._tail()}")

    def _tail(self, n: int = 5) -> str:
        with self._log_lock:
            return " | ".join(self._log_lines[-n:])

    def _win_path(self, wsl_path: str) -> Path:
        r"""输出目录 → Windows 侧可访问路径。

        以 / 开头的视为 WSL 内路径，映射为 \\wsl$\<distro>\...；盘符路径直接用。
        """
        if wsl_path.startswith("/"):
            return Path(rf"\\wsl$\{self.wsl_distro}" + wsl_path.replace("/", "\\"))
        return Path(wsl_path)

    def _wait_output(self, name: str) -> Path:
        target = self._win_path(f"{self.output_dir}/{name}")
        deadline = time.monotonic() + self.gen_timeout_seconds
        last_size = -1
        stable_rounds = 0
        while time.monotonic() < deadline:
            if self._proc is not None and self._proc.poll() is not None:
                raise NarrationError(f"Qwen3-TTS serve 中途退出：{self._tail()}")
            if target.exists():
                size = target.stat().st_size
                if size == last_size and size > 0:
                    stable_rounds += 1
                    if stable_rounds >= 2:  # 大小连续两次不变视为写完
                        return target
                last_size = size
            time.sleep(0.5)
        raise NarrationError(f"Qwen3-TTS 合成超时（{self.gen_timeout_seconds}s）：{self._tail()}")

    def synthesize(self, text: str, dest) -> Path:
        if self._proc is None or self._proc.poll() is not None:
            self._start()
        self._count += 1
        name = f"out_{self._count:04d}.wav"
        assert self._proc is not None and self._proc.stdin is not None
        self._proc.stdin.write((text + "\n").encode("utf-8"))
        self._proc.stdin.flush()
        out_file = self._wait_output(name)
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out_file, dest)
        return dest
