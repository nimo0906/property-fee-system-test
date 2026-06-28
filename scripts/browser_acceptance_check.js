#!/usr/bin/env node
// Browser acceptance checks for UI state that requires JavaScript execution.
const { chromium } = require('playwright');

const baseUrl = process.env.ACCEPTANCE_BASE_URL || 'http://127.0.0.1:5001';
const chromePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

async function login(page) {
  await page.goto(`${baseUrl}/login`, { waitUntil: 'domcontentloaded' });
  await page.fill('input[name="username"]', process.env.ACCEPTANCE_USER || 'admin');
  await page.fill('input[name="password"]', process.env.ACCEPTANCE_PASSWORD || 'admin123');
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }).catch(() => {}),
    page.click('button[type="submit"], button.auth-primary'),
  ]);
}

async function main() {
  const browser = await chromium.launch({ headless: true, executablePath: chromePath });
  const page = await browser.newPage({ viewport: { width: 1100, height: 900 } });
  const failures = [];

  page.on('pageerror', err => failures.push(`pageerror: ${err.message}`));
  page.on('response', resp => {
    const url = resp.url();
    if (resp.status() >= 400 && !url.includes('/favicon.ico')) failures.push(`HTTP ${resp.status()}: ${url}`);
  });
  page.on('console', msg => {
    const text = msg.text();
    if (msg.type() === 'error' && !text.includes('Failed to load resource')) failures.push(`console error: ${text}`);
  });

  await login(page);

  await page.goto(`${baseUrl}/bills?_r=browser-acceptance`, { waitUntil: 'networkidle' });
  if (await page.locator('tr.table-secondary').count()) {
    await page.locator('tr.table-secondary').first().click();
    await page.locator('tr.bill-room-row').first().click();
    const before = await page.locator('tr[class^="bill-detail-"]').first().evaluate(el => getComputedStyle(el).display);
    if (before === 'none') failures.push('bills detail row did not expand before navigation');
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
      page.locator('.bill-row-action').first().click(),
    ]);
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'networkidle' }),
      page.locator('.bill-detail-back').click(),
    ]);
    const afterRoom = await page.locator('tr.bill-room-row').first().evaluate(el => getComputedStyle(el).display);
    const afterBill = await page.locator('tr[class^="bill-detail-"]').first().evaluate(el => getComputedStyle(el).display);
    if (afterRoom === 'none' || afterBill === 'none') failures.push('bills expanded state was not restored after return');
  }

  await page.goto(`${baseUrl}/owners?_r=browser-acceptance`, { waitUntil: 'networkidle' });
  const ownerWidth = await page.locator('.owner-search-input').evaluate(el => el.getBoundingClientRect().width);
  if (ownerWidth > 430) failures.push(`owners search input too wide: ${ownerWidth}`);

  await page.goto(`${baseUrl}/rooms?_r=browser-acceptance`, { waitUntil: 'networkidle' });
  const roomWidth = await page.locator('.room-search-keyword').evaluate(el => el.getBoundingClientRect().width);
  if (roomWidth > 430) failures.push(`rooms search input too wide: ${roomWidth}`);

  await page.goto(`${baseUrl}/meter_readings?_r=browser-acceptance`, { waitUntil: 'networkidle' });
  const meterColor = await page.locator('.meter-page-shell .summary-tile.primary strong').first().evaluate(el => getComputedStyle(el).color);
  if (meterColor === 'rgb(255, 255, 255)') failures.push('meter primary summary number is still white');

  await page.goto(`${baseUrl}/backups?_r=browser-acceptance`, { waitUntil: 'networkidle' });
  const backupTitle = await page.locator('.page-title').innerText().catch(() => '');
  const backupNavCount = await page.locator('a.nav-link.active[href="/backups"] span', { hasText: '备份记录' }).count().catch(() => 0);
  if (!backupTitle.includes('备份记录') || backupNavCount < 1) failures.push(`backup module entry/title missing: title=${backupTitle}, activeNav=${backupNavCount}`);

  await browser.close();
  if (failures.length) {
    console.log('Browser acceptance: FAIL');
    failures.forEach(f => console.log(' - ' + f));
    process.exit(1);
  }
  console.log('Browser acceptance: PASS');
}

main().catch(err => {
  console.error('Browser acceptance crashed:', err);
  process.exit(1);
});
