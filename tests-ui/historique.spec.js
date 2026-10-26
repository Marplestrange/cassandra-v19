// L'écran Historique : le verdict à l'ouverture, une courbe au choix (SVG du kit) avec sa période et son habitude, les écarts, la prévision de saturation, les mesures muettes.
const { test, expect } = require('@playwright/test');

test("Historique : verdict, courbe et période, écarts, prévision, mesures sans données", async ({ page }) => {
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.evaluate(async () => {
    window.__appels = [];
    const pts = (n, f) => Array.from({ length: n }, (_, i) => ({ ts: '2026-10-26 ' + String(i).padStart(2, '0'), v: f(i) }));
    const metrics = [
      { key: 'disk', label: 'Disque', unit: '%', family: 'Système hôte', desc: 'Occupation du disque racine.', available: true, etat: 'a_jour', etat_texte: 'à jour', forecast: true },
      { key: 'cpu', label: 'Processeur', unit: '%', family: 'Système hôte', desc: 'Charge.', available: true, etat: 'a_jour', etat_texte: 'à jour', forecast: false },
      { key: 'ram', label: 'Mémoire', unit: '%', family: 'Système hôte', desc: '', available: true, etat: 'muette', etat_texte: 'muette', forecast: false },
    ];
    window.CASS.agir = async (c, a) => {
      window.__appels.push([c, a]);
      if (c === 'mesures.sources') return { ok: true, metrics };
      if (c === 'mesures.verdict') return { ok: true, niveau: 'alerte', titre: 'Le disque se remplit.', sous_titre: 'Une échéance approche.', lignes: [{ niveau: 'alerte', titre: 'Disque : saturation dans 30 jours', detail: 'tendance sur 14 jours', gestes: [] }, { niveau: 'muet', titre: 'Sans nouvelles : Mémoire', detail: 'dernière mesure ?', gestes: [] }] };
      if (c === 'mesures.serie') return { ok: true, key: a.cle, label: a.cle === 'cpu' ? 'Processeur' : 'Disque', unit: '%', period: a.periode, series: [{ name: 'machine', points: pts(24, (i) => 40 + i) }] };
      if (c === 'mesures.profil') return { ok: true, key: a.cle, enough: true, slot_label: 'lundi 21 h', baseline: 55, current: 62, deviation_pct: 13 };
      if (c === 'mesures.ecarts') return { ok: true, threshold: 60, deviations: [{ key: 'cpu', label: 'Processeur', family: 'Système hôte', unit: '%', current: 90, baseline: 30, deviation_pct: 200 }], coinciding: [] };
      if (c === 'mesures.prevision') return { ok: true, key: a.cle, enough: true, current: 70, trend: 0.5, saturation_days: 30, saturation_date: '2026-11-25' };
      return {};
    };
    const hote = document.createElement('div'); hote.id = 'h-essai'; hote.style.cssText = 'position:relative;z-index:1;background:var(--bg,#fff);padding:12px'; document.body.prepend(hote);
    await window.CASS.sceneSurMesure.mesures(hote, { ecran: 'mesures:vue_historique' });
  });
  const k = page.locator('#h-essai .kit');
  await expect(k.locator('.onglets button')).toHaveText(['Maintenant', 'Courbes', 'Écarts', 'Prévision', 'Sans données']);
  await expect(k).toContainText('Le disque se remplit.');
  await expect(k).toContainText('Disque : saturation dans 30 jours');
  await expect(k).toContainText('sans nouvelles');

  await k.locator('[data-s="courbes"]').click();
  await expect(k.locator('svg.courbe')).toBeVisible();
  await expect(k).toContainText('Ce qui est habituel');
  await expect(k).toContainText('lundi 21 h');
  await k.locator('[data-a="periode"][data-p="7d"]').click();
  await expect.poll(() => page.evaluate(() => window.__appels.filter((a) => a[0] === 'mesures.serie').map((a) => a[1].periode).pop())).toBe('7d');
  await k.locator('select[data-a="cle"]').selectOption('cpu');
  await expect.poll(() => page.evaluate(() => window.__appels.filter((a) => a[0] === 'mesures.serie').map((a) => a[1].cle).pop())).toBe('cpu');

  await k.locator('[data-s="ecarts"]').click();
  await expect(k).toContainText('+200 %');
  await k.locator('[data-a="ouvrir"][data-k="cpu"]').click();
  await expect(k.locator('svg.courbe')).toBeVisible();                                      // « Voir la courbe » mène à la courbe de cette mesure

  await k.locator('[data-s="prevision"]').click();
  await expect(k).toContainText('Saturation dans 30 jours (2026-11-25)');
  expect(await page.evaluate(() => window.__appels.filter((a) => a[0] === 'mesures.prevision').map((a) => a[1].cle))).toEqual(['disk']);   // seules les mesures qui peuvent saturer se prévoient

  await k.locator('[data-s="vides"]').click();
  await expect(k.locator('.li').filter({ hasText: 'Mémoire' })).toContainText('muette');
});
