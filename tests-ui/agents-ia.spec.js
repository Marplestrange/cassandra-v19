// « Agents IA » est une entrée du groupe Autonomie : elle ouvre la rubrique de Paramètres généraux seule (sans le rail), et la rubrique quitte le rail tant que l'entrée existe.
const { test, expect } = require('@playwright/test');

test("Agents IA : entrée de menu, rubrique seule, rail de Paramètres généraux sans elle", async ({ page }) => {
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.waitForSelector('body.d19', { timeout: 20000 });
  // l'entrée vient du module agents : elle paraît dès que la disposition la porte
  await expect.poll(() => page.evaluate(async () => { const d = await window.CASS.agir('affichage.lire_disposition', {}); return d.groupes.some((g) => g.id === 'auto' && g.entrees.some((e) => e.id === 'agents-ia')); }), { timeout: 40000 }).toBe(true);
  await page.evaluate(() => window.CASS.disposition.rafraichir());
  await expect.poll(() => page.evaluate(() => document.body.classList.contains('d19-rub-agents'))).toBe(true);

  await page.evaluate(() => window.CASS.disposition.aller('auto', 'agents-ia', ''));
  await expect.poll(() => page.evaluate(() => document.getElementById('tab-settings').classList.contains('set-seule'))).toBe(true);
  expect(await page.evaluate(() => document.querySelector('#tab-settings .mx-head h1').textContent)).toBe('Agents IA');
  expect(await page.evaluate(() => getComputedStyle(document.querySelector('#tab-settings .settings-corps > .set-nav')).display)).toBe('none');
  expect(await page.evaluate(() => document.querySelector('#tab-settings .settings-section[data-fam="agents"]').offsetHeight)).toBeGreaterThan(0);

  // Paramètres généraux rend son rail, mais sans la rubrique déplacée
  await page.evaluate(() => document.querySelector('#usermenu [data-um="machine"]').click());
  await expect.poll(() => page.evaluate(() => document.getElementById('tab-settings').classList.contains('set-seule'))).toBe(false);
  expect(await page.evaluate(() => getComputedStyle(document.querySelector('#tab-settings .set-nav-item[data-fam="agents"]')).display)).toBe('none');
  expect(await page.evaluate(() => getComputedStyle(document.querySelector('#tab-settings .set-nav-item[data-fam="danger"]')).display)).not.toBe('none');
});
