# Releases Organizer

Sort scene/P2P movie and TV releases into a clean, [Jellyfin](https://jellyfin.org)-friendly
library. The tool identifies each release against [The Movie Database (TMDB)](https://www.themoviedb.org/) (or
[srrDB](https://www.srrdb.com/) for movies), then creates properly named folders and moves the
media into them. **Your media files are never renamed** — only the surrounding folders are
created.

## Features

- **Movies** — organized as `movies/<lang>/Movie Name (year) [tmdbid-…]/` (or `[imdbid-tt…]`
  with srrDB).
- **TV shows** — organized as `tv/<lang>/Series Name (year) [tmdbid-…]/Season NN/`, following the
  [Jellyfin TV naming convention](https://jellyfin.org/docs/general/server/media/shows/).
  Single episodes, full-season packs, and specials (`Season 00`) are all handled, with each
  file placed into the correct season by its `SxxExx`/`Sxx` marker.
- **Language buckets** — output is split into `movies/` and `tv/`, then a language sub-folder
  (`en`, `fr`, …). Titles in the configured `PREFER_ORIGINAL_TITLE` languages use their original
  title and land in that language's folder; everything else goes under `en`.
- **Collections** — movies that belong to a TMDB collection are nested under a
  `Collection Name [tmdbid-…]` folder.
- **Nested releases** — release folders are scanned recursively, so scene TV season packs that
  nest each episode in its own sub-folder are handled. `Sample`/`Proof`/screenshot folders and
  any `*sample*` files are skipped.
- **Name cleanup (`--normalize`)** — an optional pre-pass that rewrites messy names before
  organizing: spaces → dots, strips parentheses, converts `1x01` episode numbering to `S01E01`
  (which Jellyfin matches far better), and wraps loose media files into folders. It also checks
  that every release ends with a Scene/P2P group tag (`-GROUPNAME`); if one is missing, it prompts
  you for it (suggesting a fix when the group looks like it was just dot-attached, e.g.
  `...x264.EbP` → `...x264-EbP`), then applies the same fix to any file inside the release sharing
  its exact name — the video file, `.nfo`, subtitles, or a same-named sample.
- **AKA titles** — release names using `AKA` / `A.k.a.` (e.g.
  `Foreign.Title.AKA.English.Title.1966…`) are parsed to the title next to the year/season for a
  reliable TMDB match. Works for both movies and TV.
- **Subtitles** — subtitle files (`.srt`, `.vtt`, `.ass`, `.ssa`, `.sub`/`.idx`, `.sup`) are copied
  next to the video. Subtitles inside a release folder are picked up automatically; a loose
  top-level subtitle is matched to its video by shared base name (e.g. `Movie…FLUX.mkv` +
  `Movie…FLUX.FR.srt`) and copied to the same destination.
- **Video files are moved**, everything else (`.nfo`, `.zip`, `Sample/`, …) is left behind.
- **srrDB extras** — optionally download the matching `.srr` and `.nfo` files for movies.
- **Windows-safe** — folder names are stripped of characters Windows disallows.
- **Run summary** — every run (organize, `--check-syntax`/`--check-full`, `--verify-library`/
  `--verify-library-online`) ends with an `=== summary ===` block: counts by type, elapsed time,
  and — for a normal organize run — a warning listing any video files still left in the input
  folder that weren't organized.

> [!NOTE]
> Recognized media extensions — video (moved): `avi`, `iso`, `m2ts`, `m4v`, `mk3d`, `mkv`, `mov`,
> `mp4`, `mpeg`, `mpg`, `ogg`, `ts`, `webm`; subtitles (copied): `srt`, `vtt`, `ass`, `ssa`, `sub`,
> `idx`, `sup`.

## Requirements

- Python 3
- [`requests`](https://pypi.org/project/requests/) — `pip install requests`

Provide your TMDB API key via the `TMDB_API_KEY` environment variable:

Linux/macOS (bash/zsh):

```
export TMDB_API_KEY=<your-key>
```

Windows (PowerShell):

```
$env:TMDB_API_KEY = "<your-key>"
```

Windows (cmd):

```
set TMDB_API_KEY=<your-key>
```

## Configuration

For releases in a language listed in `PREFER_ORIGINAL_TITLE`, the original title is used (and
the title is filed under a per-language folder); otherwise the English title is used. Edit the
list at the top of [`organizer.py`](organizer.py) to fit your library — use TMDB's two-letter
language codes:

```python
PREFER_ORIGINAL_TITLE = [
    'fr',
    'es',
]
```

## Usage

```
usage: Releases Organizer [-h] [-s {tmdb,srrdb}] [-de] [-ds] [-dn] [-d] [-dy] [-n] [-cs] [-cf]
                          [-vl] [-vlo] [--force-reorganize-existing-library]
                          [folder] [output]

positional arguments:
  folder                source folder to scan (default: current directory)
  output                destination library folder (default: output)

options:
  -h, --help            show this help message and exit
  -s, --source {tmdb,srrdb}
                        metadata source for movies (default: tmdb)
  -de, --delete-empty   delete empty folders after move
  -ds, --srr            download SRR file from srrDB (movies)
  -dn, --nfo            download NFO file from srrDB (movies)
  -d, --debug           enable debug output
  -dy, --dry-run        identify and print results without moving anything
  -n, --normalize       pre-normalize names (spaces->dots, strip parens, 1x01->S01E01, folder
                        loose media) before organizing
  -cs, --check-syntax   offline: report how each release parses, no TMDB, no moves
  -cf, --check-full     online: report parsing + TMDB match + destination path, no moves
  -vl, --verify-library
                        offline: audit an already-organized library for naming/structure
                        mistakes, no TMDB, no moves
  -vlo, --verify-library-online
                        online: run --verify-library plus TMDB drift checks (mistyped/dead ids,
                        collection membership changes), no moves
  --force-reorganize-existing-library
                        override the organized-library safety check and run the destructive
                        organize/normalize step anyway (dangerous)
```

> [!IMPORTANT]
> `-dy`/`--dry-run`, `-n`/`--normalize`, `-cs`/`--check-syntax`, and `-cf`/`--check-full` all work
> on **raw, not-yet-organized releases** — pass your input/downloads folder as `folder`.
>
> `-vl`/`--verify-library` and `-vlo`/`--verify-library-online` work the other way around: pass
> your already-organized **output** library as `folder` instead (e.g.
> `python organizer.py ~/Media --verify-library`).

> [!WARNING]
> `--normalize` is destructive — it renames and restructures files in the input folder **in
> place**, with no built-in undo. Always pair it with `--dry-run` first to preview the changes;
> see the notes below for exactly what it touches and how `--dry-run` affects it.

Notes:
- `--source` selects the metadata provider for **movies** only. `tmdb` produces `[tmdbid-…]`
  folders; `srrdb` looks up the IMDb id and produces `[imdbid-tt…]` folders.
  **TV shows always use TMDB** regardless of `--source`.
- When a release matches more than one title, you'll be prompted to pick the correct one
  (except in `--check-full`, which is non-interactive and flags it as `AMBIGUOUS`).
- `--normalize` is a pre-pass that runs before scanning. It modifies the source folder unless
  `--dry-run` is also given, and it applies even when combined with `--check-syntax`/`--check-full`.
  Its group-tag check prompts you interactively even under `--dry-run` (nothing is written to
  disk either way in that case) — press Enter to accept a suggested fix, type a replacement group
  name, or `n` to leave a release as-is.
- `--verify-library` is a different job from `--check-syntax`/`--check-full`: those preview how
  *raw, not-yet-organized* releases would be parsed, while `--verify-library` audits a folder
  that's already in (or supposed to be in) this tool's own output layout — e.g. `movies/en/` or
  `tv/fr/` from a previous run, or a library built by hand. It never contacts TMDB/srrDB and never
  touches the filesystem.
- `--verify-library-online` runs everything `--verify-library` does, plus a live TMDB lookup for
  every tagged movie, series, and collection folder by its `[tmdbid-…]`, to catch drift that
  builds up over time even when the local naming is perfectly formed: a mistyped id, an id whose
  TMDB entry was deleted or merged, a title/year that changed on TMDB, or a movie whose collection
  membership changed (newly added to a collection but filed as standalone, or dropped from/no
  longer matching the collection folder it's filed under). It requires `TMDB_API_KEY` and still
  never touches the filesystem. `[imdbid-tt…]` (srrDB) movie folders are skipped, since they were
  never matched against TMDB in the first place.
- **Organized-library safeguard** — the default organize step and `--normalize` refuse to run if
  the source folder itself, or anything inside it, is already named after this tool's own output
  convention (`Title (Year) [tmdbid-…]`, `Title (Year) [imdbid-tt…]`, or `Collection [tmdbid-…]`).
  This is a content check, not a path/name guess — it exists so a mistake (forgetting
  `--check-syntax`, hitting Enter too early, pointing at the wrong folder) can't silently
  re-process and corrupt an already-built library. `--check-syntax`, `--check-full`,
  `--verify-library`, `--verify-library-online`, and `--dry-run` are always allowed, since none of
  them touch the filesystem. To intentionally re-run the organize step over an existing library
  anyway, pass `--force-reorganize-existing-library`.

## Examples

Organize the current folder into `./output`:

```
python organizer.py
```

Organize a downloads folder into a media library, removing emptied source folders:

```
python organizer.py ~/Downloads ~/Media --delete-empty
```

Preview what would happen without moving files:

```
python organizer.py ~/Downloads ~/Media --dry-run
```

Clean up messy human-named files first, then organize:

```
python organizer.py ~/Downloads ~/Media --normalize
```

Check how a folder parses without touching the network or the files:

```
python organizer.py ~/Downloads --check-syntax
```

Verify TMDB matches and preview destination paths, no moves:

```
python organizer.py ~/Downloads ~/Media --check-full
```

Audit an already-organized library for naming/structure mistakes (typos, bad `Season NN`
padding, missing `[tmdbid-…]`/`[imdbid-…]` tags, misplaced episode files, …). Fully offline,
read-only, prints only problems (in red) plus a final summary:

```
python organizer.py ~/Media --verify-library
```

Same audit, plus a live check against TMDB for every tagged folder (mistyped/dead ids, title or
year drift, collection membership changes). Needs `TMDB_API_KEY`, still read-only:

```
python organizer.py ~/Media --verify-library-online
```

Use srrDB (IMDb ids) and grab the .nfo for each movie:

```
python organizer.py ~/Downloads ~/Media --source srrdb --nfo
```

## Input structure

> [!TIP]
> This is the folder a standard run (no options) scans. `-dy`/`--dry-run` and `-n`/`--normalize`
> are optional flags for a real run; `-cs`/`--check-syntax` and `-cf`/`--check-full` are separate,
> read-only modes for troubleshooting/debugging how a release parses — not part of a normal run.

The tool scans a source folder for scene/P2P style releases — a mix of self-contained release
folders and loose media files is fine, in any combination:

```
downloads/
├── Sicario.2015.1080p.BluRay.x264-SPARKS/
│   ├── Sicario.2015.1080p.BluRay.x264-SPARKS.mkv
│   ├── Sicario.2015.1080p.BluRay.x264-SPARKS.nfo
│   └── Sample/
│       └── Sicario.2015.1080p.BluRay.x264-SPARKS.sample.mkv
├── Amelie.2001.1080p.BluRay.x264-GROUP.mkv
├── Amelie.2001.1080p.BluRay.x264-GROUP.FR.srt
├── The.Mandalorian.2019.S02E05.2160p.WEB.H265-GROUP.mkv
└── Lupin.2021.S01.1080p.WEB-GROUP/
    ├── Lupin.2021.S01E01.1080p.WEB-GROUP.mkv
    ├── Lupin.2021.S01E02.1080p.WEB-GROUP.mkv
    └── Proof/
        └── proof.jpg
```

- **Release folders** (`Sicario.2015…SPARKS/`, `Lupin.2021.S01…GROUP/`) are matched against TMDB
  (or srrDB) by the folder name; **everything valid inside is moved**, `.nfo`/other extras are left
  behind, and `Sample`/`Proof`/screenshot folders are skipped entirely.
- **Loose files** (`Amelie.2001…GROUP.mkv`, `The.Mandalorian.2019.S02E05…mkv`) are matched by
  their own file name and **moved** individually. A loose subtitle sharing the same base name
  (`Amelie.2001…GROUP.FR.srt`) is picked up automatically and copied alongside its video.
  Season-pack folders can nest each episode in its own sub-folder — the tool scans recursively
  and flattens the result.
- Messy, human-renamed folders (spaces, `1x01` episode numbering, loose files not yet in their
  own folder) can be cleaned up first with `--normalize` — see [Usage](#usage).

## Output structure

> [!TIP]
> This is the folder you'd point `-vl`/`--verify-library` and `-vlo`/`--verify-library-online` at.
> Running them right after this tool organizes something isn't very useful — there's nothing to
> catch yet. They're meant for auditing a **hand-built** library, or for periodically re-checking
> your own output library over time, since TMDB titles, years, and collection memberships can
> change long after a release was first organized. A quarterly or twice-a-year re-run of
> `--verify-library-online` is a reasonable cadence.

> [!NOTE]
> The output folder is **created** by the tool; the input folder is never deleted. These stay two
> separate folders — only video files are *moved* and subtitles are *copied* from the input
> folder into the output library. Everything else (`.nfo`, `.zip`, sample files, and the emptied
> release folders themselves) is left behind in the input folder unless you also pass
> `--delete-empty`.

```
output/
├── movies/
│   ├── en/
│   │   └── Sicario Collection [tmdbid-496796]/
│   │       └── Sicario (2015) [tmdbid-273481]/
│   │           └── Sicario.2015.1080p.BluRay.x264-SPARKS.mkv
│   └── fr/
│       └── Le fabuleux destin d'Amélie Poulain (2001) [tmdbid-194]/
│           └── Amelie.2001.1080p.BluRay.x264-GROUP.mkv
└── tv/
    ├── en/
    │   └── The Mandalorian (2019) [tmdbid-82856]/
    │       └── Season 02/
    │           └── The.Mandalorian.2019.S02E05.2160p.WEB.H265-GROUP.mkv
    └── fr/
        └── Lupin (2021) [tmdbid-96677]/
            └── Season 01/
                ├── Lupin.2021.S01E01.1080p.WEB-GROUP.mkv
                └── Lupin.2021.S01E02.1080p.WEB-GROUP.mkv
```

## Naming convention

Folder names follow the Jellyfin conventions:

- Movies — https://jellyfin.org/docs/general/server/media/movies/
- TV shows — https://jellyfin.org/docs/general/server/media/shows/
- Metadata Provider Identifiers — https://jellyfin.org/docs/general/server/metadata/identifiers/
