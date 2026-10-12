import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:10002',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'desktop',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 },
        launchOptions: {
          executablePath:
            process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ||
            'C:\\Users\\xixixiaozi\\AppData\\Local\\Temp\\opencode\\chrome\\chrome-win64\\chrome.exe',
        },
      },
    },
    {
      name: 'mobile',
      use: {
        ...devices['Pixel 5'],
        viewport: { width: 390, height: 844 },
        launchOptions: {
          executablePath:
            process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ||
            'C:\\Users\\xixixiaozi\\AppData\\Local\\Temp\\opencode\\chrome\\chrome-win64\\chrome.exe',
        },
      },
    },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:10002',
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
})

