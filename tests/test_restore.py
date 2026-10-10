import base64
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from ziptotext.converter import convert_folder, convert_zip
from ziptotext.restore import parse_bundle, restore_to_folder, restore_to_zip


def _png_bytes() -> bytes:
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )


def _write_zip(path: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)


class RestoreTests(unittest.TestCase):
    def test_roundtrip_zip_to_folder(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            zip_path = root / "vb12.zip"
            png = _png_bytes()
            _write_zip(
                zip_path,
                {
                    "Form1.frm": b"VERSION 5.00\nBegin VB.Form Form1\nEnd\n",
                    "Form1.frx": b"\x00\x01\x02\xffdata",
                    "src/main.py": b"print('hi')\n",
                    "assets/dot.png": png,
                },
            )
            packed = convert_zip(zip_path, output_dir=root / "dist", max_mb=15)
            restored = restore_to_folder(packed, output_dir=root / "out")
            dest = restored["vb12"]
            self.assertEqual(
                (dest / "Form1.frm").read_bytes(),
                b"VERSION 5.00\nBegin VB.Form Form1\nEnd\n",
            )
            self.assertEqual((dest / "Form1.frx").read_bytes(), b"\x00\x01\x02\xffdata")
            self.assertEqual((dest / "src" / "main.py").read_text(encoding="utf-8"), "print('hi')\n")
            self.assertEqual((dest / "assets" / "dot.png").read_bytes(), png)

    def test_roundtrip_folder_to_zip(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "myproject"
            (project / "lib").mkdir(parents=True)
            (project / "readme.txt").write_text("hello\n", encoding="utf-8")
            (project / "lib" / "core.bin").write_bytes(b"\x00\xff")
            packed = convert_folder(project, output_dir=root / "dist", max_mb=15)
            restored = restore_to_zip(packed, output_dir=root / "out")
            zip_path = restored["myproject"]
            with zipfile.ZipFile(zip_path, "r") as archive:
                self.assertEqual(archive.read("readme.txt"), b"hello\n")
                self.assertEqual(archive.read("lib/core.bin"), b"\x00\xff")

    def test_split_parts_restore(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            zip_path = root / "zip1.zip"
            big = ("x" * 800).encode("utf-8")
            _write_zip(zip_path, {"a.txt": big, "b.txt": big, "c.txt": big})
            packed = convert_zip(zip_path, output_dir=root / "dist", max_mb=0.001)
            self.assertTrue(len(packed) >= 2)
            restored = restore_to_folder([packed[0]], output_dir=root / "out")
            dest = restored["zip1"]
            self.assertEqual((dest / "a.txt").read_bytes(), big)
            self.assertEqual((dest / "b.txt").read_bytes(), big)
            self.assertEqual((dest / "c.txt").read_bytes(), big)

    def test_rejects_path_traversal(self) -> None:
        text = (
            "--- FILE_START: ../secret.txt ---\n"
            "nope\n"
            "--- FILE_END: ../secret.txt ---\n"
        )
        with TemporaryDirectory() as tmp:
            src = Path(tmp) / "evil.txt"
            src.write_text(text, encoding="utf-8")
            with self.assertRaises(ValueError):
                restore_to_folder([src], output_dir=Path(tmp) / "out")

    def test_parse_skips_header(self) -> None:
        files = parse_bundle(
            "REBUILD INSTRUCTIONS\n"
            "ignore this\n"
            "--- FILE_START: note.txt ---\n"
            "hello\n"
            "--- FILE_END: note.txt ---\n"
        )
        self.assertEqual(files, [("note.txt", b"hello")])


if __name__ == "__main__":
    unittest.main()
