import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { evaluateReadonlyBoundary } from '../src/bridge/policyKernel.ts';

const TEST_DIR = dirname(fileURLToPath(import.meta.url));
const contract = JSON.parse(readFileSync(resolve(TEST_DIR, '../src/generated/bridgeContract.json'), 'utf-8')) as { commandTypes: string[] };

const commandTypes = contract.commandTypes;
assert.ok(Array.isArray(commandTypes) && commandTypes.length > 0, 'commandTypes must be present in generated bridge contract');

for (const commandType of commandTypes) {
  const demoDecision = evaluateReadonlyBoundary({ demoReadonly: true }, commandType);
  assert.equal(demoDecision?.level, 'hard_deny', `demo readonly must hard-deny ${commandType}`);
  assert.equal(demoDecision?.source, 'readonly', `demo readonly decision source must be readonly for ${commandType}`);

  const readonlySessionDecision = evaluateReadonlyBoundary({ demoReadonly: false, sessionWriteEnabled: false }, commandType);
  assert.equal(readonlySessionDecision?.level, 'hard_deny', `readonly session must hard-deny ${commandType}`);
  assert.equal(readonlySessionDecision?.authoritative, true, `readonly session must be authoritative for ${commandType}`);

  const observerSurfaceDecision = evaluateReadonlyBoundary({ demoReadonly: false, websocketSurfaceKind: 'bridge_observer' }, commandType);
  assert.equal(observerSurfaceDecision?.level, 'hard_deny', `observer surface must hard-deny ${commandType}`);

  const observerAuthorityDecision = evaluateReadonlyBoundary({ demoReadonly: false, websocketSurfaceAuthority: 'observer_only' }, commandType);
  assert.equal(observerAuthorityDecision?.level, 'hard_deny', `observer authority must hard-deny ${commandType}`);
}

const writableDecision = evaluateReadonlyBoundary({ demoReadonly: false, sessionWriteEnabled: true, websocketSurfaceKind: 'api_facade', websocketSurfaceAuthority: 'authoritative_operator' }, 'set_mode');
assert.equal(writableDecision, null, 'authoritative operator session must not be readonly-blocked');

console.log(JSON.stringify({ status: 'ok', commandsChecked: commandTypes.length }));
