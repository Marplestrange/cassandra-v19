// La Logithèque, ce qui touche à la sûreté des gestes directs et à ceux qui n'ont pas d'administration :
// l'impact se dit AVANT (Mode avancé), un tracé d'icône piégé n'entre jamais dans la page, l'accueil d'une instance neuve, et « Mes applications » d'un compte ordinaire.
const { test, expect } = require('@playwright/test');

async function ouvrir(page, gere, modules) {
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.evaluate(([gere, source]) => {
    const modules = eval('(' + source + ')');                           // la fabrique de catalogue voyage en texte : une fonction ne traverse pas page.evaluate
    try { localStorage.removeItem('lg.accueil'); localStorage.removeItem('lg.avance'); } catch (e) {}
    window.__appels = []; window.__demandes = [];
    const mod = (id, o) => Object.assign({ id, nom: id[0].toUpperCase() + id.slice(1), description: 'Module ' + id, version: '1.0', famille: 'socle', etat: 'actif', importance: 'optionnel', confiance: 'interne', sans: 'Sans ' + id + ' : rien de grave.', requiert: [], requis_par: [], verrou: false }, o);
    const cat = modules(mod);
    window.__cat = cat;
    window.CASS.disposition = { demander: (t) => window.__demandes.push(t), rafraichir: async () => {} };
    window.CASS.agir = async (c, a) => {
      window.__appels.push([c, a]);
      if (c === 'modules.lister') return { modules: cat, sections: [{ id: 'socle', libelle: 'Fondations', ordre: 10 }, { id: 'reseau', libelle: 'Réseau', ordre: 30 }], autonomie: 'reine', gere };
      if (c === 'modules.activite') return { autonomie: 'reine', fenetre: 'nuit', gel: false, verrous: [], actes: [] };
      if (c === 'modules.entretien') return { actions: [], constats: [], erreurs: [] };
      if (c === 'modules.activer') { cat.find((m) => m.id === a.module).etat = 'actif'; return {}; }
      if (c === 'modules.desactiver') { cat.find((m) => m.id === a.module).etat = 'inactif'; return {}; }
      if (c === 'menus.mes_entrees') return { entrees: window.__entrees || [] };
      return {};
    };
    const hote = document.createElement('div'); hote.id = 'lg-essai'; hote.style.cssText = 'position:relative;z-index:1;background:var(--bg,#fff);padding:12px'; document.body.prepend(hote);
    window.__hote = hote;
  }, [gere, modules.toString()]);
}
const catalogue = (mod) => [
  mod('droits', { importance: 'vital', requis_par: ['dns'] }),
  mod('dns', { importance: 'important', requiert: ['droits'], requis_par: ['certificats'], famille: 'reseau' }),
  mod('certificats', { etat: 'inactif', requiert: ['dns'], famille: 'reseau', importance: 'important' }),
  mod('billetterie', { etat: 'a_installer', famille: 'reseau' }),
];

test("instance de développement : une note, des interrupteurs grisés", async ({ page }) => {
  await ouvrir(page, false, catalogue);
  await page.evaluate(async () => { localStorage.setItem('lg.avance', '1'); await window.CASS.pageLogitheque(window.__hote, 'inst', {}); });
  const lg = page.locator('#lg-essai .lg');
  await expect(lg).toContainText('Instance de développement');
  await expect(lg.locator('.sw:not([disabled])')).toHaveCount(0);
});

test("Mode avancé : l'impact se dit avant, un module vital ou à installer ne se bascule pas, l'annulation n'envoie rien", async ({ page }) => {
  await ouvrir(page, true, catalogue);
  await page.evaluate(async () => { localStorage.setItem('lg.avance', '1'); await window.CASS.pageLogitheque(window.__hote, 'inst', {}); });
  const lg = page.locator('#lg-essai .lg');
  await expect(lg.locator('.sw[data-id="droits"]')).toBeDisabled();                         // un vital ne se bascule jamais
  await expect(lg.locator('.sw[data-id="billetterie"]')).toBeDisabled();                    // à installer d'abord : pas d'interrupteur

  // désactiver DNS arrêterait Certificats (inactif : rien) ; activons d'abord Certificats pour avoir un dépendant ACTIF
  await lg.locator('.sw[data-id="certificats"]').click();                                   // active Certificats : DNS est déjà actif, rien à tirer
  await expect.poll(() => page.evaluate(() => window.__appels.filter((a) => a[0] === 'modules.activer').map((a) => a[1]))).toEqual([{ module: 'certificats', avec_dependances: true }]);
  await lg.locator('.sw[data-id="dns"]').click();                                           // désactive DNS : Certificats en dépend et est actif → on le dit
  const m = page.locator('.lgm');
  await expect(m).toContainText('Désactiver Dns');
  await expect(m).toContainText('Certificats');
  await m.locator('[data-c="non"]').click();
  expect(await page.evaluate(() => window.__appels.filter((a) => a[0] === 'modules.desactiver').length)).toBe(0);     // refusé : rien n'est parti
  await lg.locator('.sw[data-id="dns"]').click();
  await page.locator('.lgm [data-c="oui"]').click();
  await expect.poll(() => page.evaluate(() => window.__appels.filter((a) => a[0] === 'modules.desactiver').map((a) => a[1]))).toEqual([{ module: 'dns', cascade: true }]);
});

test("activer un module dit ce qu'il tire avec lui ; rien ne part avant l'accord", async ({ page }) => {
  await ouvrir(page, true, (mod) => [mod('droits', { importance: 'vital' }), mod('dns', { etat: 'inactif', requiert: ['droits'] }), mod('certificats', { etat: 'inactif', requiert: ['dns'] })]);
  await page.evaluate(async () => { localStorage.setItem('lg.avance', '1'); await window.CASS.pageLogitheque(window.__hote, 'inst', {}); });
  const lg = page.locator('#lg-essai .lg');
  await lg.locator('.sw[data-id="certificats"]').click();
  await expect(page.locator('.lgm')).toContainText('Activer Certificats');
  await expect(page.locator('.lgm')).toContainText('Dns');                                  // la dépendance qui s'activera aussi
  expect(await page.evaluate(() => window.__appels.filter((a) => a[0] === 'modules.activer').length)).toBe(0);
  await page.locator('.lgm [data-c="oui"]').click();
  await expect.poll(() => page.evaluate(() => window.__appels.filter((a) => a[0] === 'modules.activer').map((a) => a[1]))).toEqual([{ module: 'certificats', avec_dependances: true }]);
});

test("une icône apportée par un module est un tracé validé : celle d'un éditeur malveillant n'entre jamais dans la page", async ({ page }) => {
  await ouvrir(page, true, (mod) => [mod('dns', { icone_trace: 'M12 3l8 4v5c0 4.4-3.1 7.6-8 9z' }), mod('piege', { icone_trace: 'M0 0"/><script>window.__piege = 1</script><path d="M1 1' })]);
  await page.evaluate(() => window.CASS.pageLogitheque(window.__hote, 'inst', {}));
  const lg = page.locator('#lg-essai .lg');
  await expect(lg.locator('.mod').filter({ hasText: 'Dns' }).locator('.ico path')).toHaveAttribute('d', 'M12 3l8 4v5c0 4.4-3.1 7.6-8 9z');
  const ds = await lg.locator('.mod').filter({ hasText: 'Piege' }).locator('.ico path').evaluateAll((n) => n.map((x) => x.getAttribute('d')));
  expect(ds.some((d) => /script/.test(d))).toBe(false);                                     // le piège est refusé : l'icône générique reste
  expect(await page.evaluate(() => window.__piege)).toBeUndefined();
  expect(await lg.locator('script').count()).toBe(0);
});

test("instance neuve : un accueil, les ensembles se cumulent, « Tout installer », la mise en place active ce qu'il faut", async ({ page }) => {
  await ouvrir(page, true, (mod) => [mod('droits', { importance: 'vital' }), mod('sites', { etat: 'inactif', requiert: ['dns'] }), mod('dns', { etat: 'inactif', requiert: ['droits'] }), mod('sauvegardes', { etat: 'inactif', requiert: ['droits'] }),
    mod('courrier', { etat: 'inactif', requiert: ['droits'] }), mod('notes', { etat: 'inactif', requiert: ['droits'] })]);
  await page.evaluate(() => window.CASS.pageLogitheque(window.__hote, 'vue', {}));
  const lg = page.locator('#lg-essai .lg');
  await expect(lg).toContainText('Bienvenue');
  await expect(lg).toContainText('Déjà en place');
  await expect(lg.locator('[data-a="ensemble"]')).toHaveCount(3);                          // Hébergeur, Bureau, Tout installer
  await lg.locator('[data-a="ensemble"][data-id="bureau"]').click();
  await lg.locator('[data-a="ensemble"][data-id="hebergeur"]').click();
  await expect(lg).toContainText('2 ensembles choisis');
  await expect(lg.locator('[data-a="ensemble"][data-id="tout"]')).toHaveClass(/on/);
  await lg.locator('[data-a="ensemble"][data-id="tout"]').click();                         // « Tout » décoche tout
  await expect(lg).toContainText('Coche un ou plusieurs ensembles');
  await lg.locator('[data-a="ensemble"][data-id="tout"]').click();
  await lg.locator('[data-a="mise-en-place"]').click();
  await expect.poll(() => page.evaluate(() => window.__appels.filter((a) => a[0] === 'modules.activer').map((a) => a[1].module).sort())).toEqual(['courrier', 'dns', 'notes', 'sauvegardes', 'sites']);
  await expect(lg).not.toContainText('Bienvenue');                                         // l'accueil ne revient pas
});

test("instance neuve : « Plus tard » ferme l'accueil sans rien faire", async ({ page }) => {
  await ouvrir(page, true, (mod) => [mod('droits', { importance: 'vital' }), mod('courrier', { etat: 'inactif', requiert: ['droits'] })]);
  await page.evaluate(() => window.CASS.pageLogitheque(window.__hote, 'vue', {}));
  const lg = page.locator('#lg-essai .lg');
  await lg.locator('[data-a="plus-tard"]').click();
  await expect(lg).toContainText('Tout va bien');
  expect(await page.evaluate(() => window.__appels.filter((a) => a[0] === 'modules.activer').length)).toBe(0);
});

test("Mes applications : un compte ordinaire voit ses applications, retire et remet, ouvre, demande", async ({ page }) => {
  await ouvrir(page, true, catalogue);
  await page.evaluate(async () => {
    window.CASS.moi = { compte: 'bea@x.fr', admin: false };
    window.__entrees = [{ id: 'courrier:c1', libelle: 'Courrier', ecran: 'courrier:vue_boite', famille: 'communication', masque: false }, { id: 'notes:n1', libelle: 'Notes', ecran: 'notes:vue_notes', famille: 'gestion', masque: true }];
    window.__ecrans = []; window.CASS.ouvrirEcran = (e, l) => window.__ecrans.push([e, l]);
    await window.CASS.pageMesApplications(window.__hote, { rafraichir: () => window.__appels.push(['rafraichir']), demander: (t) => window.__demandes.push(t) });
  });
  const lg = page.locator('#lg-essai .lg');
  await expect(lg.locator('.mod')).toHaveCount(2);
  await expect(lg.locator('.mod').filter({ hasText: 'Courrier' }).locator('.sw')).toHaveClass(/on/);
  await expect(lg.locator('.mod').filter({ hasText: 'Notes' }).locator('.sw')).not.toHaveClass(/on/);
  await expect(lg).not.toContainText('Instance de développement');                       // rien de la gestion
  await lg.locator('.sw[data-menu="courrier:c1"]').click();                                // retire Courrier de SON menu : pour son compte, jamais pour tous
  await expect.poll(() => page.evaluate(() => window.__appels.filter((a) => a[0] === 'menus.personnaliser_entree').map((a) => a[1]))).toEqual([{ entree: 'courrier:c1', masque: true, compte: 'bea@x.fr' }]);
  await lg.locator('[data-ouvrir="notes:n1"]').click();
  expect(await page.evaluate(() => window.__ecrans)).toEqual([['notes:vue_notes', 'Notes']]);
  await lg.locator('#lg-dem').fill('Je voudrais gérer mes factures');
  await lg.locator('[data-a="demande"]').click();
  expect(await page.evaluate(() => window.__demandes)).toEqual(['Je voudrais gérer mes factures']);
});
