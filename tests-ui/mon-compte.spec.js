// « Mon compte » est une entrée du menu de l'avatar, distincte de « Paramètres généraux » : chacune ouvre sa vision, le commutateur de vision a disparu.
const { test, expect } = require('@playwright/test');

test("avatar : Mon compte et Paramètres généraux ouvrent chacun leur vision", async ({ page }) => {
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.waitForSelector('body.d19', { timeout: 20000 });
  await expect.poll(() => page.evaluate(() => document.querySelectorAll('#d19-groupes button').length), { timeout: 30000 }).toBeGreaterThan(0);        // la disposition est chargée
  const libelles = await page.evaluate(() => [...document.querySelectorAll('#usermenu .um-i')].map((b) => b.textContent.trim().replace(/\s+/g, ' ')));
  expect(libelles).toEqual(expect.arrayContaining(['Mon compte', 'Paramètres généraux']));

  await page.evaluate(() => document.querySelector('#usermenu [data-um="compte"]').click());
  await expect.poll(() => page.evaluate(() => document.querySelector('#tab-settings .mx-head h1').textContent)).toBe('Mon compte');
  expect(await page.evaluate(() => document.querySelector('#set-rail-titre').textContent)).toBe('Mon compte');
  expect(await page.evaluate(() => getComputedStyle(document.getElementById('set-visions')).display)).toBe('none');

  await page.evaluate(() => document.querySelector('#usermenu [data-um="machine"]').click());
  await expect.poll(() => page.evaluate(() => document.querySelector('#tab-settings .mx-head h1').textContent)).toBe('Maintenance');       // « Paramètres généraux » ouvre sa première rubrique
});
