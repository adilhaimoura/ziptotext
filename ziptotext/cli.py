from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .converter import (
    DEFAULT_MAX_MB,
    DEFAULT_OUTPUT_DIR,
    convert_folder,
    convert_zip,
)
from .restore import restore_to_folder, restore_to_zip


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ziptotext",
        description=(
            "Pack zip archives or folders into reconstructable text bundles, "
            "and restore those text files back into a folder or zip. "
            "Text stays as text; images and other binaries are stored as base64."
        ),
    )
    parser.add_argument(
        "sources",
        nargs="*",
        help="Zip files, folders, or (with --restore) text bundles",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "-s",
        "--max-mb",
        type=float,
        default=DEFAULT_MAX_MB,
        help=f"Max size in MB per text file (default: {DEFAULT_MAX_MB})",
    )
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Skip image files instead of embedding them as base64",
    )
    parser.add_argument(
        "--no-binaries",
        action="store_true",
        help="Skip non-image binary files instead of embedding them as base64",
    )
    parser.add_argument(
        "--restore",
        action="store_true",
        help="Restore packed .txt files back into a folder tree",
    )
    parser.add_argument(
        "--restore-zip",
        action="store_true",
        help="Restore packed .txt files back into a .zip archive",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Open the graphical interface",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"ziptotext {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.restore and args.restore_zip:
        print("Error: use either --restore or --restore-zip, not both.", file=sys.stderr)
        return 1

    if args.gui or (not args.sources and not args.restore and not args.restore_zip):
        try:
            from .gui import main as gui_main
        except ModuleNotFoundError as exc:
            if "tkinter" in str(exc).lower():
                print(
                    "GUI needs python3-tk. Install it with:\n"
                    "  sudo apt install python3-tk\n"
                    "Or convert from the terminal:\n"
                    "  ziptotext archive.zip",
                    file=sys.stderr,
                )
                return 1
            raise
        gui_main()
        return 0

    if not args.sources:
        parser.print_help()
        return 1

    missing = [path for path in args.sources if not Path(path).exists()]
    if missing:
        for path in missing:
            print(f"Error: not found: {path}", file=sys.stderr)
        return 1

    if args.restore:
        restore_to_folder(args.sources, output_dir=args.output)
        return 0
    if args.restore_zip:
        restore_to_zip(args.sources, output_dir=args.output)
        return 0

    for source in args.sources:
        path = Path(source)
        if path.is_dir():
            convert_folder(
                path,
                output_dir=args.output,
                max_mb=args.max_mb,
                include_images=not args.no_images,
                include_binaries=not args.no_binaries,
            )
        else:
            convert_zip(
                path,
                output_dir=args.output,
                max_mb=args.max_mb,
                include_images=not args.no_images,
                include_binaries=not args.no_binaries,
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
