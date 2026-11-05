// Turns approved Tenma art into the files the app uses. Run it after adding or changing art:
//   pnpm tenma:assets
//
// Input (repo root):
//   Tenma/Tenma.png           the main pose
//   Tenma/<pose>.png          other approved poses, transparent background (names in Tenma/poses.toml);
//                             Tenma/source/<pose>.png works too
//   Tenma/icon.png            optional chibi head for the app icon; without it the head is cut from the main pose
//
// Output:
//   src/assets/tenma/<pose>.webp        art shown by <Tenma pose="..."> (picked up automatically)
//   public/favicon.png, public/apple-touch-icon.png
//   android launcher icons (mipmap-*) and splash screens (drawable-*)
import { existsSync, mkdirSync, readdirSync, rmSync, statSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import sharp from "sharp"

const site = resolve(dirname(fileURLToPath(import.meta.url)), "..")
const tenmaDir = resolve(site, "../Tenma")
const sourceDir = join(tenmaDir, "source")
const artOut = join(site, "src/assets/tenma")
const res = join(site, "android/app/src/main/res")

// Tenma colors (brand-600 and brand-950 of the "tenma" accent in src/styles/brand.css)
const VIOLET = "#9027d2"
const NIGHT = "#300c4c"
// Where her head is in Tenma.png (1024x1536): center and the size of a square that holds ears to chin
const HEAD = { x: 505, y: 245, size: 520 }
const ART_SIZE = 720 // longest side

function poses() {
  const found = new Map()
  for (const dir of [tenmaDir, sourceDir]) {
    if (!existsSync(dir)) continue
    for (const file of readdirSync(dir)) {
      if (!file.toLowerCase().endsWith(".png")) continue
      const name = file.slice(0, -4).toLowerCase()
      found.set(name === "tenma" ? "main" : name, join(dir, file))
    }
  }
  return found
}

async function writeArt(found) {
  rmSync(artOut, { recursive: true, force: true })
  mkdirSync(artOut, { recursive: true })
  for (const [pose, file] of found) {
    if (pose === "icon") continue
    const out = join(artOut, `${pose}.webp`)
    // Trim the empty border first so every pose fills its box the same way
    const trimmed = await sharp(file).ensureAlpha().trim({ threshold: 1 }).toBuffer()
    await sharp(trimmed)
      .resize({ width: ART_SIZE, height: ART_SIZE, fit: "inside", withoutEnlargement: true })
      .webp({ quality: 84, alphaQuality: 90, effort: 6 })
      .toFile(out)
    const { size } = statSync(out)
    console.log(`art  ${pose}.webp  ${Math.round(size / 1024)} KB`)
  }
}

// A violet radial gradient, the background of every icon and splash
function gradient(width, height) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">
    <defs><radialGradient id="g" cx="50%" cy="42%" r="70%">
      <stop offset="0" stop-color="${VIOLET}"/><stop offset="1" stop-color="${NIGHT}"/>
    </radialGradient></defs>
    <rect width="100%" height="100%" fill="url(#g)"/></svg>`
  return sharp(Buffer.from(svg)).png().toBuffer()
}

// Square picture of her head on the gradient. `zoom` < 1 shows more around the head.
async function headSquare(found, size, zoom = 1) {
  const icon = found.get("icon")
  if (icon) {
    const inner = Math.round(size * 0.8 * zoom)
    const head = await sharp(icon).trim({ threshold: 1 }).resize(inner, inner, { fit: "contain", background: "#0000" }).toBuffer()
    return sharp(await gradient(size, size)).composite([{ input: head, gravity: "center" }]).png().toBuffer()
  }
  const main = found.get("main")
  const meta = await sharp(main).metadata()
  const box = 2 * Math.round(HEAD.size / zoom / 2)
  // Put the art on a gradient canvas with room around it, so a crop past the image edge gets background
  const pad = box
  const canvas = await sharp(await gradient(meta.width + pad * 2, meta.height + pad * 2))
    .composite([{ input: main, left: pad, top: pad }])
    .png()
    .toBuffer()
  return sharp(canvas)
    .extract({ left: pad + HEAD.x - box / 2, top: pad + HEAD.y - box / 2, width: box, height: box })
    .resize(size, size)
    .png()
    .toBuffer()
}

function roundMask(size, radius) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}"><rect width="${size}" height="${size}" rx="${radius}" ry="${radius}"/></svg>`
  return Buffer.from(svg)
}

async function masked(buffer, size, radius) {
  return sharp(buffer).composite([{ input: roundMask(size, radius), blend: "dest-in" }]).png().toBuffer()
}

async function writeIcons(found) {
  mkdirSync(join(site, "public"), { recursive: true })
  // Browser icons: tight on the face so it reads at 16-32 px
  await sharp(await masked(await headSquare(found, 128, 1), 128, 28)).toFile(join(site, "public/favicon.png"))
  await sharp(await headSquare(found, 180, 0.95)).toFile(join(site, "public/apple-touch-icon.png"))
  console.log("icon public/favicon.png, public/apple-touch-icon.png")

  if (!existsSync(res)) return
  const densities = { mdpi: 1, hdpi: 1.5, xhdpi: 2, xxhdpi: 3, xxxhdpi: 4 }
  for (const [name, scale] of Object.entries(densities)) {
    const dir = join(res, `mipmap-${name}`)
    const legacy = Math.round(48 * scale)
    const square = await headSquare(found, legacy, 0.95)
    await sharp(await masked(square, legacy, legacy * 0.18)).toFile(join(dir, "ic_launcher.png"))
    await sharp(await masked(square, legacy, legacy / 2)).toFile(join(dir, "ic_launcher_round.png"))
    // Adaptive icon: 108dp, of which the launcher shows roughly the middle 72dp, so zoom out to keep the ears in
    const adaptive = Math.round(108 * scale)
    await sharp(await headSquare(found, adaptive, 0.62)).toFile(join(dir, "ic_launcher_foreground.png"))
  }
  console.log("icon android mipmap-*")
}

async function writeSplashes(found) {
  if (!existsSync(res)) return
  const art = found.get("main")
  const trimmed = await sharp(art).trim({ threshold: 1 }).toBuffer()
  for (const dir of readdirSync(res).filter((d) => d.startsWith("drawable"))) {
    const file = join(res, dir, "splash.png")
    if (!existsSync(file)) continue
    const { width, height } = await sharp(file).metadata()
    const figure = await sharp(trimmed)
      .resize({ width: Math.round(width * 0.7), height: Math.round(height * 0.62), fit: "inside" })
      .toBuffer()
    await sharp(await gradient(width, height)).composite([{ input: figure, gravity: "center" }]).png().toFile(file)
  }
  console.log("splash android drawable-*/splash.png")
}

const found = poses()
if (!found.has("main")) {
  console.error(`No art found: expected ${join(tenmaDir, "Tenma.png")}`)
  process.exit(1)
}
await writeArt(found)
await writeIcons(found)
await writeSplashes(found)
