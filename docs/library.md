# Your library

## Folder layout

Each library folder holds one folder (or one archive) per series. Inside a series folder, every chapter or volume is a `.cbz`/`.zip` archive, a `.pdf`, or a folder of images. Files are sorted the way Windows Explorer sorts them, so `v2` comes before `v10`.

```
manga/                         <- the library folder
├── Starlight Courier/
│   ├── Starlight Courier v01.cbz
│   ├── Starlight Courier v02.cbz
│   └── Starlight Courier v03.pdf
├── Paper Dragons/
│   ├── Chapter 1/
│   │   ├── 001.jpg
│   │   └── 002.jpg
│   └── Chapter 2/
└── One Shot.cbz               <- a single-volume series can sit in the library folder itself
```

- **Images:** `.jpg`, `.jpeg`, `.png`, `.webp`, `.jfif`, `.gif` (any letter case).
- **Series details:** a `ComicInfo.xml` inside the archives (title, summary, year, writer, artist, publisher, genres, reading direction) is read on the first scan. Admins can edit details in the app and users can suggest changes; approved edits are written back into the files.
- **Release years** are read from file and folder names that include a year when there's no `ComicInfo.xml`.

## Adding manga

- **Docker:** the folder mounted at `/var/manga` is added and scanned on first start.
- **Later:** copy new series or volumes into the library folder, then **Settings → Library → Scan all** (or the rescan icon next to one folder).
- **Another folder:** **Settings → Library → Add folder**.

A first scan of a big library can take a while. Behind a reverse proxy, raise its timeout (see [reverse-proxy.md](reverse-proxy.md)) so the Scan button doesn't show an error while the scan is still running.

## Moving the library

Manga are stored with their full path, so the server has to be told when files move. Reading progress, scores, tags and read marks carry over either way.

- **A whole library folder moved** (new disk, new mount path): move the files, then use **Settings → Library →** the move icon next to the folder, and pick where it is now. In Docker you can instead change the mount and start once with `--library-moved /old/path=/var/manga` (or `LIBRARY_MOVES={'/old/path' = '/var/manga'}` in `config.toml`). It's skipped once done, so it can stay.
- **One series to another library folder:** open the series, then **Manage → Move to another folder**. The server moves the files itself (copying first when the folders are on different disks).

Don't mount the same files at a second path and add that as another folder: every series would show up twice.

## Crunch and unpack

Folders of loose images take more space and are slower to copy than archives.

- **Crunch** packs a series' image folders into `.cbz` files. Run it from a series' **Manage** section, or for everything with **Settings → Library → Crunch all series…**, which shows what would change before anything happens. It's all-or-nothing per series: the old images are deleted only after the new archives are in place and scanned.
- **Unpack** does the reverse for one series.
- Reading progress and read marks follow the chapters.
- On Windows, files that are open elsewhere can't be deleted. The server remembers them and lists them in **Settings → Library** so you can delete them later.

Moving series, crunching, unpacking and writing details back all change files, so the library must be mounted read-write. The example `compose.yml` mounts it read-only (`:ro`); remove that to use these features.
