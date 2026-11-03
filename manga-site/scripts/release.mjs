// Builds a signed Android APK and publishes it as a GitHub release, which installed apps update from.
//
//   pnpm release 1.2.0 --notes "What changed"     publish version 1.2.0
//   pnpm release 1.2.0 --notes-file notes.md      notes from a file
//   pnpm release 1.2.0 --dry-run                  build the APK only, publish nothing
//
// Needs the signing key described in ~/.mymangalib/release.properties and, to publish, a GitHub
// token with "Contents: read and write" on the releases repo, in GITHUB_TOKEN or ~/.mymangalib/github-token.
import { execSync } from "node:child_process"
import { createHash } from "node:crypto"
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs"
import { homedir } from "node:os"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const REPO = process.env.MYMANGALIB_RELEASE_REPO || "XZcutable/MangaLib"
const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..")
const CONFIG_DIR = join(homedir(), ".mymangalib")
const SIGNING_FILE = process.env.MYMANGALIB_SIGNING || join(CONFIG_DIR, "release.properties")

const fail = (message) => {
  console.error(`\nRelease stopped: ${message}`)
  process.exit(1)
}
const step = (message) => console.log(`\n> ${message}`)
const run = (command, cwd = ROOT, env = {}) =>
  execSync(command, { cwd, stdio: "inherit", env: { ...process.env, ...env } })

// --- Arguments ---
const args = process.argv.slice(2)
const option = (name) => {
  const index = args.indexOf(name)
  return index >= 0 ? args[index + 1] : undefined
}
const version = args.find((arg) => /^\d+\.\d+\.\d+$/.test(arg))
const dryRun = args.includes("--dry-run")
if (!version) fail("Give the new version, e.g. pnpm release 1.2.0")
const notes = option("--notes-file")
  ? readFileSync(resolve(option("--notes-file")), "utf8").trim()
  : (option("--notes") ?? "").trim()

// --- Checks before building anything ---
const packagePath = join(ROOT, "package.json")
const pkg = JSON.parse(readFileSync(packagePath, "utf8"))
const compare = (a, b) => {
  const [x, y] = [a, b].map((v) => v.split(".").map(Number))
  return x[0] - y[0] || x[1] - y[1] || x[2] - y[2]
}
const [major, minor, patch] = version.split(".").map(Number)
if (minor > 99 || patch > 99) fail("Minor and patch numbers go up to 99 (the Android version code is built from them)")
if (compare(version, pkg.version) < 0 || (compare(version, pkg.version) === 0 && !dryRun)) {
  fail(`${version} isn't newer than the current version ${pkg.version}. Phones only install newer versions.`)
}
if (!existsSync(SIGNING_FILE)) fail(`No signing key settings at ${SIGNING_FILE}`)

let token
if (!dryRun) {
  const tokenFile = join(CONFIG_DIR, "github-token")
  token = process.env.GITHUB_TOKEN || (existsSync(tokenFile) ? readFileSync(tokenFile, "utf8").trim() : "")
  if (!token) fail(`No GitHub token. Put one in GITHUB_TOKEN or ${tokenFile}`)
}

const github = async (path, options = {}) => {
  const url = path.startsWith("https://") ? path : `https://api.github.com${path}`
  const response = await fetch(url, {
    ...options,
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      ...options.headers,
    },
  })
  const body = response.status === 204 ? null : await response.json().catch(() => null)
  if (!response.ok) {
    const error = new Error(`GitHub ${response.status}: ${body?.message ?? response.statusText}`)
    error.status = response.status
    throw error
  }
  return body
}

if (!dryRun) {
  step(`Checking ${REPO} on GitHub`)
  const repo = await github(`/repos/${REPO}`).catch((error) => fail(`${error.message}. Check the token can access ${REPO}.`))
  if (!repo.permissions?.push) fail(`The token can read ${REPO} but can't create releases there`)
  const existing = await github(`/repos/${REPO}/releases/tags/v${version}`).catch((error) =>
    error.status === 404 ? null : fail(error.message),
  )
  if (existing) fail(`A release for v${version} already exists: ${existing.html_url}`)
  var defaultBranch = repo.default_branch
}

// --- Build ---
step(`Setting the app version to ${version}`)
pkg.version = version
writeFileSync(packagePath, `${JSON.stringify(pkg, null, 2)}\n`)

step("Building the web app")
// Vite directly (same as "pnpm build"), so the script works whichever pnpm version is installed
run(`"${process.execPath}" node_modules/vite/bin/vite.js build --config vite.figma.config.js`)
step("Copying it into the Android project")
run("npx cap sync android")

step("Building the signed APK")
const androidHome =
  process.env.ANDROID_HOME || [join(process.env.LOCALAPPDATA ?? "", "Android", "Sdk")].find((path) => existsSync(path))
// Full path: pnpm stops Windows from running programs from the current folder by name
const gradle = join(ROOT, "android", process.platform === "win32" ? "gradlew.bat" : "gradlew")
run(`"${gradle}" assembleRelease --console=plain`, join(ROOT, "android"), androidHome ? { ANDROID_HOME: androidHome } : {})

const built = join(ROOT, "android", "app", "build", "outputs", "apk", "release", "app-release.apk")
if (!existsSync(built)) fail("The release APK wasn't signed. Check the settings in release.properties.")
const outDir = join(ROOT, "release")
mkdirSync(outDir, { recursive: true })
const fileName = `mymangalib-${version}.apk`
const apkPath = join(outDir, fileName)
copyFileSync(built, apkPath)
const apk = readFileSync(apkPath)
const sha256 = createHash("sha256").update(apk).digest("hex")
console.log(`\nBuilt ${apkPath}\n  ${(apk.length / 1024 / 1024).toFixed(1)} MB, sha256 ${sha256}`)

if (dryRun) {
  console.log("\nDry run: nothing was published. package.json now says", version)
  process.exit(0)
}

// --- Publish: a draft first, so apps never see a release without its APK ---
step(`Publishing v${version} to ${REPO}`)
const release = await github(`/repos/${REPO}/releases`, {
  method: "POST",
  body: JSON.stringify({
    tag_name: `v${version}`,
    target_commitish: defaultBranch,
    name: `myMangaLib ${version}`,
    body: notes || `myMangaLib ${version}`,
    draft: true,
  }),
})
try {
  const uploadUrl = release.upload_url.replace(/\{.*\}$/, "")
  const asset = await github(`${uploadUrl}?name=${encodeURIComponent(fileName)}`, {
    method: "POST",
    headers: { "Content-Type": "application/vnd.android.package-archive" },
    body: apk,
  })
  if (asset.digest && asset.digest !== `sha256:${sha256}`) throw new Error("GitHub's checksum doesn't match the APK")
  const published = await github(`/repos/${REPO}/releases/${release.id}`, {
    method: "PATCH",
    body: JSON.stringify({ draft: false, make_latest: "true" }),
  })
  console.log(`\nPublished ${published.html_url}`)
  console.log(`Installed apps will offer the update the next time they check.`)
  console.log(`Remember to commit the version change in manga-site/package.json.`)
} catch (error) {
  await github(`/repos/${REPO}/releases/${release.id}`, { method: "DELETE" }).catch(() => {})
  fail(`${error.message}. The draft release was removed; nothing was published.`)
}
