// Société › Partages et Carnet de la société : ce qu'une société partage (utilisateurs, carnet de contacts), les utilisateurs partagés à ranger dans une fonction,
// le carnet commun de la société (ajout, corbeille) et le carnet qu'une autre société partage (lecture seule)
const { test, expect } = require('@playwright/test');

test("Société : partages entre sociétés et carnet de la société", async ({ page }) => {
  test.setTimeout(120000);
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.evaluate(() => {
    window.__appels = [];
    const niv = (n) => ({ fiche: n, etablissements: n, horaires: n, pieces: n, banque: n, conformite: n, habillage: n, equipe: n });
    window.__acces = niv(3);
    let partages = [{ source: '1', destinataire: 'form', type: 'utilisateurs', mode: 'tous', actif: true, elements: [], nom_source: 'Atelier Lumen', nom_destinataire: 'Lumen Formation' }];
    let carnet = [{ id: 7, display_name: 'Client Un', company: 'Un SARL', emails: ['un@client.fr'], phone: '0102030405' }];
    const fonctions = [{ id: 's1.admin', fonction: 'admin', nom: 'Administrateur', description: '', niveaux: niv(3), membres: [], fixe: false }, { id: 's1.membre', fonction: 'membre', nom: 'Membre', description: '', niveaux: niv(1), membres: [], fixe: false }];
    window.CASS.agir = async (c, a) => {
      window.__appels.push([c, a]);
      if (c === 'societes.lister') return { societes: [{ id: '1', nom: 'Atelier Lumen', principale: true, archivee: false, ici: true, domicile: true }, { id: 'form', nom: 'Lumen Formation', principale: false, archivee: false, ici: false, domicile: false }], multi: true, superadmin: true, societe: '1' };
      if (c === 'societes.fiche_lire') return { societe: '1', rubriques: { identite: { nom: 'Atelier Lumen', forme: 'SAS' } }, acces: window.__acces };
      if (c === 'societes.partages') return { societe: '1', sortants: partages.filter((p) => p.source === '1'), entrants: [{ source: 'form', destinataire: '1', type: 'contacts', mode: 'tous', actif: true, elements: [], nom_source: 'Lumen Formation', nom_destinataire: 'Atelier Lumen' }], peut_decider: true };
      if (c === 'societes.partageables') return { societe: '1', utilisateurs: [{ compte: 'zoe@x.fr', societe: 'form', fonction: '' }] };
      if (c === 'societes.fonctions') return { societe: '1', fonctions, domaines: Object.keys(window.__acces) };
      if (c === 'societes.membres') return { societe: '1', membres: [{ compte: 'bea@x.fr', nom: 'Béa', fonction: 'titulaire', domicile: true }, { compte: 'cam@x.fr', nom: 'Cam', fonction: '', domicile: true }] };
      if (c === 'societes.partager') { partages = partages.filter((p) => !(p.destinataire === a.destinataire && p.type === a.type)).concat([{ source: a.source, destinataire: a.destinataire, type: a.type, mode: a.mode, actif: true, elements: a.elements || [], nom_source: 'Atelier Lumen', nom_destinataire: 'Lumen Formation' }]); return {}; }
      if (c === 'societes.partage_retirer') { partages = partages.filter((p) => !(p.destinataire === a.destinataire && p.type === a.type)); return {}; }
      if (c === 'societes.affecter') return {};
      if (c === 'contacts.societe_lister') return { contacts: carnet };
      if (c === 'contacts.societe_creer') { carnet = carnet.concat([{ id: 8, display_name: a.display_name, company: a.company, emails: a.emails, phone: a.phone }]); return { id: 8 }; }
      if (c === 'contacts.societe_supprimer') { carnet = carnet.filter((x) => a.ids.indexOf(x.id) < 0); return {}; }
      if (c === 'contacts.societe_partage_lister') return { depuis: a.depuis, contacts: [{ id: 3, display_name: 'Fournisseur Formation', company: '', emails: ['f@form.fr'], phone: '' }] };
      if (c === 'comptes.moi') return { compte: 'bea@x.fr' };
      return {};
    };
  });
  const monter = async (ecran) => {
    await page.evaluate(async (ecran) => {
      document.getElementById('so-essai') && document.getElementById('so-essai').remove();
      const hote = document.createElement('div'); hote.id = 'so-essai'; hote.style.cssText = 'position:relative;z-index:1;background:var(--bg,#fff);padding:12px'; document.body.prepend(hote);
      await window.CASS.sceneSurMesure.societes(hote, { ecran });
    }, ecran);
    const k = page.locator('#so-essai .so');
    await expect(k).not.toContainText('Chargement…');
    return k;
  };
  const appels = (c) => page.evaluate((c) => window.__appels.filter((a) => a[0] === c).map((a) => a[1]), c);

  // les partages : ce qu'on reçoit, ce qu'on donne, les utilisateurs à ranger
  let k = await monter('societes:s_partages');
  await expect(k).toContainText('Utilisateurs partagés avec Atelier Lumen');
  await expect(k).toContainText('Lumen Formation');                                         // l'entrant (carnet partagé) et le sortant (utilisateurs)
  await expect(k).toContainText('carnet de contacts');
  await expect(k.locator('select[data-af="zoe@x.fr"]')).toBeVisible();                     // un utilisateur partagé qu'on peut ranger
  await k.locator('select[data-af="zoe@x.fr"]').selectOption('membre');
  await expect.poll(async () => (await appels('societes.affecter')).some((x) => x.utilisateur === 'zoe@x.fr' && x.fonction === 'membre')).toBe(true);

  // un partage de carnet : toujours en entier, quelle que soit la sélection
  await k.locator('#pt-ty').selectOption('contacts');
  await k.locator('button[data-a="part-add"]').click();
  await expect.poll(async () => (await appels('societes.partager')).some((x) => x.type === 'contacts' && x.mode === 'tous')).toBe(true);
  await expect(k).toContainText('carnet de contacts');
  // le retrait d'un partage demande confirmation
  await k.locator('button[data-a="part-del"][data-ty="utilisateurs"]').click();
  await page.locator('[data-c="oui"]').click();
  await expect.poll(async () => (await appels('societes.partage_retirer')).some((x) => x.type === 'utilisateurs')).toBe(true);

  // le carnet de la société : une fiche commune, un ajout, la corbeille, et le carnet partagé en lecture seule
  k = await monter('societes:s_carnet');
  await expect(k).toContainText('Carnet de Atelier Lumen');
  await expect(k).toContainText('Client Un');
  await expect(k).toContainText('Fournisseur Formation');
  await expect(k.locator('section').filter({ hasText: 'Fournisseur Formation' }).locator('button[data-a="car-del"]')).toHaveCount(0);   // le carnet d'une autre société ne s'efface pas d'ici
  await k.locator('#car-n').fill('Client Deux');
  await k.locator('#car-e').fill('deux@client.fr');
  await k.locator('button[data-a="car-add"]').click();
  await expect(k).toContainText('Client Deux');
  expect((await appels('contacts.societe_creer'))[0].emails).toEqual(['deux@client.fr']);
  await k.locator('tr', { hasText: 'Client Un' }).locator('button[data-a="car-del"]').click();
  await expect(k).not.toContainText('Client Un');
  expect((await appels('contacts.societe_supprimer'))[0].ids).toEqual([7]);
});
