// A series' language is one of these codes (server/languages.py). Newer servers also send the list
// in /server/info "languages"; this copy covers older ones.
export const LANGUAGES = [
  { code: "en", name: "English" },
  { code: "ja", name: "Japanese" },
  { code: "ko", name: "Korean" },
  { code: "zh", name: "Chinese" },
  { code: "es", name: "Spanish" },
  { code: "ai", name: "AI Translated" },
  { code: "mul", name: "Mixed" },
]

// Values that aren't a known code (set before the list was fixed) are shown as they are
export function languageName(code, languages = LANGUAGES) {
  return languages.find((language) => language.code === code)?.name ?? code
}
