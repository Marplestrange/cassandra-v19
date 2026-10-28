// Utilisateurs et groupes : la liste, la fiche (droits en trois états appliqués d'un coup), les groupes, le départ d'un utilisateur, « voir comme », « qui peut… ? », la matrice et le journal.
const { test, expect } = require('@playwright/test');

test("Utilisateurs et groupes : liste, droits d'un compte et d'un groupe, départ, voir comme, qui peut, matrice, journal", async ({ page }) => {
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.evaluate(() => {
    window.__appels = [];
    let etat = { admins: ['root@x.fr'], groupes: [{ groupe: 'compta', libelle: 'Comptabilité', description: 'Factures', membres: ['bea@x.fr'] }], accords: [{ sujet_type: 'groupe', sujet: 'compta', droit: 'billetterie.voir', accord: 1 }] };
    const comptes = [{ compte: 'root@x.fr', display_name: 'Root', role_label: 'Admin', type: 'humain', sites: [] }, { compte: 'bea@x.fr', display_name: 'Béa', role_label: 'Compta', type: 'humain', sites: ['a.fr'] }];
    const catalogue = [{ droit: 'billetterie.voir', module: 'billetterie', libelle: 'Voir la billetterie', defaut: false, sensible: false }, { droit: 'coffre.reveler', module: 'coffre', libelle: 'Révéler un secret', defaut: false, sensible: true }];
    const decisions = (c) => ({ compte: c, admin: c === 'root@x.fr', groupes: c === 'bea@x.fr' ? ['compta'] : [], droits: catalogue.map((d) => {
      const propre = (etat.accords.find((x) => x.sujet_type === 'compte' && x.sujet === c && x.droit === d.droit) || {}).accord;
      const gr = c === 'bea@x.fr' && d.droit === 'billetterie.voir';
      return Object.assign({}, d, c === 'root@x.fr' ? { accord: true, parce: 'administrateur', propre: null } : propre === 1 ? { accord: true, parce: 'accordé au compte', propre: 'accorde' } : propre === 0 ? { accord: false, parce: 'refusé au compte', propre: 'refuse' } : gr ? { accord: true, parce: 'accordé par le groupe compta', propre: null } : { accord: false, parce: 'non attribué', propre: null });
    }) });
    window.CASS.agir = async (c, a) => {
      window.__appels.push([c, a]);
      if (c === 'comptes.lister') return { comptes };
      if (c === 'comptes.moi') return { compte: 'root@x.fr' };
      if (c === 'droits.etat') return etat;
      if (c === 'droits.catalogue') return { droits: catalogue };
      if (c === 'droits.decisions') return decisions(a.compte);
      if (c === 'societes.lister') return { societes: [{ id: '1', nom: 'Atelier Lumen', principale: true, archivee: false, ici: true, domicile: true }, { id: 'form', nom: 'Lumen Formation', principale: false, archivee: false, ici: false, domicile: false }], multi: true, superadmin: true, societe: '1' };
      if (c === 'societes.fonctions') return { societe: a.societe, fonctions: [{ fonction: 'membre', nom: 'Membre', membres: a.societe === 'form' ? ['bea@x.fr'] : [] }, { fonction: 'admin', nom: 'Administrateur', membres: [] }] };
      if (c === 'societes.affecter') return {};
      if (c === 'comptes.regles_mdp') return { regles: [], legende: '12 caractères au moins' };
      if (c === 'droits.appliquer') {
        etat = Object.assign({}, etat, { accords: etat.accords.filter((x) => !(x.sujet_type === a.sujet_type && x.sujet === a.sujet && a.accords[x.droit])).concat(Object.keys(a.accords || {}).filter((d) => a.accords[d] !== 'herite').map((d) => ({ sujet_type: a.sujet_type, sujet: a.sujet, droit: d, accord: a.accords[d] === 'accorde' ? 1 : 0 }))) });
        return { changes: Object.keys(a.accords || {}) };
      }
      if (c === 'droits.qui_peut') return { droit: a.droit, comptes: comptes.map((x) => ({ compte: x.compte, nom: x.display_name, type: 'humain', desactive: false, accord: x.compte === 'root@x.fr', parce: x.compte === 'root@x.fr' ? 'administrateur' : 'non attribué' })) };
      if (c === 'droits.voir_comme') return { compte: a.compte, admin: false, modules: [{ module: 'billetterie', nom: 'Billetterie', accordes: 1, total: 1 }, { module: 'coffre', nom: 'Coffre', accordes: 0, total: 1 }] };
      if (c === 'droits.journal') return { journal: [{ id: 1, ts: 1790000000, type: 'droit.change', par: 'root@x.fr', acteur: 'humain', agent: false, objet: 'bea@x.fr', donnees: { sujet_type: 'compte', sujet: 'bea@x.fr', changes: [{ droit: 'coffre.reveler', de: 'herite', a: 'refuse' }], admin: null } }, { id: 2, ts: 1790000100, type: 'droit.change', par: '', acteur: 'cassandra', agent: true, objet: 'bea@x.fr', donnees: { sujet_type: 'compte', sujet: 'bea@x.fr', changes: [{ droit: 'billetterie.voir', de: 'herite', a: 'accorde' }], admin: null } }] };
      return {};
    };
  });
  const monter = async (ecran) => {
    await page.evaluate(async (ecran) => {
      document.getElementById('cp-essai') && document.getElementById('cp-essai').remove();
      const hote = document.createElement('div'); hote.id = 'cp-essai'; hote.style.cssText = 'position:relative;z-index:1;background:var(--bg,#fff);padding:12px'; document.body.prepend(hote);
      await window.CASS.sceneSurMesure.comptes(hote, { ecran });
    }, ecran);
    return page.locator('#cp-essai .cu');
  };
  const appels = (c) => page.evaluate((c) => window.__appels.filter((a) => a[0] === c).map((a) => a[1]), c);

  // la liste : un administrateur, un groupe, le nombre de droits
  let k = await monter('comptes:u_liste');
  await expect(k.locator('tr.cu-l').filter({ hasText: 'Root' })).toContainText('administrateur');
  await expect(k.locator('tr.cu-l').filter({ hasText: 'Béa' })).toContainText('Comptabilité');
  await expect(k.locator('tr.cu-l').filter({ hasText: 'Béa' })).toContainText('1 / 2');

  // la fiche : refuser un droit, accorder un droit sensible (confirmation), appliquer d'un coup
  await k.locator('tr.cu-l[data-k="bea@x.fr"]').click();
  await expect(k.locator('h2')).toHaveText('Béa');
  await k.locator('.cu-rt[data-d="coffre.reveler"] button[data-v="accorde"]').click();
  await k.locator('.cu-rt[data-d="billetterie.voir"] button[data-v="refuse"]').click();
  await expect(k.locator('.cu-bar')).toContainText('2 modifications');
  await k.locator('[data-a="appliquer"]').click();
  await page.locator('.kit-m [data-c="oui"]').click();                                        // « Accorder des droits sensibles ? »
  await expect.poll(async () => (await appels('droits.appliquer')).pop()).toMatchObject({ sujet_type: 'compte', sujet: 'bea@x.fr', accords: { 'coffre.reveler': 'accorde', 'billetterie.voir': 'refuse' }, prevenir: true });
  await expect(k.locator('.cu-rt[data-d="billetterie.voir"] .cu-chip').first()).toContainText('Refusé');
  await expect(k.locator('.cu-rt[data-d="billetterie.voir"] .cu-why').last()).toContainText('refusé au compte');

  // l'onglet Sociétés : sa société, et une fonction dans une autre (accès sans être administrateur)
  await k.locator('button[data-a="onglet"][data-v="soc"]').click();
  await expect(k.locator('tr', { hasText: 'Lumen Formation' }).locator('select')).toHaveValue('membre');
  await k.locator('tr', { hasText: 'Atelier Lumen' }).locator('select').selectOption('admin');
  await expect.poll(async () => (await appels('societes.affecter')).some((x) => x.societe === '1' && x.utilisateur === 'bea@x.fr' && x.fonction === 'admin')).toBe(true);

  // les groupes : le départ, voir comme
  await k.locator('[data-a="comme"]').click();
  await expect(page.locator('.kit-m')).toContainText('Structure seulement');
  await page.locator('.kit-m [data-c]').click();
  await k.locator('[data-a="depart"]').click();
  await page.locator('.kit-m #dp-ok').click();
  await expect.poll(async () => (await appels('comptes.desactiver')).pop()).toEqual({ compte: 'bea@x.fr', vers: '', agents: 'revoquer' });

  // un groupe : ses droits, atteints à travers ses membres
  k = await monter('comptes:g_liste');
  await k.locator('tr.cu-l[data-k="compta"]').click();
  await k.locator('[data-a="onglet"][data-v="droits"]').click();
  await expect(k.locator('.cu-rt[data-d="billetterie.voir"] .cu-chip').first()).toContainText('membres');
  await k.locator('.cu-rt[data-d="billetterie.voir"] button[data-v="herite"]').click();
  await k.locator('[data-a="appliquer"]').click();
  await expect.poll(async () => (await appels('droits.appliquer')).pop()).toMatchObject({ sujet_type: 'groupe', sujet: 'compta', accords: { 'billetterie.voir': 'herite' } });

  // nouvel utilisateur : champ obligatoire, puis création
  k = await monter('comptes:u_nouveau');
  await k.locator('[data-a="nu-creer"]').click();
  await expect(k.locator('#nu-id')).toHaveClass(/cu-bad/);
  await k.locator('#nu-id').fill('nouveau@x.fr'); await k.locator('#nu-sites').fill('a.fr, b.fr');
  await k.locator('[data-a="nu-creer"]').click();
  await expect.poll(async () => (await appels('comptes.creer')).pop()).toMatchObject({ compte: 'nouveau@x.fr', sites: ['a.fr', 'b.fr'] });

  // qui peut, matrice, journal
  k = await monter('comptes:qui');
  await expect(k.locator('tr.cu-l').filter({ hasText: 'Root' })).toContainText('Oui');
  await expect(k.locator('tr.cu-l').filter({ hasText: 'Béa' })).toContainText('Non');
  k = await monter('comptes:matrice');
  await expect(k).toContainText('un module qui ne déclare aucun droit n\'est pas installé');
  await expect(k.locator('tr').filter({ hasText: 'coffre' })).toBeVisible();
  k = await monter('comptes:journal');
  await expect(k.locator('.cu-tl li').first()).toContainText('Humain');
  await expect(k.locator('.cu-tl li').nth(1)).toContainText('Agent');
});
