// La page App Store : montée sur des réponses simulées (le serveur d'essai n'a ni quarantaine ni registre) pour vérifier ce qu'elle montre, ce qu'elle exige (le consentement) et ce qu'elle n'envoie JAMAIS sans accord.
const { test, expect } = require('@playwright/test');

test("App Store : l'examen dit tout, l'installation exige le consentement, un refus ne s'installe pas", async ({ page }) => {
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.evaluate(async () => {
    window.__appels = []; window.__envoyes = 0;
    const base = { jeton: 'a'.repeat(24), id: 'sentinelle', nom: 'Sentinelle du disque', version: '0.2.0', description: 'Mesure le disque.', famille: 'supervision', confiance: 'local', importance: 'optionnel', sans: 'Plus de mesure du disque.',
      signe: true, editeur: 'ed_atek', niveau: 'verifie', taille: 2048, nb_fichiers: 7, fichiers: [], permissions: { reseau: ['api.exemple.org'], privileges: ['installer'] }, empreinte_permissions: 'abcdef0123456789',
      permissions_elargies: ['reseau : api.exemple.org'], statut: 'mise_a_jour', version_en_place: '0.1.2', requiert: ['droits'], requiert_manquants: [], versions_insuffisantes: [], conflits: [], casserait: [], politique: 'signes', autorise: true, raisons: [], avertissements: [] };
    window.__exam = base;
    const ent = (id, o) => Object.assign({ id, nom: id.charAt(0).toUpperCase() + id.slice(1), version: '1.0.0', description: 'Un module ' + id, importance: 'optionnel', etat: 'nouveau', niveau: 'officiel', editeur_id: 'cassandra', revoque: '' }, o || {});
    window.__registre = { politique: 'signes', officiel: { url: 'https://exemple.invalid/index.json', officiel: true, emis: 1700000000, expire: 1900000000, signe_par: 'principale', modules: [ent('officiel_un'), ent('chez_acme', { niveau: 'verifie', editeur_id: 'acme' }), ent('dangereux', { revoque: 'lit les fichiers du voisin' })], editeurs: [{ id: 'acme', nom: 'Acme' }], revocations: [], installes_revoques: [{ id: 'vieux', nom: 'Vieux module', version: '0.9.0', raison: 'faille connue' }] }, autre: { url: '', officiel: false, modules: [] } };
    window.CASS.agir = async (c, a) => {
      window.__appels.push([c, a]);
      if (c === 'reglages.lire') return { reglages: [{ cle: 'modules.politique_confiance', valeur: 'signes' }, { cle: 'modules.registre_url', valeur: '' }] };
      if (c === 'modules.registre') return window.__registre;
      if (c === 'modules.installer') return { id: 'sentinelle', version: '0.2.0' };
      if (c === 'modules.abandonner') return {};
      if (c === 'modules.lister') return { modules: [{ id: 'sentinelle', nom: 'Sentinelle du disque', version: '0.2.0', etat: 'inactif', extension: true, description: 'Mesure le disque.' }, { id: 'droits', nom: 'Droits', version: '0.2.0', etat: 'actif', extension: false }] };
      if (c === 'modules.versions') return { id: a.module, sauvegardes: [{ cle: '1__0.1.2__remplace', ts: 1700000000, version: '0.1.2', raison: 'remplace' }], journal: [{ acte: 'installe', ts: 1700000000, version: '0.1.2', par: 'admin' }] };
      if (c === 'modules.retour_arriere') return { id: a.module, version: '0.1.2' };
      return {};
    };
    const vrai = window.fetch;
    window.fetch = async (u, init) => {
      if (String(u).indexOf('/api/televerser/') === 0) { window.__envoyes++; return new Response(JSON.stringify({ statut: 'faite', resultat: window.__exam }), { status: 200 }); }
      return vrai(u, init);
    };
    const hote = document.createElement('div'); hote.id = 'as-essai'; document.body.prepend(hote);
    window.CASS.pageAppStore(hote);
  });
  const as = page.locator('#as-essai .as');
  await expect(as).toContainText('paquets signés seulement');
  await expect(as.locator('.onglets button')).toHaveText(['Déposer une archive', 'Registre', 'Installés']);

  // on dépose une archive : examen, rien n'est installé
  await page.setInputFiles('#as-fichier', { name: 'sentinelle.cmod', mimeType: 'application/gzip', buffer: Buffer.from([31, 139, 8, 0]) });
  await expect(as.locator('.exam h2')).toHaveText('Sentinelle du disque');
  await expect(as.locator('.exam')).toContainText('Mise à jour');
  await expect(as.locator('.exam')).toContainText('Éditeur vérifié · atek');
  await expect(as.locator('.exam')).toContainText('api.exemple.org');
  await expect(as.locator('.exam')).toContainText('Cette version demande de PLUS');          // ce qui est demandé en plus est dit à part
  expect(await page.evaluate(() => window.__appels.some((a) => a[0] === 'modules.installer'))).toBe(false);

  // sans la case cochée, le bouton reste éteint ; coché, il envoie l'empreinte des permissions montrées
  await expect(as.locator('#as-installer')).toBeDisabled();
  await as.locator('#as-consent').check();
  await expect(as.locator('#as-installer')).toBeEnabled();
  await as.locator('#as-installer').click();
  await expect(as).toContainText('installé');
  await expect(as).toContainText('inactif');
  expect(await page.evaluate(() => window.__appels.filter((a) => a[0] === 'modules.installer').map((a) => a[1]))).toEqual([{ jeton: 'a'.repeat(24), consentement: 'abcdef0123456789' }]);

  // une archive refusée ne propose ni consentement ni installation
  await as.locator('[data-a="autre"]').click();
  await page.evaluate(() => { window.__exam = Object.assign({}, window.__exam, { autorise: false, signe: false, editeur: null, niveau: '', raisons: ['paquet non signé par une clé de confiance'], permissions_elargies: [], statut: 'nouveau' }); });
  await page.setInputFiles('#as-fichier', { name: 'x.cmod', mimeType: 'application/gzip', buffer: Buffer.from([31, 139, 8, 0]) });
  await expect(as.locator('.exam')).toContainText('Refusée');
  await expect(as.locator('#as-consent')).toHaveCount(0);
  await expect(as.locator('#as-installer')).toBeDisabled();
  await as.locator('[data-a="abandonner"]').click();
  await expect(as.locator('#as-depot')).toBeVisible();

  // un fichier qui n'est pas un .cmod ne part même pas
  const avant = await page.evaluate(() => window.__envoyes);
  await page.setInputFiles('#as-fichier', { name: 'notes.txt', mimeType: 'text/plain', buffer: Buffer.from('x') });
  expect(await page.evaluate(() => window.__envoyes)).toBe(avant);

  // les installés : versions et retour arrière
  await as.locator('[data-o="installes"]').click();
  await expect(as.locator('.ligne')).toContainText('Sentinelle du disque');
  await as.locator('[data-a="versions"]').click();
  await expect(as.locator('.hist')).toContainText('v0.1.2');
  await as.locator('[data-a="remettre"]').click();
  await expect.poll(() => page.evaluate(() => window.__appels.filter((a) => a[0] === 'modules.retour_arriere').map((a) => a[1]))).toEqual([{ module: 'sentinelle', cle: '1__0.1.2__remplace' }]);

  // le registre officiel est toujours là, signé, avec les niveaux de confiance ; une version révoquée ne s'examine pas
  await as.locator('[data-o="registre"]').click();
  await expect(as).toContainText('Registre officiel de Cassandra');
  await expect(as).toContainText('index signé');
  await expect(as.locator('.mod').filter({ hasText: 'Officiel_un' })).toContainText('Officiel');
  await expect(as.locator('.mod').filter({ hasText: 'Chez_acme' })).toContainText('Éditeur vérifié · acme');
  const dangereux = as.locator('.mod').filter({ hasText: 'Dangereux' });
  await expect(dangereux).toContainText('Révoqué');
  await expect(dangereux.locator('[data-a="telecharger"]')).toBeDisabled();
  await expect(as).toContainText('Des modules installés ont été révoqués');                  // ce qui est déjà installé et révoqué est signalé
  await expect(as).toContainText('Autre registre (non officiel)');
  await expect(as).not.toContainText('Aucun registre configuré');

  // un registre officiel muet ou invalide : on le dit, rien ne s'installe
  await page.evaluate(() => { window.__registre = { politique: 'signes', officiel: { url: 'u', officiel: true, erreur: 'la signature de l’index ne correspond à aucune clé racine', modules: [], editeurs: [], revocations: [], installes_revoques: [] }, autre: { url: '', modules: [] } }; });
  await as.locator('[data-a="relire-reg"]').count();
  await as.locator('[data-o="depot"]').click();
  await as.locator('[data-o="registre"]').click();
  await as.locator('[data-o="installes"]').click();
});
