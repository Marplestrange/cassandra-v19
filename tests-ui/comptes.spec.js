// L'écran Utilisateurs et groupes : la liste, une fiche (profil, groupes, administrateur, lien), les groupes, la matrice des droits (hérité / accordé / refusé), la corbeille.
const { test, expect } = require('@playwright/test');

test("Utilisateurs et groupes : comptes, groupes, droits, corbeille", async ({ page }) => {
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.evaluate(async () => {
    window.__appels = [];
    let etat = { admins: ['root@x.fr'], groupes: [{ groupe: 'compta', libelle: 'Comptabilité', membres: ['bea@x.fr'] }], accords: [{ sujet_type: 'groupe', sujet: 'compta', droit: 'billetterie.voir', accord: 1 }] };
    const comptes = [{ compte: 'root@x.fr', display_name: 'Root', role_label: 'Admin', type: 'humain' }, { compte: 'bea@x.fr', display_name: 'Béa', role_label: 'Compta', type: 'humain' }];
    const catalogue = [{ droit: 'billetterie.voir', module: 'billetterie', libelle: 'Voir la billetterie', defaut: false, sensible: false }, { droit: 'coffre.reveler', module: 'coffre', libelle: 'Révéler un secret', defaut: false, sensible: true }];
    window.CASS.agir = async (c, a) => {
      window.__appels.push([c, a]);
      if (c === 'comptes.lister') return { comptes };
      if (c === 'comptes.moi') return { compte: 'root@x.fr' };
      if (c === 'droits.etat') return etat;
      if (c === 'droits.catalogue') return { droits: catalogue };
      if (c === 'droits.mes_droits') return { compte: a.compte, admin: false, groupes: ['compta'], droits: ['billetterie.voir'] };
      if (c === 'comptes.regles_mdp') return { regles: [], legende: '12 caractères au moins' };
      if (c === 'comptes.creer_jeton') return { compte: a.compte, jeton: 'JETON-123' };
      if (c === 'comptes.corbeille') return { corbeille: [{ id: 4, compte: 'vieux@x.fr', ts: 1790000000 }] };
      if (c === 'droits.regler') { etat = Object.assign({}, etat, { accords: etat.accords.filter((x) => !(x.sujet === a.sujet && x.droit === a.droit)).concat(a.valeur === 'herite' ? [] : [{ sujet_type: a.sujet_type, sujet: a.sujet, droit: a.droit, accord: a.valeur === 'accorde' ? 1 : 0 }]) }); return {}; }
      if (c === 'droits.groupe' && !a.supprimer) { etat = Object.assign({}, etat, { groupes: etat.groupes.concat([{ groupe: a.groupe, libelle: a.libelle, membres: [] }]) }); return {}; }
      return {};
    };
    const hote = document.createElement('div'); hote.id = 'cp-essai'; hote.style.cssText = 'position:relative;z-index:1;background:var(--bg,#fff);padding:12px'; document.body.prepend(hote);
    await window.CASS.sceneSurMesure.comptes(hote, { ecran: 'comptes:vue_utilisateurs' });
  });
  const k = page.locator('#cp-essai .kit');
  const appels = (c) => page.evaluate((c) => window.__appels.filter((a) => a[0] === c).map((a) => a[1]), c);
  await expect(k.locator('.onglets button')).toHaveText(['Utilisateurs', 'Groupes', 'Droits', 'Corbeille']);
  await expect(k).toContainText('Béa');
  await expect(k.locator('.li').filter({ hasText: 'Root' })).toContainText('administrateur');
  await expect(k.locator('.li').filter({ hasText: 'Béa' })).toContainText('Comptabilité');

  // une fiche : nom affiché, lien de mise en place, suppression refusée pour soi
  await k.locator('[data-a="fiche"][data-k="bea@x.fr"]').click();
  await k.locator('#cp-f-display_name').fill('Béatrice'); await k.locator('[data-a="profil"]').click();
  await expect.poll(async () => (await appels('comptes.modifier')).pop()).toMatchObject({ compte: 'bea@x.fr', display_name: 'Béatrice' });
  await k.locator('[data-a="jeton"]').click();
  await expect(k).toContainText('JETON-123');
  await k.locator('[data-a="membre"][data-g="compta"]').click();
  await expect.poll(async () => (await appels('droits.membre')).pop()).toEqual({ compte: 'bea@x.fr', groupe: 'compta', present: false });
  await k.locator('[data-a="retour"]').click();
  await k.locator('[data-a="fiche"][data-k="root@x.fr"]').click();
  await expect(k.locator('[data-a="supprimer"]')).toBeDisabled();
  await k.locator('[data-a="retour"]').click();

  // la matrice : l'héritage d'un groupe, puis un refus posé
  await k.locator('[data-s="droits"]').click();
  await k.locator('select[data-a="sujet"]').selectOption('groupe|compta');
  await expect(k.locator('.li').filter({ hasText: 'Voir la billetterie' }).locator('button.on')).toHaveText('Accordé');
  await expect(k.locator('.li').filter({ hasText: 'Révéler un secret' })).toContainText('sensible');
  await k.locator('.li').filter({ hasText: 'Révéler un secret' }).locator('[data-v="refuse"]').click();
  await expect.poll(async () => (await appels('droits.regler')).pop()).toEqual({ sujet_type: 'groupe', sujet: 'compta', droit: 'coffre.reveler', valeur: 'refuse' });
  await expect(k.locator('.li').filter({ hasText: 'Révéler un secret' }).locator('button.on')).toHaveText('Refusé');
  await k.locator('select[data-a="sujet"]').selectOption('compte|bea@x.fr');
  await expect(k.locator('.li').filter({ hasText: 'Voir la billetterie' })).toContainText('peut');
  await k.locator('select[data-a="sujet"]').selectOption('compte|root@x.fr');
  await expect(k).toContainText('est administrateur');                                     // un administrateur n'a rien à régler

  // un groupe, la corbeille
  await k.locator('[data-s="groupes"]').click();
  await k.locator('#cp-gid').fill('tech'); await k.locator('#cp-glib').fill('Technique'); await k.locator('[data-a="groupe-creer"]').click();
  await expect(k).toContainText('Technique');
  await k.locator('[data-s="corbeille"]').click();
  await k.locator('[data-a="restaurer"]').click();
  await expect.poll(async () => (await appels('comptes.restaurer')).pop()).toEqual({ corbeille: 4 });
});
