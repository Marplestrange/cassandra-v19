// L'écran Automatismes : les tâches et leurs états, la fiche (lancer, réglages), une nouvelle tâche avec aperçu, l'audit, la maintenance.
const { test, expect } = require('@playwright/test');

test("Automatismes : tâches, fiche, nouvelle tâche, audit, maintenance", async ({ page }) => {
  await page.goto('/');
  if (await page.locator('#login-modal').isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.fill('#login-username', process.env.UI_COMPTE);
    await page.fill('#login-password', process.env.UI_MDP);
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 10000 });
  }
  await page.evaluate(async () => {
    window.__appels = [];
    const t1 = { ref: 'root:sauve', utilisateur: 'root', horaire: '0 4 * * *', commande: '/root/sauve.sh', description: 'Sauvegarde', actif: 1, derniere: '2026-10-26 04:00:00', etat: 'échec', etat_detail: 'code 2', humain: 'tous les jours à 4 h', prochaine: '2026-10-27 04:00', projets: [], critique: 0, id: 5 };
    const t2 = { ref: 'root:menage', utilisateur: 'root', horaire: '*/5 * * * *', commande: '/root/menage.sh', description: 'Ménage', actif: 1, derniere: '', etat: 'ok', etat_detail: '', humain: 'toutes les 5 minutes', prochaine: '2026-10-26 22:05', projets: [], critique: 1, id: null };
    let maint = { actif: false, fin: '' };
    window.CASS.agir = async (c, a) => {
      window.__appels.push([c, a]);
      if (c === 'planifie.unifiee') return { taches: [t1, t2], compteurs: { total: 2, 'échec': 1, ok: 1 }, projets: [{ id: 3, nom: 'Infra' }], source_systeme: { ok: true, erreur: '' } };
      if (c === 'planifie.fiche') return { tache: a.ref === t1.ref ? t1 : t2, executions: [{ debut: '2026-10-26T04:00:00', duree_ms: 3200, code: 2, sortie: 'disque plein', declencheur: 'cron' }, { debut: '2026-10-25T04:00:00', duree_ms: 2900, code: 0, sortie: '', declencheur: 'cron' }], reglages: { essais: 0, fenetre_min: 0, verrou: 0 }, prochaines: ['2026-10-27 04:00'], cibles: [{ chemin: '/root/sauve.sh', present: 0 }], modifs: [], destructive: false, lourde: false, chevauche: false, derive: {} };
      if (c === 'planifie.apercu') return { expression: a.expression, humain: 'tous les jours à 4 h', prochaines: ['2026-10-27 04:00'] };
      if (c === 'planifie.audit') return { collisions: [{ at: '04:00', taches: [{ libelle: 'Sauvegarde' }, { libelle: 'Rotation' }] }], sauvegardes_manquantes: [{ id: 3, nom: 'Infra', domaine: 'exemple.fr' }] };
      if (c === 'planifie.chevauchements') return { chevauchements: [] };
      if (c === 'planifie.maintenance_etat') return maint;
      if (c === 'planifie.maintenance') { maint = a.actif ? { actif: true, fin: '2026-10-27 02:00' } : { actif: false, fin: '' }; return maint; }
      return {};
    };
    const hote = document.createElement('div'); hote.id = 'pl-essai'; hote.style.cssText = 'position:relative;z-index:1;background:var(--bg,#fff);padding:12px'; document.body.prepend(hote);
    await window.CASS.sceneSurMesure.planifie(hote, { ecran: 'planifie:vue_taches' });
  });
  const k = page.locator('#pl-essai .kit');
  const appels = (c) => page.evaluate((c) => window.__appels.filter((a) => a[0] === c).map((a) => a[1]), c);
  await expect(k.locator('.onglets button')).toHaveText(['Les tâches', 'Nouvelle tâche', 'Audit', 'Maintenance']);
  await expect(k).toContainText('Sauvegarde');
  await expect(k.locator('.li').filter({ hasText: 'Sauvegarde' })).toContainText('en échec');
  await k.locator('[data-a="filtre"][data-v="ok"]').click();
  await expect(k).not.toContainText('Sauvegarde');
  await k.locator('[data-a="filtre"][data-v=""]').click();

  await k.locator('[data-a="fiche"][data-k="root:sauve"]').click();
  await expect(k).toContainText('Cible absente : /root/sauve.sh');
  await expect(k).toContainText('disque plein');
  await k.locator('[data-a="essai"]').click();
  await expect.poll(async () => (await appels('planifie.executer')).pop()).toEqual({ ref: 'root:sauve', essai: true });
  await k.locator('#pl-essais').fill('2'); await k.locator('[data-a="reglages"]').click();
  await expect.poll(async () => (await appels('planifie.reglages_poser')).pop()).toMatchObject({ ref: 'root:sauve', essais: 2 });
  await k.locator('[data-a="retour"]').click();

  await k.locator('[data-s="nouvelle"]').click();
  await k.locator('#pl-h').fill('0 4 * * *'); await k.locator('[data-a="apercu"]').click();
  await expect(k).toContainText('tous les jours à 4 h');
  await k.locator('#pl-cmd').fill('/root/x.sh'); await k.locator('[data-a="creer"]').click();
  await expect.poll(async () => (await appels('planifie.sauver')).pop()).toMatchObject({ horaire: '0 4 * * *', commande: '/root/x.sh' });

  await k.locator('[data-s="audit"]').click();
  await expect(k).toContainText('Rotation');
  await expect(k).toContainText('rien ne la sauvegarde');

  await k.locator('[data-s="maintenance"]').click();
  await k.locator('[data-a="maint"][data-v="1"]').click();
  await expect(k).toContainText('en cours jusqu’à');
});
