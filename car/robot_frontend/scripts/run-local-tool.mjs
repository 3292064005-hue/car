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
  playwright: resolve(FRONTEND_ROOT, 'node_modules', 'playwright', 'cli.js'),
};

function assertFrontendDependenciesPresent(toolName, toolBinary) {
  if (existsSync(resolve(FRONTEND_ROOT, 'node_modules')) && existsSync(toolBinary)) {
    return;
  }
  throw new Error(
    `frontend dependencies for ${toolName} are missing under robot_frontend/node_modules; ` +
      'run npm ci manually for local development, or use scripts/run_frontend_workspace_command.py for isolated verification',
  );
}

function main(toolName, args) {
  if (!toolName) throw new Error('missing tool name; expected one of: tsc, vite, playwright');
  const toolBinary = TOOL_BINARIES[toolName];
  if (!toolBinary) throw new Error(`unsupported tool: ${toolName}`);
  assertFrontendDependenciesPresent(toolName, toolBinary);
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
