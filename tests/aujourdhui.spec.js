const { test, expect } = require('@playwright/test');

test.describe("Page Aujourd'hui - Glisser-déposer tactile", () => {
  test.beforeEach(async ({ page }) => {
    page.on('console', msg => console.log('BROWSER CONSOLE:', msg.type(), msg.text()));
    page.on('response', response => {
      if (response.status() >= 400) {
        console.log(`HTTP ERROR ${response.status()}: ${response.url()}`);
      }
    });

    await page.goto('/');

    const loginForm = page.locator('#login-modal');
    if (await loginForm.isVisible({ timeout: 2000 }).catch(() => false)) {
      await page.fill('#login-username', 'root@x.fr');
      await page.fill('#login-password', 'Test!2026');
      await page.click('#login-go');
      await page.waitForTimeout(2000);
    }
  });

  test('devrait permettre de créer et glisser une tâche sur la frise', async ({ page }) => {
    await page.evaluate(() => {
      if (window.CASS && window.CASS.aujourdhui) {
        window.CASS.aujourdhui.ouvrir();
      }
    });
    
    await page.waitForTimeout(2000);
    await page.waitForSelector('#aj-racine', { state: 'visible', timeout: 5000 });

    await page.fill('#aj-q', 'Tâche de test tactile');
    await page.click('#aj-f button[type="submit"]');
    
    await page.waitForTimeout(1000);

    const puce = page.locator('.aj-puce').filter({ hasText: 'Tâche de test tactile' }).first();
    await expect(puce).toBeVisible();
    const posPuce = await puce.boundingBox();
    expect(posPuce).not.toBeNull();

    const piste = page.locator('.aj-piste').first();
    await expect(piste).toBeVisible();
    const posPiste = await piste.boundingBox();
    expect(posPiste).not.toBeNull();

    // Dispatch custom touch events instead of using Playwright's mouse
    await page.evaluate(({ startX, startY, endX, endY }) => {
      const puceEl = document.querySelector('.aj-puce');
      
      const createTouch = (x, y) => new Touch({
        identifier: Date.now(),
        target: puceEl,
        clientX: x,
        clientY: y,
        pageX: x,
        pageY: y
      });

      // 1. Dispatch touchstart
      puceEl.dispatchEvent(new TouchEvent('touchstart', {
        cancelable: true,
        bubbles: true,
        touches: [createTouch(startX, startY)],
        changedTouches: [createTouch(startX, startY)]
      }));

    }, {
      startX: posPuce.x + posPuce.width / 2,
      startY: posPuce.y + posPuce.height / 2,
      endX: posPiste.x + 50,
      endY: posPiste.y + posPiste.height / 2
    });

    // 2. Wait for the 400ms long press timer in tactilePuces to expire
    await page.waitForTimeout(500);

    // 3. Dispatch touchmove and touchend
    await page.evaluate(({ startX, startY, endX, endY }) => {
      const puceEl = document.querySelector('.aj-puce');
      const createTouch = (x, y) => new Touch({
        identifier: Date.now(),
        target: puceEl,
        clientX: x,
        clientY: y,
        pageX: x,
        pageY: y
      });

      document.dispatchEvent(new TouchEvent('touchmove', {
        cancelable: true,
        bubbles: true,
        touches: [createTouch(endX, endY)],
        changedTouches: [createTouch(endX, endY)]
      }));
      
      document.dispatchEvent(new TouchEvent('touchend', {
        cancelable: true,
        bubbles: true,
        touches: [],
        changedTouches: [createTouch(endX, endY)]
      }));
    }, {
      startX: posPuce.x + posPuce.width / 2,
      startY: posPuce.y + posPuce.height / 2,
      endX: posPiste.x + 50,
      endY: posPiste.y + posPiste.height / 2
    });

    const blocSurPiste = page.locator('.aj-blk').filter({ hasText: 'Tâche de test tactile' }).first();
    await expect(blocSurPiste).toBeVisible({ timeout: 5000 });
  });
});
