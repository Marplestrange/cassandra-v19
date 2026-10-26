// Outil de développement : prend des captures de quelques onglets V18 (avec ou sans l'habillage) dans le serveur d'essai déjà lancé.
// Usage : node capture.js <dossier> [onglets séparés par des virgules]
const { chromium } = require('@playwright/test');
const dossier = process.argv[2];
const onglets = (process.argv[3] || 'fleet,mysites,history,sensorium,securite,journal').split(',');
(async () => {
  const nav = await chromium.launch();
  const page = await nav.newPage({ viewport: { width: 1360, height: 820 } });
  await page.goto('http://127.0.0.1:9005/');
  if (await page.locator('#login-modal').isVisible({ timeout: 3000 }).catch(() => false)) {
    await page.fill('#login-username', 'ui@exemple.test');
    await page.fill('#login-password', 'Essai-UI-2026!');
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 15000 });
  }
  await page.waitForSelector('body.d19', { timeout: 20000 });
  if (process.env.SANS) await page.evaluate(() => document.querySelectorAll('link[href*="habillage"]').forEach((l) => l.remove()));
  await page.waitForTimeout(3000);
  for (const o of onglets) {
    await page.evaluate((o) => switchTab(o), o);
    await page.waitForTimeout(4000);
    await page.screenshot({ path: `${dossier}/${o}.png` });
  }
  await nav.close();
})();
