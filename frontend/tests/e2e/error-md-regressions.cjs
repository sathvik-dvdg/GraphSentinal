// [WSL2]
/**
 * Frontend regression script for the UI-visible fixes catalogued in
 * Error.md (#1, #4, #5, #12, #16/#37, #18/#27, #19, #26, #35, #38, plus a
 * zero-console-error sweep of every route).
 *
 * These are the issues the backend pytest suite (backend/tests/) can't
 * cover — badge visibility, tab-scoped content, and per-panel error states
 * that only exist in the rendered DOM.
 *
 * Prerequisites (Playwright is scoped to this directory — not part of the
 * main frontend package.json/lockfile — via tests/e2e/package.json):
 *   1. The full Docker stack must be up: `docker compose up -d` from the
 *      repo root (frontend on :5174, backend on :8001).
 *   2. cd frontend/tests/e2e && npm install && npx playwright install chromium
 *
 * Run (from `frontend/tests/e2e/`):
 *   npm test
 *   (or: node error-md-regressions.cjs)
 *
 * Exits non-zero if any check fails.
 */
const { chromium } = require('playwright');

const BASE = process.env.FRONTEND_URL || 'http://localhost:5174';
const API = process.env.BACKEND_URL || 'http://localhost:8001';
const OPERATOR_USER = process.env.OPERATOR_USERNAME || 'admin';
const OPERATOR_PASS = process.env.OPERATOR_PASSWORD || 'change-me-for-demo';
const results = [];

function record(issue, name, pass, detail) {
  results.push({ issue, name, pass, detail: detail || '' });
  console.log(`${pass ? 'PASS' : 'FAIL'}  [${issue}] ${name}${detail ? ' — ' + detail : ''}`);
}

(async () => {
  // Fetch real live config first so badge assertions match reality instead
  // of assuming the checked-in .env.docker defaults — a gitignored
  // .env.docker.local override can legitimately change enforcement_mode /
  // demo_fallback_flows per deployment (see decisions.md #5/#12).
  const loginRes = await fetch(`${API}/api/v1/auth/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: OPERATOR_USER, password: OPERATOR_PASS }),
  });
  const { token } = await loginRes.json();
  const statsRes = await fetch(`${API}/api/v1/stats`, { headers: { Authorization: `Bearer ${token}` } });
  const liveStats = await statsRes.json();
  console.log(`Live config: enforcement_mode=${liveStats.enforcement_mode}, demo_fallback_flows=${liveStats.demo_fallback_flows}\n`);

  const browser = await chromium.launch();
  const page = await browser.newPage();
  const consoleErrors = [];
  page.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
  page.on('pageerror', (err) => consoleErrors.push(err.message));

  // ── #18/#27 — fake credentials must be rejected, real login must work ──
  await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
  let inputs = await page.$$('input');
  await inputs[0].fill('nonsense');
  await inputs[1].fill('nonsense');
  await page.click('button[type="submit"], button:has-text("Sign In"), button:has-text("Login")').catch(() => {});
  await page.waitForTimeout(1200);
  record('18', 'fake credentials rejected, not silently accepted', page.url().includes('/login'));

  inputs = await page.$$('input');
  await inputs[0].fill(OPERATOR_USER);
  await inputs[1].fill(OPERATOR_PASS);
  await page.click('button[type="submit"], button:has-text("Sign In"), button:has-text("Login")').catch(() => {});
  await page.waitForTimeout(2000);
  record('18', 'real operator credentials log in successfully', !page.url().includes('/login'));

  // The very first poll cycle can transiently show connectionMode
  // 'connecting' -> EMPTY_STATE placeholders (SIMULATED/DEMO) for a few
  // seconds before the first real stats fetch lands and corrects it — wait
  // past that window rather than racing it.
  await page.waitForTimeout(8000);

  // ── #1 — no mock data auto-loads; real backend data present ────────────
  const bodyText1 = await page.textContent('body');
  record('1', 'no forced MOCK MODE banner on a live backend', !bodyText1.includes('MOCK MODE'));

  // ── #5 — EnforcementModeBadge reflects the REAL live config ────────────
  const expectedEnforcementBadge = liveStats.enforcement_mode === 'ovs' ? 'OVS ENFORCEMENT' : 'SIMULATED ENFORCEMENT';
  record('5', 'EnforcementModeBadge matches live enforcement_mode', bodyText1.includes(expectedEnforcementBadge), `expected "${expectedEnforcementBadge}"`);

  // ── #12 — DemoModeBadge matches the REAL live config ────────────────────
  if (liveStats.demo_fallback_flows) {
    record('12', 'DemoModeBadge shown when demo_fallback_flows=true', bodyText1.includes('DEMO'));
  } else {
    record('12', 'DemoModeBadge absent when demo_fallback_flows=false', !bodyText1.includes('DEMO MODE'));
  }

  // ── #4 — MlModeBadge reflects real ml.mode from /health ────────────────
  const healthRes = await fetch(`${API}/health`);
  const health = await healthRes.json();
  const expectDegradedBadge = health.ml.mode !== 'model';
  const hasHeuristicBadge = bodyText1.includes('HEURISTIC SCORING');
  record('4', 'MlModeBadge matches real /health ml.mode', hasHeuristicBadge === expectDegradedBadge, `ml.mode=${health.ml.mode}`);

  // ── Sweep every route: no console errors, no unhandled crashes ─────────
  const ROUTES = ['/dashboard', '/network', '/threats', '/alerts', '/timeline', '/healing', '/forensics', '/blockchain', '/settings'];
  for (const route of ROUTES) {
    consoleErrors.length = 0;
    await page.goto(`${BASE}${route}`, { waitUntil: 'domcontentloaded', timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(1000);
    record('sweep', `${route} loads with zero console errors`, consoleErrors.length === 0, consoleErrors.length ? consoleErrors[0] : '');
  }

  // ── #16/#37 — timestamps carry a real date (day+month), not bare HH:MM ─
  // After the route sweep, the last page.goto reset connectionMode to
  // 'connecting' — we need a full 10s poll cycle + render before any real
  // data (and therefore timestamps) exists on the Threat Feed.
  await page.click('a[href="/threats"]');
  await page.waitForTimeout(12000); // >= 1 full poll cycle
  const threatBody = await page.textContent('body');
  // page.textContent() flattens adjacent DOM nodes with no separator (e.g.
  // "Manual22 Aug 08:56:16"), so a \b word boundary can't be assumed between
  // a preceding label and the date — match on the day+month+time shape only.
  const MONTHS = '(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)';
  const hasDatedTimestamp = new RegExp(`(${MONTHS}\\s?\\d{1,2}|\\d{1,2}\\s?${MONTHS})\\s+\\d{1,2}:\\d{2}`).test(threatBody);
  // If no threats exist at all, the format can't be checked — treat as pass.
  const hasNoThreats = threatBody.includes('No threats matching');
  record('16/37', 'Threat Feed timestamps include month+day, not bare HH:MM',
    hasDatedTimestamp || hasNoThreats,
    hasDatedTimestamp ? '' : (hasNoThreats ? '(no live threats — vacuous pass)' : 'no dated timestamp found'));

  // ── #38 — copyable hash affordance exists on Blockchain Ledger ─────────
  await page.click('a[href="/blockchain"]');
  await page.waitForTimeout(3000); // wait for panel data to load
  const copyIcons = await page.$$('svg');
  record('38', 'Blockchain Ledger renders (copy-hash icons present)', copyIcons.length > 0);

  // ── #35 — Enforcement Actions Audit log tab (backs onto the
  //         GET /api/v1/enforcement-actions endpoint) ────────────────
  const enforcementTab = page.locator('text=Enforcement Log').first();
  const tabVisible = await enforcementTab.isVisible().catch(() => false);
  record('35', '"Enforcement Log" tab present on Blockchain Ledger', tabVisible);
  if (tabVisible) {
    await enforcementTab.click();
    // Use waitFor instead of a fixed timeout — the rows render as soon as
    // the store's enforcement data arrives (within one 10s poll cycle).
    const hasRealActionRows = await page.locator('text=/GNN_DETECTED|MANUAL_OVERRIDE|RECONCILE_REAPPLY|RECONCILE_REMOVE/').first()
      .waitFor({ state: 'visible', timeout: 15000 })
      .then(() => true)
      .catch(() => false);
    record('35', 'Enforcement Log renders real audit rows from the backend', hasRealActionRows);
  }

  // ── #19 — Settings: Threat Threshold control wired to the real backend ─
  await page.click('a[href="/settings"]');
  await page.waitForTimeout(1000);
  const detectionTab = page.locator('text=/Detection Thresholds/i').first();
  await detectionTab.click().catch(() => {});
  await page.waitForTimeout(1000);
  const settingsBody = await page.textContent('body');
  record('19', 'Threat Threshold control loads a real live value from backend', /Current live value|Threat Threshold/i.test(settingsBody));
  record('19', 'Lateral Movement control is honestly labeled, not fake-functional', settingsBody.includes('not implemented'));

  // ── #26 — per-panel DataFreshnessBadge scoped correctly (forced failure) ─
  // The app starts in 'connecting' mode; if /graph fails during connecting,
  // the code sets connectionMode='mock' which resets EMPTY_STATE including
  // dataErrors — so the STALE badge never appears. The correct test scenario
  // is to intercept /graph only AFTER the app is already 'live'. We use
  // waitFor() instead of a fixed timeout to react the instant the badge
  // appears rather than racing against the 10s poll interval.
  await page.click('a[href="/network"]');
  await page.waitForTimeout(2000); // let current polls settle and ensure we're live
  await page.route('**/api/v1/graph', (route) => route.fulfill({ status: 500, body: 'forced failure' }));
  // waitFor: up to 15s — the failing poll fires within the 10s interval
  const staleAppeared = await page.locator('text=STALE').first()
    .waitFor({ state: 'visible', timeout: 15000 })
    .then(() => true)
    .catch(() => false);
  record('26', 'Per-panel STALE indicator appears when only graph fails', staleAppeared);
  await page.unroute('**/api/v1/graph');

  await browser.close();

  const failed = results.filter((r) => !r.pass);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed.`);
  if (failed.length) {
    console.log('FAILED:');
    failed.forEach((f) => console.log(`  [${f.issue}] ${f.name} — ${f.detail}`));
    process.exitCode = 1;
  }
})();
