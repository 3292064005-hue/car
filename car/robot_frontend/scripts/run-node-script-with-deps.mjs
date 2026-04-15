#!/usr/bin/env node
import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = resolve(SCRIPT_DIR, '..');
const TYPESCRIPT_PACKAGE = resolve(FRONTEND_ROOT, 'node_modules', 'typescript', 'lib', 'typescript.js');

function assertFrontendDependenciesPresent() {
  if (existsSync(resolve(FRONTEND_ROOT, 'node_modules')) && existsSync(TYPESCRIPT_PACKAGE)) {
    return;
  }
  throw new Error(
    'frontend TypeScript dependencies are missing under robot_frontend/node_modules; ' +
      'run npm ci manually for local development, or use scripts/run_frontend_workspace_command.py for isolated verification',
  );
}

function main(scriptPath, args) {
  if (!scriptPath) {
    throw new Error('missing script path');
  }
  assertFrontendDependenciesPresent();
  const execution = spawnSync(process.execPath, [resolve(FRONTEND_ROOT, scriptPath), ...args], {
    cwd: FRONTEND_ROOT,
    stdio: 'inherit',
    env: process.env,
  });
  if (execution.error) throw execution.error;
  return execution.status ?? 1;
}

try {
  const [, , scriptPath, ...args] = process.argv;
  process.exitCode = main(scriptPath, args);
} catch (error) {
  console.error(`[frontend-node-runner] ${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
}
