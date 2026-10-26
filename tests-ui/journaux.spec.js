// L'écran Journaux : le flux et son résumé, filtres, une source (table et fichier) paginée, chercher partout, les veilles (poser, mettre en pause, retirer), le poids et les silences.
const { test, expect } = require('@playwright/test');

test("Journaux : flux filtrable, une source, recherche, veilles, poids", async ({ page }) => {
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.evaluate(async () => {
    window.__appels = [];
    const sources = [{ key: 'agents', label: 'Journal des agents', group: 'Cassandra', count: 3, available: true }, { key: 'syslog', label: 'Syslog', group: 'Système', count: 0, available: false }, { key: 'nginx_err', label: 'nginx — erreurs', group: 'Système', count: 40, available: true }];
    let veilles = [{ id: 1, source: 'nginx_err', pattern: 'upstream timed out', label: 'timeouts', enabled: 1 }];
    const entree = (a, n) => ({ ts: '2026-10-26 21:0' + n, source: 'nginx_err', label: 'nginx — erreurs', niveau: n === 1 ? 'erreur' : 'info', acteur: '', action: a, sujet: '', detail: n === 1 ? { code: 502 } : {} });
    window.CASS.agir = async (c, a) => {
      window.__appels.push([c, a]);
      if (c === 'journal.resume') return { niveau: 'alerte', titre: '1 erreur sur 24 h.', sous_titre: '5 lignes lues dans 2 journaux', compte: { critique: 0, erreur: 1, avertissement: 0, info: 4 }, marquants: [{ ts: '2026-10-26 21:01', source: 'nginx_err', label: 'nginx — erreurs', niveau: 'erreur', action: 'upstream timed out' }] };
      if (c === 'journal.flux') return { sources: [], total: 2, entrees: [entree('upstream timed out', 1), entree('reload ok', 2)], en_defaut: ['syslog : absent'] };
      if (c === 'journal.sources') return { sources };
      if (c === 'journal.lire') return a.source === 'agents' ? { source: 'agents', kind: 'table', label: 'Journal des agents', columns: ['ts', 'qui', 'etiquette'], ts_col: 'ts', rows: [{ ts: '2026-10-26 20:00', qui: 'itare', etiquette: 'bonjour' }], total: 1, has_more: false } : { source: 'nginx_err', kind: 'file', label: 'nginx — erreurs', lines: ['ligne un', 'ligne deux'], total: 40, has_more: true };
      if (c === 'journal.chercher') return { query: a.question, results: [{ key: 'nginx_err', label: 'nginx — erreurs', total: 7 }], total: 7 };
      if (c === 'journal.veilles') return { veilles };
      if (c === 'journal.veille_poser') { if (a.wid) veilles = veilles.map((w) => (w.id === a.wid ? Object.assign({}, w, { enabled: a.enabled ? 1 : 0 }) : w)); else veilles = veilles.concat([{ id: 2, source: a.source, pattern: a.pattern, label: a.label, enabled: 1 }]); return {}; }
      if (c === 'journal.veille_retirer') { veilles = veilles.filter((w) => w.id !== a.wid); return {}; }
      if (c === 'journal.stats') return { journals: [{ key: 'nginx_err', label: 'nginx — erreurs', kind: 'file', rows: 0, bytes: 2097152 }, { key: 'agents', label: 'Journal des agents', kind: 'table', rows: 3, bytes: 900 }], bytes: 2098052 };
      if (c === 'journal.silences') return { silences: [{ key: 'agents', label: 'Journal des agents', last: '2026-10-25 10:00:00', age_s: 90000, attendu_s: 600 }] };
      return {};
    };
    const hote = document.createElement('div'); hote.id = 'j-essai'; hote.style.cssText = 'position:relative;z-index:1;background:var(--bg,#fff);padding:12px'; document.body.prepend(hote);
    await window.CASS.sceneSurMesure.journal(hote, { ecran: 'journal:vue_journal' });
  });
  const k = page.locator('#j-essai .kit');
  await expect(k.locator('.onglets button')).toHaveText(['Ce qui s’est passé', 'Une source', 'Chercher partout', 'Veilles', 'Poids']);
  await expect(k).toContainText('1 erreur sur 24 h.');
  await expect(k.locator('.li').filter({ hasText: 'reload ok' })).toContainText('info');
  await expect(k).toContainText('syslog : absent');                                        // un journal illisible se dit

  // filtres : le niveau et la recherche partent comme arguments ; la période devient une date
  await k.locator('select[data-a="niveau"]').selectOption('erreur+');
  await expect.poll(() => page.evaluate(() => window.__appels.filter((a) => a[0] === 'journal.flux').map((a) => a[1].niveau).pop())).toBe('erreur+');
  await k.locator('#jr-q').fill('timed out'); await k.locator('#jr-q').press('Enter');
  await expect.poll(() => page.evaluate(() => window.__appels.filter((a) => a[0] === 'journal.flux').map((a) => a[1].query).pop())).toBe('timed out');
  await k.locator('[data-a="h"][data-v="24"]').click();
  await expect.poll(() => page.evaluate(() => /^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$/.test(window.__appels.filter((a) => a[0] === 'journal.flux').map((a) => a[1].since).pop()))).toBe(true);

  // une source : la table, puis un fichier avec « Plus ancien »
  await k.locator('[data-s="source"]').click();
  await expect(k.locator('select[data-a="src"] option[disabled]')).toContainText('Syslog');   // un journal absent est grisé
  await k.locator('select[data-a="src"]').selectOption('agents');
  await expect(k.locator('table')).toContainText('bonjour');
  await k.locator('select[data-a="src"]').selectOption('nginx_err');
  await expect(k).toContainText('ligne deux');
  await k.locator('[data-a="plus"]').click();
  await expect.poll(() => page.evaluate(() => window.__appels.filter((a) => a[0] === 'journal.lire').map((a) => a[1].offset).pop())).toBe(100);

  // chercher partout
  await k.locator('[data-s="chercher"]').click();
  await k.locator('#jr-qc').fill('erreur'); await k.locator('#jr-qc').press('Enter');
  await expect(k).toContainText('7 résultat(s)');
  await k.locator('[data-a="ouvrir-source"][data-k="nginx_err"]').click();
  await expect(k.locator('select[data-a="src"]')).toHaveValue('nginx_err');                  // le résultat ouvre la source

  // veilles : poser, mettre en pause, retirer
  await k.locator('[data-s="veilles"]').click();
  await expect(k).toContainText('upstream timed out');
  await k.locator('#vl-motif').fill('refused'); await k.locator('#vl-nom').fill('refus');
  await k.locator('[data-a="veille-pose"]').click();
  await expect(k).toContainText('refus');
  await k.locator('[data-a="veille-bascule"][data-id="1"]').click();
  await expect(k.locator('.li').filter({ hasText: 'timeouts' })).toContainText('en pause');
  await k.locator('[data-a="veille-retire"][data-id="1"]').click();
  await expect(k).not.toContainText('timeouts');

  // poids et silences
  await k.locator('[data-s="poids"]').click();
  await expect(k).toContainText('2.0 Mo');
  await expect(k).toContainText('Journal des agents');
  await expect(k.locator('.li').filter({ hasText: 'silence' })).toHaveCount(1);
});
