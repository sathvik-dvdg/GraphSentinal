// One-off codemod, kept for the record: replace hex colour literals in src/ with
// references to constants/colors.js. Token-accurate (espree), so a hex inside
// HTML built as a string, inside a template literal, or in a JSX attribute is
// each rewritten in the form that position needs. Run from frontend/:
//   node scripts/hex-to-tokens.mjs          (rewrites files)
//   node scripts/hex-to-tokens.mjs --check  (reports what is left, changes nothing)
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'
import { GS } from '../src/constants/colors.js'

const require = createRequire(import.meta.url)
const espree = require('espree')

const CHECK = process.argv.includes('--check')
const SRC = path.resolve('src')
const SKIP = new Set([path.join(SRC, 'constants', 'colors.js')])
const HEX = /#[0-9a-fA-F]{8}\b|#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b/g

const byHex = new Map(Object.entries(GS).map(([name, hex]) => [hex.toLowerCase(), name]))
byHex.set('#fff', 'surface')
// A grey introduced on 2026-10-05 for one note; it is the subtle text colour.
byHex.set('#6b7280', 'textSubtle')

const nameOf = (hex) => {
  const name = byHex.get(hex.toLowerCase())
  if (!name) throw new Error(`no token for ${hex}`)
  return name
}

function walk(dir, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name)
    if (e.isDirectory()) walk(p, out)
    else if (/\.(js|jsx)$/.test(e.name)) out.push(p)
  }
  return out
}

let total = 0
const left = []
for (const file of walk(SRC)) {
  if (SKIP.has(file)) continue
  const code = fs.readFileSync(file, 'utf8')
  if (!HEX.test(code)) continue
  HEX.lastIndex = 0
  const tokens = espree.tokenize(code, {
    ecmaVersion: 'latest', sourceType: 'module', ecmaFeatures: { jsx: true }, range: true, comment: false,
  })
  const edits = []
  tokens.forEach((tok, i) => {
    const raw = code.slice(tok.range[0], tok.range[1])
    if (!HEX.test(raw)) return
    HEX.lastIndex = 0
    const prev = tokens[i - 1]
    const next = tokens[i + 1]
    const quoted = /^(['"])[\s\S]*\1$/.test(raw)
    const isAttr = tok.type === 'JSXText' && quoted && prev?.value === '='
    if (tok.type === 'String' || isAttr) {
      const body = raw.slice(1, -1)
      // an object key ('#fff': x) or an import path is not a value
      if (!isAttr && (next?.value === ':' && (prev?.value === '{' || prev?.value === ','))) { left.push([file, raw]); return }
      let replacement
      if (HEX.test(body) && body.replace(HEX, '') === '') {
        HEX.lastIndex = 0
        replacement = `GS.${nameOf(body)}`
      } else {
        HEX.lastIndex = 0
        if (/[`\\]|\$\{/.test(body)) { left.push([file, raw]); return }
        replacement = '`' + body.replace(HEX, (h) => '${GS.' + nameOf(h) + '}') + '`'
      }
      HEX.lastIndex = 0
      edits.push([tok.range[0], tok.range[1], isAttr ? `{${replacement}}` : replacement, (raw.match(HEX) || []).length])
    } else if (tok.type === 'Template') {
      edits.push([tok.range[0], tok.range[1], raw.replace(HEX, (h) => '${GS.' + nameOf(h) + '}'), (raw.match(HEX) || []).length])
    } else {
      left.push([file, raw.trim().slice(0, 80)])
    }
    HEX.lastIndex = 0
  })
  if (!edits.length) continue
  let out = code
  for (const [a, b, text] of edits.sort((x, y) => y[0] - x[0])) out = out.slice(0, a) + text + out.slice(b)
  const n = edits.reduce((s, e) => s + e[3], 0)
  total += n
  // invariant: every literal became exactly one reference
  const refs = (out.match(/\bGS\.[a-zA-Z]+\b/g) || []).length - (code.match(/\bGS\.[a-zA-Z]+\b/g) || []).length
  if (refs !== n) throw new Error(`${file}: ${n} literals but ${refs} references`)
  if (!/\bGS\b[^\n]*constants\/colors/.test(out)) {
    let rel = path.relative(path.dirname(file), path.join(SRC, 'constants', 'colors')).split(path.sep).join('/')
    if (!rel.startsWith('.')) rel = './' + rel
    // keep the file's own line endings: a working copy here is often CRLF
    const eol = out.includes('\r\n') ? '\r\n' : '\n'
    const imports = [...out.matchAll(/^import[\s\S]*?from\s+['"][^'"]+['"];?[ \t]*\r?\n/gm)]
    const line = `import { GS } from '${rel}'${eol}`
    if (imports.length) {
      const last = imports[imports.length - 1]
      const at = last.index + last[0].length
      out = out.slice(0, at) + line + out.slice(at)
    } else {
      const firstCode = out.search(/^(?!\/\/|\s*$)/m)
      out = out.slice(0, firstCode) + line + eol + out.slice(firstCode)
    }
  }
  if (!CHECK) fs.writeFileSync(file, out)
  console.log(`${String(n).padStart(4)}  ${path.relative(SRC, file).split(path.sep).join('/')}`)
}
console.log(`${total} literal(s) ${CHECK ? 'would be' : ''} replaced`)
if (left.length) {
  console.log(`${left.length} left for a person:`)
  for (const [f, raw] of left) console.log(`   ${path.relative(SRC, f).split(path.sep).join('/')}: ${raw}`)
}
