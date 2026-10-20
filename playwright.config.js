
// @ts-check
const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:9005',
    trace: 'on-first-retry',
  },
  webServer: {
    command: 'set CASSANDRA_ECOUTE=127.0.0.1:9005 && python CN_main.py demarrer',
    cwd: 'C:/Users/Admin/Documents/Cassandra-V19',
    url: 'http://localhost:9005/api/sante',
    reuseExistingServer: !process.env.CI,
  },
  projects: [
    {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 5'] },
    },
  ],
});
