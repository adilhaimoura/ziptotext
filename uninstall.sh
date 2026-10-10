#!/usr/bin/env bash
set -euo pipefail

APP_NAME="ziptotext"
USER_INSTALL=0
PREFIX="${PREFIX:-/usr}"

if [[ "${1:-}" == "--user" ]]; then
    PREFIX="${HOME}/.local"
    USER_INSTALL=1
fi

echo "Uninstalling ${APP_NAME} from ${PREFIX} and leftover copies"

if [[ "${USER_INSTALL}" -eq 0 ]] && [[ ! -w "${PREFIX}" ]]; then
    echo "Cannot write to ${PREFIX}."
    echo "Re-run as root:"
    echo "  su -c '$0'"
    echo "Or uninstall a user install:"
    echo "  $0 --user"
    exit 1
fi

python3 -m pip uninstall -y --break-system-packages "${APP_NAME}" >/dev/null 2>&1 || true
python3 -m pip uninstall -y --user --break-system-packages "${APP_NAME}" >/dev/null 2>&1 || true

python3 - << PY
from pathlib import Path
import shutil

app = "ziptotext"
removed = []

def drop(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()
    removed.append(str(path))

home = Path.home()
prefix = Path("${PREFIX}")
candidates = [
    prefix / "bin" / app,
    prefix / "bin" / f"{app}-gui",
    Path("/usr/bin") / app,
    Path("/usr/bin") / f"{app}-gui",
    Path("/usr/local/bin") / app,
    Path("/usr/local/bin") / f"{app}-gui",
    home / ".local/bin" / app,
    home / ".local/bin" / f"{app}-gui",
    prefix / "lib" / app,
    Path("/usr/lib") / app,
    Path("/usr/local/lib") / app,
    home / ".local/lib" / app,
    prefix / "share/applications" / f"{app}.desktop",
    home / ".local/share/applications" / f"{app}.desktop",
    prefix / "share/pixmaps" / f"{app}.png",
    prefix / "share/pixmaps" / f"{app}.svg",
    prefix / "share/icons/hicolor/scalable/apps" / f"{app}.svg",
]
for size in (16, 22, 24, 32, 48, 64, 128, 256):
    candidates.append(prefix / f"share/icons/hicolor/{size}x{size}/apps/{app}.png")

import glob
for pattern in (
    "/usr/lib/python*/dist-packages/ziptotext*",
    "/usr/local/lib/python*/dist-packages/ziptotext*",
    "/usr/local/lib/python*/site-packages/ziptotext*",
    str(home / ".local/lib/python*/site-packages/ziptotext*"),
):
    for match in glob.glob(pattern):
        candidates.append(Path(match))

for path in candidates:
    try:
        drop(path)
    except OSError as exc:
        print(f"Skip {path}: {exc}")

for item in removed:
    print(f"Removed {item}")
PY

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${PREFIX}/share/applications" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "${PREFIX}/share/icons/hicolor" >/dev/null 2>&1 || true
fi

echo
echo "Uninstalled ${APP_NAME}."
echo "Cinnamon: Alt+F2, type r, Enter if the menu item is still visible."
