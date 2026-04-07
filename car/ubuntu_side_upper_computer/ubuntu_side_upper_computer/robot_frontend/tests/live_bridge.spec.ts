import { expect, test } from '@playwright/test';

const liveBridgeTest = process.env.PLAYWRIGHT_LIVE_BRIDGE === '1' ? test : test.skip;

liveBridgeTest('dashboard connects to live robot_web_bridge and accepts a mode command', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('巡检机器人控制台')).toBeVisible();
  await expect(page.getByText('连接状态')).toBeVisible();
  await expect(page.getByText('Bridge 在线')).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText('传输类型')).toBeVisible();
  await expect(page.getByText('websocket')).toBeVisible();
  await page.getByRole('button', { name: 'MANUAL' }).click();
  await expect(page.getByText('命令队列')).toBeVisible();
  await expect(page.getByText('set_mode')).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText('ack')).toBeVisible({ timeout: 10_000 });
});
