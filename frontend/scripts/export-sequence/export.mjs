// Renders the landing page's opening frame sequence from the same Three.js
// scene the live story uses, so the two share one look and one palette.
//
//   1. npm run dev
//   2. node scripts/export-sequence/export.mjs [http://localhost:5173]
//
// Output: public/sequence/{desktop,mobile}/0001.webp ... and stills/.
import { mkdirSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { launch } from './cdp.mjs'

const origin = process.argv[2] || 'http://localhost:5173'
const outRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../public/sequence')

// Keep FRAME_COUNT in sync with src/components/landing/content.js.
const FRAME_COUNT = 120
const SETS = [
  // Keep the desktop size in sync with LANDSCAPE_FRAME in src/components/landing/framing.js.
  { name: 'desktop', width: 2304, height: 972, quality: 0.78 },
  { name: 'mobile', width: 720, height: 1280, quality: 0.74 },
]
// One still per chapter for the reduced-motion page, as story positions.
const STILLS = [0.62, 1.6, 2.92, 3.97, 5]

const browser = await launch()
const page = (query) => `${origin}/scripts/export-sequence/index.html?${query}`
const save = (file, dataUrl) => writeFileSync(file, Buffer.from(dataUrl.split(',')[1], 'base64'))
const folderSize = (dir) =>
  readdirSync(dir).reduce((sum, name) => sum + statSync(join(dir, name)).size, 0)

try {
  for (const set of SETS) {
    const dir = join(outRoot, set.name)
    rmSync(dir, { recursive: true, force: true })
    mkdirSync(dir, { recursive: true })
    await browser.setViewport(set.width, set.height)
    await browser.goto(page(`w=${set.width}&h=${set.height}`))
    await browser.waitFor('typeof window.__renderFrame === "function"')
    for (let i = 0; i < FRAME_COUNT; i++) {
      const intro = i / (FRAME_COUNT - 1)
      const dataUrl = await browser.evaluate(`window.__renderFrame(${intro}, 0, ${set.quality})`)
      save(join(dir, `${String(i + 1).padStart(4, '0')}.webp`), dataUrl)
    }
    console.log(`${set.name}: ${FRAME_COUNT} frames, ${(folderSize(dir) / 1024).toFixed(0)} KB`)
  }

  const dir = join(outRoot, 'stills')
  rmSync(dir, { recursive: true, force: true })
  mkdirSync(dir, { recursive: true })
  await browser.setViewport(1200, 900)
  await browser.goto(page('w=1200&h=900&centered=1'))
  await browser.waitFor('typeof window.__renderFrame === "function"')
  for (let i = 0; i < STILLS.length; i++) {
    const dataUrl = await browser.evaluate(`window.__renderFrame(1, ${STILLS[i]}, 0.82)`)
    save(join(dir, `chapter-${i + 1}.webp`), dataUrl)
  }
  console.log(`stills: ${STILLS.length} frames, ${(folderSize(dir) / 1024).toFixed(0)} KB`)
} finally {
  await browser.close()
}
