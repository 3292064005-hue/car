#!/usr/bin/env node
import { spawnSync } from 'node:child_process';

const candidates = [];

if (process.env.PYTHON) {
  candidates.push({ command: process.env.PYTHON, args: [] });
}

if (process.platform === 'win32') {
  candidates.push(
    { command: 'py', args: ['-3'] },
    { command: 'python', args: [] },
    { command: 'python3', args: [] },
  );
} else {
  candidates.push(
    { command: 'python3', args: [] },
    { command: 'python', args: [] },
  );
}

function findPython() {
  for (const candidate of candidates) {
    const probe = spawnSync(candidate.command, [...candidate.args, '--version'], {
      encoding: 'utf8',
      stdio: 'pipe',
    });
    if (!probe.error && probe.status === 0) {
      return candidate;
    }
  }
  return null;
}

function main(args) {
  if (args.length === 0) {
    throw new Error('missing Python script or module arguments');
  }
  const python = findPython();
  if (!python) {
    throw new Error('unable to find a working Python 3 interpreter; set PYTHON to an explicit executable');
  }
  const execution = spawnSync(python.command, [...python.args, ...args], {
    cwd: process.cwd(),
    stdio: 'inherit',
    env: process.env,
  });
  if (execution.error) throw execution.error;
  return execution.status ?? 1;
}

try {
  process.exitCode = main(process.argv.slice(2));
} catch (error) {
  console.error(`[frontend-python-runner] ${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
}
