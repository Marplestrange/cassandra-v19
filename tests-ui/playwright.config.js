// Tests d'interface (Playwright). Un serveur de test ISOLÉ est lancé à chaque suite (voir preparer_serveur.py) : données jetables, port d'essai.
// Rien ici ne touche à l'instance de développement ni à ses données.
const path = require('path');
const { defineConfig, devices } = require('@playwright/test');

const PORT = process.env.UI_PORT || '9005';
process.env.UI_COMPTE = process.env.UI_COMPTE || 'ui@exemple.test';
process.env.UI_MDP = process.env.UI_MDP || 'Essai-UI-2026!';

module.exports = defineConfig({
  testDir: __dirname,
  testMatch: '**/*.spec.js',
  fullyParallel: false,
  workers: 1,                                  // un seul serveur, un seul compte : les essais se suivent
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: [['list']],
  outputDir: path.join(__dirname, '.resultats'),
  use: { baseURL: `http://127.0.0.1:${PORT}`, trace: 'on-first-retry' },
  webServer: {
    command: `python ${JSON.stringify(path.join(__dirname, 'preparer_serveur.py'))}`,
    cwd: path.resolve(__dirname, '..'),
    url: `http://127.0.0.1:${PORT}/api/sante`,
    reuseExistingServer: false,
    timeout: 180000,
    env: { UI_PORT: PORT, UI_COMPTE: process.env.UI_COMPTE, UI_MDP: process.env.UI_MDP, PYTHONIOENCODING: 'utf-8' },
  },
  projects: [{ name: 'Mobile Chrome', use: { ...devices['Pixel 5'] } }],
});
