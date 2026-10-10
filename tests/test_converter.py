import base64
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from ziptotext.converter import (
    convert_folder,
    convert_folders,
    convert_zip,
    convert_zips,
    sanitize_stem,
)


def _png_bytes() -> bytes:
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )


def _write_zip(path: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)


class ConverterTests(unittest.TestCase):
    def test_sanitize_stem(self) -> None:
        self.assertEqual(sanitize_stem("My Project.zip"), "My_Project")
        self.assertEqual(sanitize_stem("zip1.zip"), "zip1")

    def test_named_output_and_image_embed(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            zip_path = root / "zip1.zip"
            _write_zip(
                zip_path,
                {
                    "hello.py": b"print('hi')\n",
                    "assets/dot.png": _png_bytes(),
                    "ignore.bin": b"\x00\x01\x02\x03\xff",
                    "__MACOSX/._hello.py": b"junk",
                },
            )
            out = root / "dist"
            created = convert_zip(zip_path, output_dir=out, max_mb=15)
            self.assertEqual([p.name for p in created], ["zip1.txt"])
            text = created[0].read_text(encoding="utf-8")
            self.assertTrue(text.startswith("REBUILD INSTRUCTIONS\n"))
            self.assertIn("Source archive: zip1.zip", text)
            self.assertIn("Create directories as needed", text)
            self.assertIn("Marker lines are metadata only", text)
            self.assertIn("--- FILE_START: hello.py ---", text)
            self.assertIn("print('hi')", text)
            self.assertIn("--- TYPE: image ---", text)
            self.assertIn("--- MIME: image/png ---", text)
            self.assertIn("iVBORw0KGgo", text)
            self.assertIn("--- FILE_START: ignore.bin ---", text)
            self.assertIn("--- TYPE: binary ---", text)
            self.assertIn("--- MIME: application/octet-stream ---", text)
            self.assertNotIn("__MACOSX", text)
            start = text.index("--- FILE_START: hello.py ---\n") + len("--- FILE_START: hello.py ---\n")
            end = text.index("\n--- FILE_END: hello.py ---")
            body = text[start:end]
            self.assertEqual(body, "print('hi')\n")
            self.assertNotIn("========", body)
            file_block = text[text.index("--- FILE_START: hello.py ---"):text.index("--- FILE_END: hello.py ---")]
            self.assertNotIn("========", file_block)

    def test_split_naming(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            zip_path = root / "zip1.zip"
            big = "x" * 800
            _write_zip(
                zip_path,
                {
                    "a.txt": big.encode("utf-8"),
                    "b.txt": big.encode("utf-8"),
                    "c.txt": big.encode("utf-8"),
                },
            )
            out = root / "dist"
            created = convert_zip(zip_path, output_dir=out, max_mb=0.001)
            names = [p.name for p in created]
            self.assertTrue(len(names) >= 2)
            self.assertEqual(names[0], "zip1_part1.txt")
            self.assertEqual(names[1], "zip1_part2.txt")
            part1 = created[0].read_text(encoding="utf-8")
            part2 = created[1].read_text(encoding="utf-8")
            self.assertIn("REBUILD INSTRUCTIONS", part1)
            self.assertNotIn("REBUILD INSTRUCTIONS", part2)

    def test_multiple_zips(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            one = root / "alpha.zip"
            two = root / "beta.zip"
            _write_zip(one, {"one.txt": b"one"})
            _write_zip(two, {"two.txt": b"two"})
            out = root / "dist"
            results = convert_zips([one, two], output_dir=out, max_mb=15)
            names = sorted(path.name for files in results.values() for path in files)
            self.assertEqual(names, ["alpha.txt", "beta.txt"])

    def test_folder_bundle(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "myproject"
            (project / "src").mkdir(parents=True)
            (project / "assets").mkdir()
            (project / "src" / "main.py").write_text("print('x')\n", encoding="utf-8")
            (project / "assets" / "logo.png").write_bytes(_png_bytes())
            (project / "notes.bin").write_bytes(b"\x00\x01\x02")
            (project / "__pycache__").mkdir()
            (project / "__pycache__" / "main.pyc").write_bytes(b"junk")
            out = root / "dist"

            created = convert_folder(project, output_dir=out, max_mb=15)
            self.assertEqual([p.name for p in created], ["myproject.txt"])
            text = created[0].read_text(encoding="utf-8")
            self.assertIn("Source folder: myproject", text)
            self.assertIn("--- FILE_START: src/main.py ---", text)
            self.assertIn("--- FILE_START: assets/logo.png ---", text)
            self.assertIn("--- TYPE: image ---", text)
            self.assertIn("--- FILE_START: notes.bin ---", text)
            self.assertIn("--- TYPE: binary ---", text)
            self.assertNotIn("__pycache__", text)

    def test_folder_output_not_bundled(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "proj"
            project.mkdir()
            (project / "a.txt").write_text("a", encoding="utf-8")
            out = project / "dist"
            convert_folder(project, output_dir=out, max_mb=15)
            convert_folder(project, output_dir=out, max_mb=15)
            text = (out / "proj.txt").read_text(encoding="utf-8")
            self.assertNotIn("proj.txt", text)

    def test_multiple_folders(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            one = root / "alpha"
            two = root / "beta"
            one.mkdir()
            two.mkdir()
            (one / "one.txt").write_text("one", encoding="utf-8")
            (two / "two.txt").write_text("two", encoding="utf-8")
            out = root / "dist"
            results = convert_folders([one, two], output_dir=out, max_mb=15)
            names = sorted(path.name for files in results.values() for path in files)
            self.assertEqual(names, ["alpha.txt", "beta.txt"])

    def test_binary_embed_and_skip(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            zip_path = root / "vb12.zip"
            _write_zip(
                zip_path,
                {
                    "Form1.frm": b"VERSION 5.00\nBegin VB.Form Form1\nEnd\n",
                    "Form1.frx": b"\x00\x01\x02\xffdata",
                    "project.dll": b"MZ\x00\x01",
                    "assets/dot.png": _png_bytes(),
                },
            )
            out = root / "dist"
            created = convert_zip(zip_path, output_dir=out, max_mb=15)
            text = created[0].read_text(encoding="utf-8")
            self.assertIn("TYPE: image or TYPE: binary", text)
            self.assertIn("--- FILE_START: Form1.frm ---", text)
            self.assertIn("VERSION 5.00", text)
            self.assertIn("--- FILE_START: Form1.frx ---", text)
            self.assertIn("--- TYPE: binary ---", text)
            self.assertIn("--- FILE_START: project.dll ---", text)
            self.assertIn("--- ENCODING: base64 ---", text)

            skipped = convert_zip(
                zip_path, output_dir=out / "skip", max_mb=15, include_binaries=False
            )
            skip_text = skipped[0].read_text(encoding="utf-8")
            self.assertIn("Form1.frm", skip_text)
            self.assertNotIn("Form1.frx", skip_text)
            self.assertNotIn("project.dll", skip_text)
            self.assertIn("assets/dot.png", skip_text)


if __name__ == "__main__":
    unittest.main()
