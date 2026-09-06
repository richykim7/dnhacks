import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
const dir = new URL('../../src/dnhacksbio/branch_monitoring/', import.meta.url);
const html = readFileSync(new URL('operator.html', dir), 'utf8');
const js = readFileSync(new URL('operator.js', dir), 'utf8');
const css = readFileSync(new URL('operator.css', dir), 'utf8');

test('operator monitor shows an actual single point and distinguishes missing calibration', async ({page}) => {
  // Synthetic UI fixture, not a scored investigation or evidence of monitor performance.
  await page.route('**/operator-console', r => r.fulfill({contentType:'text/html',body:html}));
  await page.route('**/operator.js', r => r.fulfill({contentType:'text/javascript',body:js}));
  await page.route('**/operator.css', r => r.fulfill({contentType:'text/css',body:css}));
  await page.route('**/api/episodes', r => {
    expect(r.request().headers()['authorization']).toBe('Bearer browser-test-token');
    return r.fulfill({json:{episodes:[{episode_id:'e',run_id:'study~1',objective:'Synthetic monitor UI fixture',status:'open',
      protocol:{terminal_budget:80,budget_unit:'research_actions'},
      history:[{checkpoint:1,cumulative_cost:18,monitor_statistic:2.5,threshold:null,would_stop:false}]}]}});
  });
  await page.route('**/api/reviews/**', r=>r.fulfill({json:{reviews:[]}}));
  await page.goto('/operator-console');
  await page.getByLabel('Operator access token').fill('browser-test-token');
  await page.getByRole('button',{name:'Open monitor'}).click();
  await page.getByRole('button',{name:/study~1/}).click();
  await expect(page.getByText('Uncalibrated; no stopping threshold.',{exact:false})).toBeVisible();
  await expect(page.locator('#chart circle')).toHaveCount(1);
  await expect(page.locator('#chart .threshold')).toHaveCount(0);
  await expect(page.getByText('No associated experimental evidence.')).toBeVisible();
  await page.screenshot({path:test.info().outputPath('dnhacks-monitor-single-point.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});
