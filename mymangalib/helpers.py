import os, re

def validate_string(string: str) -> None:
    if string is None:
        raise ValueError("Invalid None string")

    string = str.strip(string)
    if string == "":
        raise ValueError("String cannot be empty")


convert = lambda text: int(text) if str.isdigit(text) else str.lower(text)
alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', str.casefold(key))]
def _path_sort(path: str):
    if os.path.isdir(path):
        return alphanum_key(str.casefold(path))
    else:
        return alphanum_key(os.path.splitext(str.casefold(path))[0])

def sort_paths(path_list: list[str]):
    path_list.sort(key=_path_sort)

# A year in brackets, as in "Title v01 (2019) (Digital)"
YEAR_PATTERN = re.compile(r"[\(\[]((?:19|20)\d{2})[\)\]]")
def release_year_from_names(names) -> int | None:
    """The earliest bracketed year in a manga's folder, file or chapter names, or None if there isn't one."""
    years = [int(year) for name in names if name for year in YEAR_PATTERN.findall(name)]
    return min(years) if years else None
