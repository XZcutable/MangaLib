// The search language, as the search box sees it while you type. The server's parser is
// mymangalib/server/search.py; keep the keys and their operators in step with KEYS there.
//
//   tag:fantasy|action   either      tag:fantasy&action   both      tag:"slice of life"
//   nsfw:gore   nsfw: (any NSFW)     language:english|japanese      is:unread
//   -tag:romance   -nsfw   -word     "a phrase"
//
// Future keys (rating:, author:, year:...) are one more entry here with a value source.

export const KEYS = [
  { key: "tag", ops: "|&", source: "tags", label: "Tags", notLabel: "Without these tags" },
  { key: "nsfw", ops: "|&", source: "nsfwTags", label: "NSFW tags", notLabel: "Without these NSFW tags", emptyMeansAny: true },
  { key: "language", ops: "|", source: "languages", label: "Language", notLabel: "Not in this language" },
  { key: "is", ops: "|&", source: "statuses", label: "Reading status", notLabel: "Not in this reading state" },
]
const KEY_BY_NAME = Object.fromEntries(KEYS.map((spec) => [spec.key, spec]))

export const STATUSES = [
  { value: "unread", label: "Not finished" },
  { value: "read", label: "Finished" },
  { value: "progress", label: "Started, not finished" },
  { value: "tagged", label: "Has tags" },
  { value: "untagged", label: "No tags yet" },
]

const unquote = (text) => text.replaceAll('"', "").trim()
const quoteCount = (text) => (text.match(/"/g) ?? []).length

// Where each space-separated token starts and ends (spaces inside double quotes don't split)
function tokens(text) {
  const result = []
  let start = null
  let quoted = false
  for (let i = 0; i <= text.length; i++) {
    const char = text[i]
    if (char === '"') quoted = !quoted
    const isSpace = char === undefined || (!quoted && /\s/.test(char))
    if (isSpace && start !== null) {
      result.push({ start, end: i })
      start = null
    } else if (!isSpace && start === null) {
      start = i
    }
  }
  return result
}

// Splits on any of `separators` outside quotes, keeping positions
function segments(text, separators) {
  const result = []
  let start = 0
  let quoted = false
  for (let i = 0; i < text.length; i++) {
    if (text[i] === '"') quoted = !quoted
    else if (!quoted && separators.includes(text[i])) {
      result.push({ start, end: i })
      start = i + 1
    }
  }
  result.push({ start, end: text.length })
  return result
}

function keyOf(body) {
  const colon = body.indexOf(":")
  const quote = body.indexOf('"')
  if (colon <= 0 || (quote !== -1 && quote < colon)) return null
  const spec = KEY_BY_NAME[body.slice(0, colon).toLowerCase()]
  return spec ? { spec, colon } : null
}

/**
 * What the caret is in:
 *  { kind: "value", spec, negated, partial, start, end, used }  a value after key:
 *  { kind: "key", negated, partial, start, end }                a word that could become a key
 *  null                                                         nothing to suggest
 * start/end are the part of the text a suggestion replaces.
 */
export function contextAt(text, caret) {
  const token = tokens(text).find((t) => t.start <= caret && caret <= t.end)
  if (!token) return null
  const raw = text.slice(token.start, token.end)
  const negated = raw.startsWith("-")
  const offset = token.start + (negated ? 1 : 0)
  const body = text.slice(offset, token.end)
  const found = keyOf(body)

  if (found && caret > offset + found.colon) {
    const valueStart = offset + found.colon + 1
    const value = text.slice(valueStart, token.end)
    // The server reads & as | for keys without "and", so both always separate values
    const parts = segments(value, "|&")
    const local = caret - valueStart
    const part = parts.find((p) => p.start <= local && local <= p.end) ?? parts[parts.length - 1]
    const used = parts.filter((p) => p !== part).map((p) => unquote(value.slice(p.start, p.end)).toLowerCase())
    return {
      kind: "value",
      spec: found.spec,
      negated,
      partial: unquote(value.slice(part.start, local)).toLowerCase(),
      start: valueStart + part.start,
      end: valueStart + part.end,
      used: used.filter(Boolean),
    }
  }
  if (found || body.includes('"') || body.includes(":")) return null
  // Only the start of a word suggests keys, and a lone word must have a letter typed first
  const partial = text.slice(offset, caret).toLowerCase()
  if (!partial && !negated) return null
  return { kind: "key", negated, partial, start: token.start, end: token.end }
}

// Puts a chosen suggestion in. Returns { text, caret }.
export function applySuggestion(text, context, insert) {
  const before = text.slice(0, context.start)
  let after = text.slice(context.end)
  // A finished word (like -nsfw) gets a space after it, unless one is already there
  if (insert.endsWith(" ") && after.startsWith(" ")) after = after.slice(1)
  return { text: before + insert + after, caret: before.length + insert.length }
}

export function formatValue(value) {
  return /\s/.test(value) ? `"${value}"` : value
}

/**
 * The user typed a space at `caret` (in the text before the space was added). Closes the token there:
 * drops trailing | and &, and an empty key: that would do nothing. Returns { text, caret } with the
 * space added, or null when the space is part of the value (inside quotes) and nothing changes.
 */
export function endContext(text, caret) {
  const token = tokens(text).find((t) => t.start < caret && caret === t.end)
  if (!token) return null
  let head = text.slice(token.start, caret)
  if (quoteCount(head) % 2 === 1) return null
  const original = head
  head = head.replace(/[|&]+$/, "")
  const negated = head.startsWith("-")
  const found = keyOf(negated ? head.slice(1) : head)
  if (found && found.colon === (negated ? head.length - 2 : head.length - 1) && !found.spec.emptyMeansAny) head = ""
  if (head === original) return null
  const before = text.slice(0, token.start) + head
  const rest = text.slice(caret).replace(/^\s*/, "")
  const space = head ? " " : ""
  return { text: before + space + rest, caret: before.length + space.length }
}

/** Suggestions for a context from the loaded value lists: [{ label, insert, detail }] */
export function suggestionsFor(context, sources, limit = 8) {
  if (!context) return []
  if (context.kind === "key") {
    const dash = context.negated ? "-" : ""
    const items = KEYS.flatMap((spec) => {
      const list = [{ name: spec.key, insert: `${dash}${spec.key}:`, detail: context.negated ? spec.notLabel : spec.label }]
      if (spec.key === "nsfw" && context.negated) list.unshift({ name: "nsfw", insert: "-nsfw ", detail: "Hide everything NSFW" })
      return list
    })
    return items
      .filter((item) => item.name.startsWith(context.partial))
      .slice(0, limit)
      .map((item) => ({ label: item.insert.trim(), insert: item.insert, detail: item.detail }))
  }

  const values = sources[context.spec.source] ?? []
  // A value typed out in full needs no suggestion
  if (values.some((item) => item.value === context.partial)) return []
  const fresh = values.filter((item) => !context.used.includes(item.value))
  const starts = fresh.filter((item) => item.value.startsWith(context.partial))
  const contains = context.partial ? fresh.filter((item) => !item.value.startsWith(context.partial) && item.value.includes(context.partial)) : []
  return [...starts, ...contains].slice(0, limit).map((item) => ({
    label: item.label ?? item.value,
    insert: formatValue(item.value),
    detail: item.detail,
  }))
}

// Characters a key doesn't take (language: has no "and"). Returns a hint to show, or null.
export function blockedCharacter(context, char) {
  if (context?.kind !== "value" || !"|&".includes(char)) return null
  if (context.spec.ops.includes(char)) return null
  return `${context.spec.key}: takes only | (or)`
}
