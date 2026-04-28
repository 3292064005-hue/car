import { expect, test } from '@playwright/test';

const liveBridgeTest = process.env.PLAYWRIGHT_LIVE_BRIDGE === '1' ? test : test.skip;

liveBridgeTest('dashboard connects to the live operator API facade and accepts a mode command', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('巡检机器人控制台')).toBeVisible();
  await expect(page.getByText('连接状态')).toBeVisible();
  await expect(page.getByText('Bridge 在线')).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText('传输类型')).toBeVisible();
  await expect(page.getByText('websocket')).toBeVisible();
  await expect(page.getByText('api_facade')).toBeVisible();
  await expect(page.getByText('authoritative_operator')).toBeVisible();
  await page.getByRole('button', { name: 'MANUAL' }).click();
  await expect(page.getByText('命令队列')).toBeVisible();
  await expect(page.getByText('set_mode')).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText('ack')).toBeVisible({ timeout: 10_000 });
});

liveBridgeTest('dashboard applies runtime-parameter draft through the live operator transaction path', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('Bridge 在线')).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText('运行参数')).toBeVisible();

  const speedInput = page.getByLabel('最大线速度');
  await speedInput.fill('0.62');
  await page.getByRole('button', { name: '应用草稿' }).click();

  await expect(page.getByText('apply_param_draft')).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText('runtime parameter apply confirmed by all consumers')).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText('projectionState: committed')).toBeVisible({ timeout: 10_000 });
});
