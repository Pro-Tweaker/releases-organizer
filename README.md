# Releases Organizer

## Help

```
usage: Movie Release Renamer [-h] [-s {tmdb,srrdb}] [-de] [-ds] [-dn] [-d] [-dy] [folder] [output]

positional arguments:
  folder
  output

options:
  -h, --help            show this help message and exit
  -s {tmdb,srrdb}, --source {tmdb,srrdb}
  -de, --delete-empty   Delete empty folders after move
  -ds, --srr            Download SRR file from ssrDB ⚠️ NOT IMPLEMENTED
  -dn, --nfo            Download NFO file from ssrDB ⚠️ NOT IMPLEMENTED
  -d, --debug           Enable debug output
  -dy, --dry-run        Do not make the moves
```

## Naming Convention
https://jellyfin.org/docs/general/server/media/movies/