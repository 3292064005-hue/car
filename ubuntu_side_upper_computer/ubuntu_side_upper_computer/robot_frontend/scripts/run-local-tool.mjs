#!/usr/bin/env node
import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = resolve(SCRIPT_DIR, '..');
const TOOL_BINARIES = {
  tsc: resolve(FRONTEND_ROOT, 'node_modules', 'typescript', 'bin', 'tsc'),
  vite: resolve(FRONTEND_ROOT, 'node_modules', 'vite', 'bin', 'vite.js'),
};

function ensureFrontendDependenciesInstalled() {
  const npmCommand = process.platform === 'win32' ? 'npm.cmd' : 'npm';
  const install = spawnSync(npmCommand, ['ci', '--no-audit', '--no-fund'], {
    cwd: FRONTEND_ROOT,
    stdio: 'inherit',
    env: process.env,
  });
  if (install.error) throw install.error;
  if (install.status !== 0) throw new Error(`npm ci failed with exit code ${install.status ?? 'unknown'}`);
}

function main(toolName, args) {
  if (!toolName) throw new Error('missing tool name; expected one of: tsc, vite');
  const toolBinary = TOOL_BINARIES[toolName];
  if (!toolBinary) throw new Error(`unsupported tool: ${toolName}`);
  if (!existsSync(resolve(FRONTEND_ROOT, 'node_modules')) || !existsSync(toolBinary)) {
    ensureFrontendDependenciesInstalled();
  }
  const execution = spawnSync(process.execPath, [toolBinary, ...args], {
    cwd: FRONTEND_ROOT,
    stdio: 'inherit',
    env: process.env,
  });
  if (execution.error) throw execution.error;
  return execution.status ?? 1;
}

try {
  const [, , toolName, ...args] = process.argv;
  process.exitCode = main(toolName, args);
} catch (error) {
  console.error(`[frontend-toolchain] ${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
}
