// Mon coffre-fort : mes espaces (le mien, puis ceux de société), les secrets que mon rôle me laisse voir, l'ajout, la lecture et le retrait
const { test, expect } = require('@playwright/test');

test("Mon coffre-fort : espaces, rôles, ajout, lecture, retrait", async ({ page }) => {
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.evaluate(() => {
    window.__appels = [];
    const espaces = [
      { id: 'u:bea@x.fr', genre: 'perso', nom: 'Mon coffre', role: 'proprio', secrets: 1, collections: '*', expire: '', admins: null },
      { id: 's:1', genre: 'societe', nom: 'Atelier Lumen', role: 'contrib', secrets: 1, collections: 'compta', expire: '2999-01-01', mode: 'interne', admins: null },
      { id: 's:2', genre: 'societe', nom: 'Lumen Formation', role: 'lecture', secrets: 1, collections: '*', expire: '', mode: 'interne', admins: null },
    ];
    const secrets = { 'u:bea@x.fr': [{ nom: 'perso', auteur: 'bea@x.fr', collection: '' }], 's:1': [{ nom: 'ma-note', auteur: 'bea@x.fr', collection: 'compta' }], 's:2': [{ nom: 'wifi', auteur: 'dan@x.fr', collection: '' }] };
    window.CASS.agir = async (c, a) => {
      window.__appels.push([c, a]);
      if (c === 'coffre.espaces') return { espaces };
      if (c === 'coffre.list') return { noms: secrets[a.espace].map((x) => x.nom), secrets: secrets[a.espace], espace: a.espace };
      if (c === 'coffre.get') return { valeur: 'la-valeur-de-' + a.name, espace: a.espace };
      if (c === 'coffre.set') { secrets[a.espace] = secrets[a.espace].filter((x) => x.nom !== a.name).concat([{ nom: a.name, auteur: 'bea@x.fr', collection: a.collection || '' }]); return { name: a.name }; }
      if (c === 'coffre.delete') { secrets[a.espace] = secrets[a.espace].filter((x) => x.nom !== a.name); return { name: a.name }; }
      if (c === 'coffre.journal') return { journal: [{ ts: '2026-10-27 10:00', username: 'bea@x.fr', action: 'lire', secret_name: 'perso' }], espace: a.espace };
      return {};
    };
  });
  await page.evaluate(async () => {
    const hote = document.createElement('div'); hote.id = 'mc-essai'; hote.style.cssText = 'position:relative;z-index:1;background:var(--bg,#fff);padding:12px'; document.body.prepend(hote);
    await window.CASS.sceneSurMesure.coffre(hote, { ecran: 'coffre:c_secrets' });
  });
  const k = page.locator('#mc-essai .mc');
  const appels = (c) => page.evaluate((c) => window.__appels.filter((a) => a[0] === c).map((a) => a[1]), c);
  await expect(k.locator('.esp button')).toHaveCount(3);
  await expect(k.locator('.esp button.on')).toContainText('Mon coffre');
  await expect(k.locator('tbody')).toContainText('perso');

  // mon espace : j'ajoute, je lis, je retire
  await k.locator('button[data-a="nouveau"]').click();
  await page.fill('#mc-fn', 'banque');
  await page.fill('#mc-fv', 'iban-secret');
  await page.locator('.kit-m [data-c="oui"]').click();
  await expect.poll(async () => (await appels('coffre.set')).some((x) => x.name === 'banque' && x.valeur === 'iban-secret' && x.espace === 'u:bea@x.fr')).toBe(true);
  await expect(k.locator('tbody')).toContainText('banque');
  await k.locator('tr', { hasText: 'banque' }).locator('button[data-a="voir"]').click();
  await expect(page.locator('#mc-vv')).toHaveValue('la-valeur-de-banque');
  await page.locator('.kit-m [data-c="oui"]').click();
  await k.locator('tr', { hasText: 'banque' }).locator('button[data-a="retirer"]').click();
  await page.locator('.kit-m [data-c="oui"]').click();
  await expect.poll(async () => (await appels('coffre.delete')).some((x) => x.name === 'banque')).toBe(true);

  // l'espace d'une société où je suis contributeur : je vois mes secrets, la collection et l'auteur, et une mention du rôle
  await k.locator('.esp button', { hasText: 'Atelier Lumen' }).click();
  await expect(k.locator('tbody')).toContainText('compta');
  await expect(k).toContainText('Contributeur');

  // en lecture seule : je consulte, je ne peux ni ajouter ni modifier ni retirer
  await k.locator('.esp button', { hasText: 'Lumen Formation' }).click();
  await expect(k.locator('tbody')).toContainText('wifi');
  await expect(k.locator('button[data-a="nouveau"]')).toHaveCount(0);
  await expect(k.locator('button[data-a="modifier"]')).toHaveCount(0);
  await expect(k.locator('button[data-a="retirer"]')).toHaveCount(0);

  // les autres pages du menu : le tableau de bord, les outils, le rapport
  const monter = async (ecran) => {
    await page.evaluate(async (ecran) => {
      document.getElementById('mc-essai').remove();
      const hote = document.createElement('div'); hote.id = 'mc-essai'; hote.style.cssText = 'position:relative;z-index:1;background:var(--bg,#fff);padding:12px'; document.body.prepend(hote);
      await window.CASS.sceneSurMesure.coffre(hote, { ecran });
    }, ecran);
    return page.locator('#mc-essai .mc');
  };
  await expect(await monter('coffre:c_tableau')).toContainText('Tableau de bord');
  await expect(await monter('coffre:c_outils')).toContainText('Générateur de mot de passe');
  await expect(await monter('coffre:c_rapport')).toContainText('Journal de Mon coffre');
});
