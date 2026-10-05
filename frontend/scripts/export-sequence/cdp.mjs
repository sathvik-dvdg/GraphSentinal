// Minimal Chrome DevTools Protocol client: launches a local headless Chrome or
// Edge and talks to it over Node's built-in WebSocket. No npm dependencies.
import { spawn } from 'node:child_process'
import { existsSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const CANDIDATES = [
  process.env.CHROME_PATH,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/usr/bin/google-chrome',
  '/usr/bin/chromium',
].filter(Boolean)

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

export async function launch({ port = 9333, width = 1920, height = 1080, args = [] } = {}) {
  const binary = CANDIDATES.find((p) => existsSync(p))
  if (!binary) throw new Error('No Chrome or Edge found. Set CHROME_PATH.')

  const child = spawn(
    binary,
    [
      '--headless=new',
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${mkdtempSync(join(tmpdir(), 'gs-cdp-'))}`,
      `--window-size=${width},${height}`,
      '--hide-scrollbars',
      '--ignore-gpu-blocklist',
      '--enable-unsafe-swiftshader',
      '--no-first-run',
      ...args,
      'about:blank',
    ],
    { stdio: 'ignore' },
  )

  let target
  for (let attempt = 0; attempt < 50 && !target; attempt++) {
    await sleep(200)
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()
      target = list.find((t) => t.type === 'page')
    } catch {
      // browser still starting
    }
  }
  if (!target) {
    child.kill()
    throw new Error('Could not reach the browser debugging port.')
  }

  const socket = new WebSocket(target.webSocketDebuggerUrl)
  await new Promise((resolve, reject) => {
    socket.onopen = resolve
    socket.onerror = reject
  })

  let nextId = 0
  const pending = new Map()
  const listeners = new Set()
  socket.onmessage = (event) => {
    const message = JSON.parse(event.data)
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id)
      pending.delete(message.id)
      if (message.error) reject(new Error(message.error.message))
      else resolve(message.result)
    } else {
      listeners.forEach((fn) => fn(message))
    }
  }

  const send = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const id = ++nextId
      pending.set(id, { resolve, reject })
      socket.send(JSON.stringify({ id, method, params }))
    })

  const evaluate = async (expression) => {
    const { result, exceptionDetails } = await send('Runtime.evaluate', {
      expression,
      returnByValue: true,
      awaitPromise: true,
    })
    if (exceptionDetails) {
      throw new Error(exceptionDetails.exception?.description || exceptionDetails.text)
    }
    return result.value
  }

  const waitFor = async (expression, timeout = 30000) => {
    const started = Date.now()
    while (Date.now() - started < timeout) {
      if (await evaluate(expression).catch(() => false)) return
      await sleep(100)
    }
    throw new Error(`Timed out waiting for: ${expression}`)
  }

  const setViewport = (w, h, { mobile = false, scale = 1 } = {}) =>
    send('Emulation.setDeviceMetricsOverride', {
      width: w,
      height: h,
      deviceScaleFactor: scale,
      mobile,
    })

  const goto = async (url) => {
    await send('Page.enable')
    await send('Page.navigate', { url })
    await waitFor('document.readyState === "complete"')
  }

  const close = async () => {
    await send('Browser.close').catch(() => {})
    child.kill()
  }

  return {
    send,
    evaluate,
    waitFor,
    setViewport,
    goto,
    close,
    sleep,
    onEvent: (fn) => listeners.add(fn),
  }
}
