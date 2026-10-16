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
import re
import shutil
import datetime
from PIL import Image
from PIL.ExifTags import TAGS


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp",
              ".tif", ".tiff", ".heic", ".webp", ".raw",
              ".cr2", ".nef", ".arw", ".dng"}

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".m4v",
              ".wmv", ".flv", ".webm", ".3gp", ".mpg",
              ".mpeg", ".mts", ".m2ts"}

MEDIA_EXTS = IMAGE_EXTS | VIDEO_EXTS


def get_all_exif(path):
    try:
        with Image.open(path) as img:
            exif_data = img.getexif()
            if not exif_data:
                return {}

            readable_exif = {TAGS.get(tag_id, tag_id): value
                             for tag_id, value in exif_data.items()}

            exif_ifd = exif_data.get_ifd(0x8769)
            if exif_ifd:
                readable_exif.update({TAGS.get(tag_id, tag_id): value
                                      for tag_id, value in exif_ifd.items()})

            return readable_exif
    except Exception:
        return {}


# Now accepts separators between fields:
#   20131223_102619, 2013-05-13 13.35.28, Screenshot_20201203-160650_x
_FILENAME_DATE_RE = re.compile(
    r"(?<!\d)"
    r"(\d{4})[-_./]?(\d{2})[-_./]?(\d{2})"                # YYYY[-_./]MM[-_./]DD
    r"(?:[-_T\s]?(\d{2})[:.]?(\d{2})[:.]?(\d{2}))?"       # optional HH[:.]MM[:.]SS
    r"(?!\d)"
)


def _valid_ymd(y, mo, d):
    try:
        datetime.date(int(y), int(mo), int(d))
        return 1980 <= int(y) <= 2099
    except (ValueError, TypeError):
        return False


def _valid_hms(h, mi, s):
    return 0 <= int(h) <= 23 and 0 <= int(mi) <= 59 and 0 <= int(s) <= 59


def _extract_year_month(date_str):
    """Return (year, month) from a date string, accepting both
    ISO (YYYY:MM:DD) and European (DD:MM:YYYY) orders.

    Returns None if no usable year is found.
    """
    if not date_str:
        return None

    parts = re.split(r"[:/\-.\s]+", date_str.strip())
    if len(parts) < 3:
        return None

    a, b, c = parts[0], parts[1], parts[2]

    if len(a) == 4 and a.isdigit() and 1980 <= int(a) <= 2099:
        return a, b

    if len(c) == 4 and c.isdigit() and 1980 <= int(c) <= 2099:
        if b.isdigit() and int(b) > 12 and a.isdigit() and int(a) <= 12:
            return c, a          # US order: MM:DD:YYYY
        return c, b              # European or default

    return None


def get_date_from_filename(path):
    """Best-effort date extraction from the filename.

    Handles the common camera / messenger patterns:
        Screenshot_20201203-160650_Firefox.jpg   -> 2020:12:03 16:06:50
        IMG-20230326-WA0002.jpg                  -> 2023:03:26
        IMG20221123225915.jpg                    -> 2022:11:23 22:59:15
        VID20221225104422.mp4                    -> 2022:12:25 10:44:22
        2013-05-13 13.35.28.png                  -> 2013:05:13 13:35:28
        VID-20131223-WA0003.mp4                  -> 2013:12:23

    Returns 'YYYY:MM:DD HH:MM:SS', 'YYYY:MM:DD', or None.
    """
    name = os.path.splitext(os.path.basename(path))[0]

    for m in _FILENAME_DATE_RE.finditer(name):
        y, mo, d, h, mi, s = m.groups()
        if not _valid_ymd(y, mo, d):
            continue
        if h is None:
            return f"{y}:{mo}:{d}"
        if _valid_hms(h, mi, s):
            return f"{y}:{mo}:{d} {h}:{mi}:{s}"
        return f"{y}:{mo}:{d}"

    return None


def get_video_date(path):
    """Return the recording date of a video as 'YYYY:MM:DD HH:MM:SS',
    or None if it can't be determined."""
    try:
        from hachoir.parser import createParser
        from hachoir.metadata import extractMetadata
    except ImportError:
        print("WARNING: hachoir is not installed - video dates will be skipped. "
              "Install it with: pip install hachoir")
        return None

    try:
        parser = createParser(path)
        if not parser:
            return None

        metadata = extractMetadata(parser)
        if not metadata:
            return None

        for key in ("creation_date", "date", "datetime_original"):
            value = metadata.get(key)
            if value is None:
                continue
            if hasattr(value, "strftime"):
                return value.strftime("%Y:%m:%d %H:%M:%S")
            return str(value)
        return None
    except Exception:
        return None


def get_date(path):
    """Return a date string ('YYYY:MM:DD ...' / 'YYYY:MM') or None.

    Lookup order:
      1. EXIF (images) or container metadata (videos)
      2. Filename pattern
      3. None  ->  lands in the 'Unknown Date' folder
    """
    ext = os.path.splitext(path)[1].lower()

    # --- 1. embedded metadata ---
    if ext in VIDEO_EXTS:
        date = get_video_date(path)
    else:
        exif_dict = get_all_exif(path)
        date = None
        for key in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
            value = exif_dict.get(key)
            if value and isinstance(value, str) and not value.startswith("0000"):
                date = value
                break

    # Only trust the metadata date if we can actually turn it into a year/month.
    if date and _extract_year_month(date):
        return date

    # --- 2. filename fallback ---
    return get_date_from_filename(path)


def move_photo(source_path, date_str, base_destination, mode="move"):
    """Transfer a photo/video into a date-based folder.

    mode="move" -> original is removed from the source (default).
    mode="copy" -> original is left in place.
    Metadata (EXIF, mtime, permissions) is preserved in both modes.

    Files with no usable date go into <base_destination>/Unknown Date/.
    """
    ym = _extract_year_month(date_str)
    if ym is None:
        target_dir = os.path.join(base_destination, "Unknown Date")
    else:
        year, month = ym
        target_dir = os.path.join(base_destination, year, month)

    os.makedirs(target_dir, exist_ok=True)

    file_name = os.path.basename(source_path)
    name, ext = os.path.splitext(file_name)
    final_path = os.path.join(target_dir, file_name)

    counter = 1
    while os.path.exists(final_path):
        new_name = f"{name}_{counter}{ext}"
        final_path = os.path.join(target_dir, new_name)
        counter += 1

    try:
        if mode == "copy":
            shutil.copy2(source_path, final_path)
            print(f"Copied: {os.path.basename(final_path)} -> {target_dir}")
        else:
            shutil.move(source_path, final_path)
            print(f"Moved: {os.path.basename(final_path)} -> {target_dir}")
    except FileNotFoundError:
        print("Source file not found")
        raise
    except Exception as e:
        print(f"An error occurred: {e}")
        raise