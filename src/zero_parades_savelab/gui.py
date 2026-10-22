"""Tkinter desktop interface. It never runs a server or sends network requests."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import queue
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .demo import create_demo
from .diff import compare, filtered
from .discovery import default_data_directory, default_save_directory
from .errors import SafetyError
from .registry import flag_descriptions, load_presets
from .service import SaveService, write_new


class SaveLabApp:
    def __init__(self, root, service=None, directory=None):
        self.root = root
        self.service = service or SaveService()
        self.opened = None
        self.pending = {}
        self.exported = None
        self.busy = False
        self.closed = False
        self.events = queue.Queue()
        self.descriptions = flag_descriptions()
        self.presets = load_presets()
        self.diff_entries = []
        self.rows = []
        self.backup_rows = []
        self.flag_rows = {}
        self.path_var = tk.StringVar(value=str(directory or default_save_directory()))
        self.search_var = tk.StringVar()
        self.diff_search = tk.StringVar()
        self.diff_category = tk.StringVar(value="all")
        self.experimental = tk.BooleanVar(value=False)
        self.status = tk.StringVar(
            value="Select a folder, then open a save. Originals stay untouched until Apply."
        )
        self.preset_var = tk.StringVar(value=next(iter(self.presets.values())).title)
        root.title(f"ZeroParades-SaveLab {__version__}")
        root.geometry("1280x820")
        root.minsize(1000, 690)
        root.configure(background="#edf1f7")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background="#edf1f7")
        style.configure("TLabel", background="#edf1f7", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=(10, 6))
        style.configure("Treeview", font=("Segoe UI", 10), rowheight=27)
        style.configure("Treeview.Heading", font=("Segoe UI Semibold", 10))
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 21), foreground="#183153")
        style.configure("Risk.TLabel", foreground="#8a4400")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)
        title = ttk.Frame(root, padding=(18, 12))
        title.grid(row=0, column=0, sticky="ew")
        ttk.Label(title, text="ZeroParades-SaveLab", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            title, text="Local only  •  Automatic backups  •  Verified copies before originals"
        ).pack(anchor="w")
        toolbar = ttk.Frame(root, padding=(18, 0, 18, 10))
        toolbar.grid(row=1, column=0, sticky="ew")
        toolbar.columnconfigure(0, weight=1)
        ttk.Entry(toolbar, textvariable=self.path_var).grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        for column, (text, command) in enumerate(
            [
                ("Choose folder", self.choose_folder),
                ("Find saves", self.find_saves),
                ("Refresh", self.refresh),
                ("Open file…", self.choose_file),
            ],
            1,
        ):
            ttk.Button(toolbar, text=text, command=command).grid(row=0, column=column, padx=3)
        panes = ttk.Panedwindow(root, orient="horizontal")
        panes.grid(row=2, column=0, sticky="nsew", padx=18)
        sidebar = ttk.Frame(panes)
        panes.add(sidebar, weight=1)
        ttk.Label(sidebar, text="SAVES", font=("Segoe UI Semibold", 10)).pack(
            anchor="w", pady=(0, 7)
        )
        self.save_tree = self.tree(sidebar, ["label", "type"], ["Save", "Type"], [245, 75])
        self.save_tree.bind("<Double-1>", lambda _: self.open_selected())
        ttk.Button(sidebar, text="Open selected save", command=self.open_selected).pack(
            fill="x", pady=7
        )
        self.tabs = ttk.Notebook(panes)
        panes.add(self.tabs, weight=3)
        self.overview = ttk.Frame(self.tabs, padding=14)
        self.explorer = ttk.Frame(self.tabs, padding=14)
        self.diff_tab = ttk.Frame(self.tabs, padding=14)
        self.backup_tab = ttk.Frame(self.tabs, padding=14)
        for frame, title_text in [
            (self.overview, "Overview & repair"),
            (self.explorer, "Advanced Flag Explorer"),
            (self.diff_tab, "Compare saves"),
            (self.backup_tab, "Backups & restore"),
        ]:
            self.tabs.add(frame, text=title_text)
        self.build_overview()
        self.build_explorer()
        self.build_diff()
        self.build_backups()
        ttk.Label(root, textvariable=self.status, wraplength=1180, padding=(18, 9)).grid(
            row=3, column=0, sticky="ew"
        )
        ttk.Label(
            root,
            text="Unofficial tool. Not affiliated with or endorsed by ZA/UM.",
            padding=(18, 0, 18, 10),
        ).grid(row=4, column=0, sticky="w")
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.report_callback_exception = lambda kind, value, trace: self.fail(value)
        root.after(50, self.poll)

    @staticmethod
    def tree(parent, columns, headings, widths, height=None):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(
            frame, columns=columns, show="headings", height=height or 10, selectmode="browse"
        )
        for key, heading, width in zip(columns, headings, widths):
            tree.heading(key, text=heading)
            tree.column(key, width=width, minwidth=55)
        vertical = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        return tree

    @staticmethod
    def text(parent, height=5):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=(0, 10))
        widget = tk.Text(
            frame,
            height=height,
            wrap="word",
            font=("Segoe UI", 10),
            relief="flat",
            background="#ffffff",
            padx=10,
            pady=8,
        )
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=widget.yview)
        scrollbar.pack(side="right", fill="y")
        widget.pack(side="left", fill="x", expand=True)
        widget.configure(yscrollcommand=scrollbar.set, state="disabled")
        return widget

    @staticmethod
    def set_text(widget, value):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def build_overview(self):
        # Pin write actions below a scrollable review area so smaller screens
        # never hide the export/apply controls or the preset's risk text.
        self.action_bar = ttk.Frame(self.overview)
        self.action_bar.pack(side="bottom", fill="x", pady=(10, 0))
        for label, command in [
            ("Create backup", self.manual_backup),
            ("Export patched copy…", self.export_copy),
            ("Apply exported copy to original…", self.apply_copy),
        ]:
            ttk.Button(self.action_bar, text=label, command=command).pack(side="left", padx=(0, 7))
        container = ttk.Frame(self.overview)
        container.pack(fill="both", expand=True)
        self.overview_canvas = tk.Canvas(container, background="#edf1f7", highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.overview_canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.overview_canvas.pack(side="left", fill="both", expand=True)
        self.overview_canvas.configure(yscrollcommand=scrollbar.set)
        body = ttk.Frame(self.overview_canvas)
        window = self.overview_canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind(
            "<Configure>",
            lambda event: self.overview_canvas.configure(
                scrollregion=self.overview_canvas.bbox("all")
            ),
        )
        self.overview_canvas.bind(
            "<Configure>",
            lambda event: self.overview_canvas.itemconfigure(window, width=event.width),
        )
        ttk.Label(body, text="Selected save", font=("Segoe UI Semibold", 12)).pack(anchor="w")
        self.metadata_text = self.text(body, 6)
        ttk.Label(body, text="Confirmed repair", font=("Segoe UI Semibold", 12)).pack(anchor="w")
        combo = ttk.Combobox(
            body,
            textvariable=self.preset_var,
            state="readonly",
            values=[p.title for p in self.presets.values()],
        )
        combo.pack(fill="x", pady=(5, 8))
        combo.bind("<<ComboboxSelected>>", lambda event: self.describe_preset())
        self.preset_text = self.text(body, 8)
        ttk.Button(
            body, text="Check conditions & preview repair", command=self.preview_preset
        ).pack(anchor="w")
        ttk.Label(
            body, text="Pending changes — nothing written yet", font=("Segoe UI Semibold", 11)
        ).pack(anchor="w", pady=(12, 5))
        self.pending_tree = self.tree(
            body, ["id", "before", "after"], ["Flag", "Before", "After"], [420, 80, 80], 3
        )
        self.describe_preset()

    def build_explorer(self):
        ttk.Label(
            self.explorer, text="Search NPC IDs, variable IDs, values or known descriptions"
        ).pack(anchor="w")
        entry = ttk.Entry(self.explorer, textvariable=self.search_var)
        entry.pack(fill="x", pady=8)
        self.search_var.trace_add("write", lambda *_: self.populate_flags())
        ttk.Checkbutton(
            self.explorer,
            text="Acknowledge experimental editing of Unknown flags",
            variable=self.experimental,
        ).pack(anchor="w")
        ttk.Label(
            self.explorer,
            text="Unknown means unverified meaning. Counters are read-only. All edits first become a separate copy.",
            style="Risk.TLabel",
            wraplength=780,
        ).pack(anchor="w", pady=(3, 8))
        self.flags_tree = self.tree(
            self.explorer,
            ["id", "value", "kind", "status", "description"],
            ["Variable", "Value", "Kind", "Knowledge", "Description"],
            [290, 95, 80, 90, 410],
        )
        buttons = ttk.Frame(self.explorer)
        buttons.pack(fill="x", pady=8)
        ttk.Button(buttons, text="Queue True", command=lambda: self.queue_selected(True)).pack(
            side="left"
        )
        ttk.Button(buttons, text="Queue False", command=lambda: self.queue_selected(False)).pack(
            side="left", padx=8
        )
        ttk.Button(buttons, text="Clear pending changes", command=self.clear_pending).pack(
            side="left"
        )

    def build_diff(self):
        ttk.Label(
            self.diff_tab,
            text="Compare the open save with another file. Variable IDs are matched by name.",
            wraplength=760,
        ).pack(anchor="w")
        toolbar = ttk.Frame(self.diff_tab)
        toolbar.pack(fill="x", pady=8)
        ttk.Button(toolbar, text="Choose comparison save…", command=self.compare_file).pack(
            side="left"
        )
        ttk.Combobox(
            toolbar,
            textvariable=self.diff_category,
            values=["all", "flags", "counters", "inventory", "other"],
            state="readonly",
            width=12,
        ).pack(side="left", padx=8)
        ttk.Entry(toolbar, textvariable=self.diff_search).pack(side="left", fill="x", expand=True)
        self.diff_category.trace_add("write", lambda *_: self.populate_diff())
        self.diff_search.trace_add("write", lambda *_: self.populate_diff())
        self.diff_tree = self.tree(
            self.diff_tab,
            ["path", "kind", "before", "after"],
            ["State path", "Change", "Before", "After"],
            [370, 85, 180, 180],
        )
        ttk.Button(
            self.diff_tab, text="Export filtered structural diff…", command=self.export_diff
        ).pack(anchor="w", pady=8)

    def build_backups(self):
        ttk.Label(
            self.backup_tab,
            text="Every export, original replacement and restore creates a verified local backup.",
            wraplength=750,
        ).pack(anchor="w")
        ttk.Label(self.backup_tab, text=str(self.service.backup_root), wraplength=750).pack(
            anchor="w", pady=(3, 8)
        )
        self.backup_tree = self.tree(
            self.backup_tab,
            ["date", "file", "hash"],
            ["UTC", "Original file", "SHA-256"],
            [210, 260, 500],
        )
        buttons = ttk.Frame(self.backup_tab)
        buttons.pack(fill="x", pady=8)
        ttk.Button(buttons, text="Refresh backups", command=self.refresh_backups).pack(side="left")
        ttk.Button(buttons, text="Restore selected backup…", command=self.restore_backup).pack(
            side="left", padx=8
        )

    def fail(self, error):
        self.status.set(str(error))
        messagebox.showerror("Operation refused", str(error), parent=self.root)

    def work(self, label, function, done):
        if self.busy:
            self.status.set("Please wait for the current operation to finish.")
            return
        self.busy = True
        self.status.set(label)

        def worker():
            try:
                self.events.put((done, function(), None))
            except Exception as error:
                self.events.put((done, None, error))

        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        if self.closed:
            return
        try:
            while True:
                done, result, error = self.events.get_nowait()
                self.busy = False
                if error:
                    self.fail(error)
                else:
                    done(result)
        except queue.Empty:
            pass
        self.root.after(50, self.poll)

    def require_open(self):
        if self.busy:
            raise SafetyError(
                "Wait for the current operation to finish before changing the edit plan."
            )
        if not self.opened:
            raise SafetyError("Open a save first.")
        return self.opened

    def choose_folder(self):
        folder = filedialog.askdirectory(parent=self.root)
        if folder:
            self.path_var.set(folder)
            self.refresh()

    def find_saves(self):
        self.path_var.set(str(default_save_directory()))
        self.refresh()

    def refresh(self):
        directory = self.path_var.get()
        self.work(
            "Checking save headers and integrity…",
            lambda: self.service.list_saves(directory),
            self.show_saves,
        )

    def show_saves(self, rows):
        self.rows = rows
        self.save_tree.delete(*self.save_tree.get_children())
        for index, row in enumerate(rows):
            self.save_tree.insert("", "end", iid=str(index), values=(row["label"], row["type"]))
        self.status.set(f"{len(rows)} saves found. Double-click a row to inspect it.")

    def open_selected(self):
        selection = self.save_tree.selection()
        if selection:
            row = self.rows[int(selection[0])]
            if row["error"]:
                raise SafetyError(row["error"])
            self.open_path(row["path"])

    def choose_file(self):
        path = filedialog.askopenfilename(
            parent=self.root, filetypes=[("Zero Parades saves", "*.sav")]
        )
        if path:
            self.open_path(path)

    def open_path(self, path):
        self.work("Decoding and verifying save…", lambda: self.service.open(path), self.show_opened)

    def show_opened(self, opened):
        self.opened = opened
        self.pending = {}
        self.exported = None
        meta = opened.model.metadata()
        self.set_text(
            self.metadata_text,
            f"{meta['label'] or meta['name']}  •  {meta['type']}\n"
            f"File: {opened.path}\nUpdated UTC: {meta['updated_utc']}\n"
            f"Build: {meta['build']}  •  {'Verified editing profile' if meta['editable'] else 'INSPECT ONLY — unverified build'}\n"
            f"SHA-256: {meta['sha256']}\n"
            f"{meta['flag_count']} flags, {meta['counter_count']} counters. Both checksums valid.",
        )
        self.render_pending()
        self.populate_flags()
        self.tabs.select(self.overview)
        self.status.set("Save verified. Viewing does not change the original.")

    def selected_preset(self):
        return next(p for p in self.presets.values() if p.title == self.preset_var.get())

    def describe_preset(self):
        p = self.selected_preset()
        self.set_text(
            self.preset_text, p.description + "\n\n" + p.risk + "\n\nEvidence: " + p.evidence
        )

    def preview_preset(self):
        opened = self.require_open()
        self.pending = self.selected_preset().edits(opened.model)
        self.exported = None
        self.render_pending()
        self.status.set(
            "Preset conditions satisfied. Review the flag change, then export a separate copy."
        )

    def render_pending(self):
        self.pending_tree.delete(*self.pending_tree.get_children())
        if self.opened:
            for key, value in self.pending.items():
                self.pending_tree.insert(
                    "",
                    "end",
                    values=(key, str(self.opened.model.flags[key]).lower(), str(value).lower()),
                )
        self.populate_flags()

    def populate_flags(self):
        if not hasattr(self, "flags_tree"):
            return
        self.flags_tree.delete(*self.flags_tree.get_children())
        self.flag_rows = {}
        if not self.opened:
            return
        query = self.search_var.get().casefold()
        count = 0
        for kind, mapping in [
            ("Flag", self.opened.model.flags),
            ("Counter", self.opened.model.counters),
        ]:
            for key, value in sorted(mapping.items()):
                detail = self.descriptions.get(
                    key,
                    {
                        "status": "Unknown",
                        "description": "Meaning unverified; experimental changes may damage story state.",
                    },
                )
                if query not in f"{key} {json.dumps(value)} {kind} {detail}".casefold():
                    continue
                count += 1
                if count > 2000:
                    continue
                shown = json.dumps(value)
                if key in self.pending:
                    shown += " → " + json.dumps(self.pending[key])
                row_id = str(count)
                self.flag_rows[row_id] = (key, kind)
                self.flags_tree.insert(
                    "",
                    "end",
                    iid=row_id,
                    values=(key, shown, kind, detail["status"], detail["description"]),
                )
        if count > 2000:
            self.status.set(f"{count} matches; first 2000 shown. Narrow the search to view more.")

    def queue_selected(self, value):
        opened = self.require_open()
        selection = self.flags_tree.selection()
        if not selection:
            raise SafetyError("Select a boolean flag.")
        key, kind = self.flag_rows[selection[0]]
        if kind != "Flag":
            raise SafetyError("Counters are read-only.")
        if key not in self.descriptions and not self.experimental.get():
            raise SafetyError("Unknown meaning: acknowledge experimental editing first.")
        if not opened.model.decoded.editable:
            raise SafetyError("This build is inspect-only.")
        if opened.model.flags[key] == value:
            self.pending.pop(key, None)
        else:
            self.pending[key] = value
        self.exported = None
        self.render_pending()
        self.status.set("Flag queued. Review all changes on Overview; no file has changed.")

    def clear_pending(self):
        if self.busy:
            raise SafetyError("Wait for the current operation to finish.")
        self.pending = {}
        self.exported = None
        self.render_pending()

    def manual_backup(self):
        opened = self.require_open()
        self.work(
            "Creating verified backup…",
            lambda: self.service.backup(opened),
            lambda path: self.status.set(f"Verified backup created: {path}"),
        )

    def export_copy(self):
        opened = self.require_open()
        if not self.pending:
            raise SafetyError("Preview a preset or queue a flag first.")
        directory = default_data_directory() / "exports" / datetime.now().strftime("%Y%m%d-%H%M%S")
        directory.mkdir(parents=True, exist_ok=True)
        path = filedialog.asksaveasfilename(
            parent=self.root,
            initialdir=str(directory),
            initialfile=opened.path.name,
            defaultextension=".sav",
            filetypes=[("Patched save copy", "*.sav")],
        )
        if path:
            edits = dict(self.pending)
            experimental = self.experimental.get()
            self.work(
                "Backing up source, encoding and verifying copy…",
                lambda: self.service.export_patch(opened, edits, path, experimental=experimental),
                self.export_done,
            )

    def export_done(self, receipt):
        self.exported = Path(receipt["candidate"])
        self.status.set(
            f"Verified copy exported: {self.exported}. Original unchanged. Backup: {receipt['backup']}"
        )

    def apply_copy(self):
        opened = self.require_open()
        if not self.exported:
            raise SafetyError("Export and verify a copy first.")
        if not messagebox.askyesno(
            "Confirm ONE original replacement",
            f"Replace this original only?\n\n{opened.path}\n\n"
            f"Reviewed SHA-256:\n{opened.model.decoded.sha256}\n\n"
            "A verified backup is created first. The game must be closed. Steam Cloud settings will not change.",
            parent=self.root,
        ):
            return
        candidate = self.exported

        def apply():
            receipt = self.service.apply(opened, candidate, consent=True)
            return receipt, self.service.open(opened.path)

        def done(result):
            receipt, current = result
            self.show_opened(current)
            self.status.set(
                f"One original replaced and verified. Backup: {receipt['backup']}. Check the result in the game."
            )

        self.work("Checking the game is closed, backing up and applying…", apply, done)

    def compare_file(self):
        opened = self.require_open()
        path = filedialog.askopenfilename(
            parent=self.root, filetypes=[("Zero Parades saves", "*.sav")]
        )
        if path:

            def compare_files():
                other = self.service.open(path)
                return list(compare(opened.model.normalized(), other.model.normalized()))

            self.work("Comparing save states…", compare_files, self.show_diff)

    def show_diff(self, entries):
        self.diff_entries = entries
        self.populate_diff()
        self.tabs.select(self.diff_tab)

    def populate_diff(self):
        if not hasattr(self, "diff_tree"):
            return
        self.diff_tree.delete(*self.diff_tree.get_children())
        entries = list(
            filtered(self.diff_entries, self.diff_search.get(), self.diff_category.get())
        )
        for entry in entries[:2000]:
            self.diff_tree.insert(
                "",
                "end",
                values=(
                    entry.path,
                    entry.kind,
                    json.dumps(entry.before, ensure_ascii=False)[:500],
                    json.dumps(entry.after, ensure_ascii=False)[:500],
                ),
            )
        self.status.set(
            f"{len(entries)} differences match. Up to 2000 shown; JSON export includes all matches."
        )

    def export_diff(self):
        path = filedialog.asksaveasfilename(
            parent=self.root, defaultextension=".json", filetypes=[("Structural diff", "*.json")]
        )
        if path:
            entries = [
                e.to_dict()
                for e in filtered(
                    self.diff_entries, self.diff_search.get(), self.diff_category.get()
                )
            ]
            write_new(Path(path), json.dumps(entries, indent=2, ensure_ascii=False).encode("utf-8"))
            self.status.set("Filtered structural diff exported locally.")

    def refresh_backups(self):
        self.backup_rows = self.service.list_backups()
        self.backup_tree.delete(*self.backup_tree.get_children())
        for index, row in enumerate(self.backup_rows):
            self.backup_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(row.get("created_utc"), row.get("filename"), row.get("sha256")),
            )

    def restore_backup(self):
        selection = self.backup_tree.selection()
        if not selection:
            raise SafetyError("Select a backup first.")
        record = self.backup_rows[int(selection[0])]
        source = Path(record["source"])
        target = filedialog.askopenfilename(
            parent=self.root,
            title="Choose the ONE save to restore",
            initialdir=str(source.parent),
            initialfile=source.name,
            filetypes=[("Zero Parades saves", "*.sav")],
        )
        if not target:
            return
        if not messagebox.askyesno(
            "Confirm backup restore",
            f"Restore this backup to ONE selected file?\n\n{target}\n\nBackup SHA-256: {record['sha256']}\n\nThe current file will also be backed up. Close the game first.",
            parent=self.root,
        ):
            return
        reload_current = self.opened and self.opened.path.resolve() == Path(target).resolve()

        def restore():
            result = self.service.restore(record["directory"], target, consent=True)
            return result, self.service.open(target) if reload_current else None

        def done(payload):
            result, current = payload
            if current:
                self.show_opened(current)
            self.refresh_backups()
            self.status.set(
                f"Restore verified. Previous state backup: {result['previous_state_backup']}"
            )

        self.work("Verifying backup and restoring selected original…", restore, done)

    def close(self):
        if self.busy:
            self.status.set("Wait for the current operation to finish before closing.")
            return
        self.closed = True
        self.root.destroy()


def smoke_test(result_path=None):
    """Hidden Tk interaction test with synthetic files only; also runs when frozen."""
    import time
    from unittest.mock import patch

    with tempfile.TemporaryDirectory(prefix="savelab-smoke-") as directory:
        base = Path(directory)
        before, after = create_demo(base / "source")
        service = SaveService(base / "recovery", process_check=lambda: None)
        root = tk.Tk()
        root.withdraw()
        app = SaveLabApp(root, service, before.parent)
        app.show_saves(service.list_saves(before.parent))
        app.show_opened(service.open(before))
        app.search_var.set("reno")
        root.update_idletasks()
        assert app.flags_tree.get_children()
        app.preview_preset()
        assert app.pending == {"reno.HasRenoAskedForKibble": False}
        receipt = service.export_patch(app.opened, app.pending, base / "export/synthetic.sav")
        app.export_done(receipt)
        candidate = service.open(app.exported)
        assert candidate.model.flags["reno.HasRenoAskedForKibble"] is False
        app.show_diff(list(compare(app.opened.model.normalized(), candidate.model.normalized())))
        app.diff_category.set("flags")
        assert len(app.diff_tree.get_children()) == 1
        app.refresh_backups()
        assert len(app.backup_tree.get_children()) == 1
        original = before.read_bytes()

        def finish_worker():
            deadline = time.monotonic() + 10
            while app.busy and time.monotonic() < deadline:
                root.update()
                time.sleep(0.01)
            assert not app.busy, "GUI worker did not finish"

        with patch.object(messagebox, "askyesno", return_value=True):
            app.apply_copy()
            finish_worker()
        assert before.read_bytes() == candidate.model.decoded.raw
        app.refresh_backups()
        app.backup_tree.selection_set("0")
        with (
            patch.object(messagebox, "askyesno", return_value=True),
            patch.object(filedialog, "askopenfilename", return_value=str(before)),
        ):
            app.restore_backup()
            finish_worker()
        assert before.read_bytes() == original
        assert app.opened.model.flags["reno.HasRenoAskedForKibble"] is True
        assert app.action_bar.pack_info()["side"] == "bottom"
        app.show_opened(service.open(after))
        app.preset_var.set("Reno — Restore Historical Flag")
        app.preview_preset()
        assert app.pending == {"reno.HasRenoAskedForKibble": True}
        root.update_idletasks()
        app.close()
        result = {
            "ok": True,
            "synthetic_only": True,
            "tk_available": True,
            "save_list": True,
            "flag_search": True,
            "both_presets": True,
            "copy_export": True,
            "diff_filter": True,
            "backup_list": True,
            "confirmed_gui_apply_and_restore": True,
            "action_controls_pinned": True,
        }
    if result_path:
        write_new(Path(result_path), json.dumps(result, indent=2).encode())
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="ZeroParades-SaveLab Windows GUI")
    parser.add_argument(
        "--demo", action="store_true", help="Use synthetic saves in a temporary folder"
    )
    parser.add_argument(
        "--smoke-test", action="store_true", help="Run a hidden, synthetic GUI check"
    )
    parser.add_argument("--result", type=Path)
    args = parser.parse_args(argv)
    if args.smoke_test:
        smoke_test(args.result)
        return 0
    demo = tempfile.TemporaryDirectory(prefix="savelab-demo-") if args.demo else None
    try:
        root = tk.Tk()
        directory = None
        service = None
        if demo:
            directory = Path(demo.name) / "source"
            create_demo(directory)
            service = SaveService(Path(demo.name) / "recovery")
        app = SaveLabApp(root, service, directory)
        if Path(app.path_var.get()).is_dir():
            app.refresh()
        root.mainloop()
        return 0
    finally:
        if demo:
            demo.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
