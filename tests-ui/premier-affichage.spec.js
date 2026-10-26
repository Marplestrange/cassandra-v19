// Au rechargement d'une page déjà connectée, l'ancienne interface (V18) est dans le HTML dès le départ : elle ne doit JAMAIS se montrer, même une fraction de seconde,
// avant que la disposition V19 ait pris la main (body.d19).
const { test, expect } = require('@playwright/test');

test("rechargement : l'ancienne interface ne s'affiche jamais avant la disposition V19", async ({ page }) => {
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.waitForSelector('body.d19 #d19-top', { timeout: 20000 });

  // on recharge, avec un échantillonneur posé AVANT les scripts de la page : une mesure à chaque image jusqu'à ce que la V19 ait pris la main
  await page.addInitScript(() => {
    window.__echantillons = [];
    const tic = () => {
      const a = document.getElementById('app-container'), b = document.body;
      if (a && b) window.__echantillons.push({ d19: b.classList.contains('d19'), visible: getComputedStyle(a).visibility, cache: a.classList.contains('hidden') });
      if (!(b && b.classList.contains('d19'))) requestAnimationFrame(tic);
    };
    requestAnimationFrame(tic);
  });
  await page.reload();
  await page.waitForSelector('body.d19 #d19-top', { timeout: 20000 });
  const e = await page.evaluate(() => window.__echantillons);
  const vus = e.filter((x) => !x.d19 && !x.cache && x.visible === 'visible');
  expect(e.length).toBeGreaterThan(0);                                                   // l'échantillonneur a bien tourné pendant le chargement
  expect(vus, 'images où l’ancienne interface était visible avant la V19').toEqual([]);
  expect(await page.evaluate(() => getComputedStyle(document.getElementById('app-container')).visibility)).toBe('visible');   // et une fois la V19 en place, la page se montre
});
