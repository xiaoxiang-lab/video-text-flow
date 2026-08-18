import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from voxvideo.adapter import (AdapterError, AgnesImageAdapter,
                              KlingImageAdapter, get_image_adapter)

from .fakes import make_config


def fake_urlopen_factory(responses, captured=None):
    """responses: list of (bytes, code) 或 (bytes, None) 表示成功。"""

    def fake_urlopen(req, timeout):
        if captured is not None:
            captured.append(req)
        blob, code = responses.pop(0)
        if code is not None:
            raise urllib.error.HTTPError(req.full_url, code, "err", {}, io.BytesIO(blob))
        return io.BytesIO(blob)

    return fake_urlopen


class FakeOpener:
    """替代 build_opener 的假 opener：open 返回内存流。"""

    def __init__(self, blob):
        self.blob = blob

    def open(self, req, timeout=None):
        return io.BytesIO(self.blob)


class AgnesAdapterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.adapter = AgnesImageAdapter(api_key="k-agnes", timeout_seconds=30,
                                         auto_detect_proxy=False)

    def test_available_requires_key(self):
        self.assertTrue(self.adapter.available())
        self.assertFalse(AgnesImageAdapter(api_key="").available())

    def test_generate_encodes_url_into_submit_id(self):
        resp = json.dumps({"created": 1, "data": [{"url": "https://cdn.example/x.png"}]}).encode()
        with patch("voxvideo.adapter.urllib.request.urlopen", fake_urlopen_factory([(resp, None)])):
            result = self.adapter.generate("hello", self.tmp / "a.png", fingerprint="fp1")
        self.assertTrue(result["submit_id"].startswith("agnes_sync:https://cdn.example/x.png"))
        self.assertEqual(result["fingerprint"], "fp1")

    def test_wait_and_download_parses_and_downloads(self):
        blob = b"\x89PNG\r\n\x1a\n" + b"\x00" * 500
        with patch("voxvideo.adapter.urllib.request.build_opener",
                   return_value=FakeOpener(blob)) as opener:
            dest = self.adapter.wait_and_download(
                "agnes_sync:https://cdn.example/x.png", self.tmp / "out.png")
            self.assertEqual(opener.call_args.args, ())  # 无代理时零 handler
        self.assertEqual(dest.read_bytes(), blob)

    def test_download_uses_configured_proxy(self):
        adapter = AgnesImageAdapter(api_key="k", download_proxy="http://127.0.0.1:7892",
                                    auto_detect_proxy=False)
        blob = b"\x89PNG\r\n\x1a\n" + b"\x00" * 500
        with patch("voxvideo.adapter.urllib.request.build_opener",
                   return_value=FakeOpener(blob)) as opener:
            adapter.wait_and_download("agnes_sync:https://cdn.example/x.png", self.tmp / "o.png")
        handlers = opener.call_args.args
        self.assertEqual(len(handlers), 1)
        self.assertEqual(handlers[0].proxies, {"http": "http://127.0.0.1:7892",
                                               "https": "http://127.0.0.1:7892"})

    def test_detect_proxy_prefers_explicit(self):
        adapter = AgnesImageAdapter(api_key="k", download_proxy="http://127.0.0.1:9999",
                                    auto_detect_proxy=True)
        self.assertEqual(adapter._detect_proxy(), "http://127.0.0.1:9999")

    def test_wait_rejects_non_agnes_id(self):
        with self.assertRaises(AdapterError):
            self.adapter.wait_and_download("plain-task-id", self.tmp / "out.png")

    def test_http_error_echoes_body_only(self):
        err_body = b'{"error":"insufficient credit"}'
        with patch("voxvideo.adapter.urllib.request.urlopen",
                   fake_urlopen_factory([(err_body, 402)])):
            with self.assertRaises(AdapterError) as ctx:
                self.adapter.generate("x", self.tmp / "a.png")
        msg = str(ctx.exception)
        self.assertIn("402", msg)
        self.assertIn("insufficient credit", msg)
        self.assertNotIn("k-agnes", msg)

    def test_generate_with_reference_sends_base64_image(self):
        ref = self.tmp / "ref.png"
        ref.write_bytes(b"PNGDATA")
        captured = []
        resp = json.dumps({"data": [{"url": "https://cdn.example/y.png"}]}).encode()

        def fake_urlopen(req, timeout):
            captured.append(json.loads(req.data.decode("utf-8")))
            return io.BytesIO(resp)

        with patch("voxvideo.adapter.urllib.request.urlopen", fake_urlopen):
            self.adapter.generate_with_reference("p", ref, self.tmp / "b.png")
        payload = captured[0]
        self.assertEqual(payload["model"], "agnes-image-2.1-flash")
        self.assertEqual(payload["size"], "2K")
        self.assertEqual(payload["ratio"], "16:9")
        self.assertTrue(payload["image"][0].startswith("data:image/png;base64,"))

    def test_no_url_in_response_raises(self):
        resp = json.dumps({"data": [{"foo": "bar"}]}).encode()
        with patch("voxvideo.adapter.urllib.request.urlopen", fake_urlopen_factory([(resp, None)])):
            with self.assertRaises(AdapterError):
                self.adapter.generate("x", self.tmp / "a.png")


class KlingPlaceholderTest(unittest.TestCase):
    def test_all_methods_raise_not_implemented(self):
        adapter = KlingImageAdapter()
        self.assertFalse(adapter.available())
        for method, args in (
            (adapter.generate, ("p", "out.png")),
            (adapter.generate_with_reference, ("p", "ref.png", "out.png")),
            (adapter.wait_and_download, ("id", "out.png")),
        ):
            with self.subTest(method=method):
                with self.assertRaises(NotImplementedError):
                    method(*args)


class FactoryTest(unittest.TestCase):
    def test_default_is_agnes(self):
        adapter = get_image_adapter({}, env={})
        self.assertIsInstance(adapter, AgnesImageAdapter)

    def test_config_wins_over_env(self):
        adapter = get_image_adapter({"image_adapter": "kling"}, env={"IMAGE_ADAPTER": "agnes"})
        self.assertIsInstance(adapter, KlingImageAdapter)

    def test_env_used_when_no_config(self):
        adapter = get_image_adapter({}, env={"IMAGE_ADAPTER": "kling"})
        self.assertIsInstance(adapter, KlingImageAdapter)

    def test_env_supplies_agnes_key(self):
        adapter = get_image_adapter({}, env={"AGNES_API_KEY": "k-1"})
        self.assertEqual(adapter.api_key, "k-1")

    def test_unknown_backend_raises(self):
        with self.assertRaises(AdapterError) as ctx:
            get_image_adapter({}, env={"IMAGE_ADAPTER": "midjourney"})
        self.assertIn("agnes", str(ctx.exception))

    def test_config_default_matches_repo(self):
        config = make_config()
        config["image_adapter"] = "agnes"
        adapter = get_image_adapter(config, env={"IMAGE_ADAPTER": "kling"})
        self.assertIsInstance(adapter, AgnesImageAdapter)


if __name__ == "__main__":
    unittest.main()
