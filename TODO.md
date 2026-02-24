 Current Project:
1. Separate paths from Manga
 - Paths will be locations manga is stored in. If a location is found, that will be cached. If a cached location is found, that will be checked first.
   If the cache fails, then it will check all known locations and cache a hit, otherwise it will be a fail.
2. Directory handling. Have a limit of how many directories are show in the popup. Search?
3. Seach based on archive type

Change redirects to variables with string names in code
Improve performance of scanning

Bugs:
- Improve performance of folder picker when there is a lot of folders in a directory
- Better indication of the scanning process.
- Servername doesnt seemed to be honored

Next Task:
Have long titles show the full title on hover and give an indication when hovered
Add section at bottom of pages for related manga/chapters?
Add config to define related manga/chapters
Make infinite scroll optional and set by the user in settings and add pagation support
Hide tags toggle

Next Hard Tasks:
Add pending or verified status to uploading manga option

Features needs for MVP:
- users and password and registration
- way to add manga to the library
- way to view manga
- Track what is read and tags, and editable
- Random and Random unread
- search for names, tags, and special tags
- Can edit manga names
- Add Chapters to manga info
- Add way to delete manga, or mark deleted
- User History
- Mobile experience parity
- To read list
- Favorites list
- Add cbz support

Future Tasks:
Add a play options 1s,3s, 5s
eventually add pdf support
Impelement way to sync the folder names with the title names

Polish:
make site look better

Make paths relative, so data can be moved safely
Add versioning to site

