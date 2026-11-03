// « Mon compte » : le menu de l'avatar et la colonne Personnel ouvrent les six pages de l'écran personnel (CN_moncompte-ecran.js) ; « Paramètres généraux » garde sa vision.
const { test, expect } = require('@playwright/test');

async function entrer(page) {
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.waitForSelector('body.d19', { timeout: 20000 });
  await expect.poll(() => page.evaluate(() => document.querySelectorAll('#d19-groupes button').length), { timeout: 30000 }).toBeGreaterThan(0);        // la disposition est chargée
}
const visible = (page) => page.evaluate(() => { const r = [...document.querySelectorAll('.cu.mc')].filter((x) => x.offsetParent).pop(); return r ? r.innerText : ''; });

test("avatar : Mon compte ouvre la vue d'ensemble, Paramètres généraux sa première rubrique", async ({ page }) => {
  await entrer(page);
  const libelles = await page.evaluate(() => [...document.querySelectorAll('#usermenu .um-i')].map((b) => b.textContent.trim().replace(/\s+/g, ' ')));
  expect(libelles).toEqual(expect.arrayContaining(['Mon compte', 'Paramètres généraux']));
  await page.evaluate(() => document.querySelector('#usermenu [data-um="compte"]').click());
  await expect.poll(() => visible(page), { timeout: 15000 }).toContain('À faire sur mon compte');
  await page.evaluate(() => document.querySelector('#usermenu [data-um="machine"]').click());
  await expect.poll(() => page.evaluate(() => document.querySelector('#tab-settings .mx-head h1').textContent)).toBe('Maintenance');       // « Paramètres généraux » ouvre sa première rubrique
});

test("les six pages de Mon compte se dessinent, et la fiche s'enregistre ou refuse le trop long", async ({ page }) => {
  await entrer(page);
  const pages = { mc_accueil: 'Dernière activité sur mon compte', mc_profil: 'Identité', mc_liens: 'Mes branchements', mc_alertes: 'Par gravité', mc_secu: 'Journal de mon compte', mc_donnees: 'Mes droits' };
  for (const [ecran, texte] of Object.entries(pages)) {
    await page.evaluate((e) => window.CASS.ouvrirEcran('comptes:' + e, e), ecran);
    await expect.poll(() => visible(page), { timeout: 15000 }).toContain(texte);
  }
  await page.evaluate(() => window.CASS.ouvrirEcran('comptes:mc_profil', 'Profil'));
  await expect.poll(() => visible(page), { timeout: 15000 }).toContain('Identité');
  const champ = (c) => page.locator('.cu.mc:visible [data-champ="' + c + '"]');
  await champ('lastname').fill('x'.repeat(60));
  await page.locator('.cu.mc:visible [data-a="enregistrer"]').click();
  await expect(page.locator('.cu.mc:visible #mc-err')).toContainText("rien n'est coupé");
  await champ('lastname').fill('ESSAI');
  await champ('firstname').fill('Uma');
  await page.locator('.cu.mc:visible [data-a="enregistrer"]').click();
  await expect.poll(() => page.evaluate(() => { const e = [...document.querySelectorAll('.cu.mc')].filter((x) => x.offsetParent).pop().querySelector('[data-champ="lastname"]'); return e && e.value; })).toBe('ESSAI');
});
