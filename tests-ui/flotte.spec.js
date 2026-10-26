// L'écran Flotte : le verdict et les machines à l'ouverture, la fiche (courbes, diagnostic, lien), la disponibilité, les événements, le registre et l'engagement.
const { test, expect } = require('@playwright/test');

test("Flotte : verdict, fiche, disponibilité, événements, registre et engagement", async ({ page }) => {
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.evaluate(async () => {
    window.__appels = [];
    const src = { registre: { etat: 'ok', texte: 'ssh' }, tailscale: { etat: 'ok', texte: 'en ligne' } };
    const parc = { hote: 'orion', releve: '2026-10-26 21:00:00', presence: { active: true, periode_s: 300 },
      compte: { declarees: 2, tailscale: 2, disparues: 0, en_ligne: 1, attendues_hors_ligne: 1, ssh: 2, volontaires: 0, mesurees: 2 },
      machines: [
        { nom: 'orion', os: 'linux', ip: '100.1.1.1', hote: true, en_ligne: true, etat: 'ok', libelle: 'en ligne', statut: 'attendue', niveau: 'agent', groupe: 'Serveurs', sources: src, dispo: 100, dernier_contact: 'maintenant', disparue: false },
        { nom: 'athena', os: 'linux', ip: '100.1.1.2', hote: false, en_ligne: false, etat: 'erreur', libelle: 'hors ligne · panne', statut: 'attendue', niveau: 'ssh', groupe: 'Serveurs', sources: src, dispo: 97.5, dernier_contact: '2026-10-26 20:00:00', disparue: false },
      ] };
    let reg = [{ nom: 'athena', type: 'ssh', hote: 'athena', utilisateur: 'root', auth: 'cle', actif: 1, secrets_poses: ['cle'] }];
    window.CASS.agir = async (c, a) => {
      window.__appels.push([c, a]);
      if (c === 'flotte.parc') return parc;
      if (c === 'flotte.verdict') return { niveau: 'panne', titre: 'athena est attendue et ne répond plus.', sous_titre: 'Le reste du parc répond.', lignes: [{ niveau: 'panne', machine: 'athena', titre: 'athena est attendue et ne répond plus', detail: 'Dernier contact 20:00', gestes: [{ lib: 'Ouvrir la fiche', f: 'machine', a: 'athena' }, { lib: 'Éteindre l’alerte (absence volontaire)', f: 'intermittente', a: 'athena' }] }], compte: parc.compte };
      if (c === 'flotte.actions') return { actions: [{ cle: 'diagnostic', modifie: false, description: 'Charge et disques' }, { cle: 'svc_restart', modifie: true, description: 'redémarre' }] };
      if (c === 'flotte.historique') return { nom: a.nom, heures: a.heures, disponibilite: 97.5, points: [{ ts: '2026-10-26 18:00:00', cpu: 10, ram: 40, disque: 60 }, { ts: '2026-10-26 19:00:00', cpu: 30, ram: 45, disque: 60 }], evenements: [{ ts: '2026-10-26 20:00:00', genre: 'perte', detail: 'ne répond plus' }], liens: [{ genre: 'project', ref: 'p1', note: '' }], releves_detail: [{ cle: 'disque./', valeur: '60 %', gravite: 'info' }] };
      if (c === 'flotte.diagnostic') return { sortie: 'load average: 0.1' };
      if (c === 'flotte.disponibilite') return { jours: a.jours, machines: [{ nom: 'athena', disponibilite: 97.5, pannes: 2, indispo: '1 h', releves: 100 }] };
      if (c === 'flotte.evenements') return { evenements: [{ ts: '2026-10-26 20:00:00', nom: 'athena', genre: 'perte', detail: 'ne répond plus', duree_min: 0 }] };
      if (c === 'flotte.machines') return { machines: reg };
      if (c === 'flotte.machine_ajouter') { reg = reg.concat([{ nom: a.nom, type: a.type, hote: a.hote, utilisateur: 'root', auth: a.auth, actif: 1, secrets_poses: [] }]); return {}; }
      return {};
    };
    const hote = document.createElement('div'); hote.id = 'f-essai'; hote.style.cssText = 'position:relative;z-index:1;background:var(--bg,#fff);padding:12px'; document.body.prepend(hote);
    await window.CASS.sceneSurMesure.flotte(hote, { ecran: 'flotte:vue_flotte' });
  });
  const k = page.locator('#f-essai .kit');
  const appels = (c) => page.evaluate((c) => window.__appels.filter((a) => a[0] === c).map((a) => a[1]), c);
  await expect(k.locator('.onglets button')).toHaveText(['Maintenant', 'Disponibilité', 'Événements', 'Registre et engagement']);
  await expect(k).toContainText('athena est attendue et ne répond plus.');
  await expect(k).toContainText('hors ligne · panne');

  await k.locator('[data-a="vg"][data-f="intermittente"]').click();
  await expect.poll(async () => (await appels('flotte.engagement')).pop()).toEqual({ nom: 'athena', statut: 'intermittente' });

  await k.locator('[data-a="fiche"][data-k="athena"]').first().click();
  await expect(k.locator('svg.courbe')).toBeVisible();
  await expect(k.locator('[data-a="diag"]')).toHaveCount(1);                                 // la commande qui modifie n'est pas offerte ici
  await k.locator('[data-a="diag"][data-c="diagnostic"]').click();
  await expect(k).toContainText('load average');
  await k.locator('#fl-ref').fill('p2'); await k.locator('[data-a="lien"]').click();
  await expect.poll(async () => (await appels('flotte.lien_enregistrer')).pop()).toEqual({ nom: 'athena', genre: 'project', ref: 'p2' });
  await k.locator('[data-a="retour"]').click();

  await k.locator('[data-s="dispo"]').click();
  await expect(k).toContainText('97.5 %');
  await k.locator('[data-a="jours"][data-j="90"]').click();
  await expect.poll(async () => (await appels('flotte.disponibilite')).pop()).toEqual({ jours: 90 });

  await k.locator('[data-s="evenements"]').click();
  await expect(k).toContainText('ne répond plus');

  await k.locator('[data-s="registre"]').click();
  await expect(k).toContainText('secrets : cle');
  await k.locator('#fl-nom').fill('rosco'); await k.locator('#fl-hote').fill('rosco.lan'); await k.locator('[data-a="declarer"]').click();
  await expect(k.locator('.li').filter({ hasText: 'rosco' }).first()).toBeVisible();
  await k.locator('select[data-a="statut:athena"]').selectOption('retiree');
  await expect.poll(async () => (await appels('flotte.engagement')).pop()).toEqual({ nom: 'athena', statut: 'retiree' });
});
