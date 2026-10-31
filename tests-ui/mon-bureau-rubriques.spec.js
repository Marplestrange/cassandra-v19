// Ma boîte mail, Mon agenda : deux entrées (Mon Itare vit dans Agents IA) du groupe Desk, chacune ouvre sa rubrique de « Mon compte » seule et quitte le rail de Mon compte.
const { test, expect } = require('@playwright/test');
test.setTimeout(150000);   // le premier chargement d'une instance neuve est lent

test("Desk : Mon agenda, Ma boîte mail ouvrent leur rubrique seule et quittent le rail de Mon compte", async ({ page }) => {
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.waitForSelector('body.d19', { timeout: 60000 });
  const ids = ['moi-agenda', 'moi-boite', 'moi-itare'];   // moi-itare : plus d'entrée, la rubrique reste masquée du rail
  await expect.poll(() => page.evaluate(async () => { const d = await window.CASS.agir('affichage.lire_disposition', {}); const g = d.groupes.find((x) => x.id === 'desk'); return !!g && !g.entrees.some((e) => e.id === 'moi-itare') && g.entrees.some((e) => e.id === 'agenda') && g.entrees.some((e) => e.id === 'courrier'); }), { timeout: 40000 }).toBe(true);
  await page.evaluate(() => window.CASS.disposition.rafraichir());

  // « Réglage agenda » est une vue de l'entrée Agenda, pas une entrée de plus
  expect(await page.evaluate(async () => { const d = await window.CASS.agir('affichage.lire_disposition', {}); const g = d.groupes.find((x) => x.id === 'desk'); const der = (id) => g.entrees.find((e) => e.id === id).enfants.map((f) => f.libelle).pop(); return [g.entrees.some((e) => e.id === 'moi-agenda' || e.id === 'moi-boite'), der('agenda'), der('courrier')]; })).toEqual([false, 'Réglage agenda', 'Réglage Mail']);
  for (const [entree, fam, titre] of [['agenda', 'moi-agenda', 'Réglage agenda'], ['courrier', 'moi-boite', 'Réglage Mail']]) {
    await page.evaluate((e) => window.CASS.disposition.aller('desk', e, 'reglage'), entree);
    await expect.poll(() => page.evaluate(() => document.getElementById('tab-settings').classList.contains('set-seule'))).toBe(true);
    expect(await page.evaluate(() => document.querySelector('#tab-settings .mx-head h1').textContent)).toBe(titre);
    expect(await page.evaluate((f) => document.querySelector('#tab-settings .settings-section[data-fam="' + f + '"]').offsetHeight, fam)).toBeGreaterThan(0);
    expect(await page.evaluate(() => [...document.querySelectorAll('#d19-side .d19-si.on')].map((b) => b.textContent.trim()).join('|'))).toContain(titre);
  }

  // Mon compte rend son rail, sans les trois rubriques déplacées
  await page.evaluate(() => document.querySelector('#usermenu [data-um="compte"]').click());
  await expect.poll(() => page.evaluate(() => document.getElementById('tab-settings').classList.contains('set-seule'))).toBe(false);
  const rail = await page.evaluate(() => [...document.querySelectorAll('#tab-settings .set-nav-item')].filter((b) => getComputedStyle(b).display !== 'none').map((b) => b.getAttribute('data-fam')));
  for (const f of ids) expect(rail).not.toContain(f);
  expect(rail).toContain('moi-identite');
});
