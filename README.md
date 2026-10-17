# 📸 Easy PhotoSort

> **This is a fork.** The original project was written by **[Jan Slaný](https://github.com/slanja/PhotoSort)** — a simple Tkinter GUI for sorting photos into year/month folders by EXIF date. This fork keeps the original idea and interface but adds video support, recursive scanning, Move/Copy modes, filename-based date recovery, a progress bar, and other quality-of-life improvements. See [What changed in this fork](#-what-changed-in-this-fork) for the full list.

## 📄 License

Licensed under the Apache License, Version 2.0 — see [LICENSE](LICENSE) for details.

This is a fork of [Jan Slaný's PhotoSort](https://github.com/slanja/PhotoSort), also licensed under Apache 2.0.

Simple Python GUI app for sorting photos **and videos** into folders by year and month.

<div align="left">
  <img src="assets/preview.png" alt="<3" height="300" />
</div>

[![python](https://img.shields.io/badge/Python-3.9+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org)

## 📂Table of contents

- [Introduction](#introduction)
- [What changed in this fork](#-what-changed-in-this-fork)
- [Getting started](#-getting-started)
- [Usage](#usage)
- [Technical details](#technical-details)
- [Project structure](#-project-structure)
- [Building a standalone .exe](#-building-a-standalone-exe)
- [Goals](#goals)

## 📑Introduction

I wrote this application to solve my problem with unorganized folders full of photos and videos all over my laptop. It wouldn't be much of an issue — but sometimes I just want to look at old photos, which was difficult with that kind of organization. Then I was going through photos that my parents took. They were all organized in folders by year and month. That gave me the idea to write a Python script to sort my photos the same way.

## 🔀 What changed in this fork

The original PhotoSort by Jan Slaný selected individual files, sorted them by EXIF date, and moved them into `YYYY/MM/` folders. This fork builds on that but expands the scope considerably. Everything below is new or changed relative to the upstream project.

### Sorting behavior

- **Video support.** MP4, MOV, MKV, AVI, M4V, WMV, FLV, WEBM, 3GP, MPG, MPEG, MTS, M2TS. Videos don't have EXIF, so the fork reads their container metadata (`mvhd` atom / QuickTime `©day` tag) using the `hachoir` library.
- **Recursive folder scan.** Point it at a top-level folder and it will walk every subfolder with `os.walk`. The original only handled the files you manually selected.
- **Move / Copy toggle.** The user now chooses whether originals are removed (Move) or left in place (Copy). Both modes preserve metadata; the move path uses `shutil.move` so it also works across Windows drives, where the original's `os.replace` would fail.
- **Folder-based source selection.** Instead of picking individual files, you pick a source folder and a destination folder.

### Date detection

- **Filename fallback.** When EXIF and container metadata are both empty, the app tries to recover the date from the filename. Recognized patterns include `Screenshot_20201203-160650_…`, `IMG-20230326-WA0002`, `IMG20221123225915`, `VID20221225104422`, and `2013-05-13 13.35.28`. Every candidate is validated against `datetime.date` and a year range of 1980–2099, so random numeric IDs can't be misread as dates.
- **Non-standard EXIF handling.** Some cameras write dates in `DD:MM:YYYY` order instead of `YYYY:MM:DD`. The fork detects both and always produces the correct `YYYY/MM/` folder.
- **No mtime fallback.** The original used the file's modification timestamp when no EXIF was found. This fork deliberately removed that — a download date isn't a capture date, and mislabeled photos are worse than honestly-labeled unknown ones. Files with no recoverable date go to `Unknown Date/`.

### Interface

- **Progress bar.** Shows `N / total` and the current filename while sorting.
- **Background worker thread.** The GUI stays responsive; the original blocked until every file was processed.
- **Persistent settings.** Source folder, destination folder, and Move/Copy choice are saved to `~/.photosort.json` and restored on next launch. File dialogs also open in the last-used folder.
- **"Unknown Date" folder.** Renamed from the original's `Unknown` to make its meaning clearer.

### Packaging / workflow

- **`run.bat`.** One-click launcher that creates a virtual environment, installs dependencies, and starts the app.
- **`build_exe.bat`.** Optional PyInstaller build that produces a standalone `PhotoSort.exe` for machines without Python.

### What is unchanged from upstream

- The Tkinter GUI framework and overall layout.
- The core idea: read the date, create `YYYY/MM/` folders, move files there.
- EXIF priority order for images: `DateTimeOriginal` → `DateTimeDigitized` → `DateTime`.
- Duplicate filename handling: `image.jpg` → `image_1.jpg` → `image_2.jpg` so nothing is overwritten.

### Credit

All original design and code by **Jan Slaný** ([@slanja](https://github.com/slanja)). This fork is maintained separately.

## 🚀 Getting Started

### Quick launch (Windows)

Double-click **`run.bat`** in the project folder. On the first run it will:

1. Create a virtual environment in `.venv/`
2. Install the dependencies from `requirements.txt`
3. Launch the app

Every subsequent launch starts the app in about a second. If you ever add a package to `requirements.txt`, delete `.venv\.installed` (or the whole `.venv` folder) and launch again to force a reinstall.

### Manual installation

1. Clone this fork:

   ```bash
   git clone <your-fork-url>
   cd PhotoSort
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Run the application **from the project root** (the folder containing `logic/` and `ui/`):

   ```bash
   python -m ui.window
   ```

> The `-m` form is important. Running `python ui/window.py` from inside `ui/` will fail with `ModuleNotFoundError: No module named 'logic'` because Python can't see the sibling `logic/` folder.

### Dependencies

| Package | Purpose |
| --- | --- |
| `pillow` | EXIF metadata for images |
| `hachoir` | Container metadata (creation time) for videos |

## ⚙️Usage

1. Click **Browse Source Folder** and pick the folder that contains the photos/videos you want to sort. Subfolders are scanned recursively.
2. Pick a **destination folder** with the 📁 button.
3. Choose **Move** (default — original is removed) or **Copy** (original is kept).
4. Click **Sort**. A progress bar shows how many files have been processed and which file is currently being handled.

The app remembers the last used source folder, destination folder, and Move/Copy choice between sessions, so you can just hit **Sort** next time.

<div align="left">
  <img src="assets/sort_1.png" alt="<3" height="300" />
</div>

### Where the settings live

The remembered settings are stored in a small JSON file at `%USERPROFILE%\.photosort.json` (Windows) or `~/.photosort.json` (macOS/Linux). Delete it to reset the app to defaults.

## 🛠️ Technical Details

The main challenge was figuring out the exact date a photo or video was taken. Different formats store this in completely different places, so the app tries several sources in priority order.

### Date lookup order

1. **EXIF (images).** Pillow reads the EXIF block. The app checks `DateTimeOriginal`, then `DateTimeDigitized`, then `DateTime` — this is the same priority every photo tool uses.
2. **Container metadata (videos).** MP4/MOV/MKV files don't have EXIF. The app uses `hachoir` to read the container's creation timestamp (the `mvhd` atom for MP4, `©day` tag for QuickTime, and so on).
3. **Filename pattern.** Many cameras and chat apps embed the date in the filename. The app recognizes:
   - `Screenshot_20201203-160650_Firefox.jpg` → `2020:12:03 16:06:50`
   - `IMG-20230326-WA0002.jpg` → `2023:03:26`
   - `IMG20221123225915.jpg` → `2022:11:23 22:59:15`
   - `VID20221225104422.mp4` → `2022:12:25 10:44:22`
   - `2013-05-13 13.35.28.png` → `2013:05:13 13:35:28`

   The parser validates every candidate against the real calendar (`datetime.date`) and a sane year range (1980–2099), so random ID numbers can't be misread as dates.
4. **Unknown Date.** Files where nothing above yields a date go into `<destination>/Unknown Date/`.

### Other details

- **Non-standard EXIF.** A few cameras write dates in `DD:MM:YYYY` order instead of the ISO `YYYY:MM:DD`. The app detects both and always produces the correct `YYYY/MM/` folder — no more files landing in `\25\05\...` by mistake.
- **Smart folders.** The app creates the folder structure on demand, e.g. `<destination>/2023/10/` for an October 2023 photo.
- **Configurable name conflicts.** You can choose **Rename** (default) to keep both files (`image.jpg` → `image_1.jpg` → `image_2.jpg` …), or **Overwrite** to replace an existing destination file with the incoming one when the filenames match.
- **Move vs Copy.** In **Move** mode the original file is removed from the source (uses `shutil.move`, which handles cross-drive moves on Windows). In **Copy** mode the original stays put. Both modes preserve EXIF, timestamps, and permissions.
- **Empty-folder cleanup.** In Move mode, empty subfolders left behind in the source tree are removed automatically.
- **Recursive scan.** Nested folders are walked with `os.walk`; you can point the app at a top-level "Photos" folder and it will find everything underneath.
- **Background thread.** Sorting runs on a worker thread so the GUI stays responsive while the progress bar updates.

## 📁 Project structure

```
PhotoSort/
├── logic/
│   └── sorter.py         # date lookup + file transfer logic
├── ui/
│   └── window.py         # Tkinter GUI
├── assets/               # screenshots for this README
├── requirements.txt      # pillow, hachoir
├── run.bat               # one-click launcher (Windows)
├── build_exe.bat         # optional: builds a standalone .exe
└── README.md
```

## 📦 Building a standalone .exe

If you want to give PhotoSort to someone who doesn't have Python installed, you can build a single-file Windows executable with PyInstaller.

1. Make sure `run.bat` has been run at least once (it creates the `.venv`).
2. Double-click **`build_exe.bat`**. It will:
   - Install PyInstaller into the virtual environment
   - Bundle `window.py`, `logic/sorter.py`, Pillow, and hachoir into one file
3. The result is `dist\PhotoSort.exe`. Copy it anywhere — it needs no Python, no pip, no virtual environment.

The exe is around 30–50 MB because it bundles Pillow and hachoir, and the very first launch takes a few seconds while it unpacks itself. After that it opens instantly.

## 🎯Goals

- ~~add progress bar~~
- ~~recursive folder scan~~
- ~~move / copy toggle~~
- ~~remember last used folders and mode~~
- ~~support video files~~
- ~~filename-based date fallback~~
- drag and drop
- test and debug

---

<p align="center">
Original project by <a href="https://github.com/slanja">Jan Slaný</a> 🧂<br>
Fork maintained separately.
</p>