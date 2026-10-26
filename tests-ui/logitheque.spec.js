// La Logithèque : montée sur des réponses simulées pour vérifier ce qu'elle montre (récit avec le pourquoi, niveau d'autonomie, Pause),
// ce qu'elle ENVOIE (Défaire, verrou, niveau, demande à Cassandra) et ce qu'elle cache par défaut (les interrupteurs : Mode avancé).
const { test, expect } = require('@playwright/test');

test("Logithèque : Cassandra d'abord, le récit se défait, le verrou et la pause partent, les interrupteurs attendent le Mode avancé", async ({ page }) => {
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.evaluate(async () => {
    window.__appels = []; window.__demandes = [];
    const maintenant = Date.now() / 1000;
    window.__etat = {
      gel: false, autonomie: 'reine',
      modules: [
        { id: 'droits', nom: 'Droits', version: '0.2.0', famille: 'securite', etat: 'actif', importance: 'vital', confiance: 'interne', description: 'Comptes et rôles.', sans: 'Plus personne ne se connecte.', requiert: [], requis_par: ['courrier'], verrou: false },
        { id: 'courrier', nom: 'Courrier', version: '1.3.2', famille: 'communication', etat: 'actif', importance: 'important', confiance: 'interne', description: 'Boîtes et envoi.', sans: 'Plus de courrier.', requiert: ['droits'], requis_par: [], verrou: true },
        { id: 'sentinelle', nom: 'Sentinelle du disque', version: '0.1.2', famille: 'supervision', etat: 'inactif', importance: 'optionnel', confiance: 'local', description: 'Mesure le disque.', sans: 'Plus de mesure.', requiert: ['droits'], requis_par: [], verrou: false },
      ],
      sections: [{ id: 'securite', libelle: 'Sécurité et accès', icone: 'lock', ordre: 20 }, { id: 'communication', libelle: 'Courrier et messagerie', icone: 'mail', ordre: 50 }, { id: 'supervision', libelle: 'Surveillance et journaux', icone: 'eye', ordre: 110 }],
      actes: [
        { ts: maintenant - 700, par: 'cassandra', geste: 'desactive', module: 'sentinelle', version: '', detail: '', pourquoi: 'Il échouait (mesure) : mis en pause, ses données restent.', defaire: { capacite: 'modules.activer', args: { module: 'sentinelle' } } },
        { ts: maintenant - 90000, par: 'drisse@exemple.test', geste: 'active', module: 'courrier', version: '', detail: '', pourquoi: "Geste de l'utilisateur.", defaire: { capacite: 'modules.desactiver', args: { module: 'courrier' } } },
      ],
    };
    window.CASS.disposition = { demander: (t) => window.__demandes.push(t) };
    window.CASS.pageAppStore = (z) => { z.innerHTML = '<div id="appstore-monte">App Store</div>'; };
    window.CASS.agir = async (c, a) => {
      window.__appels.push([c, a]);
      const e = window.__etat;
      if (c === 'modules.lister') return { modules: e.modules, sections: e.sections, autonomie: e.autonomie, gere: true };
      if (c === 'modules.activite') return { autonomie: e.autonomie, fenetre: 'nuit', gel: e.gel, verrous: e.modules.filter((m) => m.verrou).map((m) => m.id), actes: e.actes };
      if (c === 'modules.entretien') return { niveau: e.autonomie, actions: [], constats: ['Billetterie 0.5.0 : elle demande + réseau chez un éditeur tiers, je ne la prends pas seule.'], erreurs: [] };
      if (c === 'urgence.geler') { e.gel = !!a.actif; return {}; }
      if (c === 'reglages.regler') { e.autonomie = a.valeur; return {}; }
      if (c === 'modules.verrouiller') { e.modules.find((m) => m.id === a.module).verrou = a.verrou; return {}; }
      return {};
    };
    const hote = document.createElement('div'); hote.id = 'lg-essai'; hote.style.cssText = 'position:relative;z-index:1;background:var(--bg,#fff);padding:12px'; document.body.prepend(hote);
    window.__hote = hote;
    await window.CASS.pageLogitheque(hote, 'vue', { aller: (s) => window.CASS.pageLogitheque(hote, s, {}) });
  });
  const lg = page.locator('#lg-essai .lg');

  // la Vue d'ensemble : Cassandra d'abord, le récit dit qui, quoi, POURQUOI
  await expect(lg).toContainText('Tout va bien');
  await expect(lg).toContainText('Ce que Cassandra a fait');
  await expect(lg).toContainText('Cassandra a désactivé Sentinelle du disque');
  await expect(lg).toContainText('Il échouait (mesure) : mis en pause');
  await expect(lg).toContainText("Geste de l'utilisateur.");
  await expect(lg).toContainText('Ce que je n’ai pas fait seule, et pourquoi');
  await expect(lg).toContainText('Billetterie 0.5.0');                                    // ce qu'elle a laissé de côté, avec la raison

  // Défaire : le geste inverse part pour CET acte
  await lg.locator('[data-a="defaire"]').first().click();
  await expect.poll(() => page.evaluate(() => window.__appels.filter((a) => a[0] === 'modules.annuler').map((a) => a[1]))).toEqual([{ module: 'sentinelle', geste: 'desactive' }]);

  // le niveau d'autonomie se choisit, et part comme un réglage
  await lg.locator('[data-a="autonomie"][data-k="entretien"]').click();
  await expect.poll(() => page.evaluate(() => window.__appels.filter((a) => a[0] === 'reglages.regler').map((a) => a[1]))).toEqual([{ cle: 'modules.autonomie', valeur: 'entretien' }]);
  await expect(lg.locator('[data-a="autonomie"][data-k="entretien"]')).toHaveClass(/on/);

  // Pause : le frein « gel » se pose, puis se lève
  await lg.locator('[data-a="gel"]').click();
  await expect(lg).toContainText('Cassandra est en pause');
  await lg.locator('[data-a="gel"]').click();
  await expect(lg).toContainText('Tout va bien');
  expect(await page.evaluate(() => window.__appels.filter((a) => a[0] === 'urgence.geler').map((a) => a[1]))).toEqual([{ actif: true }, { actif: false }]);

  // demander à Cassandra : par la zone, et par une suggestion
  await lg.locator('#lg-dem').fill('installe le pare-feu CrowdSec');
  await lg.locator('[data-a="demande"]').click();
  await lg.locator('[data-sug]').first().click();
  expect(await page.evaluate(() => window.__demandes)).toEqual(['installe le pare-feu CrowdSec', 'Qu’est-ce qui ne va pas ?']);

  // Installés : rangés par section, les interrupteurs sont cachés
  await page.evaluate(() => window.CASS.pageLogitheque(window.__hote, 'inst', { aller: () => {} }));
  await expect(lg.locator('.rub-t h3')).toHaveText(['Sécurité et accès', 'Courrier et messagerie', 'Surveillance et journaux']);
  await expect(lg.locator('.sw')).toHaveCount(0);
  await expect(lg.locator('.mod').filter({ hasText: 'Courrier' })).toContainText('verrouillé');
  await lg.locator('#lg-q').fill('disque');
  await expect(lg.locator('.mod')).toHaveCount(1);
  await lg.locator('[data-a="reset"]').click();
  await lg.locator('[data-etat="verrou"]').click();
  await expect(lg.locator('.mod')).toHaveCount(1);
  await lg.locator('[data-etat="tous"]').click();
  await lg.locator('[data-a="rep"][data-id="securite"]').click();                       // une section se replie
  await expect(lg.locator('.mod').filter({ hasText: 'Droits' })).toHaveCount(0);
  await lg.locator('[data-a="rep"][data-id="securite"]').click();

  // le tiroir d'un module : sans Mode avancé on DEMANDE à Cassandra ; le verrou part comme un geste
  await lg.locator('.mod').filter({ hasText: 'Sentinelle' }).click();
  const t = page.locator('#lg-tiroir');
  await expect(t).toContainText('Sans lui');
  await expect(t).toContainText('Plus de mesure.');
  await expect(t.locator('[data-t="bascule"]')).toHaveCount(0);
  await t.locator('[data-t="verrou"]').click();
  await expect.poll(() => page.evaluate(() => window.__appels.filter((a) => a[0] === 'modules.verrouiller').map((a) => a[1]))).toEqual([{ module: 'sentinelle', verrou: true }]);
  await t.locator('[data-t="demander"]').click();
  expect((await page.evaluate(() => window.__demandes)).pop()).toBe('Active Sentinelle du disque');
  await expect(page.locator('#lg-tiroir')).toHaveCount(0);

  // Mode avancé : les interrupteurs apparaissent, avec un bandeau
  await lg.locator('[data-a="avance"]').first().click();
  await expect(lg).toContainText('Mode avancé.');
  await expect(lg.locator('.sw')).toHaveCount(3);
  await expect(lg.locator('.sw[data-id="droits"]')).toBeDisabled();                     // un module vital ne se désactive pas
  await lg.locator('.sw[data-id="sentinelle"]').click();
  await expect.poll(() => page.evaluate(() => window.__appels.filter((a) => a[0] === 'modules.activer').map((a) => a[1]))).toEqual([{ module: 'sentinelle' }]);
  await lg.locator('[data-a="avance"]').first().click();                                  // on en sort
  await expect(lg.locator('.sw')).toHaveCount(0);

  // la Boutique monte l'App Store existant ; une section pas encore portée renvoie vers ce qui existe
  await page.evaluate(() => window.CASS.pageLogitheque(window.__hote, 'shop', { aller: () => {} }));
  await expect(lg.locator('#appstore-monte')).toBeVisible();
  await page.evaluate(() => window.CASS.pageLogitheque(window.__hote, 'sec', { aller: () => {} }));
  await expect(lg).toContainText('Cette section arrive');
});
