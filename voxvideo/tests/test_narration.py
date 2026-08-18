import base64
import io
import json
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from voxvideo.narration import (FishAudioNarrator, MimoTtsNarrator, NarrationError,
                                Qwen3TtsNarrator, load_env_file,
                                narrator_from_config)

from .fakes import make_config


class FakeStdout:
    def __init__(self, lines):
        self._lines = [(l + "\n").encode() for l in lines]

    def __iter__(self):
        return iter(self._lines)


class FakeStdin:
    def __init__(self):
        self.written = []

    def write(self, text):
        self.written.append(text)

    def flush(self):
        pass


class FakeProc:
    def __init__(self, lines=("Talker CUDA graph captured!",), poll_result=None):
        self.stdout = FakeStdout(lines)
        self.stdin = FakeStdin()
        self._poll = poll_result

    def poll(self):
        return self._poll

    def terminate(self):
        self._poll = 1


class EnvTest(unittest.TestCase):
    def test_load_env_file_and_real_env_wins(self):
        with tempfile.TemporaryDirectory() as d:
            env_path = Path(d) / ".env"
            env_path.write_text("FISH_API_KEY=from_file\nFISH_VOICE_ID=v1\n", encoding="utf-8")
            merged = load_env_file(env_path, environ={"FISH_VOICE_ID": "real"})
            self.assertEqual(merged["FISH_API_KEY"], "from_file")
            self.assertEqual(merged["FISH_VOICE_ID"], "real")


class FishApiContractTest(unittest.TestCase):
    def setUp(self):
        self.narrator = FishAudioNarrator(
            endpoint="https://api.fish.audio/v1/tts", api_key="k-secret",
            voice_id="v-1", model="s2-pro", format="wav", speed=1.0, timeout_seconds=30)

    def test_describe_has_no_key(self):
        desc = self.narrator.describe()
        self.assertNotIn("key", json.dumps(desc))
        self.assertEqual(desc["voice_id"], "v-1")

    def test_model_is_request_header_not_body(self):
        captured = {}

        class FakeResp:
            def __init__(self, blob):
                self._blob = blob

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return self._blob

        def fake_urlopen(req, timeout):
            captured["headers"] = {k: v for k, v in req.header_items()}
            captured["body"] = json.loads(req.data.decode("utf-8"))
            return FakeResp(b"RIFF" + b"WAVE" + b"\x00" * 64)

        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "t.wav"
            with patch("voxvideo.narration.urllib.request.urlopen", fake_urlopen):
                self.narrator.synthesize("你好", dest)
            self.assertTrue(dest.exists())
        self.assertEqual(captured["headers"]["Model"], "s2-pro")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer k-secret")
        self.assertNotIn("model", captured["body"])
        self.assertEqual(captured["body"]["reference_id"], "v-1")

    def test_http_error_echoes_body_only(self):
        err = urllib.error.HTTPError("https://api.fish.audio/v1/tts", 402, "Payment Required",
                                     {}, io.BytesIO(b'{"detail":"insufficient balance"}'))
        with patch("voxvideo.narration.urllib.request.urlopen", side_effect=err):
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(NarrationError) as ctx:
                    self.narrator.synthesize("https://api.example.com/v1/chat/completions", Path(d) / "t.wav")
        msg = str(ctx.exception)
        self.assertIn("402", msg)
        self.assertIn("insufficient balance", msg)
        self.assertNotIn("k-secret", msg)

    def test_non_wav_response_rejected(self):
        def fake_urlopen(req, timeout):
            return io.BytesIO(b"<html>error page</html>")

        with patch("voxvideo.narration.urllib.request.urlopen", fake_urlopen):
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(NarrationError):
                    self.narrator.synthesize("https://api.example.com/v1/chat/completions", Path(d) / "t.wav")

    def test_narrator_from_config_requires_keys(self):
        config = make_config()
        with self.assertRaises(NarrationError) as ctx:
            narrator_from_config(config, {})
        self.assertIn("FISH_API_KEY", str(ctx.exception))

    def test_narrator_from_config_ok(self):
        config = make_config()
        narrator = narrator_from_config(config, {"FISH_API_KEY": "k", "FISH_VOICE_ID": "v"})
        self.assertEqual(narrator.model, "s2-pro")
        self.assertEqual(narrator.api_key, "k")


class MimoTtsTest(unittest.TestCase):
    """MiMo token-plan TTS 契约：文本在 assistant 消息、顶层 audio 参数、响应 message.audio.data（base64 wav）。"""

    def _resp(self, audio_b64: str):
        body = json.dumps({
            "choices": [{"message": {"role": "assistant", "content": "", "audio": {"data": audio_b64}}}]
        }).encode("utf-8")

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return body

        return FakeResp()

    def test_synthesize_contract(self):
        captured = {}
        wav_blob = b"RIFF" + b"WAVE" + b"\x00" * 64
        audio_b64 = base64.b64encode(wav_blob).decode()

        def fake_urlopen(req, timeout):
            captured["headers"] = {k: v for k, v in req.header_items()}
            captured["body"] = json.loads(req.data.decode("utf-8"))
            return self._resp(audio_b64)

        n = MimoTtsNarrator(
            endpoint="https://token-plan-cn.xiaomimimo.com/v1/chat/completions",
            api_key="tp-secret", voice="冰糖", model="mimo-v2.5-tts",
            style_prompt="沉稳解说", timeout_seconds=30)
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "t.wav"
            with patch("voxvideo.narration.urllib.request.urlopen", fake_urlopen):
                n.synthesize("宇树 610 亿市值。", dest)
            self.assertTrue(dest.exists())
            self.assertEqual(dest.read_bytes(), wav_blob)
        # 契约：assistant 消息 = 文本；user 消息 = 风格；顶层 audio 参数
        self.assertEqual(captured["headers"]["Authorization"], "Bearer tp-secret")
        self.assertEqual(captured["body"]["model"], "mimo-v2.5-tts")
        self.assertEqual(captured["body"]["messages"][-1]["role"], "assistant")
        self.assertEqual(captured["body"]["messages"][-1]["content"], "宇树 610 亿市值。")
        self.assertEqual(captured["body"]["messages"][0]["role"], "user")
        self.assertEqual(captured["body"]["messages"][0]["content"], "沉稳解说")
        self.assertEqual(captured["body"]["audio"], {"format": "wav", "voice": "冰糖"})

    def test_describe_has_no_key(self):
        n = MimoTtsNarrator(endpoint="https://api.example.com/v1/chat/completions", api_key="tp-secret", voice="冰糖")
        self.assertNotIn("tp-secret", json.dumps(n.describe()))

    def test_http_error_reports(self):
        err = urllib.error.HTTPError("https://x/v1/chat/completions", 500, "Internal Server Error",
                                     {}, io.BytesIO(b'{"error":{"message":"boom"}}'))
        n = MimoTtsNarrator(endpoint="https://api.example.com/v1/chat/completions", api_key="tp-secret", timeout_seconds=5)
        with patch("voxvideo.narration.urllib.request.urlopen", side_effect=err):
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(NarrationError) as ctx:
                    n.synthesize("https://api.example.com/v1/chat/completions", Path(d) / "t.wav")
        msg = str(ctx.exception)
        self.assertIn("500", msg)
        self.assertIn("boom", msg)
        self.assertNotIn("tp-secret", msg)

    def test_missing_audio_data_raises(self):
        body = json.dumps({"choices": [{"message": {"content": "ok", "audio": None}}]}).encode()

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return body

        n = MimoTtsNarrator(endpoint="https://api.example.com/v1/chat/completions", api_key="tp-secret", timeout_seconds=5)
        with patch("voxvideo.narration.urllib.request.urlopen", lambda req, timeout: FakeResp()):
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(NarrationError) as ctx:
                    n.synthesize("https://api.example.com/v1/chat/completions", Path(d) / "t.wav")
        self.assertIn("audio.data", str(ctx.exception))

    def test_non_wav_rejected(self):
        n = MimoTtsNarrator(endpoint="https://api.example.com/v1/chat/completions", api_key="tp-secret", timeout_seconds=5)
        with patch("voxvideo.narration.urllib.request.urlopen",
                   lambda req, timeout: self._resp(base64.b64encode(b"NOTWAVE").decode())):
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(NarrationError) as ctx:
                    n.synthesize("文本", Path(d) / "t.wav")
        self.assertIn("wav", str(ctx.exception))

    def test_from_config_picks_mimo(self):
        config = make_config()
        config["narration"]["provider"] = "mimo-tts"
        n = narrator_from_config(config, {"MIMO_API_KEY": "tp-key"})
        self.assertIsInstance(n, MimoTtsNarrator)
        self.assertEqual(n.voice, "mimo_default")
        self.assertNotIn("tp-key", json.dumps(n.describe()))

    def test_from_config_mimo_requires_key(self):
        config = make_config()
        config["narration"]["provider"] = "mimo-tts"
        with self.assertRaises(NarrationError) as ctx:
            narrator_from_config(config, {})
        self.assertIn("MIMO_API_KEY", str(ctx.exception))


class Qwen3TtsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.out_dir = self.tmp / "tts-out"

    def _narrator(self, proc, out_dir=None):
        return Qwen3TtsNarrator(
            wsl_distro="Ubuntu-24.04", cli="/x/faster-qwen3-tts",
            model="/x/qwen3tts", ref_audio="/x/ref.wav",
            ref_text="参考文字", language="Chinese", device="cuda",
            output_dir=str(out_dir or self.out_dir),
            startup_timeout_seconds=5, gen_timeout_seconds=5,
            proc_factory=lambda *a, **k: proc,
        )

    def test_start_and_synthesize(self):
        proc = FakeProc()
        n = self._narrator(proc)
        dest = self.tmp / "take.wav"
        out_file = self.out_dir / "out_0001.wav"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_bytes(b"WAVDATA")
        time.sleep(0.6)  # 让文件大小连续两次不变
        n.synthesize("你好", dest)
        self.assertEqual(dest.read_bytes(), b"WAVDATA")
        self.assertEqual(proc.stdin.written, ["你好\n".encode("utf-8")])
        n.close()

    def test_startup_failure_raises(self):
        proc = FakeProc(poll_result=1)
        n = self._narrator(proc)
        with self.assertRaises(NarrationError) as ctx:
            n.synthesize("你好", self.tmp / "a.wav")
        self.assertIn("启动即退出", str(ctx.exception))

    def test_describe_has_no_secrets(self):
        n = self._narrator(FakeProc())
        desc = json.dumps(n.describe())
        self.assertNotIn("sk-", desc)
        n.close()

    def test_from_config_picks_qwen3(self):
        config = make_config()
        config["narration"]["provider"] = "qwen3-tts"
        config["narration"]["qwen3_tts"] = {
            "wsl_distro": "Ubuntu-24.04", "cli": "/x/cli", "model": "/x/model",
            "ref_audio": "/x/ref.wav", "ref_text": "参考文字",
        }
        n = narrator_from_config(config, {})
        self.assertIsInstance(n, Qwen3TtsNarrator)
        self.assertEqual(n.ref_text, "参考文字")

    def test_from_config_defaults_to_fish(self):
        config = make_config()
        config["narration"]["provider"] = "fish-audio"
        with self.assertRaises(NarrationError):
            narrator_from_config(config, {})


if __name__ == "__main__":
    unittest.main()
