# Releases Organizer

Sort scene/P2P movie and TV releases into a clean, [Jellyfin](https://jellyfin.org)-friendly
library. The tool identifies each release against [TMDB](https://www.themoviedb.org/) (or
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
  (which Jellyfin matches far better), and wraps loose media files into folders.
- **AKA titles** — release names using `AKA` / `A.k.a.` (e.g.
  `Foreign.Title.AKA.English.Title.1966…`) are parsed to the title next to the year/season for a
  reliable TMDB match. Works for both movies and TV.
- **Subtitles** — `.srt` files are copied next to the video. Subtitles inside a release folder are
  picked up automatically; a loose top-level subtitle is matched to its video by shared base name
  (e.g. `Movie…FLUX.mkv` + `Movie…FLUX.FR.srt`) and copied to the same destination.
- **Video files are moved**, everything else (`.nfo`, `.zip`, `Sample/`, …) is left behind.
- **srrDB extras** — optionally download the matching `.srr` and `.nfo` files for movies.
- **Windows-safe** — folder names are stripped of characters Windows disallows.

Recognized media extensions: `avi`, `iso`, `m2ts`, `mk3d`, `mkv`, `mov`, `mp4`, `mpeg`, `mpg`,
`ts` (moved); `srt` (copied).

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

## Usage

```
usage: Movie Release Renamer [-h] [-s {tmdb,srrdb}] [-de] [-ds] [-dn] [-d] [-dy] [-n] [-cs] [-cf] [folder] [output]

positional arguments:
  folder                source folder to scan (default: current directory)
  output                destination library folder (default: output)

options:
  -h, --help            show this help message and exit
  -s, --source {tmdb,srrdb}
                        metadata source for movies (default: tmdb)
  -de, --delete-empty   delete source folders once empty after the move
  -ds, --srr            download the .srr file from srrDB (movies)
  -dn, --nfo            download the .nfo file from srrDB (movies)
  -d, --debug           enable debug output
  -dy, --dry-run        identify and print results without moving anything
  -n, --normalize       pre-normalize names (spaces->dots, strip parens, 1x01->S01E01, folder loose media) before organizing
  -cs, --check-syntax   offline: report how each release parses (no TMDB, no moves)
  -cf, --check-full     report parsing + TMDB match + destination path (no moves)
```

Notes:
- `--source` selects the metadata provider for **movies** only. `tmdb` produces `[tmdbid-…]`
  folders; `srrdb` looks up the IMDb id and produces `[imdbid-tt…]` folders.
  **TV shows always use TMDB** regardless of `--source`.
- When a release matches more than one title, you'll be prompted to pick the correct one
  (except in `--check-full`, which is non-interactive and flags it as `AMBIGUOUS`).
- `--normalize` is a pre-pass that runs before scanning. It modifies the source folder unless
  `--dry-run` is also given, and it applies even when combined with `--check-syntax`/`--check-full`.

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

Use srrDB (IMDb ids) and grab the .nfo for each movie:

```
python organizer.py ~/Downloads ~/Media --source srrdb --nfo
```

## Output structure

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
