import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';

// Connect to a locally launched headless Chrome. No remote service or upload.
const browser = await chromium.connectOverCDP('http://127.0.0.1:9227');
await mkdir('test-results', { recursive: true });
const results: object[] = [];
try {
  for (const viewport of [{ width: 360, height: 640 }, { width: 390, height: 844 }, { width: 430, height: 932 }]) {
    const context = await browser.newContext({ viewport, reducedMotion: 'reduce' });
    const page = await context.newPage();
    const errors: string[] = [];
    const external: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('request', request => { if (!request.url().startsWith('http://localhost:5173') && !request.url().startsWith('data:')) external.push(request.url()); });
    await page.goto('http://localhost:5173');
    await page.getByRole('button', { name: '돌리기', exact: true }).waitFor();
    await page.screenshot({ path: `test-results/home-${viewport.width}.png` });
    const dimensions = await page.evaluate(() => {
      const shell = document.querySelector('.app-shell')!;
      return { width: shell.clientWidth, scrollWidth: shell.scrollWidth, height: shell.clientHeight, screenHeight: innerHeight };
    });
    assert.equal(dimensions.width, dimensions.scrollWidth, 'No horizontal overflow');
    assert.equal(dimensions.height, dimensions.screenHeight, 'Shell fills dynamic viewport');
    await page.getByLabel('추가할 메뉴').fill('버섯 덮밥');
    await page.getByLabel('추가할 메뉴').press('Enter');
    await page.getByRole('button', { name: '버섯 덮밥 삭제' }).waitFor();
    await page.reload();
    await page.getByRole('button', { name: '버섯 덮밥 삭제' }).waitFor();
    await context.setOffline(true);
    await page.getByRole('button', { name: '돌리기', exact: true }).click();
    const dialog = page.getByRole('dialog');
    await dialog.waitFor();
    const winner = await dialog.getByRole('heading').innerText();
    const wheelWinner = await page.evaluate(() => {
      const wheel = document.querySelector('.wheel > g') as SVGElement;
      const angle = Number(/rotate\(([-\d.]+)deg\)/.exec(wheel.style.transform)![1]);
      const labels = [...wheel.querySelectorAll('text title')].map(node => node.textContent);
      const normalized = ((-angle % 360) + 360) % 360;
      return labels[Math.floor(normalized / (360 / labels.length))];
    });
    assert.equal(winner, wheelWinner, 'Visible wheel agrees with result');
    await page.screenshot({ path: `test-results/result-${viewport.width}.png` });
    await dialog.getByRole('button', { name: '결과 복사' }).click();
    await dialog.getByRole('status').waitFor();
    await page.keyboard.press('Escape');
    assert.equal(await dialog.count(), 0, 'Escape dismisses modal');
    await page.getByRole('link', { name: '개인정보처리방침' }).click();
    await page.getByRole('heading', { name: '개인정보처리방침', exact: true }).waitFor();
    await page.getByRole('button', { name: '룰렛으로 이동' }).click();
    await page.getByRole('link', { name: '이용약관' }).click();
    await page.getByRole('heading', { name: '이용약관', exact: true }).waitFor();
    assert.deepEqual(errors, [], 'No browser console/page errors');
    assert.deepEqual(external, [], 'No external runtime requests');
    results.push({ viewport, dimensions, winner, errors, external, offlineInteractions: 'passed' });
    await context.close();
  }
  console.log(JSON.stringify(results, null, 2));
} finally { await browser.close(); }
