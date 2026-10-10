from __future__ import annotations

import base64
import os
import re
import zipfile
from pathlib import Path
from typing import Callable, Optional

DEFAULT_MAX_MB = 15.0
DEFAULT_OUTPUT_DIR = "dist"

IMAGE_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".tif", ".tiff",
})

SKIP_EXTENSIONS = frozenset({
    ".pyc", ".pyo", ".pyd",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".tgz", ".tbz2",
    ".mp3", ".mp4", ".wav", ".flac", ".ogg", ".avi", ".mov", ".mkv", ".webm",
    ".iso", ".dmg",
})

SKIP_DIR_NAMES = frozenset({
    "__macosx", "__pycache__", ".git", ".svn", ".hg", "node_modules",
})

MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".ico": "image/x-icon",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".svg": "image/svg+xml",
    ".bin": "application/octet-stream",
    ".exe": "application/vnd.microsoft.portable-executable",
    ".dll": "application/vnd.microsoft.portable-executable",
    ".so": "application/x-sharedlib",
    ".dylib": "application/x-sharedlib",
    ".class": "application/java-vm",
    ".o": "application/octet-stream",
    ".a": "application/octet-stream",
    ".obj": "application/octet-stream",
    ".lib": "application/octet-stream",
    ".pdb": "application/octet-stream",
    ".res": "application/octet-stream",
    ".frx": "application/octet-stream",
    ".ocx": "application/vnd.microsoft.portable-executable",
    ".tlb": "application/octet-stream",
    ".pdf": "application/pdf",
    ".db": "application/octet-stream",
    ".sqlite": "application/vnd.sqlite3",
    ".sqlite3": "application/vnd.sqlite3",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".eot": "application/vnd.ms-fontobject",
}

ProgressCb = Optional[Callable[[str], None]]


def sanitize_stem(name: str) -> str:
    stem = Path(name).stem
    cleaned = re.sub(r"[^\w\-]+", "_", stem, flags=re.UNICODE).strip("_")
    return cleaned or "archive"


def _emit(progress: ProgressCb, message: str) -> None:
    if progress:
        progress(message)
    else:
        print(message)


def _should_skip_entry(name: str) -> bool:
    path = Path(name)
    if name.endswith("/"):
        return True
    parts_lower = [part.lower() for part in path.parts]
    if any(part in SKIP_DIR_NAMES for part in parts_lower):
        return True
    if path.name.startswith(".") or path.name.lower() in {".ds_store", "thumbs.db"}:
        return True
    if ".." in path.parts:
        return True
    return False


def _looks_like_text(data: bytes) -> bool:
    if not data:
        return True
    sample = data[:8192]
    if b"\x00" in sample:
        return False
    decoded = sample.decode("utf-8", errors="replace")
    if decoded.count("\ufffd") / max(len(decoded), 1) > 0.30:
        return False
    return True


def _wrap_text(path: str, content: str) -> str:
    return f"--- FILE_START: {path} ---\n{content}\n--- FILE_END: {path} ---\n\n"


def rebuild_header(source_name: str, source_kind: str = "archive") -> str:
    label = "Source folder:" if source_kind == "folder" else "Source archive:"
    return (
        "REBUILD INSTRUCTIONS\n"
        f"{label} {source_name}\n"
        "This text is a packed project tree. Reconstruct files as follows.\n"
        "You can restore with: ziptotext --restore this-file.txt\n"
        "\n"
        "Marker lines are metadata only. Never write them into reconstructed files.\n"
        "That includes FILE_START, FILE_END, TYPE, MIME, and ENCODING lines.\n"
        "\n"
        "1. Treat this file (and later parts if present) as one archive.\n"
        "   If split, filenames are <name>_part1.txt, <name>_part2.txt, ...\n"
        "   Concatenate parts in order before extracting.\n"
        "2. Walk every block between:\n"
        "   --- FILE_START: <relative/path> ---\n"
        "   and\n"
        "   --- FILE_END: <relative/path> ---\n"
        "3. Create directories as needed, then write that path.\n"
        "4. File body is only the text strictly between those two marker lines.\n"
        "   Do not keep the marker lines. They are not part of the file.\n"
        "5. If the block has TYPE: image or TYPE: binary and ENCODING: base64,\n"
        "   decode the body with standard base64 and write the original bytes.\n"
        "   That covers jpg/png and other binaries (.bin, .dll, .exe, .frx).\n"
        "   Skip TYPE/MIME/ENCODING lines; they are not file bytes.\n"
        "   Otherwise write the body as UTF-8 text, unchanged.\n"
        "6. Ignore this header. Keep original relative paths.\n"
        "7. Result should be the original file tree, ready to use.\n"
        "END REBUILD INSTRUCTIONS\n\n"
    )


def _wrap_binary(path: str, data: bytes, mime: str, kind: str = "binary") -> str:
    b64 = base64.encodebytes(data).decode("ascii")
    return (
        f"--- FILE_START: {path} ---\n"
        f"--- TYPE: {kind} ---\n"
        f"--- MIME: {mime} ---\n"
        "--- ENCODING: base64 ---\n"
        f"{b64}"
        f"--- FILE_END: {path} ---\n\n"
    )


def _entry_text(
    file_path: str,
    data: bytes,
    include_images: bool,
    progress: ProgressCb,
    include_binaries: bool = True,
) -> str | None:
    suffix = Path(file_path).suffix.lower()

    if suffix in SKIP_EXTENSIONS:
        return None

    if suffix in IMAGE_EXTENSIONS:
        if not include_images:
            return None
        mime = MIME_TYPES.get(suffix, "application/octet-stream")
        _emit(progress, f"  Embedding image: {file_path} ({len(data)} bytes)")
        return _wrap_binary(file_path, data, mime, kind="image")

    if suffix == ".svg":
        text = data.decode("utf-8", errors="replace")
        return _wrap_text(file_path, text)

    if not _looks_like_text(data):
        if not include_binaries:
            _emit(progress, f"  Skipping binary: {file_path}")
            return None
        mime = MIME_TYPES.get(suffix, "application/octet-stream")
        _emit(progress, f"  Embedding binary: {file_path} ({len(data)} bytes)")
        return _wrap_binary(file_path, data, mime, kind="binary")

    text = data.decode("utf-8", errors="replace")
    return _wrap_text(file_path, text)


class _PartWriter:
    def __init__(
        self,
        output_dir: Path,
        safe_name: str,
        max_bytes: int,
        progress: ProgressCb,
        header: str = "",
    ):
        self.output_dir = output_dir
        self.safe_name = safe_name
        self.max_bytes = max_bytes
        self.progress = progress
        self.header = header
        self.bundle_idx = 1
        self.current_bytes = len(header.encode("utf-8")) if header else 0
        self.current_files = 0
        self.buffer: list[str] = [header] if header else []
        self.created: list[Path] = []
        self.split = False

    def _path_for(self, index: int) -> Path:
        if not self.split and index == 1:
            return self.output_dir / f"{self.safe_name}.txt"
        return self.output_dir / f"{self.safe_name}_part{index}.txt"

    def _rename_first_to_part(self) -> None:
        if self.split or not self.created:
            return
        old = self.created[0]
        new = self.output_dir / f"{self.safe_name}_part1.txt"
        if old != new:
            old.replace(new)
            self.created[0] = new
            _emit(self.progress, f"Renamed: {old.name} -> {new.name}")
        self.split = True

    def _flush(self) -> None:
        if self.current_files == 0:
            return
        out_path = self._path_for(self.bundle_idx)
        out_path.write_text("".join(self.buffer), encoding="utf-8")
        size_mb = out_path.stat().st_size / (1024 * 1024)
        _emit(
            self.progress,
            f"Created: {out_path} ({size_mb:.2f} MB, {self.current_files} files)",
        )
        self.created.append(out_path)
        self.bundle_idx += 1
        self.current_bytes = 0
        self.current_files = 0
        self.buffer = []

    def add(self, file_text: str) -> None:
        file_bytes = len(file_text.encode("utf-8"))
        if file_bytes > self.max_bytes:
            _emit(
                self.progress,
                f"  Warning: entry is {file_bytes / (1024 * 1024):.2f} MB "
                f"(over {self.max_bytes / (1024 * 1024):.1f} MB limit)",
            )
        if self.current_files and self.current_bytes + file_bytes > self.max_bytes:
            self._flush()
            self._rename_first_to_part()
        self.buffer.append(file_text)
        self.current_bytes += file_bytes
        self.current_files += 1

    def finish(self) -> list[Path]:
        self._flush()
        return self.created



def convert_zip(
    zip_path: str | Path,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    max_mb: float = DEFAULT_MAX_MB,
    include_images: bool = True,
    include_binaries: bool = True,
    progress: ProgressCb = None,
) -> list[Path]:
    zip_path = Path(zip_path).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()

    if not zip_path.is_file():
        raise FileNotFoundError(f"Zip file not found: {zip_path}")
    if not zipfile.is_zipfile(zip_path):
        raise ValueError(f"Not a valid zip archive: {zip_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    max_bytes = int(max_mb * 1024 * 1024)
    safe_name = sanitize_stem(zip_path.name)
    writer = _PartWriter(
        output_dir,
        safe_name,
        max_bytes,
        progress,
        header=rebuild_header(zip_path.name),
    )

    _emit(progress, f"Processing: {zip_path.name}")

    with zipfile.ZipFile(zip_path, "r") as archive:
        names = [name for name in archive.namelist() if not _should_skip_entry(name)]
        _emit(progress, f"  {len(names)} entries to scan")

        for file_path in names:
            try:
                data = archive.read(file_path)
            except Exception as exc:
                _emit(progress, f"  Skipping {file_path}: {exc}")
                continue

            try:
                file_text = _entry_text(
                    file_path,
                    data,
                    include_images,
                    progress,
                    include_binaries=include_binaries,
                )
            except Exception as exc:
                _emit(progress, f"  Skipping {file_path}: {exc}")
                continue

            if file_text is None:
                continue
            writer.add(file_text)

    created = writer.finish()
    if not created:
        _emit(progress, f"  No convertible files in {zip_path.name}")
    return created


def convert_zips(
    zip_paths: list[str | Path],
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    max_mb: float = DEFAULT_MAX_MB,
    include_images: bool = True,
    include_binaries: bool = True,
    progress: ProgressCb = None,
) -> dict[str, list[Path]]:
    results: dict[str, list[Path]] = {}
    for zip_path in zip_paths:
        created = convert_zip(
            zip_path,
            output_dir=output_dir,
            max_mb=max_mb,
            include_images=include_images,
            include_binaries=include_binaries,
            progress=progress,
        )
        results[str(zip_path)] = created
    return results


def _iter_folder_files(folder: Path, output_dir: Path):
    skip_dirs = set(SKIP_DIR_NAMES)
    for root, dirnames, filenames in os.walk(folder):
        root_path = Path(root)
        if root_path.resolve() == output_dir:
            dirnames[:] = []
            continue
        dirnames[:] = [
            name
            for name in dirnames
            if name.lower() not in skip_dirs and not name.startswith(".")
        ]
        for filename in filenames:
            full = root_path / filename
            try:
                relative = full.relative_to(folder).as_posix()
            except ValueError:
                continue
            yield full, relative


def convert_folder(
    folder_path: str | Path,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    max_mb: float = DEFAULT_MAX_MB,
    include_images: bool = True,
    include_binaries: bool = True,
    progress: ProgressCb = None,
) -> list[Path]:
    folder_path = Path(folder_path).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()

    if not folder_path.is_dir():
        raise NotADirectoryError(f"Folder not found: {folder_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    max_bytes = int(max_mb * 1024 * 1024)
    safe_name = sanitize_stem(folder_path.name)
    writer = _PartWriter(
        output_dir,
        safe_name,
        max_bytes,
        progress,
        header=rebuild_header(folder_path.name, "folder"),
    )

    _emit(progress, f"Processing folder: {folder_path.name}")

    count = 0
    for full, relative in _iter_folder_files(folder_path, output_dir):
        if _should_skip_entry(relative):
            continue
        try:
            data = full.read_bytes()
        except Exception as exc:
            _emit(progress, f"  Skipping {relative}: {exc}")
            continue
        try:
            file_text = _entry_text(
                relative,
                data,
                include_images,
                progress,
                include_binaries=include_binaries,
            )
        except Exception as exc:
            _emit(progress, f"  Skipping {relative}: {exc}")
            continue
        if file_text is None:
            continue
        writer.add(file_text)
        count += 1

    _emit(progress, f"  {count} entries added")
    created = writer.finish()
    if not created:
        _emit(progress, f"  No convertible files in {folder_path.name}")
    return created


def convert_folders(
    folder_paths: list[str | Path],
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    max_mb: float = DEFAULT_MAX_MB,
    include_images: bool = True,
    include_binaries: bool = True,
    progress: ProgressCb = None,
) -> dict[str, list[Path]]:
    results: dict[str, list[Path]] = {}
    for folder_path in folder_paths:
        created = convert_folder(
            folder_path,
            output_dir=output_dir,
            max_mb=max_mb,
            include_images=include_images,
            include_binaries=include_binaries,
            progress=progress,
        )
        results[str(folder_path)] = created
    return results
