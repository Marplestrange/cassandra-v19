// L'écran Sensorium : le verdict à l'ouverture, les relevés par famille, l'histoire d'un relevé, les changements, les capteurs.
const { test, expect } = require('@playwright/test');

test("Sensorium : maintenant, famille, histoire d'un relevé, changements, capteurs", async ({ page }) => {
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.evaluate(async () => {
    window.__appels = [];
    const maintenant = new Date().toISOString().slice(0, 19) + 'Z';
    const r = (wkey, value, severity, extra) => Object.assign({ wkey, value, severity: severity || 'info', observed_at: maintenant, libelle: wkey.split('.').pop() }, extra || {});
    const rows = [
      r('system.hostname', 'orion'), r('system.os', 'Debian 12'), r('system.uptime', '3 j'), r('health.score', '92 · tout va bien'),
      r('disk./.usage', '71 %', 'warning', { libelle: 'Disque /', detail: JSON.stringify({ causes_probables: ['journaux nginx'] }) }), r('ram.usage', '40 %'),
      r('prevision.disk', 'saturé dans 30 j'), r('fleet.athena', 'en ligne'), r('machine.athena.mises_a_jour', 'dernière mise à jour il y a 2 j'),
      r('capteur.nginx', 'muet', 'warning'),
    ];
    window.CASS.agir = async (c, a) => {
      window.__appels.push([c, a]);
      if (c === 'sensorium.monde') return rows;
      if (c === 'sensorium.changements') return [{ entity_name: 'nginx', change_type: 'modified', new_value: 'actif', old_value: 'en échec', severity: 'info', timestamp: '2026-10-26T20:00:00' }];
      if (c === 'sensorium.historique') return { historique: [{ change_type: 'modified', new_value: '71 %', timestamp: '2026-10-26T19:00:00' }], disponibilite_30j: 99.9 };
      return {};
    };
    const hote = document.createElement('div'); hote.id = 's-essai'; hote.style.cssText = 'position:relative;z-index:1;background:var(--bg,#fff);padding:12px'; document.body.prepend(hote);
    await window.CASS.sceneSurMesure.sensorium(hote, { ecran: 'sensorium:vue_sensorium' });
  });
  const k = page.locator('#s-essai .kit');
  await expect(k.locator('.onglets button')).toHaveText(['Maintenant', 'Par famille', 'Ce qui a changé', 'Les capteurs']);
  await expect(k).toContainText('1 point demande un regard');
  await expect(k).toContainText('cause probable : journaux nginx');
  await expect(k).toContainText('saturé dans 30 j');
  await expect(k).toContainText('athena');
  await expect(k).toContainText('1 capteur en défaut');

  await k.locator('[data-a="histo"]').first().click();
  await expect(k).toContainText('Disponibilité sur 30 jours');
  await k.locator('[data-a="fermer"]').click();

  await k.locator('[data-s="famille"]').click();
  await k.locator('[data-a="fam"][data-k="ressources"]').click();
  await expect(k).toContainText('Ressources · 2 relevés');

  await k.locator('[data-s="changements"]').click();
  await expect(k).toContainText('en échec');

  await k.locator('[data-s="capteurs"]').click();
  await expect(k.locator('.li').filter({ hasText: 'nginx' })).toContainText('à voir');
});
