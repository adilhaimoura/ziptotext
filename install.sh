#!/usr/bin/env bash
set -euo pipefail

APP_NAME="ziptotext"
APP_VERSION="1.5.0"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="${PREFIX:-/usr}"
USER_INSTALL=0

if [[ "${1:-}" == "--user" ]]; then
    PREFIX="${HOME}/.local"
    USER_INSTALL=1
fi

BIN_DIR="${PREFIX}/bin"
LIB_DIR="${PREFIX}/lib/${APP_NAME}"
APP_DIR="${PREFIX}/share/applications"
ICON_ROOT="${PREFIX}/share/icons/hicolor"
PIXMAP_DIR="${PREFIX}/share/pixmaps"

echo "Installing ${APP_NAME} ${APP_VERSION} to ${PREFIX}"
echo "App code goes to ${LIB_DIR} so old pip copies cannot hide it."

if [[ ! -w "${PREFIX}" ]] && [[ ! -w "$(dirname "${PREFIX}")" ]]; then
    echo "Cannot write to ${PREFIX}."
    echo "Re-run as root:"
    echo "  su -c '${ROOT}/install.sh'"
    echo "Or user install:"
    echo "  ${ROOT}/install.sh --user"
    exit 1
fi

if ! python3 -c "import tkinter" >/dev/null 2>&1; then
    echo "python3-tk is not installed. GUI needs it."
    echo "On Debian/Ubuntu: apt install python3-tk"
fi

purge_old_pip() {
    python3 -m pip uninstall -y --break-system-packages "${APP_NAME}" >/dev/null 2>&1 || true
    python3 -m pip uninstall -y --user --break-system-packages "${APP_NAME}" >/dev/null 2>&1 || true
}

echo "Removing leftover pip installs of ${APP_NAME} (if any)"
purge_old_pip

mkdir -p "${BIN_DIR}" "${LIB_DIR}" "${APP_DIR}" "${PIXMAP_DIR}"

python3 - << PY
from pathlib import Path
import shutil

src = Path("${ROOT}") / "ziptotext"
dst = Path("${LIB_DIR}") / "ziptotext"
dst.mkdir(parents=True, exist_ok=True)
for path in src.glob("*.py"):
    shutil.copy2(path, dst / path.name)
print(f"Copied package to {dst}")
PY

write_wrapper() {
    local dest="$1"
    local module="$2"
    cat > "${dest}" << EOF
#!/usr/bin/env python3
# ziptotext ${APP_VERSION} -> ${LIB_DIR}
import sys
sys.path.insert(0, "${LIB_DIR}")
from ${module} import main
raise SystemExit(main())
EOF
    chmod 755 "${dest}"
}

write_wrapper "${BIN_DIR}/ziptotext" "ziptotext.cli"
write_wrapper "${BIN_DIR}/ziptotext-gui" "ziptotext.gui"

# Stop PATH from launching stale pip wrappers
for extra in /usr/local/bin /usr/bin "${HOME}/.local/bin"; do
    if [[ "${extra}" == "${BIN_DIR}" ]]; then
        continue
    fi
    if [[ -w "${extra}" ]]; then
        write_wrapper "${extra}/ziptotext" "ziptotext.cli"
        write_wrapper "${extra}/ziptotext-gui" "ziptotext.gui"
    fi
done

install -m 644 "${ROOT}/share/applications/${APP_NAME}.desktop" "${APP_DIR}/${APP_NAME}.desktop"
sed -i "s|^Exec=.*|Exec=${BIN_DIR}/ziptotext-gui|" "${APP_DIR}/${APP_NAME}.desktop"
sed -i "s|^TryExec=.*|TryExec=${BIN_DIR}/ziptotext-gui|" "${APP_DIR}/${APP_NAME}.desktop"

# Replace any leftover user desktop entry that still points at the old command
if [[ -f "${HOME}/.local/share/applications/${APP_NAME}.desktop" ]]; then
    install -m 644 "${APP_DIR}/${APP_NAME}.desktop" "${HOME}/.local/share/applications/${APP_NAME}.desktop"
fi

install -D -m 644 \
    "${ROOT}/share/icons/hicolor/scalable/apps/${APP_NAME}.svg" \
    "${ICON_ROOT}/scalable/apps/${APP_NAME}.svg"

for size in 16 22 24 32 48 64 128 256; do
    src="${ROOT}/share/icons/hicolor/${size}x${size}/apps/${APP_NAME}.png"
    if [[ -f "${src}" ]]; then
        install -D -m 644 "${src}" "${ICON_ROOT}/${size}x${size}/apps/${APP_NAME}.png"
    fi
done

install -m 644 "${ROOT}/share/pixmaps/${APP_NAME}.png" "${PIXMAP_DIR}/${APP_NAME}.png"
install -m 644 "${ROOT}/share/icons/hicolor/scalable/apps/${APP_NAME}.svg" "${PIXMAP_DIR}/${APP_NAME}.svg"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${APP_DIR}" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "${ICON_ROOT}" >/dev/null 2>&1 || true
fi
if command -v xdg-desktop-menu >/dev/null 2>&1; then
    xdg-desktop-menu forceupdate >/dev/null 2>&1 || true
fi

echo
echo "Installed ${APP_NAME} ${APP_VERSION}"
echo "  launcher: ${BIN_DIR}/ziptotext-gui"
echo "  code:     ${LIB_DIR}/ziptotext"
echo "  menu:     ${APP_DIR}/${APP_NAME}.desktop"
echo
echo "Window title must say: Zip / Folder to Text ${APP_VERSION}"
echo "If Cinnamon still opens an old build: Alt+F2, type r, Enter"
echo "Then open Accessories -> Zip to Text"
echo
echo "Update:  ${ROOT}/update.sh"
echo "Remove:  ${ROOT}/uninstall.sh"
