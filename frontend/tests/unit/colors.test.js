// Run from frontend/:  node --test tests/unit/colors.test.js
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

import { GS } from '../../src/constants/colors.js'

const HEX = /#[0-9a-fA-F]{8}\b|#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b/

function sources(dir, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name)
    if (e.isDirectory()) sources(p, out)
    else if (/\.(js|jsx)$/.test(e.name)) out.push(p)
  }
  return out
}

test('no component carries a hex colour literal: colours come from constants/colors.js', () => {
  const offenders = []
  for (const file of sources('src')) {
    if (file.endsWith(path.join('constants', 'colors.js'))) continue
    fs.readFileSync(file, 'utf8').split('\n').forEach((line, i) => {
      if (HEX.test(line)) offenders.push(`${file}:${i + 1}: ${line.trim().slice(0, 80)}`)
    })
  }
  assert.deepEqual(offenders, [])
})

test('every palette entry is a hex colour and no two names differ only by case of value', () => {
  for (const [name, value] of Object.entries(GS)) {
    assert.match(value, /^#[0-9a-f]{6}([0-9a-f]{2})?$/, name)
  }
})

test('every GS.<name> a component references exists in the palette', () => {
  const missing = new Set()
  for (const file of sources('src')) {
    for (const m of fs.readFileSync(file, 'utf8').matchAll(/\bGS\.([a-zA-Z]+)\b/g)) {
      if (!(m[1] in GS)) missing.add(`${file}: GS.${m[1]}`)
    }
  }
  assert.deepEqual([...missing], [])
})
