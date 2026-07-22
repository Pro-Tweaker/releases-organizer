#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import os
import re
import shutil
import sys
import time

from datetime import datetime

from srrdb import *
from tmdb import *
from utils import *

DEBUG = False
DRY_RUN = False

VALID_EXTENSIONS = [
    'avi',   # Audio Video Interleave
    'iso',   # Optical disc image (BD/DVD)
    'm2ts',  # Blu-ray BDAV MPEG-2 Transport Stream
    'm4v',   # MPEG-4 video (Apple)
    'mk3d',  # Matroska 3D
    'mkv',   # Matroska Video
    'mov',   # QuickTime Movie
    'mp4',   # MPEG-4 Part 14
    'mpeg',  # MPEG program stream
    'mpg',   # MPEG program stream
    'ogg',   # Ogg container
    'ts',    # MPEG transport stream
    'webm',  # WebM (VP8/VP9)
]

VALID_EXTENSIONS_TO_MOVE = [
    'avi',   # Audio Video Interleave
    'iso',   # Optical disc image (BD/DVD)
    'm2ts',  # Blu-ray BDAV MPEG-2 Transport Stream
    'm4v',   # MPEG-4 video (Apple)
    'mk3d',  # Matroska 3D
    'mkv',   # Matroska Video
    'mov',   # QuickTime Movie
    'mp4',   # MPEG-4 Part 14
    'mpeg',  # MPEG program stream
    'mpg',   # MPEG program stream
    'ogg',   # Ogg container
    'ts',    # MPEG transport stream
    'webm',  # WebM (VP8/VP9)
]

VALID_EXTENSIONS_TO_COPY = [
    'srt',   # SubRip Text
    'vtt',   # WebVTT
    'ass',   # ASS
    'ssa',   # SSA
    'sub',   # VobSub (paired with .idx)
    'idx',   # VobSub index
    'sup',   # PGS
]

PREFER_ORIGINAL_TITLE = [
    'fr',
    #'es'
]

# A release is treated as TV when its name carries a season pack or episode marker
TV_PATTERN = r'[.\s]S\d{2}(?:E\d{2})?[.\s]' # dot or space, season pack or episode

# --verify-library: patterns describing this tool's own output naming convention, used to lint an
# already-organized (or hand-built) library instead of parsing raw scene release names.
SEASON_NAME_RE = re.compile(r'^Season \d{2}$')
SEASON_LIKE_RE = re.compile(r'(?i)^season')
SUBS_DIR_RE = re.compile(r'(?i)^(subs?|subtitles)$')
COLLECTION_NAME_RE = re.compile(r'^(?P<title>.+) \[tmdbid-(?P<id>\d+)\]$')
MOVIE_TMDB_NAME_RE = re.compile(r'^(?P<title>.+) \((?P<year>\d{4})\) \[tmdbid-(?P<id>\d+)\]$')
MOVIE_IMDB_NAME_RE = re.compile(r'^.+ \((?:\d{4}|YearUnknown)\) \[imdbid-tt\d+\]$')
SERIES_NAME_RE = re.compile(r'^(?P<title>.+?)(?: \((?P<year>\d{4})\))? \[tmdbid-(?P<id>\d+)\]$')
KNOWN_CONTAINER_RE = re.compile(r'(?i)^(movies|tv)$')
LANGUAGE_CODE_RE = re.compile(r'^[A-Za-z]{2}(-[A-Za-z]{2})?$')

ANSI_RED = "\x1b[31m"
ANSI_GREEN = "\x1b[32m"
ANSI_RESET = "\x1b[0m"

# Sentinel for _verify_movie_online: the movie's parent collection folder name is itself
# malformed, so there's no reliable expected collection id to compare against - the name
# problem is already reported at the collection folder itself, don't cascade a second,
# confusing "filed as standalone" error onto every movie inside it.
PARENT_COLLECTION_UNKNOWN = object()

class Release:
    def __init__(self, name, is_folder, files=None):
        self.name = name
        self.is_folder = is_folder
        self.files = files

# Sub-directories inside a release that never hold the actual media
JUNK_DIRS = ('sample', 'proof', 'screens', 'screenshots')

def collect_valid_files(folder_path):
    # Walk the release recursively (scene TV packs nest each episode in its own
    # sub-folder) and return valid files as paths relative to the release folder.
    valid_exts = tuple(VALID_EXTENSIONS_TO_MOVE) + tuple(VALID_EXTENSIONS_TO_COPY)
    collected = []
    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if d.lower() not in JUNK_DIRS]
        for name in files:
            if 'sample' in name.lower():
                continue
            if name.endswith(valid_exts):
                collected.append(os.path.relpath(os.path.join(root, name), folder_path))
    return collected

def remove_empty_dirs(root):
    # Remove empty sub-directories bottom-up, then the root itself if it is empty.
    for dirpath, _, _ in os.walk(root, topdown=False):
        try:
            if not os.listdir(dirpath):
                os.rmdir(dirpath)
        except OSError:
            pass

def sibling_subtitles(folder_path, video_name):
    # Loose subtitle files that belong to a loose video by sharing its base name,
    # e.g. "Movie.2022.x264-GRP.mkv" -> "Movie.2022.x264-GRP.FR.srt". The dot check
    # keeps "Movie.1080p" from claiming "Movie.1080p.Extended"'s subtitles.
    stem = os.path.splitext(video_name)[0]
    return [f for f in os.listdir(folder_path)
            if f != video_name and f.endswith(tuple(VALID_EXTENSIONS_TO_COPY))
            and f[:len(stem)] == stem and f[len(stem):len(stem) + 1] == '.']

def separate(folder_path):
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        contents = os.listdir(folder_path)
        release_objects = []

        for item in contents:
            item_path = os.path.join(folder_path, item)
            is_folder = os.path.isdir(item_path)

            if is_folder:
                # If the item is a folder, list its contents (recursively)
                subfolder_contents = collect_valid_files(item_path)

                if len(subfolder_contents) != 0:
                    release_objects.append(Release(item, is_folder, subfolder_contents))
            else:
                # Check if the file has a valid extension
                file_extension = item.split('.')[-1]
                if file_extension in VALID_EXTENSIONS:
                    release_objects.append(Release(item, is_folder))
                    if DEBUG:
                        print(item)

        return release_objects
    else:
        print("The specified folder does not exist.")
        return []

def normalize_aka(text):
    # Normalise "A.k.a." / "a.k.a" style tokens to a plain AKA marker
    return re.sub(r'(?i)(?<![a-z0-9])a\.?k\.?a\.?(?![a-z0-9])', 'AKA', text)

def strip_aka(name):
    # When a title carries an "AKA", keep only the title after the last marker
    # (e.g. "Foreign.Title.AKA.English.Title" -> "English.Title")
    if re.search(r'(?<![A-Za-z0-9])AKA(?![A-Za-z0-9])', name):
        return re.split(r'(?<![A-Za-z0-9])AKA(?![A-Za-z0-9])', name)[-1]
    return name

def extract_movie_info(release_name):
    normalized = normalize_aka(release_name)

    # Regular expression pattern to match movie names and release dates.
    # Greedy title match: some movie titles carry their own year-like number
    # (e.g. "Blade.Runner.2049", "Wonder.Woman.1984"). A non-greedy title would
    # stop at that embedded number instead of the real release year that follows
    # it, so match as much title as possible and let the year be the *last*
    # delimited 4-digit token in the string, which is always the true release year.
    # The year itself may be wrapped in parentheses (e.g. "Hamnet (2025) (2160p...")
    # instead of plain scene-style dots, so the parens are optional either way.
    pattern = r'(.+)[.\s]\(?(\d{4})\)?[.\s]' # dot or space, year optionally in parens

    match = re.search(pattern, normalized)

    if match:
        # When the title carries an "AKA", keep only the title next to the year
        movie_name = strip_aka(match.group(1)).replace('.', ' ').strip()
        release_date = match.group(2)
    else:
        # If no match is found, set default values
        movie_name = "Unknown Movie"
        release_date = "YearUnknown"

    return movie_name, release_date

def srrdb(release_name):
    search_result = srrdb_search(release_name)
    if search_result:
        results_count = search_result.get('resultsCount', 0)
        if results_count == 0:
            print("No results found.")
        elif results_count > 1:
            print(f"Multiple results found for {release_name}. Please choose which result to use:")

            for index, result in enumerate(search_result['results'], start=1):
                print(f"{index}. {result['release']}")
            print("0. None of these - skip this release")

            while True:
                try:
                    user_choice = int(input("Enter the number of the result to use: "))
                    if user_choice == 0:
                        print(f"Skipped: no matching result chosen for {release_name}")
                        return None
                    if 1 <= user_choice <= results_count:
                        selected_result = search_result['results'][user_choice - 1]
                        print(f"You selected: {selected_result['release']}")
                        break
                    else:
                        print("Invalid choice. Please enter a valid number.")
                except ValueError:
                    print("Invalid input. Please enter a number.")

        imdb_result = srrdb_imdb(release_name)
        if imdb_result:
            return imdb_result
        else:
            return None

def extract_tmdb_info(release_name, tmdb_data):
    if tmdb_data is None:
        return None, None, None, None

    if 'total_results' in tmdb_data and tmdb_data['total_results'] > 0:
        if tmdb_data['total_results'] == 1:
            # If there's only one result, return it
            first_movie = tmdb_data['results'][0]
        else:
            print(f"Multiple results found for {release_name}. Please choose which result to use:")

            for i, movie in enumerate(tmdb_data['results']):
                print(f"{i + 1}. {movie['title']} ({movie['release_date']}) - https://www.themoviedb.org/movie/{movie['id']}")
            print("0. None of these - skip this release")

            while True:
                try:
                    choice = int(input("Enter the number of the entry you want: "))
                    if choice == 0:
                        print(f"Skipped: no matching result chosen for {release_name}")
                        return None, None, None, None
                    if 1 <= choice <= tmdb_data['total_results']:
                        first_movie = tmdb_data['results'][choice - 1]
                        break
                    else:
                        print("Invalid choice. Please enter a valid number.")
                except ValueError:
                    print("Invalid input. Please enter a number.")

        id = first_movie['id']
        if first_movie['original_language'] in PREFER_ORIGINAL_TITLE:
            title = first_movie['original_title']
            output_per_language = first_movie['original_language']
        else:
            title = first_movie['title']
            output_per_language = "en"
        release_date = first_movie['release_date']
        return id, title, release_date, output_per_language
    else:
        return None, None, None, None

def extract_tmdb_collection_info(tmdb_collection_data):
    if tmdb_collection_data is None:
        return None, None

    if tmdb_collection_data['belongs_to_collection'] is not None:
        return tmdb_collection_data['belongs_to_collection']['id'], tmdb_collection_data['belongs_to_collection']['name']
    else:
        return None, None

def rename_release_with_srrdb(release_name, imdb_data):
    # Extract movie name and release date from the IMDb data
    if 'releases' in imdb_data and imdb_data['releases']:
        movie_name = imdb_data['releases'][0]['title']
        imdb_id = imdb_data['releases'][0]['imdb']
    else:
        return release_name  # If IMDb data is not available, keep the original name

    # Reuse extract_movie_info's year parsing rather than a separate ad hoc regex
    _, release_date = extract_movie_info(release_name)

    # Generate the new release name format
    new_release_name = f"{movie_name} ({release_date}) [imdbid-tt{imdb_id}]"

    return new_release_name

def rename_release_with_tmdb(movie_id, movie_name, release_date):
    try:
        # Parse the release_date string using a specified format
        release_date = datetime.strptime(release_date, "%Y-%m-%d")

        # Extract the year as a string
        year = str(release_date.year)

        return f"{movie_name} ({year}) [tmdbid-{movie_id}]"
    except ValueError:
        return None

def rename_collection_with_tmdb(tmdb_collection_id, tmdb_collection_name):
    try:
        if tmdb_collection_id is not None:
            return f"{tmdb_collection_name} [tmdbid-{tmdb_collection_id}]"
        else:
            return None
    except ValueError:
        return None

def extract_tv_info(release_name):
    normalized = normalize_aka(release_name)

    # Match "Series Name . SxxExx" or "Series Name . Sxx" (season part captured)
    pattern = r'(.+?)[.\s]S(\d{1,2})(?:E\d{1,2})?[.\s]'
    match = re.search(pattern, normalized, re.IGNORECASE)

    if not match:
        return "Unknown Series", None, None

    # When the title carries an "AKA", keep only the title next to the season marker
    raw_name = strip_aka(match.group(1))
    season = int(match.group(2))

    # Pull a trailing year token out of the series name if present (e.g. "Series.Name.2019"
    # or "Series Name (2019)" - the parens some libraries use around the year are optional)
    year = None
    year_match = re.search(r'^(.*?)[.\s]\(?(19\d{2}|20\d{2})\)?$', raw_name)
    if year_match:
        raw_name = year_match.group(1)
        year = year_match.group(2)

    series_name = raw_name.replace('.', ' ').strip()
    return series_name, year, season

def extract_tmdb_tv_info(release_name, tv_data):
    if tv_data is None:
        return None, None, None, None

    if 'total_results' in tv_data and tv_data['total_results'] > 0:
        if tv_data['total_results'] == 1:
            # If there's only one result, return it
            first_show = tv_data['results'][0]
        else:
            print(f"Multiple results found for {release_name}. Please choose which result to use:")

            for i, show in enumerate(tv_data['results']):
                print(f"{i + 1}. {show['name']} ({show.get('first_air_date', 'N/A')}) - https://www.themoviedb.org/tv/{show['id']}")
            print("0. None of these - skip this release")

            while True:
                try:
                    choice = int(input("Enter the number of the result to use: "))
                    if choice == 0:
                        print(f"Skipped: no matching result chosen for {release_name}")
                        return None, None, None, None
                    if 1 <= choice <= len(tv_data['results']):
                        first_show = tv_data['results'][choice - 1]
                        break
                    else:
                        print("Invalid choice. Please enter a valid number.")
                except ValueError:
                    print("Invalid input. Please enter a number.")

        id = first_show['id']
        if first_show.get('original_language') in PREFER_ORIGINAL_TITLE:
            title = first_show['original_name']
            output_per_language = first_show['original_language']
        else:
            title = first_show['name']
            output_per_language = "en"
        first_air_date = first_show.get('first_air_date', '')
        return id, title, first_air_date, output_per_language
    else:
        return None, None, None, None

def rename_series_with_tmdb(series_id, series_name, first_air_date):
    try:
        # Parse the air date string and keep the year; Jellyfin allows omitting it
        year = datetime.strptime(first_air_date, "%Y-%m-%d").year
        return f"{series_name} ({year}) [tmdbid-{series_id}]"
    except (ValueError, TypeError):
        return f"{series_name} [tmdbid-{series_id}]"

def season_from_filename(filename):
    # Prefer the SxxExx marker, fall back to a bare Sxx (season packs)
    match = re.search(r'S(\d{1,2})E\d{1,2}', filename, re.IGNORECASE)
    if not match:
        match = re.search(r'[.\s_-]S(\d{1,2})[.\s_-]', filename, re.IGNORECASE)
    if not match:
        # "1x01" style episode numbering (e.g. "1x01 A Guy Walks Into a Bar.mkv")
        match = re.search(r'(?<!\d)(\d{1,2})x\d{2,3}(?!\d)', filename, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None

def season_folder(season_number):
    return f"Season {int(season_number):02d}"

def sanitize_for_windows(input_string):
    # French typography uses non-breaking/narrow-no-break spaces (U+00A0, U+202F, etc.)
    # around punctuation like "!", "?", ":" ("Au poste !", "Titre : Sous-titre").
    # These render identically to a plain space in a terminal or file explorer, but are a
    # different character - left alone, they'd make a freshly-computed name compare unequal
    # to an on-disk name that happens to use a regular space (or vice versa), causing
    # confusing "does not match" reports where the two printed strings look the same.
    # Collapse every Unicode whitespace character to a plain ASCII space up front so the
    # rest of this function - and any later comparisons - only ever deal with those.
    sanitized_string = re.sub(r'\s', ' ', input_string)

    # French typography spaces both sides of ":" ("Titre : Sous-titre"), and "/" is
    # sometimes used the same way between alternate/co-titles ("King's Game / Kingmaker
    # Collection"). Treat either spaced form as a separator and normalize it to this
    # tool's existing " - " convention (already used for collection suffixes like
    # "OSS 117 - Saga"). An unspaced colon or slash (English "Title: Subtitle",
    # "Face/Off") falls through to the blanket strip below unchanged - it already
    # collapses to a single space correctly.
    sanitized_string = re.sub(r' [:/] ', ' - ', sanitized_string)

    # Define a regex pattern to match characters not allowed in Windows filenames
    invalid_chars_regex = r'[\/:*?"<>|]'

    # Replace invalid characters with nothing
    sanitized_string = re.sub(invalid_chars_regex, '', sanitized_string)

    # Deleting a punctuation character can leave an orphaned run of spaces behind -
    # e.g. French titles conventionally space ":"/"?" ("Titre : Sous-titre"), so
    # removing just the punctuation leaves a double space.
    sanitized_string = re.sub(r' {2,}', ' ', sanitized_string).strip()

    # Remove trailing periods and spaces (Windows does not allow these at the end of folder names)
    sanitized_string = sanitized_string.rstrip(' .')

    # Ensure the string is not empty after sanitization
    if not sanitized_string:
        sanitized_string = '_'

    return sanitized_string

def movie_destination(output, language, renamed_collection, renamed_release):
    if renamed_collection is not None:
        return os.path.join(output, "movies", language, sanitize_for_windows(renamed_collection), sanitize_for_windows(renamed_release))
    return os.path.join(output, "movies", language, sanitize_for_windows(renamed_release))

def tv_destination(output, language, renamed_series, season):
    return os.path.join(output, "tv", language, sanitize_for_windows(renamed_series), season_folder(season))

def classify_release(release):
    # Parse a release with no network access: what it is and how it reads
    if release.is_folder:
        release_name = release.name
        files = release.files
    else:
        release_name = os.path.splitext(release.name)[0]
        files = [release.name]

    if re.findall(TV_PATTERN, release.name):
        series_name, series_year, _ = extract_tv_info(release_name)
        seasons = {}
        for f in files:
            seasons.setdefault(season_from_filename(os.path.basename(f)), []).append(os.path.basename(f))
        parsed_ok = series_name != "Unknown Series" and any(s is not None for s in seasons)
        return {'kind': 'tv', 'release': release.name, 'name': series_name,
                'year': series_year, 'seasons': seasons, 'parsed_ok': parsed_ok}

    movie_name, year = extract_movie_info(release_name)
    parsed_ok = movie_name != "Unknown Movie" and year != "YearUnknown"
    return {'kind': 'movie', 'release': release.name, 'name': movie_name,
            'year': year, 'parsed_ok': parsed_ok}

def normalize_name(name):
    # spaces -> dots, strip parentheses, and rewrite "1x01" episode numbering to
    # SxxExx (Jellyfin handles S01E01 far better than the 1x01 form)
    name = re.sub(r'(?<!\d)(\d{1,2})x(\d{2,3})(?!\d)',
                  lambda m: f"S{int(m.group(1)):02d}E{m.group(2)}", name)
    return name.replace(' ', '.').replace('(', '').replace(')', '')

def normalize_input(folder_path, dry_run=False):
    # Python port of Releases-renamer.ps1, scoped to folder_path:
    # 1) normalise names (spaces->dots, strip parens, 1x01->S01E01),
    # 2) wrap loose media in a folder
    if not os.path.isdir(folder_path):
        print("The specified folder does not exist.")
        return

    # 1. Rename bottom-up so renamed parents never invalidate child paths
    for root, dirs, files in os.walk(folder_path, topdown=False):
        for name in files + dirs:
            new_name = normalize_name(name)
            if new_name == name:
                continue
            src, dst = os.path.join(root, name), os.path.join(root, new_name)
            if dry_run:
                print(f"[normalize] rename: {name} -> {new_name}")
            elif os.path.exists(dst):
                print(f"[normalize] skip (target exists): {new_name}")
            else:
                os.rename(src, dst)

    # 2. Wrap each loose top-level media file in a folder named after it
    for name in os.listdir(folder_path):
        path = os.path.join(folder_path, name)
        if not (os.path.isfile(path) and name.endswith(tuple(VALID_EXTENSIONS_TO_MOVE))):
            continue
        stem = os.path.splitext(name)[0]
        dest_dir = os.path.join(folder_path, stem)
        subs = sibling_subtitles(folder_path, name)
        if dry_run:
            print(f"[normalize] folder: {name} -> {stem}/{name}")
            for sub in subs:
                print(f"[normalize] folder: {sub} -> {stem}/{sub}")
            continue
        os.makedirs(dest_dir, exist_ok=True)
        move_file(path, os.path.join(dest_dir, name))
        for sub in subs:
            move_file(os.path.join(folder_path, sub), os.path.join(dest_dir, sub))

def resolve_release(info, output, source):
    # Look a parsed release up on TMDB (single result only, never prompts) and
    # return (status, destination_path_or_None) for the report.
    if info['kind'] == 'movie':
        if source == 'srrdb':
            return "SKIP (srrdb not checked)", None
        data = tmdb_search(info['name'], info['year'])
        if not data or data.get('total_results', 0) == 0:
            return "NO TMDB MATCH", None
        if data['total_results'] > 1:
            return f"AMBIGUOUS ({data['total_results']} matches)", None
        tid, title, rdate, lang = extract_tmdb_info(info['release'], data)
        renamed = rename_release_with_tmdb(tid, title, rdate)
        if not renamed:
            return "BAD RELEASE DATE", None
        cid, cname = extract_tmdb_collection_info(
            tmdb_collection_search(tid, language=lang if lang in PREFER_ORIGINAL_TITLE else None))
        renamed_coll = rename_collection_with_tmdb(cid, cname)
        return "OK", movie_destination(output, lang, renamed_coll, renamed)

    data = tmdb_tv_search(info['name'], info['year'])
    if not data or data.get('total_results', 0) == 0:
        return "NO TMDB MATCH", None
    if data['total_results'] > 1:
        return f"AMBIGUOUS ({data['total_results']} matches)", None
    tid, title, air, lang = extract_tmdb_tv_info(info['release'], data)
    renamed = rename_series_with_tmdb(tid, title, air)
    seasons = sorted(s for s in info['seasons'] if s is not None)
    if not seasons:
        return "NO SEASON DETERMINED", None
    season_list = ", ".join(f"{s:02d}" for s in seasons)
    return f"OK (seasons {season_list})", os.path.join(output, "tv", lang, sanitize_for_windows(renamed))

def run_report(releases, output, source, full=False):
    mode = "check-full" if full else "check-syntax"
    print(f"=== {mode}: {len(releases)} release(s) ===\n")
    counts = {'movie': 0, 'tv': 0, 'unparsed': 0, 'resolved': 0, 'failed': 0}

    for release in releases:
        info = classify_release(release)
        counts[info['kind']] += 1

        if info['kind'] == 'tv':
            season_desc = ", ".join(
                (f"S{s:02d}" if s is not None else "S??") + f"({len(v)})"
                for s, v in sorted(info['seasons'].items(), key=lambda x: (x[0] is None, x[0])))
            print(f"TV   {info['release']}")
            print(f"     -> {info['name']} ({info['year'] or '----'})  seasons: {season_desc}")
        else:
            print(f"MOV  {info['release']}")
            print(f"     -> {info['name']} ({info['year']})")

        if not info['parsed_ok']:
            counts['unparsed'] += 1
            print("     STATUS: SKIP (could not parse)\n")
            continue

        if not full:
            print("     STATUS: parsed\n")
            continue

        status, dest = resolve_release(info, output, source)
        if dest:
            counts['resolved'] += 1
            print(f"     STATUS: {status}")
            print(f"     DEST:   {dest}\n")
        else:
            counts['failed'] += 1
            print(f"     STATUS: {status}\n")

    print("=== summary ===")
    print(f"movies: {counts['movie']}   tv: {counts['tv']}   unparsed: {counts['unparsed']}")
    if full:
        print(f"resolved: {counts['resolved']}   failed: {counts['failed']}")

def _count_subfolders(root):
    # Fast, local-only pre-pass so the online walk can show progress against a total. Approximate:
    # doesn't replicate every early-return quirk in _verify_folder/_verify_season_folder (e.g. a
    # season folder's own unexpected sub-folders aren't descended into by the real walk), but that
    # only matters for already-broken libraries and this is just a progress estimate.
    total = 1  # root itself, which _verify_folder(is_root=True) also counts
    for _, dirs, _ in os.walk(root):
        total += len(dirs)
    return total

def _tick_progress(counts):
    if not counts.get('progress_enabled') or counts.get('total') is None:
        return
    now = time.monotonic()
    done = counts['folders']
    total = counts['total']
    if done < total and now - counts['last_progress_time'] < 0.1:
        return # throttle redraws so huge libraries don't spam the terminal
    counts['last_progress_time'] = now
    if counts.get('blank_before_next_progress'):
        sys.stdout.write('\n')
        counts['blank_before_next_progress'] = False
    pct = min(done * 100 // total, 100)
    elapsed = int(now - counts['start_time'])
    line = (f"  checked {done}/{total} folders (~{pct}%), "
            f"{counts['errors']} problem(s) so far, {elapsed // 60}:{elapsed % 60:02d} elapsed")
    pad = max(0, counts.get('last_progress_len', 0) - len(line))
    sys.stdout.write('\r' + line + ' ' * pad)
    sys.stdout.flush()
    counts['last_progress_len'] = len(line)

def _clear_progress_line(counts):
    if counts.get('last_progress_len'):
        sys.stdout.write('\r' + ' ' * counts['last_progress_len'] + '\r')
        sys.stdout.flush()
        counts['last_progress_len'] = 0

def _tmdb_retry_progress_logger(counts):
    # Retry warnings from tmdb.py print to stderr mid-run; without this they'd land on top of
    # the live \r-based progress line instead of their own line. Same clear-then-print pattern
    # _report_problem uses for error reports.
    def log(message):
        _clear_progress_line(counts)
        print(f"  [tmdb] {message}", file=sys.stderr)
        counts['blank_before_next_progress'] = True
    return log

def _report_problem(path, message, counts):
    _clear_progress_line(counts)
    counts['errors'] += 1
    # Blank line whenever we move from one folder's group of problems to another's, so a run
    # against a large library reads as separate blocks per offending folder instead of a wall of text
    group = counts.get('current_group')
    if counts.get('last_printed_group') is not None and counts['last_printed_group'] != group:
        print()
    counts['last_printed_group'] = group
    print(f"{ANSI_RED}ERROR{ANSI_RESET}: {path}\n       {message}")
    counts['blank_before_next_progress'] = True

def _is_pass_through_folder(name):
    # movies/, tv/, and a bare language code (en, fr, pt-BR, ...) are containers this tool
    # creates but never itself names per-release, so they're never validated - only descended into
    return bool(KNOWN_CONTAINER_RE.match(name) or LANGUAGE_CODE_RE.match(name))

def _is_video_file(filename):
    return filename.lower().endswith(tuple(VALID_EXTENSIONS)) and 'sample' not in filename.lower()

_ORGANIZED_SCAN_MAX_DEPTH = 4

def _has_organized_marker(name):
    # Any of this tool's own output name shapes - never produced by raw scene releases.
    # Deliberately excludes SEASON_NAME_RE ("Season NN"): that shape carries no
    # [tmdbid-.../imdbid-...] tag and could plausibly appear in a raw, not-yet-organized
    # folder too, so on its own it's too weak a signal to refuse a run over.
    return bool(MOVIE_TMDB_NAME_RE.match(name) or MOVIE_IMDB_NAME_RE.match(name)
                or SERIES_NAME_RE.match(name) or COLLECTION_NAME_RE.match(name))

def _scan_for_organized_marker(path, name, depth):
    if _has_organized_marker(name):
        return True
    if depth > _ORGANIZED_SCAN_MAX_DEPTH:
        return False
    # depth 0: always descend into whatever the user pointed at.
    # deeper: only follow this tool's own pass-through containers (movies/tv/lang
    # code) - a raw scene dump won't have these, so detection stays cheap and
    # short-circuits on the first hit.
    if depth == 0 or _is_pass_through_folder(name):
        try:
            children = list(os.scandir(path))
        except OSError:
            return False
        return any(_scan_for_organized_marker(c.path, c.name, depth + 1)
                   for c in children if c.is_dir())
    return False

def detect_organized_library(folder):
    # Safety check for the destructive organize/normalize steps: is `folder` itself,
    # or something inside it, already named after this tool's own output convention?
    # Never trust the path string the caller passed in (folder names mean nothing -
    # only what's actually inside the folder does).
    return _scan_for_organized_marker(folder, os.path.basename(os.path.normpath(folder)), 0)

def _bracket_mismatch(name):
    # Catches typos like a missing closing paren/bracket (e.g. "Show (2018 [tmdbid-1]") that
    # would otherwise slip through the naming regexes, since '(' and '[' are also valid
    # characters within a free-form title
    return name.count('(') != name.count(')') or name.count('[') != name.count(']')

def _pick_movie_title(data):
    if data.get('original_language') in PREFER_ORIGINAL_TITLE:
        return data.get('original_title')
    return data.get('title')

def _pick_series_title(data):
    if data.get('original_language') in PREFER_ORIGINAL_TITLE:
        return data.get('original_name')
    return data.get('name')

def _localized_collection_name(collection, movie_lang):
    # Unlike movies/shows, a TMDB collection has no original_name/original_language
    # field of its own - the only way to get it in the movie's preferred language is
    # to explicitly re-request the collection in that language.
    if movie_lang not in PREFER_ORIGINAL_TITLE:
        return collection['name']
    localized = tmdb_get_collection_by_id(collection['id'], language=movie_lang)
    if isinstance(localized, dict) and localized.get('name'):
        return localized['name']
    return collection['name']

def _report_name_mismatch(path, local_name, expected_name, counts):
    _report_problem(path,
        f'does not match current TMDB data (local: "{local_name}", expected: "{expected_name}")', counts)

def _verify_movie_online(path, name, match, parent_collection_id, counts):
    data = tmdb_get_movie_by_id(match.group('id'))
    if data is False:
        _report_problem(path, 'TMDB id no longer exists (movie may have been deleted or merged)', counts)
        return
    if data is None:
        _report_problem(path, 'could not verify against TMDB (network/API error)', counts)
        return

    # Rebuild the name exactly the way it was first created (rename_release_with_tmdb + the same
    # sanitize_for_windows pass tv_destination/movie_destination apply) and compare the whole
    # thing, rather than the title/year fragments in isolation - sanitizing an isolated title
    # fragment strips trailing punctuation ("Broute 24." -> "Broute 24") that is only trailing
    # relative to the title, not to the full folder name, causing false-positive mismatches
    expected = rename_release_with_tmdb(match.group('id'), _pick_movie_title(data), data.get('release_date'))
    if expected is None:
        _report_problem(path, 'TMDB no longer provides a valid release date to verify against', counts)
    else:
        expected = sanitize_for_windows(expected)
        if expected != name:
            _report_name_mismatch(path, name, expected, counts)

    collection = data.get('belongs_to_collection')
    if parent_collection_id is PARENT_COLLECTION_UNKNOWN:
        pass # enclosing collection folder's own id couldn't be determined; already reported there
    elif parent_collection_id is None:
        if collection is not None:
            cname = _localized_collection_name(collection, data.get('original_language'))
            _report_problem(path,
                f'movie now belongs to TMDB collection "{cname} [tmdbid-{collection["id"]}]" '
                'but is filed as a standalone movie', counts)
    elif collection is None:
        _report_problem(path,
            'movie no longer belongs to any TMDB collection, but is filed under a collection folder', counts)
    elif str(collection['id']) != str(parent_collection_id):
        cname = _localized_collection_name(collection, data.get('original_language'))
        _report_problem(path,
            f'movie belongs to TMDB collection "{cname} [tmdbid-{collection["id"]}]" '
            f'but is filed under collection [tmdbid-{parent_collection_id}]', counts)

def _verify_series_online(path, name, match, counts):
    data = tmdb_get_tv_by_id(match.group('id'))
    if data is False:
        _report_problem(path, 'TMDB id no longer exists (series may have been deleted or merged)', counts)
        return
    if data is None:
        _report_problem(path, 'could not verify against TMDB (network/API error)', counts)
        return

    expected = sanitize_for_windows(
        rename_series_with_tmdb(match.group('id'), _pick_series_title(data), data.get('first_air_date')))
    if expected != name:
        _report_name_mismatch(path, name, expected, counts)

def _verify_collection_online(path, name, match, counts):
    data = tmdb_get_collection_by_id(match.group('id'))
    if data is False:
        _report_problem(path,
            'TMDB collection id no longer exists (deleted, merged, or was never official)', counts)
        return
    if data is None:
        _report_problem(path, 'could not verify against TMDB (network/API error)', counts)
        return

    # A collection has no original_language of its own; infer it from one of its
    # movies (which do carry original_language) and re-fetch in that language so the
    # comparison isn't always pinned to TMDB's English-default name.
    parts = data.get('parts') or []
    collection_lang = parts[0].get('original_language') if parts else None
    if collection_lang in PREFER_ORIGINAL_TITLE:
        localized = tmdb_get_collection_by_id(match.group('id'), language=collection_lang)
        if isinstance(localized, dict) and localized.get('name'):
            data = localized

    expected = sanitize_for_windows(rename_collection_with_tmdb(match.group('id'), data.get('name')))
    if expected != name:
        _report_name_mismatch(path, name, expected, counts)

def _verify_season_folder(entry, counts):
    counts['folders'] += 1
    _tick_progress(counts)
    counts['current_group'] = entry.path
    if not SEASON_NAME_RE.match(entry.name):
        _report_problem(entry.path,
            'season folder name does not match "Season NN" (zero-padded, e.g. "Season 02")', counts)

    try:
        children = list(os.scandir(entry.path))
    except OSError as e:
        _report_problem(entry.path, f'could not read folder: {e}', counts)
        return

    subdirs = [c for c in children if c.is_dir()]
    media_files = [c for c in children if c.is_file() and _is_video_file(c.name)]

    # A "Subs" (or "Sub"/"Subtitles") folder holding matching subtitle files is a standard way
    # to ship subtitles alongside a season pack - accept at most one such folder instead of
    # rejecting it outright; any other sub-folder is still unexpected.
    subs_dir = next((d for d in subdirs if SUBS_DIR_RE.match(d.name)), None)
    for d in subdirs:
        if d is not subs_dir:
            _report_problem(d.path, 'unexpected sub-folder inside a season folder', counts)

    if not media_files:
        _report_problem(entry.path, 'season folder contains no video files', counts)
        return

    season_match = SEASON_NAME_RE.match(entry.name)
    season_num = int(season_match.group(0).split()[1]) if season_match else None

    for f in media_files:
        counts['files'] += 1
        season = season_from_filename(f.name)
        if season is None:
            _report_problem(f.path, 'episode file name has no SxxExx/Sxx season marker', counts)
        elif season_num is not None and season != season_num:
            _report_problem(f.path,
                f'episode marker season {season:02d} does not match its "Season {season_num:02d}" folder', counts)

    if subs_dir is not None:
        _verify_subs_folder(subs_dir, season_num, counts)

def _verify_subs_folder(entry, season_num, counts):
    counts['folders'] += 1
    _tick_progress(counts)
    try:
        children = list(os.scandir(entry.path))
    except OSError as e:
        _report_problem(entry.path, f'could not read folder: {e}', counts)
        return

    for c in children:
        if c.is_dir():
            _report_problem(c.path, 'unexpected sub-folder inside a Subs folder', counts)
        elif not c.name.lower().endswith(tuple(VALID_EXTENSIONS_TO_COPY)):
            _report_problem(c.path, 'unexpected non-subtitle file inside a Subs folder', counts)
        elif season_num is not None:
            season = season_from_filename(c.name)
            if season is not None and season != season_num:
                _report_problem(c.path,
                    f'subtitle marker season {season:02d} does not match its "Season {season_num:02d}" folder', counts)

def _verify_folder(path, name, counts, is_root=False, online=False, parent_collection_id=None):
    counts['folders'] += 1
    _tick_progress(counts)
    counts['current_group'] = path

    try:
        children = list(os.scandir(path))
    except OSError as e:
        _report_problem(path, f'could not read folder: {e}', counts)
        return

    subdirs = [c for c in children if c.is_dir()]
    media_files = [c for c in children if c.is_file() and _is_video_file(c.name)]

    if is_root or _is_pass_through_folder(name):
        for d in subdirs:
            _verify_folder(d.path, d.name, counts, online=online)
        return

    if media_files and subdirs:
        _report_problem(path, 'folder mixes video files and sub-folders', counts)
        for d in subdirs:
            _verify_folder(d.path, d.name, counts, online=online)
        return

    if subdirs and all(SEASON_LIKE_RE.match(d.name) for d in subdirs):
        if _bracket_mismatch(name):
            _report_problem(path, 'series folder name has mismatched parentheses or brackets', counts)
        else:
            match = SERIES_NAME_RE.match(name)
            if not match:
                _report_problem(path,
                    'series folder name does not match "Title (Year) [tmdbid-N]" or "Title [tmdbid-N]"', counts)
            elif online:
                _verify_series_online(path, name, match, counts)
        for d in subdirs:
            _verify_season_folder(d, counts)
        return

    if media_files and not subdirs:
        counts['files'] += len(media_files)
        if _bracket_mismatch(name):
            _report_problem(path, 'movie folder name has mismatched parentheses or brackets', counts)
        else:
            match = MOVIE_TMDB_NAME_RE.match(name)
            if match:
                if online:
                    _verify_movie_online(path, name, match, parent_collection_id, counts)
            elif not MOVIE_IMDB_NAME_RE.match(name):
                _report_problem(path,
                    'movie folder name does not match "Title (Year) [tmdbid-N]" or "Title (Year) [imdbid-ttN]"', counts)
        return

    if subdirs and not media_files:
        if _bracket_mismatch(name):
            _report_problem(path, 'collection folder name has mismatched parentheses or brackets', counts)
            collection_id = PARENT_COLLECTION_UNKNOWN
        else:
            match = COLLECTION_NAME_RE.match(name)
            if not match:
                _report_problem(path, 'collection folder name does not match "Title [tmdbid-N]"', counts)
                collection_id = PARENT_COLLECTION_UNKNOWN
            else:
                if online:
                    _verify_collection_online(path, name, match, counts)
                collection_id = match.group('id')
        for d in subdirs:
            _verify_folder(d.path, d.name, counts, online=online, parent_collection_id=collection_id)
        return

    _report_problem(path, 'folder has no recognized video files or sub-folders', counts)

def verify_library(root, online=False):
    # Lint pass over an already-organized (or hand-built) library: walks the tree and flags any
    # folder/file that doesn't match this tool's own naming convention. Read-only - no renames or
    # moves. With online=True, also re-checks every tagged movie/series/collection against TMDB.
    if not os.path.isdir(root):
        print("The specified folder does not exist.")
        return

    counts = {'folders': 0, 'files': 0, 'errors': 0, 'current_group': None, 'last_printed_group': None,
              'total': None, 'progress_enabled': False, 'last_progress_len': 0,
              'last_progress_time': 0.0, 'start_time': time.monotonic()}
    mode = "verify-library-online" if online else "verify-library"
    print(f"=== {mode}: {root} ===\n")
    if online:
        counts['progress_enabled'] = sys.stdout.isatty()
        counts['total'] = _count_subfolders(root)
        counts['start_time'] = time.monotonic()
        set_retry_logger(_tmdb_retry_progress_logger(counts))
    try:
        _verify_folder(root, os.path.basename(os.path.normpath(root)), counts, is_root=True, online=online)
    finally:
        if online:
            set_retry_logger(None)
    _clear_progress_line(counts)
    print()
    print("=== summary ===")
    print(f"folders checked: {counts['folders']}   files checked: {counts['files']}   errors: {counts['errors']}")
    if counts['errors'] == 0:
        print(f"{ANSI_GREEN}Everything looks good - no problems found.{ANSI_RESET}")

def print_tmdb_api_key_help():
    print("         Set it with:")
    print("           Linux/macOS (bash/zsh):  export TMDB_API_KEY=<your-key>")
    print("           Windows (PowerShell):    $env:TMDB_API_KEY = \"<your-key>\"")
    print("           Windows (cmd):           set TMDB_API_KEY=<your-key>")

def arguments():
    parser = argparse.ArgumentParser(
                    prog='Releases Organizer',
                    description='',
                    epilog='')

    parser.add_argument('folder', nargs='?', default='.', help='source folder to scan (default: current directory)')
    parser.add_argument('output', nargs='?', default='output', help='destination library folder (default: output)')
    parser.add_argument('-s', '--source', choices=['tmdb', 'srrdb'], default='tmdb', help='metadata source for movies (default: tmdb)')
    parser.add_argument('-de', '--delete-empty', action='store_true', default=False, help='delete empty folders after move')
    parser.add_argument('-ds', '--srr', action='store_true', default=False, help='download SRR file from srrDB (movies)')
    parser.add_argument('-dn', '--nfo', action='store_true', default=False, help='download NFO file from srrDB (movies)')
    parser.add_argument('-d', '--debug', action='store_true', default=False, help='enable debug output')
    parser.add_argument('-dy', '--dry-run', action='store_true', default=False, help='identify and print results without moving anything')
    parser.add_argument('-n', '--normalize', action='store_true', default=False, help='pre-normalize names (spaces->dots, strip parens, 1x01->S01E01, folder loose media) before organizing')
    parser.add_argument('-cs', '--check-syntax', action='store_true', default=False, help='offline: report how each release parses, no TMDB, no moves')
    parser.add_argument('-cf', '--check-full', action='store_true', default=False, help='online: report parsing + TMDB match + destination path, no moves')
    parser.add_argument('-vl', '--verify-library', action='store_true', default=False, help='offline: audit an already-organized library for naming/structure mistakes, no TMDB, no moves')
    parser.add_argument('-vlo', '--verify-library-online', action='store_true', default=False, help='online: run --verify-library plus TMDB drift checks (mistyped/dead ids, collection membership changes), no moves')
    parser.add_argument('--force-reorganize-existing-library', action='store_true', default=False, help='override the organized-library safety check and run the destructive organize/normalize step anyway (dangerous)')

    return parser.parse_args()

def main():
    # Force UTF-8 output regardless of the console/redirect encoding - Windows defaults
    # stdout to the system code page (e.g. cp1252) when it's not a real console (piped or
    # redirected with `>`), which can't represent every character release/folder names carry.
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

    args = arguments()

    folder = args.folder
    output = args.output
    source = args.source
    delete_empty = args.delete_empty
    download_srr = args.srr
    download_nfo = args.nfo

    DEBUG = args.debug
    DRY_RUN = args.dry_run

    # TMDB is needed for TV (always) and for movies unless --source srrdb.
    # --check-syntax and --verify-library are fully offline, so they never need a key.
    # --verify-library-online gets its own hard-stop check below instead of this soft warning.
    if (API_KEY == 'YOUR_TMDB_API_KEY' and not args.check_syntax and not args.verify_library
            and not args.verify_library_online):
        if source == 'srrdb':
            # Movies won't hit TMDB in this mode; only TV releases or collection lookups
            # would still fail, so a warning is enough - no need to hard-stop.
            print("WARNING: TMDB_API_KEY is not set - TMDB lookups will fail.")
            print_tmdb_api_key_help()
            print()
        else:
            # source == 'tmdb': every release needs a working key, so fail fast instead of
            # printing "No TMDb movie match" once per release across the whole library.
            print("TMDB_API_KEY is not set - this command requires a working TMDB API key.")
            print_tmdb_api_key_help()
            return

    if args.verify_library_online:
        if API_KEY == 'YOUR_TMDB_API_KEY':
            print("TMDB_API_KEY is not set - --verify-library-online requires a working TMDB API key.")
            print_tmdb_api_key_help()
            return
        verify_library(folder, online=True)
        return

    if args.verify_library:
        verify_library(folder)
        return

    destructive = not (args.check_syntax or args.check_full or args.dry_run
                       or args.force_reorganize_existing_library)
    if destructive and detect_organized_library(folder):
        print(f"{ANSI_RED}REFUSING TO RUN{ANSI_RESET}: '{folder}' already contains an organized library")
        print("(found a folder named after this tool's own convention, e.g. \"Title (Year) [tmdbid-N]\").")
        print()
        print("Running the organize step here would re-parse already-tagged releases as raw scene")
        print("dumps and rename/move them again - which can corrupt an already-built library.")
        print()
        print("Safe commands against an existing library:")
        print("  -cs / --check-syntax            offline parse preview, no TMDB, no moves")
        print("  -cf / --check-full              online TMDB preview, no moves")
        print("  -vl / --verify-library          offline structure/naming audit, no moves")
        print("  -vlo / --verify-library-online  online audit + TMDB drift check, no moves")
        print("  -dy / --dry-run                 preview only, no moves")
        print()
        print("To force the organize step to run here anyway, pass --force-reorganize-existing-library.")
        return

    if args.normalize:
        normalize_input(folder, DRY_RUN)

    results = separate(folder)

    if args.check_syntax or args.check_full:
        run_report(results, output, source, full=args.check_full)
        return

    for release in results:

        if(release.is_folder):
            release_name = release.name

            if DEBUG:
                print(f"Name: {release.name}")
                print(f"Is Folder: {release.is_folder}")
                if release.is_folder:
                    print(f"Contents: {', '.join(release.files)}")
                print()
        else:
            release_name, _ = os.path.splitext(release.name)

        movie_name, release_date = extract_movie_info(release_name)
        
        if DEBUG:
            print(f"Release Name: {release_name}")
            print(f"Movie Name: {movie_name}")
            print(f"Release Date: {release_date}")

        # Check if file or folder is tv season or episodes
        #tv_pattern = r'\.S\d{2}\.' # dot only
        tv_pattern = r'[.\s]S\d{2}(?:E\d{2})?[.\s]' # dot or space, season pack or episode
        tv_matches = re.findall(tv_pattern, release.name)
        if tv_matches:
            if DEBUG:
                print("The file or folder contains the pattern:", tv_matches)
                print()

            series_name, series_year, _ = extract_tv_info(release_name)

            if DEBUG:
                print(f"Series Name: {series_name}")
                print(f"Series Year: {series_year}")

            if series_name == "Unknown Series":
                print(f"Could not parse a series name from '{release_name}' - skipping. "
                      "Run --check-syntax to preview parsing.")
                print("")
                continue

            tv_data = tmdb_tv_search(series_name, series_year)
            tv_id, tv_title, tv_first_air_date, tv_language = extract_tmdb_tv_info(release_name, tv_data)

            if not tv_id:
                print(f"No TMDb series match for {release_name}")
                print("")
                continue

            renamed_series = rename_series_with_tmdb(tv_id, tv_title, tv_first_air_date)
            print(f"Renamed Series: {renamed_series}")
            if DEBUG:
                print(f"Language set: {tv_language}")

            if DRY_RUN:
                print("Dry run enabled, not moving the files")
                print("")
                continue

            # Collect the episode files (a season pack folder, or a single episode file)
            if release.is_folder:
                source_dir = os.path.join(folder, release.name)
                episode_files = release.files
            else:
                source_dir = folder
                episode_files = [release.name]

            for file in episode_files:
                # file may be a nested relative path; the season and the destination
                # name come from the file's own base name, flattening any sub-folders
                base = os.path.basename(file)
                season = season_from_filename(base)
                if season is None:
                    print(f"Could not determine season for {base}, skipping.")
                    continue

                # Keep the original file name; only the series/season folders are created
                season_dir = tv_destination(output, tv_language, renamed_series, season)
                if not os.path.exists(season_dir):
                    os.makedirs(season_dir)

                source_file = os.path.join(source_dir, file)
                destination_file = os.path.join(season_dir, base)
                if any(base.endswith(ext) for ext in VALID_EXTENSIONS_TO_COPY):
                    copy_file(source_file, destination_file)
                elif any(base.endswith(ext) for ext in VALID_EXTENSIONS_TO_MOVE):
                    move_file(source_file, destination_file)

                # A loose episode may have loose sibling subtitles next to it
                if not release.is_folder:
                    for sub in sibling_subtitles(folder, release.name):
                        copy_file(os.path.join(folder, sub), os.path.join(season_dir, sub))

            # Remove the source folder if it is now empty
            if release.is_folder and delete_empty:
                remove_empty_dirs(os.path.join(folder, release.name))

            print("")
            continue
        
        if movie_name == "Unknown Movie" or release_date == "YearUnknown":
            print(f"Could not parse a title/year from '{release_name}' - skipping. "
                  "Run --check-syntax to preview parsing.")
            print("")
            continue

        renamed_collection = None
        tmdb_language = "en"

        if source == "srrdb":
            result = srrdb(release_name)
            if result is None:
                print(f"No srrDB match for {release_name}")
                print("")
                continue
            renamed_release = rename_release_with_srrdb(release_name, result)
        elif source == "tmdb":
            tmdb_data = tmdb_search(movie_name, release_date)
            tmdb_id, tmdb_title, tmdb_release_date, tmdb_language = extract_tmdb_info(release_name, tmdb_data)
            # search for collection information
            tmdb_collection_data = tmdb_collection_search(
                tmdb_id, language=tmdb_language if tmdb_language in PREFER_ORIGINAL_TITLE else None)
            tmdb_collection_id, tmdb_collection_name = extract_tmdb_collection_info(tmdb_collection_data)

            if tmdb_id:
                if DEBUG:
                    print("TMDb Movie Info:")
                    print(f"ID: {tmdb_id}")
                    print(f"Title: {tmdb_title}")
                    print(f"Release Date: {tmdb_release_date}")
                    print(f"Language set: {tmdb_language}")
                    if tmdb_collection_id is not None and tmdb_collection_name is not None:
                        print(f"Collection ID: {tmdb_collection_id}")
                        print(f"Collection Name: {tmdb_collection_name}")
                renamed_release = rename_release_with_tmdb(tmdb_id, tmdb_title, tmdb_release_date)
                renamed_collection = rename_collection_with_tmdb(tmdb_collection_id, tmdb_collection_name)
            else:
                print(f"No TMDb movie match for {release_name}")
                print("")
                continue

        print(f"Renamed Release: {renamed_release}")
        if renamed_collection:
            print(f"Renamed Collection: {renamed_collection}")

        if DRY_RUN:
            print(f"Dry run enabled, not moving the files")
            if download_srr:
                print(f"Dry run enabled, not downloading SRR for {release_name}")
            if download_nfo:
                print(f"Dry run enabled, not downloading NFO for {release_name}")
        else:
            path = movie_destination(output, tmdb_language, renamed_collection, renamed_release)

            if not os.path.exists(path):
                os.makedirs(path)

            if release.is_folder:
                # Iterate through files in the source folder (may be nested); the
                # destination keeps only the base name, flattening any sub-folders
                for file in release.files:
                    base = os.path.basename(file)
                    source_file = os.path.join(folder, release.name, file)
                    if any(base.endswith(ext) for ext in VALID_EXTENSIONS_TO_COPY):
                        copy_file(source_file, os.path.join(path, base))
                    elif any(base.endswith(ext) for ext in VALID_EXTENSIONS_TO_MOVE):
                        move_file(source_file, os.path.join(path, base))

                # Check if the source folder is empty and delete it
                if delete_empty:
                    remove_empty_dirs(os.path.join(folder, release.name))
            else:
                move_file(os.path.join(folder, release.name), os.path.join(path, release.name))
                # A loose video may have loose sibling subtitles next to it
                for sub in sibling_subtitles(folder, release.name):
                    copy_file(os.path.join(folder, sub), os.path.join(path, sub))

            if download_srr:
                srrdb_download_srr(release_name, path)
            if download_nfo:
                srrdb_download_nfo(release_name, path)

        print("")

if __name__ == "__main__":
    main()