import { api } from "./api"

// Editable series details, in form order. Keys match the server (server/metadata.py).
export const METADATA_FIELDS = [
  { key: "title", label: "Title", type: "text", max: 300 },
  { key: "summary", label: "Summary", type: "textarea", max: 5000 },
  { key: "writer", label: "Writer", type: "text", max: 200 },
  { key: "artist", label: "Artist", type: "text", max: 200 },
  { key: "publisher", label: "Publisher", type: "text", max: 200 },
  { key: "genres", label: "Genres", type: "list", hint: "Separate with commas" },
  { key: "year", label: "Year", type: "year" },
  { key: "language", label: "Language", type: "text", max: 20, hint: "e.g. en, ja" },
  { key: "age_rating", label: "Age rating", type: "text", max: 50 },
  { key: "format", label: "Format", type: "text", max: 50, hint: "\"Webtoon\" opens it in vertical scroll" },
  { key: "reading_direction", label: "Reading direction", type: "direction" },
  { key: "web", label: "Link", type: "text", max: 500, hint: "https://…" },
]

export const FIELD_LABELS = Object.fromEntries(METADATA_FIELDS.map((field) => [field.key, field.label]))

// How a value reads in the review list and on the series page
export function formatValue(key, value) {
  if (value === null || value === undefined || value === "" || (Array.isArray(value) && !value.length))
    return "—"
  if (key === "genres") return value.join(", ")
  if (key === "reading_direction") return value === "rtl" ? "Right to left" : "Left to right"
  return String(value)
}

// Polls a background job until it finishes. onProgress gets the job each time.
export async function waitForJob(job, onProgress = () => {}) {
  let current = job
  while (current && (current.status === "queued" || current.status === "running")) {
    onProgress(current)
    await new Promise((resolve) => setTimeout(resolve, 1000))
    current = (await api.job(current.id)).job
  }
  onProgress(current)
  if (current?.status === "failed") throw new Error(current.error || "The job failed")
  return current
}
