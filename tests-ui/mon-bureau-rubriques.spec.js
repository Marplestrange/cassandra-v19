// Ma boîte mail, Mon agenda, Mon Itare : trois entrées du groupe Desk, chacune ouvre sa rubrique de « Mon compte » seule et quitte le rail de Mon compte.
const { test, expect } = require('@playwright/test');

test("Desk : Mon agenda, Ma boîte mail, Mon Itare ouvrent leur rubrique seule et quittent le rail de Mon compte", async ({ page }) => {
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.waitForSelector('body.d19', { timeout: 20000 });
  const ids = ['moi-agenda', 'moi-boite', 'moi-itare'];
  await expect.poll(() => page.evaluate(async (ids) => { const d = await window.CASS.agir('affichage.lire_disposition', {}); const g = d.groupes.find((x) => x.id === 'desk'); return !!g && ids.every((i) => g.entrees.some((e) => e.id === i)); }, ids), { timeout: 40000 }).toBe(true);
  await page.evaluate(() => window.CASS.disposition.rafraichir());

  const titres = { 'moi-agenda': 'Mon agenda', 'moi-boite': 'Ma boîte mail', 'moi-itare': 'Mon Itare' };
  for (const id of ids) {
    await page.evaluate((id) => window.CASS.disposition.aller('desk', id, ''), id);
    await expect.poll(() => page.evaluate(() => document.getElementById('tab-settings').classList.contains('set-seule'))).toBe(true);
    expect(await page.evaluate(() => document.querySelector('#tab-settings .mx-head h1').textContent)).toBe(titres[id]);
    expect(await page.evaluate((id) => document.querySelector('#tab-settings .settings-section[data-fam="' + id + '"]').offsetHeight, id)).toBeGreaterThan(0);
  }
  // Mon compte rend son rail, sans les trois rubriques déplacées
  await page.evaluate(() => document.querySelector('#usermenu [data-um="compte"]').click());
  await expect.poll(() => page.evaluate(() => document.getElementById('tab-settings').classList.contains('set-seule'))).toBe(false);
  const rail = await page.evaluate(() => [...document.querySelectorAll('#tab-settings .set-nav-item')].filter((b) => getComputedStyle(b).display !== 'none').map((b) => b.getAttribute('data-fam')));
  for (const f of ids) expect(rail).not.toContain(f);
  expect(rail).toContain('moi-identite');
});
