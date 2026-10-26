// L'écran Sites : vigilances et liste, déclarer, fiche (courbe, lien, accord), disponibilité, demandes, journal.
const { test, expect } = require('@playwright/test');

test("Sites : liste, déclarer, fiche, disponibilité, demandes, journal", async ({ page }) => {
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.evaluate(async () => {
    window.__appels = [];
    const base = Math.floor(Date.now() / 1000) - 7200;
    let sites = [
      { domaine: 'exemple.fr', source: 'panneau', origine: 'panneau', up: true, code: 200, ms: 180, ssl_jours: 40, php: '8.3', dispo30: { disponibilite: 99.9 }, comptes: ['root'], demande: null },
      { domaine: 'perso.net', source: 'declare', origine: 'declare', up: false, code: 502, ms: null, ssl_jours: 5, php: '', dispo30: null, comptes: ['root'], demande: null },
    ];
    const vue = () => ({ sites, vigilances: [{ niveau: 'panne', site: 'perso.net', titre: 'perso.net ne répond pas', detail: 'code 502', geste: null }, { niveau: 'info', site: 'perso.net', titre: 'perso.net : hors panneau', detail: 'suivi à la main', geste: 'demander' }], portee: { admin: true, compte: 'root', sites: sites.length, panneau: 1, declares: sites.length - 1, panneau_lu: true } });
    window.CASS.agir = async (c, a) => {
      window.__appels.push([c, a]);
      if (c === 'sites.vue') return vue();
      if (c === 'sites.fiche') return { domaine: a.domaine, site: sites.find((s) => s.domaine === a.domaine), mien: true, hors_panneau: true, liens: [{ genre: 'project', ref: 'p1', note: '' }], journal: [{ ts: '2026-10-26 20:00:00', verbe: 'declare', detail: '' }], accord: null, gestes: { retirer: true, attribuer: true, transferer: false, demander: false, accorder: false } };
      if (c === 'sites.historique') return { domaine: a.domaine, disponibilite: 80, reponse_moy_ms: 200, points: [{ ts: base, up: true, ms: 150 }, { ts: base + 3600, up: true, ms: 250 }], evenements: [] };
      if (c === 'sites.disponibilite') return { jours: a.jours, sites: [{ domaine: 'exemple.fr', disponibilite: 99.9, pannes: 0, indisponible: '', reponse_moy_ms: 180 }], plus_suivis: [] };
      if (c === 'sites.demandes') return { demandes: [{ id: 7, domaine: 'perso.net', compte: 'bea', message: 'svp', statut: 'ouverte', reponse: '', ts: base }] };
      if (c === 'sites.journal') return { lignes: [{ ts: '2026-10-26 20:00:00', verbe: 'panne', domaine: 'perso.net', detail: 'code 502', source: 'veille' }] };
      if (c === 'sites.declarer') { sites = sites.concat([{ domaine: a.domaine, source: 'declare', origine: 'declare', up: null, ssl_jours: null, dispo30: null, comptes: ['root'], demande: null }]); return {}; }
      return {};
    };
    const hote = document.createElement('div'); hote.id = 'si-essai'; hote.style.cssText = 'position:relative;z-index:1;background:var(--bg,#fff);padding:12px'; document.body.prepend(hote);
    await window.CASS.sceneSurMesure.sites(hote, { ecran: 'sites:vue_sites' });
  });
  const k = page.locator('#si-essai .kit');
  const appels = (c) => page.evaluate((c) => window.__appels.filter((a) => a[0] === c).map((a) => a[1]), c);
  await expect(k.locator('.onglets button')).toHaveText(['Mes sites', 'Disponibilité', 'Demandes', 'Journal']);
  await expect(k).toContainText('perso.net ne répond pas');
  await expect(k).toContainText('certificat 5 j');

  await k.locator('#st-dom').fill('neuf.org'); await k.locator('[data-a="declarer"]').click();
  await expect(k).toContainText('neuf.org');

  await k.locator('[data-a="fiche"][data-k="exemple.fr"]').first().click();
  await expect(k.locator('svg.courbe')).toBeVisible();
  await k.locator('#st-ref').fill('p9'); await k.locator('[data-a="lier"]').click();
  await expect.poll(async () => (await appels('sites.lier')).pop()).toEqual({ domaine: 'exemple.fr', genre: 'project', ref: 'p9' });
  await k.locator('[data-a="retour"]').click();

  await k.locator('[data-s="dispo"]').click();
  await expect(k).toContainText('99.9 %');
  await k.locator('[data-s="demandes"]').click();
  await k.locator('[data-a="repondre"][data-d="fait"]').click();
  await expect.poll(async () => (await appels('sites.repondre_demande')).pop()).toEqual({ id: 7, decision: 'fait' });
  await k.locator('[data-s="journal"]').click();
  await expect(k).toContainText('code 502');
});
