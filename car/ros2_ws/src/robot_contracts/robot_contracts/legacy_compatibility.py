from __future__ import annotations

"""Declared retirement policy for the remaining legacy compatibility surfaces."""

from robot_contracts.contract_versions import PROTOCOL_VERSION

LEGACY_COMPATIBILITY_POLICY_VERSION = 1
LEGACY_RETIREMENT_STAGE = 'audit_enforced'
LEGACY_COMPATIBILITY_POLICY = {
    'policyVersion': LEGACY_COMPATIBILITY_POLICY_VERSION,
    'currentProtocolVersion': PROTOCOL_VERSION,
    'retirementStage': LEGACY_RETIREMENT_STAGE,
    'deprecationStartVersion': '4.0.0',
    'newCommandPolicy': 'frozen_no_legacy_only_command_routes',
    'allowedUse': 'emergency_rollback_only',
    'stageExitCriteria': {
        'motionInputAliases': 'runtime hit count == 0 across the current acceptance window',
        'ackStatusAlias': 'all supported consumers read lifecycleStatus and runtime alias emission hit count == 0 across the current acceptance window',
        'legacyRollbackPath': 'split bridge passes command semantic gate for every P0 command and target/HIL evidence path is documented',
    },
    'removedLegacyOutputs': [
        'cmd_vel.linear',
        'cmd_vel.angular',
    ],
    'remainingInputTolerances': [
        'cmd_vel.linear',
        'cmd_vel.angular',
    ],
    'remainingCompatibilityAliases': [
        'command_ack.status',
    ],
    'retirementMilestones': [
        {
            'milestone': 'freeze_new_aliases',
            'targetVersion': '4.0.0',
            'status': 'completed',
            'scope': 'no new legacy bridge fields may be added; canonical cmd_vel output uses vx/wz only',
        },
        {
            'milestone': 'remove_motion_input_tolerance',
            'targetVersion': '4.1.0',
            'status': 'in_progress',
            'scope': 'drop cmd_vel.linear/angular input tolerance after runtime usage audit reaches zero',
        },
        {
            'milestone': 'freeze_legacy_rollback_commands',
            'targetVersion': '4.0.1',
            'status': 'completed',
            'scope': 'legacy bridge may receive emergency rollback traffic but must not be the only implementation path for new commands',
        },
        {
            'milestone': 'remove_ack_status_alias',
            'targetVersion': '4.2.0',
            'status': 'planned',
            'scope': 'drop command_ack.status once lifecycleStatus is the only supported consumer path',
        },
    ],
}
