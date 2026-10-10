# ziptotext

Pack a zip archive or a folder into plain text. Unpack that text back into a folder or a zip.

Text files stay as text. Images (`.jpg`, `.png`, and similar) and other binaries (`.bin`, `.dll`, `.exe`, `.frx`, and similar) are stored as base64 so the full tree can be rebuilt later.

## Why this exists

Some AI chat tools, coding agents, and upload forms accept text, but reject zip files, folders, or mixed binary trees. That is a real limit, not a hack against the host. ziptotext is a local, honest workaround: you turn the project into ordinary `.txt` files that those tools will take, then restore the original tree yourself.

Typical uses:

- Send a whole project, including binaries, as text when zip upload is blocked
- Keep a reconstructable snapshot of a VB6 / VB12 (or any) tree
- Split large trees into sized parts when a service caps text size (default 15 MB)

This tool does not bypass account limits, CAPTCHAs, or access controls. It only changes how files are encoded.

## What you get

Pack:

- one part: `project.txt`
- split parts: `project_part1.txt`, `project_part2.txt`

Restore:

- text to folder
- text to zip

The first part starts with rebuild instructions. Marker lines (`FILE_START`, `FILE_END`, `TYPE`, `MIME`, `ENCODING`) are metadata only. They must not be written into reconstructed files.

Images and binaries inflate by about one third as base64. Keep `--max-mb` at or below any upload cap you care about.

Needs Python 3.9+. The GUI needs `python3-tk` (`sudo apt install python3-tk` on Debian/Ubuntu).

## License

MIT. Full text is in `license/LICENSE`.

## Install on Linux

System-wide, same layout as GIMP (`/usr/bin` + `/usr/share`):

```bash
chmod +x install.sh
su -c ./install.sh
```

That installs:

- `/usr/bin/ziptotext` and `/usr/bin/ziptotext-gui`
- `/usr/lib/ziptotext/` (the actual app; menu uses this path)
- `/usr/share/applications/ziptotext.desktop`
- `/usr/share/icons/hicolor/*/apps/ziptotext.png` plus SVG
- `/usr/share/pixmaps/ziptotext.png`

Cinnamon menu: **Accessories** (Utility) -> **Zip to Text**.

If the icon or menu item does not show yet, press Alt+F2, type `r`, Enter, or log out.

User-only install (no root):

```bash
./install.sh --user
```

Launch:

```bash
ziptotext-gui
ziptotext archive.zip other.zip
```

## Update / uninstall

If the window still says `1.0.0`, Cinnamon is launching an old copy. `update.sh` copies this source into `/usr/lib/ziptotext` and points the menu at that absolute path. After install, Alt+F2, type `r`, Enter.

```bash
# Force-replace the installed app with this source
su -c ./update.sh

# Remove binaries, menu entry, icons, and the Python package
su -c ./uninstall.sh
```

User-only copies:

```bash
# Update a user install
./update.sh --user

# Uninstall a user install
./uninstall.sh --user
```

## CLI

```bash
# Pack zips
ziptotext file1.zip file2.zip

# Pack folders
ziptotext ./my-project ./other-folder

# Mix files and folders, set cap, skip images or binaries
ziptotext -o dist --max-mb 15 archive.zip ./my-project
ziptotext --no-images archive.zip
ziptotext --no-binaries archive.zip

# Restore text back to a folder tree
ziptotext --restore -o restored project.txt
ziptotext --restore -o restored project_part1.txt

# Restore text back to a zip
ziptotext --restore-zip -o restored project.txt

ziptotext --gui
```

Split parts named `name_part1.txt`, `name_part2.txt`, ... are concatenated in order before restore. Point at the first part, a list of parts, or a folder of `.txt` files.

## Image and binary format

```text
--- FILE_START: assets/logo.png ---
--- TYPE: image ---
--- MIME: image/png ---
--- ENCODING: base64 ---
iVBORw0KGgoAAAANSUhEUgAA...
--- FILE_END: assets/logo.png ---

--- FILE_START: Form1.frx ---
--- TYPE: binary ---
--- MIME: application/octet-stream ---
--- ENCODING: base64 ---
AAEC/2RhdGE=
--- FILE_END: Form1.frx ---
```
