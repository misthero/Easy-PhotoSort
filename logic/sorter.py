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
import hashlib
from PIL import Image
from PIL.ExifTags import TAGS


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp",
              ".tif", ".tiff", ".heic", ".webp", ".raw",
              ".cr2", ".nef", ".arw", ".dng"}

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".m4v",
              ".wmv", ".flv", ".webm", ".3gp", ".mpg",
              ".mpeg", ".mts", ".m2ts"}

MEDIA_EXTS = IMAGE_EXTS | VIDEO_EXTS

try:
    import piexif
except ImportError:
    piexif = None


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


# Accepts separators between fields:
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
            value = _normalize_metadata_value(metadata.get(key))
            if value and _extract_year_month(value):
                return value
        return None
    except Exception:
        return None


def get_date(path, return_source=False):
    """Return a date string ('YYYY:MM:DD ...' / 'YYYY:MM') or None.

    Lookup order:
      1. EXIF (images) or container metadata (videos)
      2. Filename pattern
      3. None  ->  lands in the 'Unknown Date' folder

    If return_source is True, also returns one of:
      'metadata'  - EXIF / container date found
      'filename'  - date recovered from the filename
      None        - no date anywhere
    """
    ext = os.path.splitext(path)[1].lower()

    if ext in VIDEO_EXTS:
        date = get_video_date(path)
    else:
        exif_dict = get_all_exif(path)
        date = None
        for key in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
            value = _normalize_metadata_value(exif_dict.get(key))
            if value and not value.startswith("0000"):
                date = value
                break

    if date and _extract_year_month(date):
        return (date, "metadata") if return_source else date

    from_filename = get_date_from_filename(path)
    if from_filename:
        return (from_filename, "filename") if return_source else from_filename

    return (None, None) if return_source else None


def _to_exif_datetime(date_str):
    """Convert 'YYYY:MM:DD' or 'YYYY:MM:DD HH:MM:SS' to full EXIF form.
    EXIF always wants 'YYYY:MM:DD HH:MM:SS', so date-only gets 00:00:00."""
    if not date_str:
        return None
    parts = date_str.strip().split(" ")
    if len(parts) >= 2:
        return date_str
    return f"{parts[0]} 00:00:00"


def write_exif_date(path, date_str):
    """Write DateTimeOriginal / DateTimeDigitized / DateTime into a file.

    Only JPEG, WebP, and TIFF can be tagged with piexif. Other formats
    are silently skipped (returns False).
    """
    if piexif is None:
        print("WARNING: piexif not installed - cannot write EXIF dates. "
              "Install it with: pip install piexif")
        return False

    ext = os.path.splitext(path)[1].lower()
    if ext not in {".jpg", ".jpeg", ".webp", ".tif", ".tiff"}:
        return False

    exif_datetime = _to_exif_datetime(date_str)
    if not exif_datetime:
        return False

    try:
        try:
            exif_dict = piexif.load(path)
        except Exception:
            # File has no EXIF block yet - build one from scratch
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "Interop": {}, "1st": {}}

        exif_dict.setdefault("0th", {})[piexif.ImageIFD.DateTime] = exif_datetime
        exif_dict.setdefault("Exif", {})[piexif.ExifIFD.DateTimeOriginal] = exif_datetime
        exif_dict.setdefault("Exif", {})[piexif.ExifIFD.DateTimeDigitized] = exif_datetime

        piexif.insert(piexif.dump(exif_dict), path)
        return True
    except Exception as e:
        print(f"Could not write EXIF to {path}: {e}")
        return False


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def _file_hash(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _normalize_metadata_value(value):
    """Coerce EXIF/container metadata values into a clean string."""
    if value is None:
        return None
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8", "replace")
        except Exception:
            return None
    elif hasattr(value, "strftime"):
        try:
            return value.strftime("%Y:%m:%d %H:%M:%S")
        except Exception:
            return None
    value = str(value).strip("\x00").strip()
    return value or None


def _normalize_exif_datetime(value):
    """Strip trailing NULs and whitespace that PIL/piexif sometimes leave."""
    return _normalize_metadata_value(value)


def _file_has_exif_datetime(path, expected):
    """True if `path` has an EXIF DateTimeOriginal equal to `expected`."""
    try:
        exif_dict = get_all_exif(path)
    except Exception:
        return False
    value = _normalize_exif_datetime(exif_dict.get("DateTimeOriginal"))
    if not value:
        return False
    return value == expected


class DestinationIndex:
    """In-memory snapshot of files already in the destination tree.

    Built once per sort. The eager scan only does `os.path.getsize` (fast
    stat calls) and buckets files by size; hashing is done lazily, only for
    same-size candidates. A source file is only hashed if the destination
    already contains a file of the same size.
    """

    def __init__(self, base_destination):
        self.base = base_destination
        self.by_size = {}    # size -> [paths]
        self.by_name = {}    # lowercase basename -> [paths]
        self.hash_by_path = {}  # lazily populated for destination candidates
        if os.path.isdir(base_destination):
            for root, _, files in os.walk(base_destination):
                for f in files:
                    self._register(os.path.join(root, f))

    def _register(self, path):
        try:
            size = os.path.getsize(path)
        except OSError:
            return
        name = os.path.basename(path).lower()
        self.by_size.setdefault(size, []).append(path)
        self.by_name.setdefault(name, []).append(path)

    def _unregister(self, path):
        for bucket_size in list(self.by_size.keys()):
            paths = self.by_size[bucket_size]
            self.by_size[bucket_size] = [p for p in paths if p != path]
            if not self.by_size[bucket_size]:
                del self.by_size[bucket_size]

        name = os.path.basename(path).lower()
        named = self.by_name.get(name)
        if named:
            self.by_name[name] = [p for p in named if p != path]
            if not self.by_name[name]:
                del self.by_name[name]

        self.hash_by_path.pop(path, None)

    def add(self, path):
        """Register a newly-written file so later checks see it."""
        self._register(path)

    def replace(self, path):
        """Refresh index state for a path whose content was overwritten."""
        self._unregister(path)
        self._register(path)

    def _destination_hash(self, path):
        cached = self.hash_by_path.get(path)
        if cached:
            return cached
        try:
            hashed = _file_hash(path)
        except OSError:
            return None
        self.hash_by_path[path] = hashed
        return hashed

    def find_by_content(self, path):
        """Return the path of an identical file in the destination, or None."""
        try:
            size = os.path.getsize(path)
        except OSError:
            return None

        candidates = self.by_size.get(size)
        if not candidates:
            return None

        try:
            src_hash = _file_hash(path)
        except OSError:
            return None

        for candidate in candidates:
            candidate_hash = self._destination_hash(candidate)
            if candidate_hash and candidate_hash == src_hash:
                return candidate
        return None

    def find_by_name(self, name):
        return self.by_name.get(name.lower(), [])


def _skip_duplicate(source_path, existing_path, mode):
    """Log a duplicate; in move mode remove the now-redundant source."""
    print(f"Duplicate skipped: {source_path}  ==  {existing_path}")
    if mode == "move":
        try:
            os.remove(source_path)
        except OSError as e:
            print(f"  Could not remove redundant source: {e}")


def _replace_temp_path(path):
    base = f"{path}.photosort_tmp"
    candidate = base
    suffix = 1
    while os.path.exists(candidate):
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def move_photo(source_path, date_str, base_destination, mode="move",
               write_exif_from_filename=False, dest_index=None,
               date_source=None, overwrite_same_name=False):
    """Transfer a photo/video into a date-based folder.

    mode="move" -> original is removed from the source (default).
    mode="copy" -> original is left in place.
    write_exif_from_filename=True + mode="copy":
        if the date was recovered from the filename, the copy gets EXIF
        DateTimeOriginal written into it so future runs see real EXIF.
    overwrite_same_name=True:
        if destination already has the same filename, replace it.
        False (default): preserve existing file by renaming incoming one.
    dest_index: DestinationIndex built once per sort. Pass it in to get
        near-O(1) duplicate checks instead of walking the destination
        tree on every call.
    date_source: 'metadata' or 'filename' (from get_date with
        return_source=True). Used to detect copies we tagged earlier.

    Returns one of: 'moved', 'copied', 'overwritten', 'duplicate_skipped'.

    Metadata (EXIF, mtime, permissions) is preserved in both modes.
    Files with no usable date go into <base_destination>/Unknown Date/.
    """
    # --- Compute target folder ----------------------------------------------
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

    overwrite_existing = overwrite_same_name and os.path.exists(final_path)

    # --- Duplicate detection -------------------------------------------------
    # If overwrite mode is active and the exact target filename exists, prefer
    # an explicit overwrite over duplicate short-circuiting so UI behavior
    # matches user intent.
    if dest_index is not None and not overwrite_existing:
        # 1. Exact content match.
        content_dup = dest_index.find_by_content(source_path)
        if content_dup:
            _skip_duplicate(source_path, content_dup, mode)
            return "duplicate_skipped"

        # 2. Filename-fallback files that we already tagged in a prior run.
        #    Once write_exif_date() has run, the copy's bytes no longer match
        #    the source, so the content check can't find it. Fall back to
        #    name + EXIF match instead.
        if date_source == "filename" and date_str:
            expected = _to_exif_datetime(date_str)
            for candidate in dest_index.find_by_name(file_name):
                if _file_has_exif_datetime(candidate, expected):
                    _skip_duplicate(source_path, candidate, mode)
                    return "duplicate_skipped"

    if not overwrite_same_name:
        counter = 1
        while os.path.exists(final_path):
            new_name = f"{name}_{counter}{ext}"
            final_path = os.path.join(target_dir, new_name)
            counter += 1

    # --- Transfer ------------------------------------------------------------
    try:
        if mode == "copy":
            if overwrite_existing:
                temp_path = _replace_temp_path(final_path)
                try:
                    shutil.copy2(source_path, temp_path)
                    if write_exif_from_filename and date_source == "filename":
                        if write_exif_date(temp_path, date_str):
                            print(f"  EXIF date written: {_to_exif_datetime(date_str)}")
                    os.replace(temp_path, final_path)
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                print(f"Overwritten: {os.path.basename(final_path)} -> {target_dir}")
                if dest_index is not None:
                    dest_index.replace(final_path)
                return "overwritten"
            else:
                shutil.copy2(source_path, final_path)
                print(f"Copied: {os.path.basename(final_path)} -> {target_dir}")
                if write_exif_from_filename and date_source == "filename":
                    if write_exif_date(final_path, date_str):
                        print(f"  EXIF date written: {_to_exif_datetime(date_str)}")
                if dest_index is not None:
                    dest_index.add(final_path)
                return "copied"
        else:
            if overwrite_existing:
                try:
                    os.replace(source_path, final_path)
                except OSError:
                    temp_path = _replace_temp_path(final_path)
                    try:
                        shutil.copy2(source_path, temp_path)
                        os.replace(temp_path, final_path)
                        os.remove(source_path)
                    finally:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                print(f"Overwritten: {os.path.basename(final_path)} -> {target_dir}")
                if dest_index is not None:
                    dest_index.replace(final_path)
                return "overwritten"
            else:
                shutil.move(source_path, final_path)
                print(f"Moved: {os.path.basename(final_path)} -> {target_dir}")
                if dest_index is not None:
                    dest_index.add(final_path)
                return "moved"
    except FileNotFoundError:
        print("Source file not found")
        raise
    except Exception as e:
        print(f"An error occurred: {e}")
        raise