// « Agents IA » est une entrée du groupe Autonomie ouverte à tous les comptes : elle ouvre l'écran du module agents (équipe pour l'administrateur, Mon Itare pour un compte ordinaire).
// « Mon Itare » n'est plus une entrée du Desk. Les écrans sont reliés aux autres modules, jamais copiés.
const { test, expect } = require('@playwright/test');
test.setTimeout(150000);   // le premier chargement d'une instance neuve est lent

async function entrer(page) {
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.waitForSelector('body.d19', { timeout: 60000 });
}
const disposition = (page) => page.evaluate(async () => (await window.CASS.agir('affichage.lire_disposition', {})).groupes);

test("Agents IA : l'entrée est ouverte à tous, Mon Itare a quitté le Desk, l'écran de l'équipe s'ouvre", async ({ page }) => {
  await entrer(page);
  await expect.poll(async () => { const g = (await disposition(page)).find((x) => x.id === 'auto'); return !!g && g.entrees.some((e) => e.id === 'agents-ia'); }, { timeout: 40000 }).toBe(true);
  const g = await disposition(page);
  const entree = g.find((x) => x.id === 'auto').entrees.find((e) => e.id === 'agents-ia');
  expect(entree.role).toBe('utilisateur');
  expect(entree.ecran).toBe('agents:equipe');
  const desk = g.find((x) => x.id === 'desk');
  expect(desk.entrees.some((e) => e.id === 'moi-itare')).toBe(false);

  await page.evaluate(() => window.CASS.disposition.rafraichir());
  await page.evaluate(() => window.CASS.disposition.aller('auto', 'agents-ia', ''));
  await expect.poll(() => page.evaluate(() => !!document.querySelector('#tab-mod-agents-equipe .ag-nav')), { timeout: 60000 }).toBe(true);
  // le compte d'essai est administrateur : l'équipe, ses cartes, ses services
  const nav = await page.evaluate(() => [...document.querySelectorAll('#tab-mod-agents-equipe .ag-nav button')].map((b) => b.textContent.trim()));
  expect(nav.join('|')).toMatch(/L'équipe.*Conversations.*À valider.*Journal.*Modèles & clés/);
  expect(await page.evaluate(() => document.querySelectorAll('#tab-mod-agents-equipe .ag-cartes button.carte').length)).toBeGreaterThanOrEqual(5);
});

test("Agents IA, vue administrateur : la fiche d'un agent et ses onglets", async ({ page }) => {
  await entrer(page);
  await expect.poll(async () => (await disposition(page)).some((x) => x.entrees.some((e) => e.id === 'agents-ia')), { timeout: 40000 }).toBe(true);
  await page.evaluate(() => window.CASS.disposition.rafraichir());
  await page.evaluate(() => window.CASS.disposition.aller('auto', 'agents-ia', ''));
  await page.waitForSelector('#tab-mod-agents-equipe .ag-cartes button[data-agent="cassandra"]', { timeout: 60000 });
  await page.click('#tab-mod-agents-equipe button[data-agent="cassandra"]');
  await page.waitForSelector('#tab-mod-agents-equipe #ag-ong', { timeout: 10000 });
  const onglets = await page.evaluate(() => [...document.querySelectorAll('#ag-ong button')].map((b) => b.textContent.trim()));
  expect(onglets).toEqual(['Aperçu', 'Outils & palier', 'Journal', 'Essai en direct', 'Fait & proposé', 'Coût', 'Sûr & refusé', 'Mémoire', 'Réglages']);
  // le niveau se règle et se relit
  await page.click('[data-niveau="observer"]');
  await expect.poll(() => page.evaluate(() => !!document.querySelector('[data-niveau="observer"].on'))).toBe(true);
  await page.click('[data-niveau="reine"]');
  await expect.poll(() => page.evaluate(() => !!document.querySelector('[data-niveau="reine"].on'))).toBe(true);
  // l'onglet Coût et celui des plafonds (administrateur)
  await page.click('#ag-ong [data-o="cout"]');
  await page.waitForSelector('#ag-pl-poser');
  // la Mémoire est ouverte chez son module, pas recopiée
  await page.click('#ag-ong [data-o="memoire"]');
  await page.waitForSelector('[data-chez="memory"]');
  // aucun débordement horizontal
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
});

test("Agents IA, vue utilisateur : seulement Mon Itare, Conversations, À valider, Journal", async ({ page }) => {
  await entrer(page);
  await expect.poll(async () => (await disposition(page)).some((x) => x.entrees.some((e) => e.id === 'agents-ia')), { timeout: 40000 }).toBe(true);
  // un compte ordinaire : la scène est dessinée avec une équipe réduite à son Itare
  await page.evaluate(() => { const r = window.CASS.agir; window.CASS.agir = async (c, a) => { const d = await r(c, a); if (c === 'agents.equipe') return { ...d, administrateur: false, equipe: d.equipe.filter((x) => x.portee === 'compte') }; return d; }; });
  await page.evaluate(() => window.CASS.disposition.rafraichir());
  await page.evaluate(() => window.CASS.disposition.aller('auto', 'agents-ia', ''));
  await page.waitForSelector('#tab-mod-agents-equipe .ag-nav', { timeout: 60000 });
  const nav = await page.evaluate(() => [...document.querySelectorAll('#tab-mod-agents-equipe .ag-nav[role=tablist]:not(#ag-ong) button')].map((b) => b.textContent.trim().replace(/\d+$/, '')));
  expect(nav).toEqual(['Mon Itare', 'Conversations', 'À valider', 'Journal']);
  expect(await page.evaluate(() => document.querySelector('#tab-mod-agents-equipe').textContent)).not.toMatch(/Cassandra|Amizo|Relecteur/);
  expect(await page.evaluate(() => document.querySelectorAll('#tab-mod-agents-equipe .ag-cartes').length)).toBe(0);
  const onglets = await page.evaluate(() => [...document.querySelectorAll('#ag-ong button')].map((b) => b.textContent.trim()));
  expect(onglets).toEqual(['Aperçu', 'Outils & palier', 'Journal', 'Fait & proposé', 'Mémoire', 'Réglages']);
});
