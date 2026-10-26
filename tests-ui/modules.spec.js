// La page des modules : montée sur un catalogue simulé (le serveur d'essai n'a pas la gestion des modules) pour éprouver l'impact des changements et leur ordre d'application.
const { test, expect } = require('@playwright/test');

async function monter(page, gere) {
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.evaluate((gere) => {
    window.__appels = []; window.__console = [];
    const mod = (id, o) => Object.assign({ id, nom: id[0].toUpperCase() + id.slice(1), description: 'Module ' + id, version: '1.0', famille: 'socle', etat: 'actif', essentiel: false, importance: 'optionnel', sans: 'Sans ' + id + ' : rien de grave.', confiance: 'interne',
      requiert: [], requis_par: [], capacites: 3, detecteurs: 1, moteurs: 0, permissions: { reseau: [], ecritures: [] }, peut_activer: { ok: true, modules: [id] }, peut_desactiver: { ok: true } }, o);
    let cat = [mod('droits', { essentiel: true, importance: 'vital', requis_par: ['dns'] }),
      mod('dns', { importance: 'important', requiert: ['droits'], requis_par: ['certificats'], famille: 'reseau' }),
      mod('certificats', { etat: 'inactif', requiert: ['dns'], famille: 'securite', importance: 'important' }),
      mod('billetterie', { etat: 'a_installer', famille: 'gestion' })];
    const reel = window.CASS.modulesUi;                                                   // le VRAI validateur de tracés : c'est lui qu'on éprouve
    window.CASS.modulesUi = { lire: async () => {}, catalogue: () => cat, gere: () => gere, famLib: (f) => f, familles: () => ['socle', 'reseau', 'securite', 'gestion'], trace: reel && reel.trace, famTrace: () => '' };
    window.CASS.ouvrirConsole = (id, nom, onglet) => window.__console.push([id, onglet || null]);
    window.CASS.agir = async (c, a) => {
      window.__appels.push([c, a]);
      if (c === 'modules.activer') cat.find((m) => m.id === a.module).etat = 'actif';
      if (c === 'modules.desactiver') cat.find((m) => m.id === a.module).etat = 'inactif';
      return {};
    };
    const el = document.createElement('div'); el.id = 'mp-essai'; document.body.prepend(el);
    window.CASS.pageModules(el, 'tous', { rendre: async () => window.CASS.pageModules(el, 'tous', { rendre: async () => {} }) });
  }, gere);
}

test('instance de développement : une note, des interrupteurs grisés, les réglages restent accessibles', async ({ page }) => {
  await monter(page, false);
  const mp = page.locator('#mp-essai .mp');
  await expect(mp).toContainText('Instance de développement');
  await expect(mp.locator('input[data-bas]:not(:disabled)')).toHaveCount(0);
  await mp.locator('.rgl[data-reg="dns"]').click();
  expect(await page.evaluate(() => window.__console)).toEqual([['dns', 'reglages']]);          // l'engrenage ouvre la console sur l'onglet Réglages
});

test('gestion réelle : l’impact se dit avant, les dépendances se tirent, un bloqué se débloque en cascade, l’ordre d’application est sûr', async ({ page }) => {
  await monter(page, true);
  const mp = page.locator('#mp-essai .mp'), sur = page.locator('.mpo');
  await expect(mp.locator('.carte[data-id="droits"] input[data-bas]')).toBeDisabled();           // un essentiel ne se bascule jamais
  await expect(mp.locator('.carte[data-id="billetterie"] input[data-bas]')).toBeDisabled();       // à installer d'abord
  await expect(mp.locator('.carte[data-id="droits"]')).toContainText('Vital');

  await mp.locator('.carte[data-id="certificats"] input[data-bas]').evaluate((e) => e.click());   // activer Certificats
  await mp.locator('.carte[data-id="dns"] input[data-bas]').evaluate((e) => e.click());           // et désactiver DNS : incompatible
  await expect(sur.locator('.plateau')).toContainText('2 changements en attente');
  await expect(sur.locator('.plateau')).toContainText('Bloqué');
  await expect(sur.locator('.plateau [data-a="appliquer"]')).toBeDisabled();

  await sur.locator('.plateau [data-a="impact"]').click();
  await expect(sur.locator('.feuille')).toContainText('Impossible tel quel');
  await sur.locator('.feuille [data-a="cascade"]').click();                                        // désactiver aussi le dépendant : Certificats passe de « activer » à « désactiver »
  await expect(sur.locator('.feuille')).not.toContainText('Impossible tel quel');
  await expect(sur.locator('.feuille')).toContainText('Désactiver Dns');
  await sur.locator('.feuille [data-a="appliquer"]').click();
  await expect.poll(() => page.evaluate(() => window.__appels.filter((a) => a[0].indexOf('modules.') === 0).map((a) => a[0] + ':' + a[1].module))).toEqual(['modules.desactiver:certificats', 'modules.desactiver:dns']);   // le dépendant d'abord
});

test('activer un module active ses dépendances ; rien ne part avant l’accord', async ({ page }) => {
  await monter(page, true);
  const mp = page.locator('#mp-essai .mp'), sur = page.locator('.mpo');
  await mp.locator('.carte[data-id="dns"] input[data-bas]').evaluate((e) => e.click());           // désactiver DNS (Certificats est inactif : rien ne bloque)
  await mp.locator('.carte[data-id="certificats"] input[data-bas]').evaluate((e) => e.click());   // activer Certificats : tire DNS
  await sur.locator('.plateau [data-a="impact"]').click();
  expect(await page.evaluate(() => window.__appels.filter((a) => a[0].indexOf('modules.') === 0 && a[0] !== 'modules.lister' && a[0] !== 'modules.fiche').length)).toBe(0);
  await sur.locator('.feuille [data-a="retour"]').click();
  await sur.locator('.plateau [data-a="annuler"]').click();
  await expect(sur.locator('.plateau')).not.toHaveClass(/o/);
  expect(await page.evaluate(() => window.__appels.filter((a) => a[0].indexOf('modules.') === 0 && a[0] !== 'modules.lister' && a[0] !== 'modules.fiche').length)).toBe(0);
});

test('une icône apportée par un module est un tracé validé : celle d’un éditeur malveillant n’entre jamais dans la page', async ({ page }) => {
  await monter(page, true);
  await page.evaluate(() => {
    const cat = window.CASS.modulesUi.catalogue();
    cat[1].icone_trace = 'M12 3l8 4v5c0 4.4-3.1 7.6-8 9z';                         // dns : un tracé honnête
    cat[2].icone_trace = 'M0 0"/><script>window.__piege = 1</script><path d="M1 1';   // certificats : un piège
    window.CASS.pageModules(document.getElementById('mp-essai'), 'tous', { rendre: async () => {} });
  });
  const mp = page.locator('#mp-essai .mp');
  await expect(mp.locator('.carte[data-id="dns"] .ico path')).toHaveAttribute('d', 'M12 3l8 4v5c0 4.4-3.1 7.6-8 9z');
  await expect(mp.locator('.carte[data-id="certificats"] .ico path')).not.toHaveAttribute('d', /script/);          // le piège est refusé : l'icône de sa famille reste
  expect(await page.evaluate(() => window.__piege)).toBeUndefined();
  expect(await mp.locator('script').count()).toBe(0);
});
