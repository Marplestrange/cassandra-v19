// La console d'un module : montée sur un module simulé (fiche, lectures, gestes, réglages) pour vérifier ce qu'elle montre et surtout ce qu'elle ne lance pas sans confirmation.
const { test, expect } = require('@playwright/test');

test('console de module : aperçu, lectures triables, gestes confirmés, réglages enregistrés', async ({ page }) => {
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.evaluate(async () => {
    window.__appels = [];
    const cap = (id, o) => Object.assign({ cle: 'essai.' + id, id, droit: '', ecrit: false, libelle: 'Libellé de ' + id, masque: [], parametres: [], perimetre: [], preuve: '', retour: '', reversible: false, risque: 'lecture' }, o || {});
    const fiche = { module: { id: 'essai', nom: 'Module d’essai', description: 'Un module pour l’essai.', etat: 'actif', famille: 'reseau', version: '1.2.3', requiert: [], requis_par: ['autre'] },
      capacites: [cap('liste'), cap('un'), cap('trois', { parametres: [{ nom: 'n', type: 'entier', requis: false, defaut: 5 }] }),
        cap('geste_doux', { ecrit: true, risque: 'faible', retour: 'rien' }),
        cap('geste_lourd', { ecrit: true, risque: 'moyen', droit: 'essai.gerer', perimetre: ['une zone'], preuve: 'relire', retour: 'remettre', reversible: true, parametres: [{ nom: 'nom', type: 'texte', requis: true, defaut: '' }] })] };
    window.CASS.agir = async (c, a) => {
      window.__appels.push([c, a]);
      if (c === 'modules.fiche') return fiche;
      if (c === 'modules.lister') return { gere: false, modules: [{ id: 'essai', detecteurs: 2, moteurs: 1, objets: 1, ecrans: 1, auteur: 'Moi', licence: 'AGPL', permissions: { reseau: ['rdap.org'], ecritures: [] } }] };
      if (c === 'evolution.etat') return { points: [{ point: 'essai.calcul', etat: 'reference' }] };
      if (c === 'reglages.lire') return { reglages: [{ cle: 'essai.seuil', module: 'essai', libelle: 'Le seuil', aide: 'en jours', type: 'entier', valeur: 45, defaut: 45, pose: false, choix: [] }] };
      if (c === 'reglages.historique') return { historique: [{ ts: Date.now() / 1000, par: 'moi', avant: null, apres: 50 }] };
      if (c === 'essai.liste') return [{ nom: 'b', n: 2 }, { nom: 'a', n: 10 }, { nom: 'c', n: 1 }];
      if (c === 'essai.un') return { ok: true, valeur: 7 };
      return {};
    };
    const hote = document.createElement('div'); hote.id = 'cx-essai'; document.body.prepend(hote);
    await window.CASS.console('essai', hote);
  });
  const cx = page.locator('#cx-essai .cmx');
  await expect(cx.locator('h2')).toHaveText('Module d’essai');
  await expect(cx.locator('.onglets [data-o]')).toHaveCount(5);                          // aperçu, lectures, gestes, réglages, évolution
  await expect(cx).toContainText('rdap.org');                                            // ce que le module peut faire hors de lui
  await expect(cx).toContainText('geste_lourd');                                         // un geste qui compte est signalé dès l'aperçu

  await cx.locator('[data-o="lire"]').click();
  const table = cx.locator('table[data-t]').first();
  await expect(table).toBeVisible({ timeout: 5000 });                                     // les deux premières lectures sans paramètre se lisent seules
  await table.locator('th').nth(1).click();                                              // tri par la colonne n
  await expect(table.locator('tbody tr').first().locator('td').first()).toHaveText('c');
  await expect(cx.locator('.cap').nth(2).locator('.res')).toBeEmpty();                   // la troisième, à paramètre, attend le clic

  await cx.locator('[data-o="agir"]').click();
  await cx.locator('.cap').filter({ hasText: 'geste_lourd' }).locator('input[data-p="nom"]').fill('x');
  const go = cx.locator('.cap').filter({ hasText: 'geste_lourd' }).locator('[data-go]');
  await go.click();                                                                       // premier clic : confirmation demandée, rien n'est lancé
  await expect(go).toHaveText('Confirmer ?');
  expect(await page.evaluate(() => window.__appels.some((a) => a[0] === 'essai.geste_lourd'))).toBe(false);
  await go.click();
  await expect.poll(() => page.evaluate(() => window.__appels.filter((a) => a[0] === 'essai.geste_lourd').map((a) => a[1]))).toEqual([{ nom: 'x' }]);

  await cx.locator('[data-o="reglages"]').click();
  await expect(cx.locator('.rg')).toHaveCount(1);
  await cx.locator('.rg input').fill('60');
  await cx.locator('.rg input').dispatchEvent('change');
  await expect.poll(() => page.evaluate(() => window.__appels.filter((a) => a[0] === 'reglages.regler').map((a) => a[1]))).toEqual([{ cle: 'essai.seuil', valeur: 60 }]);
});
