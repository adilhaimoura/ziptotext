from __future__ import annotations

import base64
import re
import zipfile
from pathlib import Path
from typing import Callable, Optional

ProgressCb = Optional[Callable[[str], None]]

START_RE = re.compile(r"^--- FILE_START: (.+?) ---\s*$")
END_RE = re.compile(r"^--- FILE_END: (.+?) ---\s*$")
META_RE = re.compile(r"^--- (TYPE|MIME|ENCODING): (.+?) ---\s*$")
PART_RE = re.compile(r"^(?P<name>.+)_part(?P<n>\d+)$", re.IGNORECASE)


def _emit(progress: ProgressCb, message: str) -> None:
    if progress:
        progress(message)
    else:
        print(message)


def _safe_relative(path: str) -> Path:
    raw = path.replace("\\", "/").strip()
    if not raw or raw.startswith("/") or re.match(r"^[a-zA-Z]:", raw):
        raise ValueError(f"Unsafe path rejected: {path}")
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Unsafe path rejected: {path}")
    return relative


def parse_bundle(text: str) -> list[tuple[str, bytes]]:
    files: list[tuple[str, bytes]] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        start = START_RE.match(lines[i])
        if not start:
            i += 1
            continue
        path = start.group(1).strip()
        i += 1
        meta: dict[str, str] = {}
        while i < len(lines):
            marker = META_RE.match(lines[i])
            if not marker:
                break
            meta[marker.group(1).upper()] = marker.group(2).strip()
            i += 1
        body_lines: list[str] = []
        found_end = False
        while i < len(lines):
            end = END_RE.match(lines[i])
            if end:
                if end.group(1).strip() != path:
                    raise ValueError(
                        f"FILE_END mismatch: started {path}, ended {end.group(1)}"
                    )
                found_end = True
                i += 1
                break
            body_lines.append(lines[i])
            i += 1
        if not found_end:
            raise ValueError(f"Missing FILE_END for {path}")
        body = "\n".join(body_lines)
        kind = meta.get("TYPE", "").lower()
        encoding = meta.get("ENCODING", "").lower()
        if encoding == "base64" or kind in {"image", "binary"}:
            data = base64.b64decode("".join(body.split()), validate=False)
        else:
            data = body.encode("utf-8")
        files.append((path, data))
    return files


def _expand_sources(sources: list[str | Path]) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()
    for source in sources:
        path = Path(source).expanduser().resolve()
        if path.is_dir():
            candidates = sorted(
                p for p in path.iterdir() if p.is_file() and p.suffix.lower() == ".txt"
            )
        elif path.is_file():
            candidates = [path]
        else:
            raise FileNotFoundError(f"Not found: {path}")
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved not in seen:
                files.append(resolved)
                seen.add(resolved)
    return files


def _complete_parts(sample: Path, name: str) -> list[Path]:
    found: list[Path] = []
    index = 1
    while True:
        candidate = sample.parent / f"{name}_part{index}.txt"
        if not candidate.is_file():
            break
        found.append(candidate.resolve())
        index += 1
    return found


def group_text_bundles(sources: list[str | Path]) -> list[tuple[str, list[Path]]]:
    files = _expand_sources(sources)
    claimed: set[Path] = set()
    bundles: list[tuple[str, list[Path]]] = []

    part_files = []
    singles = []
    for path in files:
        match = PART_RE.match(path.stem)
        if match:
            part_files.append((match.group("name"), path))
        else:
            singles.append(path)

    seen_names: set[str] = set()
    for name, sample in part_files:
        if name in seen_names:
            continue
        parts = _complete_parts(sample, name)
        if not parts:
            parts = [sample.resolve()]
        claimed.update(parts)
        seen_names.add(name)
        bundles.append((name, parts))

    for path in singles:
        if path in claimed:
            continue
        bundles.append((path.stem, [path]))
    return bundles


def read_bundle_text(paths: list[Path]) -> str:
    chunks = [path.read_text(encoding="utf-8") for path in paths]
    return "".join(chunks)


def restore_to_folder(
    sources: list[str | Path],
    output_dir: str | Path,
    progress: ProgressCb = None,
) -> dict[str, Path]:
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, Path] = {}
    for name, paths in group_text_bundles(sources):
        _emit(progress, f"Restoring folder: {name} ({len(paths)} part(s))")
        files = parse_bundle(read_bundle_text(paths))
        if not files:
            _emit(progress, f"  No FILE_START blocks in {name}")
            continue
        dest = output_dir / name
        dest.mkdir(parents=True, exist_ok=True)
        for relative, data in files:
            target = dest / _safe_relative(relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            _emit(progress, f"  Wrote {relative} ({len(data)} bytes)")
        _emit(progress, f"Restored {len(files)} file(s) -> {dest}")
        results[name] = dest
    return results


def restore_to_zip(
    sources: list[str | Path],
    output_dir: str | Path,
    progress: ProgressCb = None,
) -> dict[str, Path]:
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, Path] = {}
    for name, paths in group_text_bundles(sources):
        _emit(progress, f"Restoring zip: {name} ({len(paths)} part(s))")
        files = parse_bundle(read_bundle_text(paths))
        if not files:
            _emit(progress, f"  No FILE_START blocks in {name}")
            continue
        dest = output_dir / f"{name}.zip"
        with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for relative, data in files:
                archive.writestr(_safe_relative(relative).as_posix(), data)
                _emit(progress, f"  Added {relative} ({len(data)} bytes)")
        _emit(progress, f"Restored {len(files)} file(s) -> {dest}")
        results[name] = dest
    return results
