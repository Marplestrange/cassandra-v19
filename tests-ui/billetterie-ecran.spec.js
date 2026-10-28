// L'écran du titulaire et la caisse : vue d'ensemble, fiche d'événement, vente à la caisse (avec réserve de numéros signés). Les capacités sont simulées : on vérifie ce que l'ÉCRAN demande et affiche.
const { test, expect } = require('@playwright/test');

async function ouvrir(page) {
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.waitForFunction(() => window.CASS && window.CASS.sceneSurMesure && window.CASS.sceneSurMesure.billetterie && window.CASS.qr);
}

async function simuler(page) {
  await page.evaluate(() => {
    window.__appels = [];
    const evt = { id: 1, ref: 'EVT-000001', nom: "Soirée d'hiver", date_iso: '2026-12-12', salle_id: 1, quota: 120, prix: 1500, statut: 'en vente', publie: 1, portes: '19:30', debut: '20:00', fin: '23:00', pause: 10, ancienne_date: '', motif_annulation: '' };
    const types = [{ id: 1, nom: 'Plein tarif', description: '', prix: 1500, quota: 0, entrees: 1, visible: 1 }, { id: 2, nom: 'Tarif réduit', description: '', prix: 1000, quota: 0, entrees: 1, visible: 1 }];
    let reserve = 0;
    window.CASS.agir = async (c, a) => {
      window.__appels.push([c.replace('billetterie.', ''), a]);
      const cap = c.replace('billetterie.', '');
      if (cap === 'evenements') return { evenements: [evt] };
      if (cap === 'stock') return { evenement_id: 1, quota: 120, vendus: 30, retenus: 2, restant: 88, types: [{ id: 1, nom: 'Plein tarif', quota: 0, vendus: 30, retenus: 2, restant: null }] };
      if (cap === 'commandes') return { commandes: [{ id: 1, ref: 'CMD-000001', etat: 'payee', total: 4500, nom: 'Sophie', evenement_id: 1, cree_le: '2026-10-28 10:00', moyen: 'especes' }] };
      if (cap === 'retraits') return { retraits: a.etat === 'demandee' ? [{ id: 1 }] : [] };
      if (cap === 'conflits' || cap === 'courriels' || cap === 'attente_liste') return { conflits: [], courriels: [], attente: [] };
      if (cap === 'evenement_fiche') return { evenement: evt, salle: { nom: 'Salle des fêtes' }, jauge: { total: 125, quota: 120, invitations: 5, capacite: 140, depasse: false }, types, programme: [], affectations: [], invitations: [] };
      if (cap === 'caisses') return { caisses: [{ id: 1, ref: 'CAI-000001', evenement_id: 1, fond: 5000, etat: 'ouverte' }] };
      if (cap === 'caisse_etat') return { caisse: { id: 1, ref: 'CAI-000001', fond: 5000 }, totaux: { total: 0, billets: 0, attendu_especes: 5000 }, reserve_libre: 50, ventes: [] };
      if (cap === 'caisse_reserver') { const out = []; for (let i = 0; i < 50; i++) { reserve++; out.push({ numero: 'A-' + String(reserve).padStart(4, '0'), qr: 'CASS1.A-' + String(reserve).padStart(4, '0') + '.ABCDEF', code_controle: 'A-' + String(reserve).padStart(4, '0') + '-ABCDEF' }); } return { caisse_id: 1, numeros: out }; }
      if (cap === 'caisse_vendre') return { id: 1, ref: 'CMD-000009', total: 1500, rendu: 500, numeros: a.numeros };
      return {};
    };
  });
}

async function monter(page, ecran) {
  await page.evaluate(async (e) => {
    document.querySelectorAll('#bl-essai').forEach((x) => x.remove());
    const racine = document.createElement('div'); racine.id = 'bl-essai'; racine.style.cssText = 'position:fixed;inset:0;overflow:auto;background:var(--bg,#fff);z-index:5000;padding:12px';
    document.body.appendChild(racine);
    await window.CASS.sceneSurMesure.billetterie(racine, { ecran: 'billetterie:' + e });
  }, ecran);
}

test("Billetterie : vue d'ensemble — chiffres, alerte de retrait, carte de l'événement", async ({ page }) => {
  await ouvrir(page);
  await simuler(page);
  await monter(page, 'b_vue');
  const R = page.locator('#bl-essai');
  await expect(R).toContainText('Billetterie');
  await expect(R.locator('.tuile').first()).toContainText('événements à venir');
  await expect(R.locator('.alerte', { hasText: 'retrait' })).toBeVisible();
  await expect(R.locator('button.evt')).toContainText("Soirée d'hiver");
  await expect(R.locator('button.evt')).toContainText('30 / 120 vendus');
});

test("Billetterie : fiche d'un événement — onglets et confirmation d'annulation", async ({ page }) => {
  await ouvrir(page);
  await simuler(page);
  await monter(page, 'b_evenements');
  const R = page.locator('#bl-essai');
  await R.locator('tr[data-a=ouvrir]').click();
  await expect(R.locator('h2').first()).toContainText("Soirée d'hiver");
  for (const o of ['Billets', 'Programme', 'Revendeurs', 'Invitations', 'Ventes', 'Liste d’attente']) {
    await R.locator('.onglets button', { hasText: o }).click();
    await expect(R.locator('.onglets button.on')).toHaveText(o);
  }
  await R.locator('.onglets button', { hasText: 'Résumé' }).click();
  await expect(R).toContainText('125 (vente 120 + invitations 5) pour 140 places');
  await page.evaluate(() => { const f = window.CASS.agir; window.CASS.agir = async (c, a) => (c === 'billetterie.evenement_impact' ? { evenement: { nom: "Soirée d'hiver" }, commandes_payees: 3, a_rembourser: 14000, par_moyen: {}, commandes_en_cours: 1, invitations: 1, artistes: [], revendeurs: [], salle: { acompte: 10000, annulation: 'Acompte perdu' } } : f(c, a)); });
  await R.locator('[data-a=annuler]').click();
  await expect(page.locator('.kit-m')).toContainText('3 commande(s) payée(s)');
  await expect(page.locator('.kit-m')).toContainText('Acompte versé à la salle');
  await page.locator('.kit-m [data-c=non]').click();
  expect((await page.evaluate(() => window.__appels.map((x) => x[0]))).includes('evenement_annuler')).toBe(false);          // annuler le dialogue n'annule rien
});

test("Billetterie : caisse — vente en espèces avec numéros réservés, QR affiché, rendu de monnaie", async ({ page }) => {
  await ouvrir(page);
  await simuler(page);
  await page.evaluate(() => { try { Object.keys(localStorage).filter((k) => k.startsWith('bl.')).forEach((k) => localStorage.removeItem(k)); } catch (e) { /* pas de stockage */ } });
  await monter(page, 'b_caisse');
  const R = page.locator('#bl-essai');
  await expect(R).toContainText('Caisse · Soirée d\'hiver');
  await R.locator('[data-a=plus]').first().click();
  await R.locator('[data-a=recu][data-v="2000"]').click();
  await expect(R.locator('.rendu')).toHaveText(/5,00/);
  await R.locator('[data-a=encaisser]').click();
  await expect(R).toContainText('Vente enregistrée');
  await expect(R.locator('.billet-qr svg')).toBeVisible();
  const vente = await page.evaluate(() => window.__appels.filter((x) => x[0] === 'caisse_vendre').pop()[1]);
  expect(vente).toMatchObject({ caisse_id: 1, moyen: 'especes', recu: 2000, lignes: [{ type_billet_id: 1, quantite: 1 }] });
  expect(vente.numeros).toEqual(['A-0001']);                                                                                         // le numéro vient de la réserve signée, pas du hasard
});
