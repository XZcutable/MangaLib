// Releases a new version of myMangaLib (server and app share the version):
//   - a signed Android APK, which installed apps update from
//   - the server bundle (mymangalib-server-X.Y.Z.tar.gz), which running servers download and apply from Settings
//   - the Docker image ghcr.io/xzcutable/mangalib, tagged X.Y.Z, X.Y, X and latest
//
//   pnpm release 1.2.0 --notes "What changed"     publish version 1.2.0
//   pnpm release 1.2.0 --notes-file notes.md      notes from a file
//   pnpm release 1.2.0 --dry-run                  build everything, publish nothing
//   pnpm release 1.2.0 --skip-docker              don't build or push the Docker image
//
// Releasing through GitHub Actions instead (.github/workflows/release.yml):
//   pnpm release 1.2.0 --tag --notes "What changed"   set the version, commit it and tag v1.2.0 (nothing is
//                                                     built or pushed); then: git push origin main v1.2.0
//   The tag reaches GitHub through the GitLab mirror, and the workflow runs this script with --ci, which
//   builds the committed version as-is and stops if the tag and the version in the files differ.
//
// Needs the signing key described in ~/.mymangalib/release.properties and, to publish:
//   - a GitHub token with "Contents: read and write" on the releases repo, in GITHUB_TOKEN or
//     ~/.mymangalib/github-token
//   - for the Docker image, a classic token with the write:packages scope (GHCR doesn't take fine-grained
//     tokens), in GHCR_TOKEN or ~/.mymangalib/ghcr-token. With GHCR_USER set too (GitHub Actions' own
//     token), the scope check is skipped.
// Run it from manga-site (pnpm release) or the repo root (node scripts/release.mjs).
// Docker runs inside WSL on Windows (MYMANGALIB_WSL_DISTRO, default Ubuntu) and directly elsewhere.
import { execSync, spawnSync } from "node:child_process"
import { createHash } from "node:crypto"
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs"
import { homedir } from "node:os"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const REPO = process.env.MYMANGALIB_RELEASE_REPO || "XZcutable/MangaLib"
const IMAGE = process.env.MYMANGALIB_IMAGE || "ghcr.io/xzcutable/mangalib"
const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..")
const APP_DIR = join(REPO_ROOT, "manga-site")
const CONFIG_DIR = join(homedir(), ".mymangalib")
const SIGNING_FILE = process.env.MYMANGALIB_SIGNING || join(CONFIG_DIR, "release.properties")

const fail = (message) => {
  console.error(`\nRelease stopped: ${message}`)
  process.exit(1)
}
const step = (message) => console.log(`\n> ${message}`)
const run = (command, cwd = APP_DIR, env = {}) =>
  execSync(command, { cwd, stdio: "inherit", env: { ...process.env, ...env } })

// --- Arguments ---
const args = process.argv.slice(2)
const option = (name) => {
  const index = args.indexOf(name)
  return index >= 0 ? args[index + 1] : undefined
}
const version = args.find((arg) => /^\d+\.\d+\.\d+$/.test(arg))
const dryRun = args.includes("--dry-run")
const skipDocker = args.includes("--skip-docker")
const tagOnly = args.includes("--tag")
const ci = args.includes("--ci")
if (!version) fail("Give the new version, e.g. pnpm release 1.2.0")
const notes = option("--notes-file")
  ? readFileSync(resolve(option("--notes-file")), "utf8").trim()
  : (option("--notes") ?? "").trim()

// --- Checks before building anything ---
const packagePath = join(APP_DIR, "package.json")
const pkg = JSON.parse(readFileSync(packagePath, "utf8"))
const compare = (a, b) => {
  const [x, y] = [a, b].map((v) => v.split(".").map(Number))
  return x[0] - y[0] || x[1] - y[1] || x[2] - y[2]
}
const [major, minor, patch] = version.split(".").map(Number)
if (minor > 99 || patch > 99) fail("Minor and patch numbers go up to 99 (the Android version code is built from them)")
// The same version is fine: after a --dry-run, package.json already has it. A version that was already
// published is caught by the GitHub check below.
if (compare(version, pkg.version) < 0) {
  fail(`${version} is older than the current version ${pkg.version}. Phones only install newer versions.`)
}

const pyprojectPath = join(REPO_ROOT, "pyproject.toml")
const pyprojectVersion = () => readFileSync(pyprojectPath, "utf8").match(/^version = "(.*)"\r?$/m)?.[1]
const setVersion = () => {
  pkg.version = version
  writeFileSync(packagePath, `${JSON.stringify(pkg, null, 2)}\n`)
  const pyproject = readFileSync(pyprojectPath, "utf8")
  if (!pyprojectVersion()) fail("No version line in pyproject.toml")
  writeFileSync(pyprojectPath, pyproject.replace(/^version = ".*"(\r?)$/m, `version = "${version}"$1`))
}

// --tag: commit the version and tag it here; GitHub Actions builds and publishes it once the tag arrives
if (tagOnly) {
  const git = (command) => execSync(`git ${command}`, { cwd: REPO_ROOT, encoding: "utf8" }).trim()
  const tag = `v${version}`
  if (git(`tag --list ${tag}`)) fail(`The tag ${tag} already exists`)
  const versionFiles = '"manga-site/package.json" "pyproject.toml"'
  if (git(`status --porcelain -- ${versionFiles}`)) fail("package.json or pyproject.toml has uncommitted changes")
  if (pkg.version !== version || pyprojectVersion() !== version) {
    step(`Setting the version to ${version} and committing it`)
    setVersion()
    git(`commit -q -m "Version ${version}" -- ${versionFiles}`)
  }
  step(`Tagging ${tag}`)
  execSync(`git tag -a ${tag} -F -`, { cwd: REPO_ROOT, input: notes || `myMangaLib ${version}` })
  const branch = git("rev-parse --abbrev-ref HEAD")
  console.log(`\nTagged ${tag} on ${branch}. Publish it with:\n  git push origin ${branch} ${tag}`)
  console.log("GitLab mirrors it to GitHub, where the release workflow builds and publishes it.")
  process.exit(0)
}

// --ci: build exactly what was committed and tagged
if (ci && (pkg.version !== version || pyprojectVersion() !== version)) {
  fail(
    `The tag says ${version}, but package.json says ${pkg.version} and pyproject.toml says ${pyprojectVersion()}. ` +
      "Make the tag with: pnpm release X.Y.Z --tag",
  )
}

if (!existsSync(SIGNING_FILE)) fail(`No signing key settings at ${SIGNING_FILE}`)

// Python for packing the server bundle: the project's .venv, or PYTHON
const python =
  process.env.PYTHON ||
  [join(REPO_ROOT, ".venv", "Scripts", "python.exe"), join(REPO_ROOT, ".venv", "bin", "python")].find((path) =>
    existsSync(path),
  ) ||
  "python3"

// Docker: inside WSL on Windows (Docker isn't installed on Windows itself), directly elsewhere
const wslDistro = process.env.MYMANGALIB_WSL_DISTRO || "Ubuntu"
const toWslPath = (path) =>
  path.replace(/^([A-Za-z]):/, (_, drive) => `/mnt/${drive.toLowerCase()}`).split("\\").join("/")
const docker = (args, input) => {
  const options = { cwd: REPO_ROOT, stdio: [input ? "pipe" : "inherit", "inherit", "inherit"], input }
  const [command, commandArgs] =
    process.platform === "win32"
      ? ["wsl", ["-d", wslDistro, "--cd", toWslPath(REPO_ROOT), "--", "docker", ...args]]
      : ["docker", args]
  const result = spawnSync(command, commandArgs, options)
  if (result.status !== 0) throw new Error(`docker ${args[0]} failed`)
}

let token
if (!dryRun) {
  const tokenFile = join(CONFIG_DIR, "github-token")
  token = process.env.GITHUB_TOKEN || (existsSync(tokenFile) ? readFileSync(tokenFile, "utf8").trim() : "")
  if (!token) fail(`No GitHub token. Put one in GITHUB_TOKEN or ${tokenFile}`)
}

let ghcrToken
if (!dryRun && !skipDocker) {
  const tokenFile = join(CONFIG_DIR, "ghcr-token")
  ghcrToken = process.env.GHCR_TOKEN || (existsSync(tokenFile) ? readFileSync(tokenFile, "utf8").trim() : "")
  if (!ghcrToken) {
    fail(
      "No token for the Docker image. Make a classic GitHub token with the write:packages scope and put it in " +
        `GHCR_TOKEN or ${tokenFile}, or add --skip-docker.`,
    )
  }
}

const github = async (path, options = {}) => {
  const url = path.startsWith("https://") ? path : `https://api.github.com${path}`
  const request = () =>
    fetch(url, {
      ...options,
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${token}`,
        "X-GitHub-Api-Version": "2022-11-28",
        ...options.headers,
      },
    })
  // GitHub closes connections left idle during the build (HTTP/2 GOAWAY), and fetch then fails without
  // an answer. A failure with no answer is retried on a new connection.
  let response
  for (let attempt = 1; ; attempt++) {
    try {
      response = await request()
      break
    } catch (error) {
      if (attempt >= 3 || !options.retry) throw error
      console.log(`  GitHub connection dropped (${error.cause?.message ?? error.message}); trying again`)
      await new Promise((resolve) => setTimeout(resolve, 2000 * attempt))
    }
  }
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
  // GitHub Actions' own token gets no "permissions" in this answer; its rights come from the workflow
  if (repo.permissions && !repo.permissions.push) fail(`The token can read ${REPO} but can't create releases there`)
  const existing = await github(`/repos/${REPO}/releases/tags/v${version}`).catch((error) =>
    error.status === 404 ? null : fail(error.message),
  )
  if (existing) fail(`A release for v${version} already exists: ${existing.html_url}`)
  var defaultBranch = repo.default_branch

  // GitHub Actions' token can't read /user; the workflow passes the account name as GHCR_USER
  if (!skipDocker && process.env.GHCR_USER) var ghcrUser = process.env.GHCR_USER
  else if (!skipDocker) {
    step("Checking the Docker image token")
    const response = await fetch("https://api.github.com/user", { headers: { Authorization: `Bearer ${ghcrToken}` } })
    if (!response.ok) fail(`The Docker image token doesn't work (GitHub ${response.status})`)
    const scopes = (response.headers.get("x-oauth-scopes") || "").split(",").map((scope) => scope.trim())
    if (!scopes.includes("write:packages")) {
      fail("The Docker image token needs the write:packages scope (a classic token; GHCR doesn't take fine-grained ones)")
    }
    var ghcrUser = (await response.json()).login
  }
}

// --- Build ---
if (!ci) {
  step(`Setting the version to ${version} (app and server)`)
  setVersion()
}

step("Building the web app")
// Vite directly (same as "pnpm build"), so the script works whichever pnpm version is installed
run(`"${process.execPath}" node_modules/vite/bin/vite.js build`)
step("Copying it into the Android project")
run("npx cap sync android")

step("Building the signed APK")
const androidHome =
  process.env.ANDROID_HOME || [join(process.env.LOCALAPPDATA ?? "", "Android", "Sdk")].find((path) => existsSync(path))
// Full path: pnpm stops Windows from running programs from the current folder by name
const gradle = join(APP_DIR, "android", process.platform === "win32" ? "gradlew.bat" : "gradlew")
run(`"${gradle}" assembleRelease --console=plain`, join(APP_DIR, "android"), androidHome ? { ANDROID_HOME: androidHome } : {})

const built = join(APP_DIR, "android", "app", "build", "outputs", "apk", "release", "app-release.apk")
if (!existsSync(built)) fail("The release APK wasn't signed. Check the settings in release.properties.")
const outDir = join(APP_DIR, "release")
mkdirSync(outDir, { recursive: true })
const fileName = `mymangalib-${version}.apk`
const apkPath = join(outDir, fileName)
copyFileSync(built, apkPath)
const apk = readFileSync(apkPath)
const sha256 = createHash("sha256").update(apk).digest("hex")
console.log(`\nBuilt ${apkPath}\n  ${(apk.length / 1024 / 1024).toFixed(1)} MB, sha256 ${sha256}`)

step("Packing the server bundle")
const bundleName = `mymangalib-server-${version}.tar.gz`
const bundlePath = join(outDir, bundleName)
run(`"${python}" -I "${join(REPO_ROOT, "scripts", "make_server_bundle.py")}" ${version} "${join(APP_DIR, "dist")}" "${bundlePath}"`)
const bundle = readFileSync(bundlePath)
const bundleSha256 = createHash("sha256").update(bundle).digest("hex")

const imageTags = [version, `${major}.${minor}`, `${major}`, "latest"].map((tag) => `${IMAGE}:${tag}`)
if (!skipDocker) {
  step(`Building the Docker image ${IMAGE}:${version}`)
  try {
    docker(["build", "--build-arg", `VERSION=${version}`, ...imageTags.flatMap((tag) => ["-t", tag]), "."])
  } catch (error) {
    fail(`${error.message}. Is Docker running${process.platform === "win32" ? ` in WSL (${wslDistro})` : ""}?`)
  }
}

if (dryRun) {
  console.log("\nDry run: nothing was published. package.json and pyproject.toml now say", version)
  console.log(`Server bundle: ${bundlePath}`)
  if (!skipDocker) console.log(`Docker image (local only): ${imageTags.join(", ")}`)
  process.exit(0)
}

// --- Publish: a draft first, so apps never see a release without its APK ---
step(`Publishing v${version} to ${REPO}`)
// A draft from a dropped connection may exist already; drafts can't be found by tag, so list them
const findDraft = async () =>
  (await github(`/repos/${REPO}/releases?per_page=20`, { retry: true })).find(
    (candidate) => candidate.draft && candidate.tag_name === `v${version}`,
  )
const createDraft = () =>
  github(`/repos/${REPO}/releases`, {
    method: "POST",
    body: JSON.stringify({
      tag_name: `v${version}`,
      target_commitish: defaultBranch,
      name: `myMangaLib ${version}`,
      body: notes || `myMangaLib ${version}`,
      draft: true,
    }),
  })
let release = await findDraft()
for (let attempt = 1; !release; attempt++) {
  try {
    release = await createDraft()
  } catch (error) {
    if (error.status || attempt >= 3) fail(error.message)
    console.log(`  GitHub connection dropped (${error.cause?.message ?? error.message}); trying again`)
    await new Promise((resolve) => setTimeout(resolve, 2000 * attempt))
    release = await findDraft()
  }
}
try {
  const uploadUrl = release.upload_url.replace(/\{.*\}$/, "")
  const upload = async (name, type, data, checksum) => {
    const asset = await github(`${uploadUrl}?name=${encodeURIComponent(name)}`, {
      method: "POST",
      headers: { "Content-Type": type },
      body: data,
    })
    if (asset.digest && asset.digest !== `sha256:${checksum}`) throw new Error(`GitHub's checksum doesn't match ${name}`)
  }
  await upload(fileName, "application/vnd.android.package-archive", apk, sha256)
  // Servers only apply a bundle whose checksum GitHub lists (the asset's digest)
  await upload(bundleName, "application/gzip", bundle, bundleSha256)

  if (!skipDocker) {
    step(`Pushing ${imageTags.join(", ")}`)
    docker(["login", "ghcr.io", "-u", ghcrUser, "--password-stdin"], ghcrToken)
    for (const tag of imageTags) docker(["push", tag])
  }

  const published = await github(`/repos/${REPO}/releases/${release.id}`, {
    method: "PATCH",
    retry: true,
    body: JSON.stringify({ draft: false, make_latest: "true" }),
  })
  console.log(`\nPublished ${published.html_url}`)
  console.log(`Installed apps will offer the update the next time they check, and servers download it.`)
  if (!ci) console.log(`Remember to commit the version change in manga-site/package.json and pyproject.toml.`)
} catch (error) {
  await github(`/repos/${REPO}/releases/${release.id}`, { method: "DELETE", retry: true }).catch(() => {})
  fail(`${error.message}. The draft release was removed; nothing was published.`)
}
