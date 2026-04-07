import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'on-first-retry'
  },
  webServer: {
    command: 'VITE_ENABLE_MOCK=false npm run build && npm run preview -- --host 127.0.0.1 --port 4173',
    port: 4173,
    reuseExistingServer: !process.env.CI
  },
  projects: [
    {
      name: 'chromium',
      use: { browserName: 'chromium' }
    }
  ]
});
