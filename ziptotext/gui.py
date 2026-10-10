from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from . import __version__
from .converter import (
    DEFAULT_MAX_MB,
    DEFAULT_OUTPUT_DIR,
    convert_folders,
    convert_zips,
)
from .restore import restore_to_folder, restore_to_zip

BG = "#0b0f14"
BG_DEEP = "#05080c"
HEADER_BG = "#04070b"
CARD = "#121821"
BORDER = "#242e3b"
FG = "#e6edf3"
MUTED = "#8b98a9"
DANGER = "#f85149"
GREEN = "#35ff6f"

FONT = "DejaVu Sans"
FONT_MONO = "DejaVu Sans Mono"

SKY = [(0.0, "#a6e0ff"), (0.45, "#4fb0e4"), (1.0, "#1f77ab")]
SKY_HOVER = [(0.0, "#c2ecff"), (0.45, "#66c2f0"), (1.0, "#2b8bc2")]
SKY_PRESS = [(0.0, "#1f77ab"), (0.55, "#2f96ca"), (1.0, "#6cc3ec")]
STEEL = [(0.0, "#3f7ea4"), (0.5, "#2d6486"), (1.0, "#1c4660")]
STEEL_HOVER = [(0.0, "#5296bd"), (0.5, "#3a789c"), (1.0, "#265673")]
STEEL_PRESS = [(0.0, "#1c4660"), (0.55, "#2d6486"), (1.0, "#4a8bb0")]
DISABLED = [(0.0, "#3a4653"), (0.5, "#2c3641"), (1.0, "#222b34")]

TAB_ACTIVE = [(0.0, "#9fdcff"), (0.45, "#4fb0e4"), (1.0, "#1f77ab")]
TAB_ACTIVE_HOVER = [(0.0, "#b7e7ff"), (0.45, "#63bdee"), (1.0, "#2b8bc2")]
TAB_IDLE = [(0.0, "#2b3644"), (0.5, "#1e2732"), (1.0, "#151c24")]
TAB_IDLE_HOVER = [(0.0, "#3a4a5e"), (0.5, "#2a3646"), (1.0, "#1c2530")]


def _rgb(color: str) -> tuple[int, int, int]:
    h = color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _mix(c1, c2, t: float):
    return tuple(round(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _sample(stops, t: float):
    if t <= stops[0][0]:
        return stops[0][1]
    for i in range(1, len(stops)):
        a, b = stops[i - 1], stops[i]
        if t <= b[0]:
            span = (b[0] - a[0]) or 1
            return _mix(a[1], b[1], (t - a[0]) / span)
    return stops[-1][1]


def _prep(stops):
    return [(pos, _rgb(col)) for pos, col in stops]


def gradient_round_rect(canvas, x0, y0, x1, y1, radius, stops, tag=None) -> None:
    stops = _prep(stops)
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        return
    radius = max(0.0, min(radius, w / 2, h / 2))
    y = int(y0)
    while y < y1:
        yc = y + 0.5
        t = (yc - y0) / h
        col = "#%02x%02x%02x" % _sample(stops, t)
        inset = 0.0
        if radius > 0:
            if yc < y0 + radius:
                dy = radius - (yc - y0)
                inset = radius - (radius * radius - dy * dy) ** 0.5
            elif yc > y1 - radius:
                dy = yc - (y1 - radius)
                inset = radius - (radius * radius - dy * dy) ** 0.5
        canvas.create_line(x0 + inset, yc, x1 - inset, yc, fill=col, tags=tag)
        y += 1


def round_rect_points(x0, y0, x1, y1, r):
    r = max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    return [
        x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r,
        x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
        x0, y1, x0, y1 - r, x0, y0 + r, x0, y0,
    ]


class GradientButton(tk.Canvas):
    def __init__(
        self,
        master,
        text: str,
        command=None,
        *,
        width: int | None = None,
        height: int = 34,
        radius: int = 10,
        style: str = "sky",
        font=None,
        padx: int = 18,
    ) -> None:
        self.bg_out = master["bg"] if isinstance(master["bg"], str) else BG
        super().__init__(
            master,
            highlightthickness=0,
            bd=0,
            bg=self.bg_out,
            height=height,
            width=width or (len(text) * 7 + padx * 2),
        )
        self.command = command
        self.label = text
        self.radius = radius
        self.style = style
        self.font = font or (FONT, 9, "bold")
        self._hover = False
        self._pressed = False
        self._enabled = True
        self.configure(cursor="hand2")
        self.bind("<Configure>", self._redraw)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _palette(self):
        if not self._enabled:
            return DISABLED, "#6b7684"
        base = SKY if self.style == "sky" else STEEL
        hover = SKY_HOVER if self.style == "sky" else STEEL_HOVER
        press = SKY_PRESS if self.style == "sky" else STEEL_PRESS
        if self._pressed:
            return press, "#ffffff"
        if self._hover:
            return hover, "#ffffff"
        return base, "#ffffff"

    def _redraw(self, _event=None) -> None:
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 1 or h <= 1:
            return
        stops, fg = self._palette()
        gradient_round_rect(self, 1, 1, w - 1, h - 1, self.radius, stops)
        self.create_line(
            self.radius + 2, 2, w - self.radius - 2, 2,
            fill="#dff4ff" if self._enabled else "#4b5765",
        )
        self.create_line(
            2, h - 2, w - 2, h - 2,
            fill="#0d3d5c" if self._enabled else "#161d25",
        )
        self.create_text(w / 2 + 1, h / 2 + 2, text=self.label, font=self.font, fill="#062033")
        self.create_text(w / 2, h / 2, text=self.label, font=self.font, fill=fg)

    def _on_enter(self, _event) -> None:
        if self._enabled:
            self._hover = True
            self._redraw()

    def _on_leave(self, _event) -> None:
        self._hover = False
        self._pressed = False
        self._redraw()

    def _on_press(self, _event) -> None:
        if self._enabled:
            self._pressed = True
            self._redraw()

    def _on_release(self, _event) -> None:
        if not self._enabled:
            return
        was_pressed = self._pressed
        self._pressed = False
        self._redraw()
        if was_pressed and self.command:
            self.command()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self._redraw()

    def set_text(self, text: str) -> None:
        self.label = text
        self._redraw()


class FolderTab(tk.Canvas):
    def __init__(self, master, text: str, command=None) -> None:
        self.bg_out = master["bg"] if isinstance(master["bg"], str) else BG
        super().__init__(master, highlightthickness=0, bd=0, bg=self.bg_out, height=46)
        self.label = text
        self.command = command
        self.active = False
        self._hover = False
        self.configure(cursor="hand2")
        self.bind("<Configure>", self._redraw)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _palette(self):
        if self.active:
            return (TAB_ACTIVE_HOVER if self._hover else TAB_ACTIVE), "#ffffff"
        return (TAB_IDLE_HOVER if self._hover else TAB_IDLE), (FG if self._hover else MUTED)

    def _redraw(self, _event=None) -> None:
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 1 or h <= 1:
            return
        stops, fg = self._palette()
        stops = _prep(stops)
        top = 6
        slant = 14
        side = 8
        for y in range(top, h):
            if y < top + slant:
                f = (y - top) / slant
                left = side + slant * (1 - f)
                right = w - side - slant * (1 - f)
            else:
                left = side
                right = w - side
            t = (y - top) / max(h - top, 1)
            col = "#%02x%02x%02x" % _sample(stops, t)
            self.create_line(left, y + 0.5, right, y + 0.5, fill=col)
        pts = [
            side, h, side, top + slant, side + slant, top,
            w - side - slant, top, w - side, top + slant, w - side, h,
        ]
        self.create_polygon(
            pts, outline="#0d3d5c" if self.active else "#10161e",
            fill="", width=1,
        )
        if self.active:
            self.create_line(
                side + slant, top + 1, w - side - slant, top + 1, fill="#dff4ff"
            )
        self.create_text(
            w / 2 + 1, (h + top) / 2 + 2, text=self.label,
            font=(FONT, 11, "bold"), fill="#062033",
        )
        self.create_text(
            w / 2, (h + top) / 2, text=self.label, font=(FONT, 11, "bold"), fill=fg
        )

    def set_active(self, active: bool) -> None:
        self.active = active
        self._redraw()

    def _on_enter(self, _event) -> None:
        self._hover = True
        self._redraw()

    def _on_leave(self, _event) -> None:
        self._hover = False
        self._redraw()

    def _on_click(self, _event) -> None:
        if self.command:
            self.command()


class TerminalLog(tk.Frame):
    def __init__(self, master, bg_out: str, height: int = 150) -> None:
        super().__init__(master, bg=bg_out)
        self.bg_out = bg_out
        self.canvas = tk.Canvas(
            self, bg=bg_out, highlightthickness=0, bd=0, height=height
        )
        self.canvas.pack(fill="both", expand=True)
        self.text = tk.Text(
            self.canvas,
            bg="#000000",
            fg=GREEN,
            insertbackground=GREEN,
            selectbackground="#0b3d1f",
            selectforeground=GREEN,
            font=(FONT_MONO, 9),
            relief="flat",
            bd=0,
            highlightthickness=0,
            wrap="word",
            state="disabled",
        )
        self._win = self.canvas.create_window(0, 0, window=self.text, anchor="nw")
        self.canvas.bind("<Configure>", self._resize)

    def _resize(self, event) -> None:
        self.canvas.delete("bg")
        pts = round_rect_points(1, 1, event.width - 1, event.height - 1, 14)
        self.canvas.create_polygon(
            pts, smooth=True, splinesteps=24,
            fill="#000000", outline="#1f6f3f", width=1, tags="bg",
        )
        self.canvas.tag_lower("bg")
        self.canvas.coords(self._win, 12, 12)
        self.canvas.itemconfigure(
            self._win, width=max(1, event.width - 24), height=max(1, event.height - 24)
        )


class SourceTab(tk.Frame):
    def __init__(self, master: tk.Misc, *, kind: str) -> None:
        super().__init__(master, bg=BG)
        self.kind = kind
        self.paths: list[str] = []
        self._build()

    def _build(self) -> None:
        if self.kind == "zip":
            card_title = "Zip files"
            add_label = "Add zips"
            folder_label = "Add folder of zips"
        elif self.kind == "restore":
            card_title = "Packed text files"
            add_label = "Add text files"
            folder_label = "Add folder of text"
        else:
            card_title = "Folders"
            add_label = "Add folders"
            folder_label = None

        card = tk.Frame(self, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="both", expand=True, padx=2, pady=2)

        tk.Label(
            card, text=card_title, bg=CARD, fg=FG, font=(FONT, 11, "bold")
        ).pack(anchor="w", padx=14, pady=(12, 8))

        btns = tk.Frame(card, bg=CARD)
        btns.pack(fill="x", padx=14, pady=(0, 10))
        GradientButton(btns, add_label, self._add_items).pack(side="left", padx=(0, 8))
        if folder_label:
            GradientButton(btns, folder_label, self._add_folder).pack(
                side="left", padx=(0, 8)
            )
        GradientButton(btns, "Remove selected", self._remove_selected).pack(
            side="left", padx=(0, 8)
        )
        GradientButton(btns, "Clear", self._clear).pack(side="left")

        wrap = tk.Frame(card, bg=CARD)
        wrap.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        scroll = tk.Scrollbar(
            wrap, orient="vertical", bg=CARD, troughcolor=CARD,
            activebackground=BORDER, highlightthickness=0, bd=0, relief="flat",
        )
        scroll.pack(side="right", fill="y")
        self.listbox = tk.Listbox(
            wrap,
            selectmode="extended",
            font=(FONT_MONO, 9),
            bg=BG_DEEP,
            fg=FG,
            selectbackground="#2b8bc2",
            selectforeground="#ffffff",
            highlightbackground=BORDER,
            highlightcolor="#4fb0e4",
            highlightthickness=1,
            relief="flat",
            bd=0,
            activestyle="none",
            yscrollcommand=scroll.set,
            height=9,
        )
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll.config(command=self.listbox.yview)

    def _add_unique(self, paths: list[str]) -> int:
        added = 0
        existing = set(self.paths)
        for path in paths:
            resolved = str(Path(path).expanduser().resolve())
            if resolved in existing:
                continue
            self.paths.append(resolved)
            existing.add(resolved)
            self.listbox.insert("end", resolved)
            added += 1
        return added

    def _add_items(self) -> None:
        if self.kind == "zip":
            chosen = filedialog.askopenfilenames(
                title="Select zip archives",
                filetypes=[
                    ("Zip archives", "*.zip *.zi"),
                    ("Zip archives", "*.zip"),
                    ("All files", "*.*"),
                ],
            )
            if chosen:
                self._add_unique(list(chosen))
        elif self.kind == "restore":
            chosen = filedialog.askopenfilenames(
                title="Select packed text files",
                filetypes=[
                    ("Text bundles", "*.txt"),
                    ("All files", "*.*"),
                ],
            )
            if chosen:
                self._add_unique(list(chosen))
        else:
            folder = filedialog.askdirectory(title="Select a folder to bundle")
            if folder:
                self._add_unique([folder])

    def _add_folder(self) -> None:
        if self.kind == "restore":
            folder = filedialog.askdirectory(title="Select folder containing packed text files")
            if not folder:
                return
            texts = sorted(
                str(path)
                for path in Path(folder).iterdir()
                if path.is_file() and path.suffix.lower() == ".txt"
            )
            if not texts:
                messagebox.showinfo("No text files", "No .txt files found in that folder.")
                return
            self._add_unique(texts)
            return
        folder = filedialog.askdirectory(title="Select folder containing zip files")
        if not folder:
            return
        zips = sorted(
            str(path)
            for path in Path(folder).iterdir()
            if path.is_file() and path.suffix.lower() in {".zip", ".zi"}
        )
        if not zips:
            messagebox.showinfo("No zips", "No .zip files found in that folder.")
            return
        self._add_unique(zips)

    def _remove_selected(self) -> None:
        selected = list(self.listbox.curselection())
        for index in reversed(selected):
            self.listbox.delete(index)
            del self.paths[index]

    def _clear(self) -> None:
        self.listbox.delete(0, "end")
        self.paths.clear()


class ZipToTextApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__(className="ZipToText")
        self.title(f"Zip / Folder to Text {__version__}")
        self.geometry("880x900")
        self.minsize(760, 780)
        self.configure(bg=BG)
        self._busy = False
        self._icon_images: list[tk.PhotoImage] = []

        self.protocol("WM_DELETE_WINDOW", self._close)
        self._set_icon()
        self._build()

    def _icon_candidates(self) -> list[Path]:
        here = Path(__file__).resolve().parent.parent
        names = [
            "share/icons/hicolor/64x64/apps/ziptotext.png",
            "share/icons/hicolor/48x48/apps/ziptotext.png",
            "share/pixmaps/ziptotext.png",
        ]
        roots = [Path("/usr"), Path("/usr/local"), Path.home() / ".local", here]
        paths: list[Path] = []
        for root in roots:
            for name in names:
                paths.append(root / name)
        return paths

    def _set_icon(self) -> None:
        for path in self._icon_candidates():
            if not path.is_file():
                continue
            try:
                image = tk.PhotoImage(file=str(path))
            except tk.TclError:
                continue
            self._icon_images.append(image)
            self.iconphoto(True, image)
            break

    def _build(self) -> None:
        header = tk.Frame(
            self, bg=HEADER_BG, highlightbackground=BORDER, highlightthickness=1
        )
        header.pack(fill="x")
        header_top = tk.Frame(header, bg=HEADER_BG)
        header_top.pack(fill="x", padx=20, pady=(16, 2))
        tk.Label(
            header_top,
            text=f"Zip / Folder to Text {__version__}",
            bg=HEADER_BG,
            fg=FG,
            font=(FONT, 18, "bold"),
        ).pack(side="left")
        GradientButton(
            header_top, "Close", self._close, style="steel", height=32, padx=16
        ).pack(side="right")
        tk.Label(
            header,
            text="Pack zips or folders into reconstructable text, then restore them. Images and binaries travel as base64.",
            bg=HEADER_BG,
            fg=MUTED,
            font=(FONT, 10),
        ).pack(anchor="w", padx=20, pady=(0, 14))

        self._build_tabbar()

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=16, pady=12)

        footer = tk.Frame(body, bg=BG)
        footer.pack(side="bottom", fill="x", pady=(10, 0))
        tk.Label(footer, text=f"v{__version__}", bg=BG, fg=MUTED, font=(FONT, 9)).pack(
            side="left"
        )
        GradientButton(
            footer, "Close", self._close, style="steel", height=40, padx=22
        ).pack(side="right")
        self.convert_btn = GradientButton(
            footer, "Convert all", self._start_convert, style="sky", height=40, padx=26,
            font=(FONT, 10, "bold"),
        )
        self.convert_btn.pack(side="right", padx=(0, 8))

        options = tk.Frame(body, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        tk.Label(options, text="Options", bg=CARD, fg=FG, font=(FONT, 11, "bold")).pack(
            anchor="w", padx=14, pady=(12, 8)
        )

        out_row = tk.Frame(options, bg=CARD)
        out_row.pack(fill="x", padx=14, pady=(0, 10))
        tk.Label(out_row, text="Output folder", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(
            side="left"
        )
        self.output_var = tk.StringVar(value=str(Path.cwd() / DEFAULT_OUTPUT_DIR))
        tk.Entry(
            out_row,
            textvariable=self.output_var,
            bg=BG_DEEP,
            fg=FG,
            insertbackground=FG,
            highlightbackground=BORDER,
            highlightcolor="#4fb0e4",
            highlightthickness=1,
            relief="flat",
            bd=0,
        ).pack(side="left", fill="x", expand=True, padx=8, ipady=4)
        GradientButton(
            out_row, "Browse", self._browse_output, style="steel", height=30, padx=12,
            font=(FONT, 9),
        ).pack(side="left")

        settings = tk.Frame(options, bg=CARD)
        settings.pack(fill="x", padx=14, pady=(0, 14))
        tk.Label(settings, text="Max MB per part", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(
            side="left"
        )
        self.max_mb_var = tk.DoubleVar(value=DEFAULT_MAX_MB)
        tk.Spinbox(
            settings,
            from_=0.5,
            to=100.0,
            increment=0.5,
            textvariable=self.max_mb_var,
            width=8,
            bg=BG_DEEP,
            fg=FG,
            insertbackground=FG,
            buttonbackground="#2d6486",
            highlightbackground=BORDER,
            highlightcolor="#4fb0e4",
            highlightthickness=1,
            relief="flat",
            bd=0,
            font=(FONT, 9),
        ).pack(side="left", padx=(8, 20), ipady=3)
        self.images_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            settings,
            text="Embed images (jpg/png) as base64",
            variable=self.images_var,
            bg=CARD,
            fg=FG,
            activebackground=CARD,
            activeforeground=FG,
            selectcolor=BG_DEEP,
            highlightthickness=0,
            bd=0,
            font=(FONT, 9),
            cursor="hand2",
        ).pack(side="left")
        self.binaries_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            settings,
            text="Embed binaries (.bin/.dll/.exe) as base64",
            variable=self.binaries_var,
            bg=CARD,
            fg=FG,
            activebackground=CARD,
            activeforeground=FG,
            selectcolor=BG_DEEP,
            highlightthickness=0,
            bd=0,
            font=(FONT, 9),
            cursor="hand2",
        ).pack(side="left", padx=(16, 0))
        self.restore_zip_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            settings,
            text="Restore as zip (not folder)",
            variable=self.restore_zip_var,
            bg=CARD,
            fg=FG,
            activebackground=CARD,
            activeforeground=FG,
            selectcolor=BG_DEEP,
            highlightthickness=0,
            bd=0,
            font=(FONT, 9),
            cursor="hand2",
        ).pack(side="left", padx=(16, 0))

        self.content_holder = tk.Frame(body, bg=BG)
        self.content_holder.pack(fill="both", expand=True)

        log_card = tk.Frame(body, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        log_card.pack(side="bottom", fill="both", expand=True, pady=(10, 0))
        tk.Label(log_card, text="Terminal", bg=CARD, fg=FG, font=(FONT, 11, "bold")).pack(
            anchor="w", padx=14, pady=(10, 6)
        )
        terminal = TerminalLog(log_card, CARD, height=150)
        terminal.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.log = terminal.text

        options.pack(side="top", fill="x", pady=(10, 0))
        self._select_tab("zip")

    def _build_tabbar(self) -> None:
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", padx=16, pady=(0, 0))
        bar.columnconfigure(0, weight=1, uniform="tab")
        bar.columnconfigure(1, weight=1, uniform="tab")
        bar.columnconfigure(2, weight=1, uniform="tab")

        self._tab_buttons: dict[str, FolderTab] = {}
        for col, (key, label) in enumerate(
            (("zip", "Zip to Text"), ("folder", "Folder to Text"), ("restore", "Text to Files"))
        ):
            tab = FolderTab(bar, label, command=lambda k=key: self._select_tab(k))
            tab.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 4, 0))
            self._tab_buttons[key] = tab

    def _select_tab(self, key: str) -> None:
        for child in self.content_holder.winfo_children():
            child.pack_forget()
        if not hasattr(self, "_tabs"):
            self._tabs = {
                "zip": SourceTab(self.content_holder, kind="zip"),
                "folder": SourceTab(self.content_holder, kind="folder"),
                "restore": SourceTab(self.content_holder, kind="restore"),
            }
        self._active_key = key
        self._tabs[key].pack(fill="both", expand=True)
        for name, tab in self._tab_buttons.items():
            tab.set_active(name == key)
        if hasattr(self, "convert_btn") and not self._busy:
            self.convert_btn.set_text("Restore all" if key == "restore" else "Convert all")

    @property
    def zip_tab(self) -> SourceTab:
        return self._tabs["zip"]

    @property
    def folder_tab(self) -> SourceTab:
        return self._tabs["folder"]

    def _append_log(self, message: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _ui_log(self, message: str) -> None:
        self.after(0, lambda: self._append_log(message))

    def _browse_output(self) -> None:
        folder = filedialog.askdirectory(title="Select output folder")
        if folder:
            self.output_var.set(folder)

    def _active_tab(self) -> SourceTab:
        return self._tabs[self._active_key]

    def _start_convert(self) -> None:
        if self._busy:
            return
        tab = self._active_tab()
        subjects = {
            "zip": "zip files",
            "folder": "folders",
            "restore": "text files",
        }
        if not tab.paths:
            messagebox.showwarning(
                "Nothing selected",
                f"Add one or more {subjects.get(tab.kind, 'items')} first.",
            )
            return

        output_dir = self.output_var.get().strip() or DEFAULT_OUTPUT_DIR
        include_images = bool(self.images_var.get())
        include_binaries = bool(self.binaries_var.get())
        restore_as_zip = bool(self.restore_zip_var.get())
        items = list(tab.paths)
        kind = tab.kind
        max_mb = DEFAULT_MAX_MB
        if kind != "restore":
            try:
                max_mb = float(self.max_mb_var.get())
            except (tk.TclError, ValueError):
                messagebox.showerror("Invalid size", "Max MB must be a number.")
                return
            if max_mb <= 0:
                messagebox.showerror("Invalid size", "Max MB must be greater than 0.")
                return

        self._busy = True
        self.convert_btn.set_enabled(False)
        self.convert_btn.set_text("Working...")
        labels = {
            "zip": "archive(s)",
            "folder": "folder(s)",
            "restore": "text bundle(s)",
        }
        action = "Restoring" if kind == "restore" else "Starting"
        self._append_log(f"{action} {len(items)} {labels.get(kind, 'item(s)')} -> {output_dir}")

        def work() -> None:
            try:
                if kind == "restore":
                    if restore_as_zip:
                        restored = restore_to_zip(
                            items, output_dir=output_dir, progress=self._ui_log
                        )
                    else:
                        restored = restore_to_folder(
                            items, output_dir=output_dir, progress=self._ui_log
                        )
                    total = len(restored)
                    kind_label = "zip(s)" if restore_as_zip else "folder(s)"
                    self._ui_log(f"Done. Restored {total} {kind_label}.")
                    self.after(
                        0,
                        lambda: messagebox.showinfo(
                            "Finished",
                            f"Restored {total} {kind_label} to:\n{output_dir}",
                        ),
                    )
                    return
                if kind == "zip":
                    results = convert_zips(
                        items,
                        output_dir=output_dir,
                        max_mb=max_mb,
                        include_images=include_images,
                        include_binaries=include_binaries,
                        progress=self._ui_log,
                    )
                else:
                    results = convert_folders(
                        items,
                        output_dir=output_dir,
                        max_mb=max_mb,
                        include_images=include_images,
                        include_binaries=include_binaries,
                        progress=self._ui_log,
                    )
                total = sum(len(files) for files in results.values())
                self._ui_log(f"Done. Wrote {total} text file(s).")
                self.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Finished", f"Wrote {total} text file(s) to:\n{output_dir}"
                    ),
                )
            except Exception as exc:
                message = str(exc)
                self._ui_log(f"Error: {message}")
                self.after(0, lambda m=message: messagebox.showerror("Convert failed", m))
            finally:
                self.after(0, self._unlock)

        threading.Thread(target=work, daemon=True).start()

    def _unlock(self) -> None:
        self._busy = False
        self.convert_btn.set_enabled(True)
        label = "Restore all" if getattr(self, "_active_key", "") == "restore" else "Convert all"
        self.convert_btn.set_text(label)

    def _close(self) -> None:
        if self._busy:
            if not messagebox.askyesno("Busy", "Conversion is still running. Close anyway?"):
                return
        self.destroy()


def main() -> None:
    app = ZipToTextApp()
    app.mainloop()


if __name__ == "__main__":
    main()
