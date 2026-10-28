// Société / Organisation : l'identité (aperçu en direct, validation du SIREN, enregistrement champ par champ), les fonctions (grille, confirmation d'un droit sensible,
// affectation), le coffre de la société (accès avec rôle, collections, date de fin), les droits qui masquent les rubriques, et le multi-sociétés réservé au superadministrateur
const { test, expect } = require('@playwright/test');

test("Société : identité, fonctions, coffre, rubriques fermées sans droit, multi-sociétés", async ({ page }) => {
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
    window.__acces = { fiche: 3, etablissements: 3, horaires: 3, pieces: 3, banque: 3, conformite: 3, habillage: 3, equipe: 3 };
    window.__multi = false;
    const rub = {
      identite: { forme: 'SAS', siren: '', ape: '', capital: '', creation: '', nom: 'Atelier Lumen' },
      siege: { adresse: '12 quai des Chartrons', cp: '33000', ville: 'Bordeaux', pays: 'France', tel: '', email: 'contact@lumen.test', web: '' },
      regional: { devise: 'EUR', langue: 'Français', fuseau: '' },
      presence: { linkedin: '', instagram: '', facebook: '', youtube: '', whatsapp: '' },
      etablissements: { items: [] },
      horaires: { jours: [0, 1, 2, 3, 4, 5, 6].map((i) => ({ o: i < 5, a: '09:00', f: '18:00' })), feries: true, exceptions: [] },
      pieces: { items: [{ id: 'p1', nom: 'Assurance', exp: '2999-01-01', lien: '' }] },
      banque: { iban: 'FR14 •••• •••• •••• 2606', bic: '', banque: '', pref_devis: '', pref_facture: '', tva_taux: '', exo_deb: '01-01', exo_fin: '12-31' },
      conformite: { mentions: true, rgpd: false, dpo: false, cgv: false, cookies: false },
      habillage: { accent: '#0b7c74', entete: 'classique', signature: 'complete' },
      roles: { titulaire: '', legal: '', dpo: '', facturation: '', securite: '' },
    };
    const niveaux = (n) => ({ fiche: n, etablissements: n, horaires: n, pieces: n, banque: n, conformite: n, habillage: n, equipe: n });
    const fonctions = [
      { id: 's1.titulaire', fonction: 'titulaire', nom: 'Titulaire', description: 'Propriétaire', niveaux: niveaux(3), membres: ['bea@x.fr'], fixe: true },
      { id: 's1.admin', fonction: 'admin', nom: 'Administrateur', description: 'Gère', niveaux: niveaux(2), membres: [], fixe: false },
      { id: 's1.membre', fonction: 'membre', nom: 'Membre', description: 'Consulte', niveaux: niveaux(1), membres: [], fixe: false },
    ];
    const membres = [{ compte: 'bea@x.fr', nom: 'Béa', fonction: 'titulaire', domicile: true }, { compte: 'cam@x.fr', nom: 'Cam', fonction: '', domicile: true }];
    let espaces = [{ id: 'u:bea@x.fr', genre: 'perso', nom: 'Mon coffre', role: 'proprio', secrets: 0, collections: '*', expire: '', admins: null }, { id: 's:1', genre: 'societe', nom: 'Atelier Lumen', role: 'admin', secrets: 2, collections: '', expire: '', mode: 'interne', admins: 1 }];
    let cof = [{ compte: 'bea@x.fr', role: 'admin', collections: '', expire: '', accorde_par: '', cree: '' }];
    window.CASS.agir = async (c, a) => {
      window.__appels.push([c, a]);
      if (c === 'societes.lister') return { societes: [{ id: '1', nom: rub.identite.nom, principale: true, archivee: false, ici: true, domicile: true }].concat(window.__multi ? [{ id: 'form', nom: 'Lumen Formation', principale: false, archivee: false, ici: false, domicile: false }] : []), multi: window.__multi, superadmin: true, societe: '1' };
      if (c === 'societes.fiche_lire') {
        const ouvert = {}; const ac = window.__acces;
        const dom = { identite: 'fiche', siege: 'fiche', regional: 'fiche', presence: 'fiche', etablissements: 'etablissements', horaires: 'horaires', pieces: 'pieces', banque: 'banque', conformite: 'conformite', habillage: 'habillage', roles: 'equipe' };
        Object.keys(rub).forEach((r) => { if ((ac[dom[r]] || 0) >= 1) ouvert[r] = JSON.parse(JSON.stringify(rub[r])); });
        return { societe: '1', rubriques: ouvert, acces: ac };
      }
      if (c === 'societes.fiche_regler') { Object.assign(rub[a.rubrique], a.valeurs); if (a.valeurs.siren === '123456789') throw new Error('siren : 9 chiffres, clé de contrôle valide'); return { societe: '1', rubrique: a.rubrique }; }
      if (c === 'societes.fonctions') return { societe: '1', fonctions, domaines: Object.keys(niveaux(0)) };
      if (c === 'societes.membres') return { societe: '1', membres };
      if (c === 'societes.fonction_regler') { fonctions.find((f) => f.fonction === a.fonction).niveaux[a.domaine] = a.niveau; return {}; }
      if (c === 'societes.affecter') { return {}; }
      if (c === 'societes.echeances') return { societe: '1', echeances: [{ nom: 'Assurance', date: '2999-01-01', jours: 400, genre: 'piece' }] };
      if (c === 'societes.historique') return { societe: '1', historique: [{ id: 1, ts: 1790000000, qui: 'bea@x.fr', rubrique: 'siege', resume: 'a modifié ville' }] };
      if (c === 'societes.iban_voir') return { iban: 'FR1420041010050500013M02606' };
      if (c === 'societes.creer') { window.__multi = true; return { societe: 'form' }; }
      if (c === 'reglages.regler') { if (a.cle === 'societes.multi') window.__multi = !!a.valeur; else window.__vm = a.valeur; return {}; }
      if (c === 'coffre.espaces') return { espaces };
      if (c === 'coffre.membres') return { espace: 's:1', membres: cof, admins: 1 };
      if (c === 'coffre.list') return { noms: [], secrets: [{ nom: 'banque', auteur: 'bea@x.fr', collection: 'compta' }, { nom: 'ovh', auteur: 'bea@x.fr', collection: 'hebergement' }], espace: 's:1', role: 'admin' };
      if (c === 'coffre.accorder') { cof = cof.filter((x) => x.compte !== a.utilisateur).concat([{ compte: a.utilisateur, role: a.role, collections: a.collections, expire: a.expire, accorde_par: '', cree: '' }]); return {}; }
      if (c === 'coffre.retirer') { cof = cof.filter((x) => x.compte !== a.utilisateur); return {}; }
      if (c === 'societes.modules') return { societe: '1', modules: [{ id: 'comptes', nom: 'Comptes', importance: 'vital', vital: true, ouvert: true, choisi: false }, { id: 'ged', nom: 'Documents', importance: 'optionnel', vital: false, ouvert: !!window.__ged, choisi: true }], peut_regler: true };
      if (c === 'societes.module_regler') { window.__ged = !!a.ouvert; return {}; }
      if (c === 'reglages.lire') return { societe: '1', reglages: [{ cle: 'contacts.vue_modele', module: 'contacts', libelle: 'Ce qu’un modèle voit', type: 'choix', portee: 'societe', valeur: window.__vm || 'expurgee', pose: !!window.__vm, choix: ['expurgee', 'complete'], aide: '' }, { cle: 'comptes.session_heures', module: 'comptes', libelle: 'Durée', type: 'entier', portee: 'global', valeur: 24, pose: false, choix: [], aide: '' }] };
      if (c === 'reglages.reinitialiser') { window.__vm = ''; return {}; }
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

  // l'identité : un aperçu qui suit la saisie, un SIREN contrôlé, un champ enregistré à la validation
  let k = await monter('societes:s_identite');
  await expect(k.locator('#so-pv')).toContainText('Atelier Lumen SAS');
  await k.locator('#c-identite-nom').fill('Atelier Lumen Test');
  await expect(k.locator('#so-pv')).toContainText('Atelier Lumen Test');
  await k.locator('#c-identite-siren').fill('123456789');
  await expect(k.locator('#h-siren')).toContainText('invalide');
  await k.locator('#c-identite-siren').fill('123 456 782');
  await expect(k.locator('#h-siren')).toContainText('Valide');
  await k.locator('#c-identite-siren').press('Tab');
  await expect.poll(async () => (await appels('societes.fiche_regler')).filter((x) => x.rubrique === 'identite' && x.valeurs.siren).length).toBeGreaterThan(0);
  await expect(k.locator('#so-pv')).toContainText('FR');                               // la TVA se déduit du SIREN valide
  await k.locator('button[data-a="sug"]').click();                                     // la suggestion de Cassandra : le fuseau
  await expect.poll(async () => (await appels('societes.fiche_regler')).some((x) => x.rubrique === 'regional' && x.valeurs.fuseau === 'Europe/Paris')).toBe(true);

  // la banque : l'IBAN est masqué, son affichage passe par la capacité qui l'inscrit à l'historique
  k = await monter('societes:s_banque');
  await expect(k.locator('#b-iban')).toHaveValue(/••••/);
  await k.locator('button[data-a="iban"]').click();
  await expect(k.locator('#b-iban')).toHaveValue('FR1420041010050500013M02606');
  expect((await appels('societes.iban_voir')).length).toBe(1);

  // les fonctions : un droit sensible demande confirmation ; une fonction se donne à un utilisateur
  k = await monter('societes:s_fonctions');
  await expect(k.locator('th').filter({ hasText: 'Administrateur' })).toBeVisible();
  await k.locator('select[data-fc="admin|equipe"]').selectOption('3');
  await page.locator('.kit-m [data-c="oui"]').click();
  await expect.poll(async () => (await appels('societes.fonction_regler')).some((x) => x.fonction === 'admin' && x.domaine === 'equipe' && x.niveau === 3)).toBe(true);
  await k.locator('select[data-af="cam@x.fr"]').selectOption('membre');
  await expect.poll(async () => (await appels('societes.affecter')).some((x) => x.utilisateur === 'cam@x.fr' && x.fonction === 'membre')).toBe(true);

  // le coffre : l'accès se donne avec un rôle, des collections et une date de fin facultative
  k = await monter('societes:s_coffre');
  await expect(k.locator('table')).toContainText('compta');
  await k.locator('#cm-n').selectOption('cam@x.fr');
  await k.locator('#cm-r').selectOption('contrib');
  await k.locator('#cm-c').fill('compta');
  await k.locator('#cm-e').fill('2999-12-31');
  await k.locator('button[data-a="cof-accorder"]').click();
  await expect.poll(async () => (await appels('coffre.accorder')).some((x) => x.espace === 's:1' && x.utilisateur === 'cam@x.fr' && x.role === 'contrib' && x.collections === 'compta' && x.expire === '2999-12-31')).toBe(true);

  // sans droit sur un domaine, la rubrique se ferme avec une explication
  await page.evaluate(() => { window.__acces = { fiche: 1, etablissements: 0, horaires: 0, pieces: 0, banque: 0, conformite: 0, habillage: 0, equipe: 0 }; });
  k = await monter('societes:s_banque');
  await expect(k).toContainText('ne vous ouvre pas cette rubrique');
  k = await monter('societes:s_identite');
  await expect(k.locator('#c-identite-nom')).toBeDisabled();                           // voir n'est pas modifier

  // les modules de la société : un module vital reste ouvert, les autres s'ouvrent et se ferment
  k = await monter('societes:s_modules');
  await expect(k.locator('tr', { hasText: 'Comptes' })).toContainText('toujours ouvert');
  await k.locator('button[data-a="mod"][data-id="ged"]').click();
  await expect.poll(async () => (await appels('societes.module_regler')).some((x) => x.module === 'ged' && x.ouvert === true && x.societe === '1')).toBe(true);
  await expect(k.locator('button[data-a="mod"][data-id="ged"]')).toHaveClass(/on/);

  // les réglages de la société : seuls ceux qui peuvent différer d'une société à l'autre ; on les pose, puis on reprend la valeur de l'instance
  k = await monter('societes:s_reglages');
  await expect(k).toContainText('contacts');
  await expect(k).not.toContainText('Durée');
  await k.locator('select[data-rg="contacts.vue_modele"]').selectOption('complete');
  await expect.poll(async () => (await appels('reglages.regler')).some((x) => x.cle === 'contacts.vue_modele' && x.valeur === 'complete' && x.pour_societe === '1')).toBe(true);
  await expect(k).toContainText('propre à la société');
  await k.locator('button[data-a="rg-reset"]').click();
  await expect.poll(async () => (await appels('reglages.reinitialiser')).length).toBe(1);

  // le multi-sociétés : l'activation est proposée, puis la création d'une société
  await page.evaluate(() => { window.__acces = { fiche: 3, etablissements: 3, horaires: 3, pieces: 3, banque: 3, conformite: 3, habillage: 3, equipe: 3 }; });
  k = await monter('societes:s_multi');
  await expect(k).toContainText('Non activé');
  await k.locator('button[data-a="multi-on"]').click();
  await expect(k).toContainText('Sociétés de l’instance');
  await k.locator('#sc-n').fill('Lumen Formation');
  await k.locator('#sc-a').fill('cam@x.fr');
  await k.locator('button[data-a="soc-add"]').click();
  await expect.poll(async () => (await appels('societes.creer')).some((x) => x.nom === 'Lumen Formation' && x.administrateur === 'cam@x.fr')).toBe(true);
});
