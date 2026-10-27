// Le grand menu « Paramètres » : Maintenance, Données, Services tiers, Canaux, Surveillances. Chacune ouvre sa rubrique seule, reste l'entrée active, et quitte le rail de Paramètres généraux.
const { test, expect } = require('@playwright/test');

test("Paramètres : cinq entrées, chacune ouvre sa rubrique seule et quitte le rail", async ({ page }) => {
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.waitForSelector('body.d19', { timeout: 20000 });
  const ids = ['reg-maintenance', 'reg-donnees', 'reg-tiers', 'reg-canaux', 'reg-veille'];
  await expect.poll(() => page.evaluate(async (ids) => { const d = await window.CASS.agir('affichage.lire_disposition', {}); const g = d.groupes.find((x) => x.id === 'parametres'); return !!g && ids.every((i) => g.entrees.some((e) => e.id === i)); }, ids), { timeout: 40000 }).toBe(true);
  await page.evaluate(() => window.CASS.disposition.rafraichir());

  // pas de tuile « Paramètres » dans la barre du haut ; la colonne de gauche liste tout le menu
  expect(await page.evaluate(() => [...document.querySelectorAll('#d19-groupes button')].map((b) => b.getAttribute('aria-label')))).not.toContain('Paramètres');
  await page.evaluate(() => window.CASS.disposition.aller('parametres', 'reg-donnees', ''));
  await expect.poll(() => page.evaluate(() => [...document.querySelectorAll('#d19-side .d19-si')].map((b) => b.textContent.trim()))).toEqual(expect.arrayContaining(['Mon compte', 'Mon coffre-fort', 'Paramètres généraux', 'Maintenance', 'Données', 'Services tiers', 'Canaux', 'Surveillances']));

  const titres = { 'reg-maintenance': 'Maintenance', 'reg-donnees': 'Données', 'reg-tiers': 'Services tiers', 'reg-canaux': 'Canaux', 'reg-veille': 'Surveillances' };
  for (const id of ids) {
    await page.evaluate((id) => window.CASS.disposition.aller('parametres', id, ''), id);
    await expect.poll(() => page.evaluate(() => document.querySelector('#tab-settings .mx-head h1').textContent)).toBe(titres[id]);
    expect(await page.evaluate(() => document.getElementById('tab-settings').classList.contains('set-seule'))).toBe(true);
    expect(await page.evaluate(() => [...document.querySelectorAll('#d19-side .d19-si.on')].map((b) => b.textContent.trim()))).toEqual([titres[id]]);   // l'entrée reste active
  }
  // le rail de Paramètres généraux ne porte plus leurs pastilles
  await page.evaluate(() => document.querySelector('#usermenu [data-um="machine"]').click());
  await expect.poll(() => page.evaluate(() => document.getElementById('tab-settings').classList.contains('set-seule'))).toBe(false);
  const rail = await page.evaluate(() => [...document.querySelectorAll('#tab-settings .set-nav-item')].filter((b) => getComputedStyle(b).display !== 'none').map((b) => b.getAttribute('data-fam')));
  for (const f of ['tiers', 'maintenance', 'donnees', 'veille', 'canaux']) expect(rail).not.toContain(f);
  expect(rail).toContain('danger');
});
