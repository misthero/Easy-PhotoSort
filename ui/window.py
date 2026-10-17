# This file is part of PhotoSort (fork).
#
# Original work Copyright (c) Jan Slaný
#   https://github.com/slanja/PhotoSort
# Licensed under the Apache License, Version 2.0.
#
# Modifications Copyright (c) misthero, 2026.
# This file has been substantially modified from the original.
# See the "What changed in this fork" section in README.md for details.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
import json
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logic.sorter import DestinationIndex, get_date, move_photo, MEDIA_EXTS


# Where settings live. Stored under the user's home directory so the
# file survives repo moves and doesn't clutter git status.
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".photosort.json")


def load_config():
    """Return the saved settings dict, or {} if none / unreadable."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except OSError as e:
        print(f"Could not save settings: {e}")


class PhotoSorterApp:
    PROGRESS_UPDATE_EVERY = 10
    NAME_CONFLICT_POLICIES = ("rename", "overwrite")

    def __init__(self, root):
        self.root = root
        self.root.title("PhotoSort")
        self.root.geometry("500x520")
        self.root.configure(bg="#f0f2f5")

        # Load persisted state up front
        self.config = load_config()
        self.source_folder = self.config.get("source_folder", "")
        self.destination_folder = self.config.get("destination_folder", "")
        saved_mode = self.config.get("mode", "move")
        if saved_mode not in ("move", "copy"):
            saved_mode = "move"
        saved_conflict_policy = self.config.get("name_conflict_policy", "rename")
        if saved_conflict_policy not in self.NAME_CONFLICT_POLICIES:
            saved_conflict_policy = "rename"

        self.init_ui(saved_mode, saved_conflict_policy)

        # Restore the UI from the loaded config
        self._restore_from_config()

        # Persist on close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def init_ui(self, initial_mode, initial_name_conflict_policy):
        tk.Label(self.root, text="Photo Sort", font=("Arial", 18, "bold"),
                 bg="#f0f2f5").pack(pady=10)

        self.file_frame = tk.Frame(self.root, bd=2, relief="groove", bg="white")
        self.file_frame.pack(pady=20, padx=40, fill="both", expand=True)

        self.file_label = tk.Label(self.file_frame, text="No source folder selected",
                                   bg="white", fg="#666", wraplength=380, justify="center")
        self.file_label.pack(pady=20)

        tk.Button(self.file_frame, text="Browse Source Folder",
                  command=self.browse_source,
                  bg="#007bff", fg="white", font=("Arial", 10, "bold"),
                  padx=10).pack(pady=10)

        # ---- Move / Copy selector ----
        mode_frame = tk.Frame(self.file_frame, bg="white")
        mode_frame.pack(pady=(5, 15))

        tk.Label(mode_frame, text="Action:", bg="white", fg="#666").pack(
            side="left", padx=(0, 8))

        self.mode_var = tk.StringVar(value=initial_mode)
        tk.Radiobutton(mode_frame, text="Move", variable=self.mode_var,
                       value="move", bg="white", fg="#333",
                       selectcolor="white", activebackground="white",
                       command=self._save_state).pack(side="left")
        tk.Radiobutton(mode_frame, text="Copy", variable=self.mode_var,
                       value="copy", bg="white", fg="#333",
                       selectcolor="white", activebackground="white",
                       command=self._save_state).pack(side="left", padx=(8, 0))

        # ---- Name conflict selector ----
        conflict_frame = tk.Frame(self.file_frame, bg="white")
        conflict_frame.pack(pady=(0, 15))

        tk.Label(conflict_frame, text="If same filename exists:", bg="white",
                 fg="#666").pack(side="left", padx=(0, 8))

        self.name_conflict_policy_var = tk.StringVar(
            value=initial_name_conflict_policy
        )
        tk.Radiobutton(conflict_frame, text="Rename", variable=self.name_conflict_policy_var,
                       value="rename", bg="white", fg="#333",
                       selectcolor="white", activebackground="white",
                       command=self._save_state).pack(side="left")
        tk.Radiobutton(conflict_frame, text="Overwrite", variable=self.name_conflict_policy_var,
                       value="overwrite", bg="white", fg="#333",
                       selectcolor="white", activebackground="white",
                       command=self._save_state).pack(side="left", padx=(8, 0))

        # ---- progress bar ----
        progress_frame = tk.Frame(self.file_frame, bg="white")
        progress_frame.pack(fill="x", padx=20, pady=(0, 15))

        self.progress = ttk.Progressbar(progress_frame, orient="horizontal",
                                        mode="determinate", length=380)
        self.progress.pack(fill="x")

        self.progress_label = tk.Label(progress_frame, text="", bg="white",
                                       fg="#666", font=("Arial", 9))
        self.progress_label.pack(pady=(4, 0))

        # ---- bottom bar ----
        bottom_frame = tk.Frame(self.root, bg="#f0f2f5")
        bottom_frame.pack(side="bottom", fill="x", padx=20, pady=20)

        self.dest_label = tk.Entry(bottom_frame, fg="#666")
        self.dest_label.insert(0, "Select Destination Folder")
        self.dest_label.config(state="readonly")
        self.dest_label.pack(side="left", fill="x", expand=True, padx=(0, 10))

        tk.Button(bottom_frame, text="📁", command=self.select_folder).pack(
            side="left", padx=(0, 10))

        self.sort_btn = tk.Button(bottom_frame, text="Sort", command=self.start_sort,
                                  bg="#28a745", fg="white",
                                  font=("Arial", 10, "bold"), padx=15)
        self.sort_btn.pack(side="right")

    # ---------- persistence ----------
    def _restore_from_config(self):
        """Repopulate UI fields from self.config after widgets exist."""
        if self.source_folder and os.path.isdir(self.source_folder):
            count = self._count_images(self.source_folder)
            self.file_label.config(
                text=f"Source: {self.source_folder}\n"
                     f"{count} media file(s) found (recursive)")
        else:
            self.source_folder = ""

        if self.destination_folder and os.path.isdir(self.destination_folder):
            self._set_dest_entry(self.destination_folder)
        else:
            self.destination_folder = ""

    def _save_state(self):
        save_config({
            "source_folder": self.source_folder,
            "destination_folder": self.destination_folder,
            "mode": self.mode_var.get(),
            "name_conflict_policy": self.name_conflict_policy_var.get(),
        })

    @staticmethod
    def _paths_conflict(source, destination):
        if not source or not destination:
            return False

        src = os.path.abspath(source)
        dst = os.path.abspath(destination)
        if src == dst:
            return True

        try:
            common = os.path.commonpath([src, dst])
        except ValueError:
            return False

        return common == src or common == dst

    def _set_dest_entry(self, folder):
        self.dest_label.config(state="normal")
        self.dest_label.delete(0, tk.END)
        self.dest_label.insert(0, folder)
        self.dest_label.config(state="readonly")

    def _on_close(self):
        self._save_state()
        self.root.destroy()

    # ---------- pickers ----------
    def browse_source(self):
        # Start the dialog in the last-used source folder if we have one.
        initial = self.source_folder if os.path.isdir(self.source_folder) else None
        folder = filedialog.askdirectory(title="Select Source Folder",
                                         initialdir=initial)
        if not folder:
            return
        self.source_folder = folder
        count = self._count_images(folder)
        self.file_label.config(
            text=f"Source: {folder}\n{count} media file(s) found (recursive)")
        self._save_state()

    def select_folder(self):
        initial = self.destination_folder if os.path.isdir(self.destination_folder) else None
        folder = filedialog.askdirectory(title="Select Destination Folder",
                                         initialdir=initial)
        if folder:
            self.destination_folder = folder
            self._set_dest_entry(folder)
            self._save_state()

    # ---------- helpers ----------
    @staticmethod
    def _is_media_file(name):
        return os.path.splitext(name)[1].lower() in MEDIA_EXTS

    def _iter_media_files(self, root_folder):
        for dirpath, _, filenames in os.walk(root_folder):
            for name in filenames:
                if self._is_media_file(name):
                    yield os.path.join(dirpath, name)

    def _collect_media_files(self, folder):
        return list(self._iter_media_files(folder))

    def _count_media_files(self, folder):
        return sum(1 for _ in self._iter_media_files(folder))

    def _count_images(self, folder):
        return self._count_media_files(folder)

    @staticmethod
    def _prune_empty_dirs(root_dir):
        for dirpath, _, _ in os.walk(root_dir, topdown=False):
            if os.path.abspath(dirpath) == os.path.abspath(root_dir):
                continue
            try:
                os.rmdir(dirpath)
            except OSError:
                pass

    # ---------- progress helpers ----------
    def _reset_progress(self):
        self.progress["value"] = 0
        self.progress["maximum"] = 100
        self.progress_label.config(text="")

    def _set_progress(self, done, total, current_name=""):
        def update():
            self.progress["maximum"] = total
            self.progress["value"] = done
            if current_name:
                self.progress_label.config(
                    text=f"{done} / {total}  —  {current_name}")
            else:
                self.progress_label.config(text=f"{done} / {total}")
        self.root.after(0, update)

    # ---------- run ----------
    def start_sort(self):
        if not self.source_folder:
            messagebox.showwarning("Warning", "Please select a source folder!")
            return
        if not self.destination_folder:
            messagebox.showwarning("Warning", "Please select a destination folder!")
            return
        if self._paths_conflict(self.source_folder, self.destination_folder):
            messagebox.showwarning(
                "Warning",
                "Source and destination folders must be different and not overlap!"
            )
            return
        if self.name_conflict_policy_var.get() == "overwrite":
            proceed = messagebox.askyesno(
                "Confirm overwrite",
                "Overwrite mode is enabled.\n\n"
                "Files in the destination with the same filename will be replaced.\n"
                "This cannot be undone.\n\n"
                "Do you want to continue?"
            )
            if not proceed:
                return

        self.sort_btn.config(state="disabled")
        self._reset_progress()
        self.progress_label.config(text="Scanning…")
        threading.Thread(target=self._run_sort, daemon=True).start()

    def _run_sort(self):
        src = self.source_folder
        dst = self.destination_folder
        mode = self.mode_var.get()
        name_conflict_policy = self.name_conflict_policy_var.get()

        files = self._collect_media_files(src)

        total = len(files)
        if total == 0:
            self.root.after(0, lambda: messagebox.showinfo(
                "Nothing to do", "No media files found in the source folder."))
            self.root.after(0, lambda: self.sort_btn.config(state="normal"))
            self.root.after(0, self._reset_progress)
            return

        self._set_progress(0, total)

        dest_index = DestinationIndex(dst)

        done, failed, overwritten = 0, 0, 0
        for i, path in enumerate(files, start=1):
            name = os.path.basename(path)
            should_update = (
                i == 1
                or i == total
                or i % self.PROGRESS_UPDATE_EVERY == 0
            )
            if should_update:
                self._set_progress(i - 1, total, name)
            try:
                date, date_source = get_date(path, return_source=True)
                result = move_photo(
                    path,
                    date,
                    dst,
                    mode=mode,
                    overwrite_same_name=(name_conflict_policy == "overwrite"),
                    write_exif_from_filename=(mode == "copy" and date_source == "filename"),
                    dest_index=dest_index,
                    date_source=date_source,
                )
                if result == "overwritten":
                    overwritten += 1
                done += 1
            except Exception as e:
                failed += 1
                print(f"Failed on {path}: {e}")
            if should_update:
                self._set_progress(i, total, name)

        if mode == "move":
            self._prune_empty_dirs(src)

        self.root.after(0, lambda: self._on_done(done, failed, overwritten, mode, total))

    def _on_done(self, done, failed, overwritten, mode, total):
        verb = "Copied" if mode == "copy" else "Moved"
        details = f"Photos sorted!\n{verb}: {done}\nFailed: {failed}"
        if overwritten:
            details += f"\nOverwritten: {overwritten}"
        messagebox.showinfo(
            "Success",
            details
        )
        self.progress_label.config(text=f"Done — {done} / {total}")
        if self.source_folder and os.path.isdir(self.source_folder):
            remaining = self._count_images(self.source_folder)
            self.file_label.config(
                text=f"Source: {self.source_folder}\n"
                     f"{remaining} media file(s) found (recursive)")
        else:
            self.source_folder = ""
            self.file_label.config(text="No source folder selected")
        self.sort_btn.config(state="normal")
        self._save_state()


if __name__ == "__main__":
    root = tk.Tk()
    app = PhotoSorterApp(root)
    root.mainloop()