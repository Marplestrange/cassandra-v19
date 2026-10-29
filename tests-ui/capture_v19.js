// Outil de développement : prend les captures d'écran du README de la V19 dans le serveur d'essai déjà lancé (python tests-ui/serveur_dev.py, données fictives).
// Usage : node capture_v19.js <dossier de sortie>
const { chromium } = require('@playwright/test');
const dossier = process.argv[2];
if (!dossier) { console.error('Usage : node capture_v19.js <dossier>'); process.exit(1); }
(async () => {
  const nav = await chromium.launch();
  const page = await nav.newPage({ viewport: { width: 1440, height: 860 } });
  await page.goto('http://127.0.0.1:9005/');
  await page.evaluate(() => { try { localStorage.setItem('cn.societe', '1'); } catch (e) { /* sans mémoire locale */ } });
  if (await page.locator('#login-modal').isVisible({ timeout: 3000 }).catch(() => false)) {
    await page.fill('#login-username', 'ui@exemple.test');
    await page.fill('#login-password', 'Essai-UI-2026!');
    await page.click('#login-go');
    await page.waitForSelector('#login-modal', { state: 'hidden', timeout: 15000 });
  }
  await page.waitForSelector('body.d19', { timeout: 30000 });
  await page.waitForTimeout(5000);
  const photo = async (nom) => { await page.waitForTimeout(2500); await page.screenshot({ path: `${dossier}/CN_capture-${nom}.png` }); console.log('ok', nom); };
  const sous = async (libelle) => { await page.evaluate((l) => { const b = [...document.querySelectorAll('#d19-side .sub')].find((x) => x.textContent.trim() === l); if (b) b.click(); }, libelle); };

  const attendre = async () => { await page.waitForTimeout(1500); for (let i = 0; i < 40; i++) { const charge = await page.evaluate(() => /Chargement/.test(document.body.innerText)); if (!charge) break; await page.waitForTimeout(500); } };
  await photo('bureau');                                                     // le Desk : Aujourd'hui

  await page.evaluate(() => window.ouvrirMonCoffre());                       // Paramètres : Société / Organisation
  await page.waitForTimeout(2500);
  await page.evaluate(() => { const b = [...document.querySelectorAll('#d19-side button')].find((x) => x.textContent.trim().startsWith('Société / Organisation')); if (b && ![...document.querySelectorAll('#d19-side .sub')].some((x) => x.textContent.trim() === 'Modules')) b.click(); });
  await page.waitForTimeout(1500);
  await page.evaluate(async () => {                                         // des partages d'exemple, pour que la page ne soit pas vide
    for (const t of ['utilisateurs', 'contacts', 'modeles']) { try { await CASS.agir('societes.partager', { source: '1', destinataire: 'lumen-formation', type: t, mode: 'tous' }); } catch (e) { /* déjà fait */ } }
  });
  for (const [libelle, nom] of [['Identité', 'societe'], ['Fonctions et droits', 'fonctions'], ['Partages', 'partages'], ['Modules', 'modules-societe']]) {
    await sous(libelle);
    await attendre();
    await photo(nom);
  }

  // les mêmes écrans en mode sombre et sur un téléphone (l'interface s'adapte, on le montre)
  const variante = async (options, nom, sombre) => {
    const ctx = await nav.newContext(options);
    const pg = await ctx.newPage();
    await pg.goto('http://127.0.0.1:9005/');
    await pg.evaluate(() => { try { localStorage.setItem('cn.societe', '1'); } catch (e) { /* sans mémoire locale */ } });
    if (await pg.locator('#login-modal').isVisible({ timeout: 3000 }).catch(() => false)) {
      await pg.fill('#login-username', 'ui@exemple.test');
      await pg.fill('#login-password', 'Essai-UI-2026!');
      await pg.click('#login-go');
      await pg.waitForSelector('#login-modal', { state: 'hidden', timeout: 15000 });
    }
    await pg.waitForSelector('body.d19', { timeout: 30000 });
    await pg.waitForSelector('#d19-side button, #d19-bas button', { timeout: 20000 }).catch(() => {});
    await pg.waitForTimeout(6000);
    if (sombre) { for (let i = 0; i < 3 && (await pg.evaluate(() => document.documentElement.getAttribute('data-theme'))) !== 'dark'; i++) { await pg.click('#theme-btn'); await pg.waitForTimeout(1500); } }
    await pg.screenshot({ path: `${dossier}/CN_capture-${nom}.png` });
    console.log('ok', nom);
    await ctx.close();
  };
  await variante({ viewport: { width: 1440, height: 860 }, colorScheme: 'dark' }, 'bureau-sombre', true);
  await variante({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true }, 'bureau-telephone');
  await nav.close();
})();
