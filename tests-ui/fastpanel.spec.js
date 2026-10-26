// L'écran Hébergement : vue d'ensemble et audit, sites et renouvellement, certificats et sonde, bases, sauvegardes, courriel, services.
const { test, expect } = require('@playwright/test');

test("Hébergement : audit, sites, certificats, bases, sauvegardes, services", async ({ page }) => {
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.evaluate(async () => {
    window.__appels = [];
    const sites = [{ domaine: 'exemple.fr', proprietaire: 'bea', statut: 'on', ssl: { etat: 'proche', jours: 9, echeance: '2026-11-04' }, php: '8.1', gestionnaire: 'php_fpm', fichiers_mo: 120 }, { domaine: 'autre.org', proprietaire: 'bea', statut: 'on', ssl: { etat: 'actif', jours: 70, echeance: '2027-01-04' }, php: '8.3', gestionnaire: 'php_fpm' }];
    window.CASS.agir = async (c, a) => {
      window.__appels.push([c, a]);
      if (c === 'fastpanel.resume') return { etat: 'ok', erreur: '', services: { total: 12, tombes: 1 } };
      if (c === 'fastpanel.audit') return { certificats: { echus: [], proches: [{ domaine: 'exemple.fr', jours: 9, echeance: '2026-11-04' }], sans: [], inconnus: [], actifs: 2, total: 2 }, sauvegardes: { seuil_j: 7, sans: ['autre.org'], perimees: [], total: 2 }, php: { fin_de_support: [{ domaine: 'exemple.fr', php: '8.1', fin: '2025-12-31' }], bientot: [], version_non_lue: [] } };
      if (c === 'fastpanel.sites') return sites;
      if (c === 'fastpanel.certificats') return { echus: [], proches: [{ domaine: 'exemple.fr', jours: 9, echeance: '2026-11-04' }], sans: [], inconnus: [], actifs: 2, total: 2 };
      if (c === 'fastpanel.ssl_sonder') return { domaine: a.domaine, ok: true, emetteur: 'Let’s Encrypt', echeance: 'Jan 4 2027', jours: 70, noms: [a.domaine] };
      if (c === 'fastpanel.bases') return [{ id: 1, nom: 'wp_bea', moteur: 'mysql', taille_mo: 12.5, proprietaire: 'bea', site: 'exemple.fr', derniere_copie: '2026-10-25 04:00:00' }];
      if (c === 'fastpanel.sauvegardes') return [{ plan: 'nuit', etat: 'reussie', partielle: false, envoye_mo: 300, debut: '2026-10-25 04:00:00', duree_min: 3, compte: 'bea', destination: 'local (local)' }];
      if (c === 'fastpanel.plans') return [{ name: 'nuit', keep: 7 }];
      if (c === 'fastpanel.stockages') return [{ name: 'local', type: 'local', path: '/backup' }];
      if (c === 'fastpanel.mail') return [{ adresse: 'bea@exemple.fr', domaine: 'exemple.fr', quota_mo: 1000, utilise_mo: 20, statut: 'active' }];
      if (c === 'fastpanel.ftp') return [];
      if (c === 'fastpanel.services') return [{ id: '1', nom: 'nginx', etat: 'running', actif: true, alias: [] }];
      return {};
    };
    const hote = document.createElement('div'); hote.id = 'fp-essai'; hote.style.cssText = 'position:relative;z-index:1;background:var(--bg,#fff);padding:12px'; document.body.prepend(hote);
    await window.CASS.sceneSurMesure.fastpanel(hote, { ecran: 'fastpanel:vue_hebergement' });
  });
  const k = page.locator('#fp-essai .kit');
  const appels = (c) => page.evaluate((c) => window.__appels.filter((a) => a[0] === c).map((a) => a[1]), c);
  await expect(k.locator('.onglets button').first()).toHaveText('Vue d’ensemble');
  await expect(k).toContainText('Le panneau répond');
  await expect(k).toContainText('Aucune sauvegarde réussie pour autre.org');
  await expect(k).toContainText('PHP 8.1 sans correctifs : exemple.fr');

  await k.locator('[data-s="sites"]').click();
  await expect(k).toContainText('proche · 9 j');
  await k.locator('[data-a="renouveler"][data-k="exemple.fr"]').click();
  await page.locator('.kit-m [data-c="oui"]').click();
  await expect.poll(async () => (await appels('fastpanel.ssl_renouveler')).pop()).toEqual({ domaine: 'exemple.fr' });

  await k.locator('[data-s="certificats"]').click();
  await k.locator('#fp-dom').fill('autre.org'); await k.locator('[data-a="sonder"]').click();
  await expect(k).toContainText('Émis par Let’s Encrypt');

  await k.locator('[data-s="bases"]').click();
  await expect(k).toContainText('wp_bea');
  await k.locator('#fp-base').fill('neuve'); await k.locator('[data-a="base"]').click();
  await expect.poll(async () => (await appels('fastpanel.base_creer')).pop()).toEqual({ nom: 'neuve' });

  await k.locator('[data-s="sauvegardes"]').click();
  await expect(k).toContainText('réussie');
  await expect(k).toContainText('/backup');

  await k.locator('[data-s="courriel"]').click();
  await expect(k).toContainText('bea@exemple.fr');

  await k.locator('[data-s="services"]').click();
  await k.locator('[data-a="svc"][data-c="relancer"]').click();
  await page.locator('.kit-m [data-c="oui"]').click();
  await expect.poll(async () => (await appels('fastpanel.service_relancer')).pop()).toEqual({ service: 'nginx' });
});
