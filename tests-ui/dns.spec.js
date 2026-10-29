// L'écran « Zones DNS » : on le monte sur des données simulées (le serveur d'essai n'a ni domaine suivi ni réseau) et on vérifie ce qu'il montre et ce qu'il demande.
const { test, expect } = require('@playwright/test');

test('Zones DNS : zones, dérives, courrier, gestes confirmés', async ({ page }) => {
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.evaluate(async () => {
    window.__appels = [];
    const ts = (s) => Date.now() / 1000 - s, jour = (n) => new Date(Date.now() + n * 86400000).toISOString().slice(0, 10);
    const ref = { 'exemple.org|A': ['203.0.113.10'], 'exemple.org|MX': ['10 mail.exemple.org'], 'exemple.org|TXT': ['v=spf1 -all'], '_dmarc.exemple.org|TXT': ['v=DMARC1; p=none'], 'app.exemple.org|A': ['203.0.113.11'] };
    window.CASS.agir = async (cap, a) => {
      window.__appels.push([cap, a]);
      if (cap === 'dns.etat') return { suivis: ['exemple.org'], jeton: true, expire_jours: 45, ip_publique: '203.0.113.10', ip_reference: '203.0.113.11', zones: [
        { domaine: 'exemple.org', releve: ts(7200), serveur: 'ns1.exemple.org', expiration: jour(200), version: 3, derives: [{ cle: 'app.exemple.org|A', nom: 'app.exemple.org', type: 'A', attendu: ['203.0.113.11'], observe: ['203.0.113.11'], ip_derivee: true }] },
        { domaine: 'vieux.net', releve: ts(900), serveur: 'ns', expiration: jour(9), version: 1, derives: [] },
        { domaine: 'neuf.io', releve: null, serveur: '', expiration: null, version: 0, derives: [] }] };
      if (cap === 'dns.reference') return a.historique ? { versions: [{ id: 3, ts: ts(7200), auteur: 'admin', annulee: 0 }] } : { domaine: a.domaine, version: 3, contenu: a.domaine === 'exemple.org' ? ref : {} };
      if (cap === 'reglages.regler' || cap === 'reglages.regler_secret') return { ok: true };
      if (cap === 'reglages.lire') return { reglages: [{ cle: 'dns.domaines', valeur: 'exemple.org', pose: true }, { cle: 'dns.jeton_cloudflare', pose: true }, { cle: 'dns.expire_jours', valeur: 45 }] };
      if (cap === 'dns.relever_zone') return { domaine: a.domaine, serveur: 'ns1', enregistrements: Object.assign({}, ref, { 'app.exemple.org|A': ['203.0.113.10'] }), non_lus: [] };
      return {};
    };
    const corps = document.createElement('div'); corps.id = 'dz-essai'; document.body.prepend(corps);
    await window.CASS.sceneSurMesure.dns(corps, {});
  });
  const dz = page.locator('#dz-essai .dz');
  await expect(dz.locator('.zone')).toHaveCount(3);
  await expect(dz.locator('.hero')).toContainText('203.0.113.10');
  await expect(dz.locator('.hero')).toContainText('a changé');
  await expect(dz.locator('.zone').first()).toContainText('exemple.org');               // la zone à corriger passe en tête
  await expect(dz.locator('.zone.on')).toContainText('exemple.org');

  await dz.locator('[data-o="courrier"]').click();                                       // DMARC « none » : un avertissement, pas un faux ✓
  await expect(dz.locator('.verif').filter({ hasText: 'DMARC' })).toContainText('surveillance seule');

  await dz.locator('[data-o="derives"]').click();
  await expect(dz.locator('.drv')).toContainText('ancienne adresse');
  await dz.locator('[data-a="demander-c"]').click();                                     // rien ne part sans confirmation
  expect(await page.evaluate(() => window.__appels.some((a) => a[0] === 'dns.corriger_enregistrement'))).toBe(false);
  await dz.locator('[data-a="corriger"]').click();
  await expect.poll(() => page.evaluate(() => window.__appels.filter((a) => a[0] === 'dns.corriger_enregistrement').map((a) => a[1]))).toEqual([{ nom: 'app.exemple.org', type: 'A', valeur: '203.0.113.10' }]);

  await dz.locator('[data-a="reglages"]').first().click();                              // les réglages vivent dans la page : suivre, retirer, jeton, seuils
  await expect(dz.locator('[data-rg]')).toHaveCount(4);
  await dz.locator('#dz-nv').fill('nouveau.org');
  await dz.locator('[data-a="ajouter"]').click();
  await expect.poll(() => page.evaluate(() => window.__appels.filter((a) => a[0] === 'reglages.regler').map((a) => a[1]))).toContainEqual({ cle: 'dns.domaines', valeur: 'exemple.org,nouveau.org' });
  await dz.locator('[data-a="retirer"][data-d="exemple.org"]').click();
  await expect.poll(() => page.evaluate(() => window.__appels.filter((a) => a[0] === 'reglages.regler').map((a) => a[1].valeur))).toContain('');
  await dz.locator('#dz-jeton').fill('jeton-d-essai');
  await dz.locator('[data-a="jeton"]').click();
  await expect.poll(() => page.evaluate(() => window.__appels.some((a) => a[0] === 'reglages.regler_secret' && a[1].cle === 'dns.jeton_cloudflare'))).toBe(true);
  await dz.locator('[data-rg="expire_jours"]').fill('60');
  await dz.locator('[data-rg="expire_jours"]').dispatchEvent('change');
  await expect.poll(() => page.evaluate(() => window.__appels.filter((a) => a[0] === 'reglages.regler').map((a) => a[1]))).toContainEqual({ cle: 'dns.expire_jours', valeur: 60 });
  await dz.locator('[data-a="reglages"]').first().click();                              // on referme le panneau

  await dz.locator('[data-o="enreg"]').click();
  await dz.locator('[data-a="relever"]').first().click();
  await expect(dz.locator('.rang').filter({ hasText: 'app.exemple.org' })).toContainText('changé');
});
