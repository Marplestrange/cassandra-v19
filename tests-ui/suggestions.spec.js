// Les suggestions d'Itare et le menu de gauche. Les tâches sont posées sur DEMAIN : la fenêtre entière est alors libre, quelle que soit l'heure à laquelle la suite tourne.
const { test, expect } = require('@playwright/test');

async function ouvrirAujourdhui(page) {
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.evaluate(() => window.CASS && window.CASS.aujourdhui && window.CASS.aujourdhui.ouvrir());
  await page.waitForSelector('#aj-racine', { state: 'visible', timeout: 10000 });
}

async function ajouter(page, texte) {
  await page.fill('#aj-q', texte);
  await page.click('#aj-f button[type="submit"]');
  await expect(page.locator('.aj-puce').filter({ hasText: texte }).first()).toBeVisible({ timeout: 5000 });
}

test.describe("Aujourd'hui - suggestions d'Itare", () => {
  test.beforeEach(async ({ page }) => {
    await ouvrirAujourdhui(page);
    await page.evaluate(async () => {                         // une page neuve : les tâches des essais précédents ne comptent pas
      const l = await window.CASS.agir('taches.lister', { limite: 500 });
      for (const t of (l && l.taches) || []) await window.CASS.agir('taches.supprimer', { id: t.id });
    });
    await page.evaluate(() => window.CASS.aujourdhui.ouvrir());
    await page.evaluate(() => document.querySelector('[data-jour="1"]').click());      // demain
    await expect(page.locator('#aj-auj')).not.toHaveClass(/on/);
  });

  test('propose une heure pour chaque tâche à placer, puis tout accepter les pose sans chevauchement', async ({ page }) => {
    await ajouter(page, 'Suggestion A');
    await ajouter(page, 'Suggestion B');
    const bandeau = page.locator('#aj-sug');
    await expect(bandeau).toBeVisible({ timeout: 8000 });
    await expect(bandeau).toContainText('Itare propose');
    await expect(page.locator('.aj-fant-sug')).toHaveCount(2);

    await page.click('[data-sug-tout]');
    await expect(bandeau).toBeHidden();
    await expect(page.locator('.aj-fant-sug')).toHaveCount(0);

    const demain = await page.locator('#aj-date').inputValue();
    const lire = () => page.evaluate((jour) => window.CASS.agir('affichage.lire_plan', { jour }), demain);   // ce que le serveur a gardé, pas ce que l'écran dessine
    await expect.poll(async () => ((await lire()).blocs || []).length, { timeout: 8000 }).toBe(2);                // l'enregistrement du plan est différé
    const plan = await lire();
    const blocs = plan.blocs.map((b) => [b.deb, b.deb + b.duree]).sort((x, y) => x[0] - y[0]);
    expect(blocs.length).toBe(2);
    expect(blocs[0][1]).toBeLessThanOrEqual(blocs[1][0]);        // l'un finit avant que l'autre commence
  });

  test('ignorer écarte le bandeau sans rien placer', async ({ page }) => {
    await ajouter(page, 'Suggestion C');
    await expect(page.locator('#aj-sug')).toBeVisible({ timeout: 8000 });
    await page.click('[data-sug-non]');
    await expect(page.locator('#aj-sug')).toBeHidden();
    await expect(page.locator('.aj-fant-sug')).toHaveCount(0);
    await expect(page.locator('.aj-blk').filter({ hasText: 'Suggestion C' })).toHaveCount(0);
  });

  test('cliquer une case fantôme n’accepte que celle-là', async ({ page }) => {
    await ajouter(page, 'Suggestion D');
    await ajouter(page, 'Suggestion E');
    await expect(page.locator('.aj-fant-sug')).toHaveCount(2, { timeout: 8000 });
    await page.locator('.aj-fant-sug').first().click();
    await expect(page.locator('.aj-blk').filter({ hasText: /Suggestion [DE]/ })).toHaveCount(1);
  });
});

test.describe('Menu de gauche', () => {
  test('se dessine sans erreur de script et ouvre une rubrique', async ({ page }) => {
    const erreurs = [];
    page.on('pageerror', (e) => erreurs.push(e.message));
    await ouvrirAujourdhui(page);
    await expect(page.locator('body.d19')).toHaveCount(1);        // le socle de disposition est posé
    await expect(page.locator('#d19-side')).toHaveCount(1);
    expect(erreurs).toEqual([]);
  });
});
