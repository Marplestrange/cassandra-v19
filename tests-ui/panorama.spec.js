// Le Panorama : une page par entrée. On pilote vuAller (ce que le menu appelle) et on lit ce que le CSS laisse voir.
const { test, expect } = require('@playwright/test');

const PAGES = {
  verdict: ['Vue d’ensemble', ['vu-verdict', 'vu-kpis']],
  gestes: ['Ce qui demande un geste', ['vu-gestes']],
  cass: ['Cassandra, maintenant', ['vu-cass']],
  sites: ['Les sites', ['vu-sites']],
  flotte: ['La flotte', ['vu-flotte']],
  fil: ['Ce qui a changé', ['vu-fil']],
  machine: ['La machine', ['vu-machine']],
};

test('chaque entrée du Panorama n’affiche que sa page', async ({ page }) => {
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.evaluate(() => {                                    // on montre l'onglet et on pose des sections pleines : le test porte sur l'affichage, pas sur les données
    document.querySelectorAll('.tab-content').forEach((t) => t.classList.remove('active'));
    const t = document.getElementById('tab-overview'); t.classList.add('active'); t.style.display = 'block';
    ['vu-verdict', 'vu-kpis', 'vu-gestes', 'vu-cass', 'vu-parc', 'vu-fil', 'vu-machine'].forEach((id) => { const e = document.getElementById(id); e.hidden = false; if (!e.textContent.trim()) e.textContent = id; });
    ['vu-sites', 'vu-flotte'].forEach((id) => { const e = document.getElementById(id); if (!e.textContent.trim()) e.textContent = id; });
  });
  for (const [vue, [titre, visibles]] of Object.entries(PAGES)) {
    await page.evaluate((v) => window.vuAller(v), vue);
    await expect(page.locator('#tab-overview')).toHaveAttribute('data-vue', vue);
    await expect(page.locator('#tab-overview .mx-head h1')).toHaveText(titre);
    const vus = await page.evaluate(() => ['vu-verdict', 'vu-kpis', 'vu-gestes', 'vu-cass', 'vu-sites', 'vu-flotte', 'vu-fil', 'vu-machine'].filter((id) => { const e = document.getElementById(id); return e && e.offsetParent !== null; }));
    const attendu = vue === 'verdict' ? [...visibles, 'vu-gestes'] : visibles;           // l'accueil porte aussi les premiers gestes
    expect(vus.sort()).toEqual(attendu.sort());
  }
});
