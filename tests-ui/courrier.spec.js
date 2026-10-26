// « ✎ Réponse » : un message devient un BROUILLON de réponse. La boîte et le modèle sont simulés (aucun IMAP ici) : on vérifie l'enchaînement et que rien ne part.
const { test, expect } = require('@playwright/test');

test("un message non lu se change en brouillon de réponse, sans envoi", async ({ page }) => {
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.evaluate(() => window.CASS.aujourdhui.ouvrir());
  await page.waitForSelector('#aj-racine', { state: 'visible', timeout: 10000 });

  await page.evaluate(() => {
    window.__appels = [];
    const vrai = window.CASS.agir.bind(window.CASS);
    window.CASS.agir = async (cap, args) => {
      if (cap === 'courrier.lire') { window.__appels.push([cap, args]); return { uid: 42, de: 'Léa <lea@exemple.fr>', repondre_a: '', objet: 'Devis', texte: 'Pouvez-vous confirmer le devis ?', message_id: '<abc@exemple.fr>', references: '' }; }
      if (cap === 'modeles.completer') { window.__appels.push([cap, args]); return { ok: true, reponse: 'Bonjour Léa, je confirme.' }; }
      if (cap === 'courrier.brouillon_creer') { window.__appels.push([cap, args]); return { dossier: 'Drafts' }; }
      if (cap === 'courrier.envoyer') { window.__appels.push([cap, args]); return {}; }
      return vrai(cap, args);
    };
    const zone = document.querySelector('#bu-mail-apercu');
    zone.innerHTML = '<div class="bu-row" data-uid="42"><div class="tx"><span>Devis</span></div></div>';
  });
  const bouton = page.locator('#bu-mail-apercu [data-mp]');
  await expect(bouton).toHaveCount(1, { timeout: 5000 });
  await bouton.evaluate((b) => b.click());

  await expect.poll(() => page.evaluate(() => window.__appels.map((a) => a[0]).join(',')), { timeout: 5000 })
    .toBe('courrier.lire,modeles.completer,courrier.brouillon_creer');
  const brouillon = await page.evaluate(() => window.__appels[2][1]);
  expect(brouillon.a).toContain('lea@exemple.fr');
  expect(brouillon.objet).toBe('Re: Devis');
  expect(brouillon.texte).toBe('Bonjour Léa, je confirme.');
  expect(brouillon.repond_a_message).toBe('<abc@exemple.fr>');
  expect(await page.evaluate(() => window.__appels.some((a) => a[0] === 'courrier.envoyer'))).toBe(false);
});
