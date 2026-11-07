"""The languages a series can be marked with. The stored value is the code; ComicInfo.xml gets it as
LanguageISO. "mul" is the standard code for several languages; "ai" is this app's own."""
from typing import Optional

LANGUAGES = [
    {"code": "en", "name": "English"},
    {"code": "ja", "name": "Japanese"},
    {"code": "ko", "name": "Korean"},
    {"code": "zh", "name": "Chinese"},
    {"code": "es", "name": "Spanish"},
    {"code": "ai", "name": "AI Translated"},
    {"code": "mul", "name": "Mixed"},
]
CODES = {language["code"] for language in LANGUAGES}

# Other ways files and people write these languages
_ALIASES = {
    "en": ("eng", "english"),
    "ja": ("jp", "jpn", "japanese"),
    "ko": ("kr", "kor", "korean"),
    "zh": ("cn", "chi", "zho", "chinese", "zh-hans", "zh-hant", "zh-cn", "zh-tw", "zh-hk"),
    "es": ("spa", "spanish", "espanol", "español", "es-419"),
    "ai": ("ai translated", "ai-translated", "ai_translated", "machine translated", "mtl"),
    "mul": ("mixed", "multi", "multiple", "multilingual"),
}
_LOOKUP = {code: code for code in CODES}
_LOOKUP.update({alias: code for code, aliases in _ALIASES.items() for alias in aliases})

def normalize(value: Optional[str]) -> Optional[str]:
    """The code for a language as written in a file or by a person ("English", "en-US", "jp"...).
    Values that can't be matched come back unchanged; empty ones as None."""
    text = (value or "").strip()
    if not text:
        return None
    key = text.lower()
    if key in _LOOKUP:
        return _LOOKUP[key]
    # Region variants like en-US or pt_BR
    base = key.replace("_", "-").split("-")[0]
    return _LOOKUP.get(base, text)

def search_code(word: str) -> Optional[str]:
    """The code a language: search value means: a name, a code or an alias."""
    key = word.strip().lower()
    for language in LANGUAGES:
        if key == language["name"].lower():
            return language["code"]
    return _LOOKUP.get(key)
