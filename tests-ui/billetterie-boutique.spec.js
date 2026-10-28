// La boutique publique : programmation, événement, panier, commande, suivi avec QR, compte. L'API publique est simulée (page.route) : on vérifie ce que l'ÉCRAN envoie et montre.
const { test, expect } = require('@playwright/test');

const ok = (resultat) => ({ status: 200, contentType: 'application/json', body: JSON.stringify({ statut: 'faite', resultat }) });
const echec = (erreur) => ({ status: 500, contentType: 'application/json', body: JSON.stringify({ statut: 'echec', erreur }) });

const EVENEMENT = {
  evenement: { ref: 'EVT-000001', nom: "Soirée d'hiver", date: '2026-12-12', description: 'Une nuit.', accroche: 'Soul et folk', tags: '', portes: '19:30', debut: '20:00', fin: '23:00', age: 'Tous publics', configuration: 'debout', etat: 'ouvert' },
  salle: { nom: 'Salle des fêtes', adresse: '1 place de la Mairie', pmr: true, equipements: '' },
  programme: [{ ordre: 1, duree: 45, scene: 'Les Marées', genre: 'Folk', bio: '', heure: '20:00' }],
  billets: [{ ref: 'TYP-000001', nom: 'Plein tarif', description: 'Entrée simple', prix: 1500, entrees: 1, etat: 'ok', plus_que: null }, { ref: 'TYP-000002', nom: 'Tarif réduit', description: '', prix: 1000, entrees: 1, etat: 'ok', plus_que: null }],
  places_restantes: 100, achat: { compte_obligatoire: false, frais_sans_compte: 200, don_possible: true },
  paiements: [{ id: 'virement', libelle: 'Virement bancaire', detail: 'Places retenues 3 jours' }], liste_attente: true, organisateur: { nom: 'Maison Bohème', mail: 'contact@exemple.fr' },
};

test("Boutique : programmation, panier chiffré, commande, suivi avec QR et PDF", async ({ page }) => {
  const appels = [];
  await page.route('**/api/public/billetterie.*', async (route) => {
    const cap = route.request().url().split('billetterie.')[1];
    const args = (JSON.parse(route.request().postData() || '{}')).args || {};
    appels.push([cap, args]);
    if (cap === 'public_calendrier') return route.fulfill(ok({ organisateur: 'Maison Bohème', evenements: [
      { ref: 'EVT-000001', nom: "Soirée d'hiver", date: '2026-12-12', accroche: 'Soul et folk', lieu: 'Salle des fêtes', a_partir_de: 1000, etat: 'ouvert' },
      { ref: 'EVT-000009', nom: 'Vieille soirée', date: '2020-01-01', accroche: '', lieu: '', a_partir_de: 500, etat: 'terminé' }] }));
    if (cap === 'public_evenement') return route.fulfill(ok(EVENEMENT));
    if (cap === 'public_compte_moi') return route.fulfill(echec('votre session a expiré : reconnectez-vous'));
    if (cap === 'public_panier') {
      const n = args.lignes.reduce((s, l) => s + l.quantite, 0);
      return route.fulfill(ok({ lignes: args.lignes.map((l) => ({ nom: 'Plein tarif', prix: 1500, quantite: l.quantite })), places: n, sous_total: 1500 * n, remise: 0, promo: '', don: args.don || 0, frais: 200, total: 1500 * n + (args.don || 0) + 200 }));
    }
    if (cap === 'public_commander') {
      if (args.mail === 'refuse@exemple.org') return route.fulfill(echec('il ne reste que 0 place(s)'));
      return route.fulfill(ok({ commande: 'CMD-000001', suivi: 'jeton-suivi', total: 3200, places: 2, expire_le: Date.now() / 1000 + 600, attribution: '', paiement: { type: 'virement', iban: 'FR76 1', reference: 'CMD-000001', montant: 3200, delai_jours: 3 } }));
    }
    if (cap === 'public_suivre') return route.fulfill(ok({ commande: 'CMD-000001', etat: 'payee', total: 3200, don: 0, nom: 'Camille', evenement: { ref: 'EVT-000001', nom: "Soirée d'hiver", date: '2026-12-12', portes: '19:30', debut: '20:00', lieu: 'Salle des fêtes', adresse: '1 place' },
      billets: [{ numero: 'A-0001', nom: 'Camille', etat: 'valide', qr: 'CASS1.A-0001.ABCDEF', code_controle: 'A-0001-ABCDEF' }, { numero: 'A-0002', nom: 'Camille', etat: 'valide', qr: 'CASS1.A-0002.GHJKLM', code_controle: 'A-0002-GHJKLM' }] }));
    if (cap === 'public_billets_pdf') return route.fulfill(ok({ nom: 'billets-CMD-000001.pdf', pdf: Buffer.from('%PDF-1.4 essai').toString('base64'), billets: 2 }));
    return route.fulfill(echec('capacité non simulée : ' + cap));
  });

  await page.goto('/boutique.html?r=lea-0001');
  await expect(page.locator('a.evt')).toHaveCount(1);                                    // l'événement terminé n'est pas proposé
  await expect(page.locator('a.evt')).toContainText("Soirée d'hiver");
  await page.locator('a.evt').click();
  await expect(page.locator('h1')).toHaveText("Soirée d'hiver");
  await expect(page.locator('#achat')).toContainText('Code revendeur appliqué');

  await page.locator('[data-plus="TYP-000001"]').click();
  await page.locator('[data-plus="TYP-000001"]').click();
  await expect(page.locator('#total')).toHaveText(/32,00/);                              // 2 x 15 € + 2 € de frais d'achat sans compte
  await page.fill('input[name=don]', '5');
  await expect(page.locator('#total')).toHaveText(/37,00/);
  const panier = appels.filter((a) => a[0] === 'public_panier').pop()[1];
  expect(panier.lignes).toEqual([{ type: 'TYP-000001', quantite: 2 }]);
  expect(panier.session).toBe('');                                                       // sans compte : jamais « sans_compte » envoyé par l'écran, c'est la session qui décide

  await page.fill('input[name=nom]', 'Camille Test');
  await page.fill('input[name=mail]', 'refuse@exemple.org');
  await page.locator('#valider').click();
  await expect(page.locator('#msg')).toContainText('il ne reste que 0 place');           // un refus est dit, la page reste utilisable
  await page.fill('input[name=mail]', 'camille@exemple.org');
  await page.locator('#valider').click();
  await expect(page).toHaveURL(/#\/c\/CMD-000001\?s=jeton-suivi/);
  const cmd = appels.filter((a) => a[0] === 'public_commander').pop()[1];
  expect(cmd).toMatchObject({ evenement: 'EVT-000001', moyen: 'virement', code_revendeur: 'LEA-0001', don: 500, nom: 'Camille Test', mail: 'camille@exemple.org' });

  await expect(page.locator('.ticket')).toHaveCount(2);
  await expect(page.locator('.ticket svg').first()).toBeVisible();
  await expect(page.locator('.ticket').first()).toContainText('A-0001-ABCDEF');
  const [dl] = await Promise.all([page.waitForEvent('download'), page.locator('#pdf').click()]);
  expect(dl.suggestedFilename()).toBe('billets-CMD-000001.pdf');
});

test("Boutique : l'espace client demande un lien de connexion, sans mot de passe", async ({ page }) => {
  const appels = [];
  await page.route('**/api/public/billetterie.*', async (route) => {
    const cap = route.request().url().split('billetterie.')[1];
    appels.push([cap, (JSON.parse(route.request().postData() || '{}')).args || {}]);
    if (cap === 'public_calendrier') return route.fulfill(ok({ organisateur: 'Maison Bohème', evenements: [] }));
    if (cap === 'public_compte_lien') return route.fulfill(ok({ ok: true }));
    return route.fulfill(echec('capacité non simulée : ' + cap));
  });
  await page.goto('/boutique.html#/compte');
  await expect(page.locator('h1')).toHaveText('Mon espace');
  await expect(page.locator('input[type=password]')).toHaveCount(0);
  await page.fill('input[name=mail]', 'sophie@exemple.org');
  await page.locator('#lien button[type=submit]').click();
  await expect(page.locator('#lien')).toContainText('lien de connexion');
  expect(appels.filter((a) => a[0] === 'public_compte_lien')[0][1]).toEqual({ mail: 'sophie@exemple.org' });
});

test("Boutique : un événement complet propose la liste d'attente", async ({ page }) => {
  await page.route('**/api/public/billetterie.*', async (route) => {
    const cap = route.request().url().split('billetterie.')[1];
    if (cap === 'public_evenement') return route.fulfill(ok(Object.assign({}, EVENEMENT, { evenement: Object.assign({}, EVENEMENT.evenement, { etat: 'complet' }), billets: EVENEMENT.billets.map((b) => Object.assign({}, b, { etat: 'épuisé' })) })));
    if (cap === 'public_attente_inscrire') return route.fulfill(ok({ attente: 'ATT-000001', suivi: 'jeton-attente', rang: 3 }));
    if (cap === 'public_attente_suivre') return route.fulfill(ok({ attente: 'ATT-000001', etat: 'attente', evenement: { ref: 'EVT-000001', nom: "Soirée d'hiver", date: '2026-12-12' }, places: 2, rang: 3 }));
    return route.fulfill(echec('capacité non simulée : ' + cap));
  });
  await page.goto('/boutique.html#/e/EVT-000001');
  await expect(page.locator('#achat')).toContainText("Il n’y a plus de place");
  await page.fill('#attente input[name=nom]', 'Alix');
  await page.fill('#attente input[name=mail]', 'alix@exemple.org');
  await page.selectOption('#attente select[name=quantite]', '2');
  await page.locator('#attente button[type=submit]').click();
  await expect(page).toHaveURL(/#\/a\/jeton-attente/);
  await expect(page.locator('#app')).toContainText('n° 3');
});
