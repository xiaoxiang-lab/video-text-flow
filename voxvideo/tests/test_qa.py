import tempfile
import unittest
from pathlib import Path

from voxvideo.qa import QaError, validate_image_file


class QaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def _file(self, name, head):
        p = self.tmp / name
        p.write_bytes(head + b"\x00" * 1500)
        return p

    def test_png_ok(self):
        validate_image_file(self._file("a.png", b"\x89PNG\r\n\x1a\n"))

    def test_jpeg_ok(self):
        validate_image_file(self._file("a.jpg", b"\xff\xd8\xff"))
        validate_image_file(self._file("a.jpeg", b"\xff\xd8\xff"))

    def test_webp_ok(self):
        validate_image_file(self._file("a.webp", b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP"))

    def test_garbage_rejected(self):
        p = self._file("a.png", b"this is not an image at all")
        with self.assertRaises(QaError):
            validate_image_file(p)

    def test_wrong_extension_rejected(self):
        p = self.tmp / "a.txt"
        p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 1500)
        with self.assertRaises(QaError):
            validate_image_file(p)

    def test_too_small_rejected(self):
        p = self.tmp / "a.png"
        p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 100)
        with self.assertRaises(QaError):
            validate_image_file(p)

    def test_missing_rejected(self):
        with self.assertRaises(QaError):
            validate_image_file(self.tmp / "nope.png")


if __name__ == "__main__":
    unittest.main()
