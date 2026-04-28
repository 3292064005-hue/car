from __future__ import annotations

import json
from pathlib import Path
import sys
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]
ROS2_ROOT = ROOT / 'ros2_ws' / 'src'
for pkg in ROS2_ROOT.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_contracts.bridge_contract import (  # type: ignore
    BRIDGE_CAPABILITIES,
    COMMAND_LIFECYCLE_PHASES,
    COMMAND_TYPES,
    COMPATIBILITY_MODES,
    INBOUND_EVENT_TYPES,
    PROTOCOL_VERSION,
    RUNTIME_PARAM_BACKEND_AUTHORITATIVE_KEYS,
    RUNTIME_PARAM_FRONTEND_LOCAL_KEYS,
    RUNTIME_PARAM_SCOPE_BACKEND_AUTHORITATIVE,
    RUNTIME_PARAM_SCOPE_FRONTEND_LOCAL,
    report_surface_entries,
    report_surface_kind_list,
    report_surface_registry_payload,
    validate_report_surface_registry,
    runtime_param_field_contracts,
    SCHEMA_VERSION,
    TCP_PROTOCOL_VERSION,
    UART_PROTOCOL_VERSION,
)
from robot_contracts.capabilities import (  # type: ignore
    DEPRECATED_BRIDGE_CAPABILITY_ALIASES,
    canonical_bridge_capabilities,
)
from robot_utils.mode_catalog import MODE_SEQUENCE, MODE_TRANSITION_TARGETS  # type: ignore
from robot_contracts.product_interface_contract import product_interface_contract  # type: ignore
from robot_decision.mission_catalog import mission_catalog_payload  # type: ignore

GENERATED_DIR = ROOT / 'robot_frontend' / 'src' / 'generated'
TS_PATH = GENERATED_DIR / 'bridgeContract.ts'
JSON_PATH = GENERATED_DIR / 'bridgeContract.json'
MODE_TRANSITIONS_JSON_PATH = GENERATED_DIR / 'modeTransitions.json'
MODE_TRANSITIONS_TS_PATH = GENERATED_DIR / 'modeTransitions.ts'
REPORT_SURFACE_CONTRACT_JSON_PATH = GENERATED_DIR / 'reportSurfaceContract.json'
REPORT_SURFACE_CONTRACT_TS_PATH = GENERATED_DIR / 'reportSurfaceContract.ts'
PRODUCT_INTERFACE_JSON_PATH = GENERATED_DIR / 'productInterface.json'
PRODUCT_INTERFACE_TS_PATH = GENERATED_DIR / 'productInterface.ts'
MISSION_CATALOG_JSON_PATH = GENERATED_DIR / 'missionCatalog.json'
MISSION_CATALOG_TS_PATH = GENERATED_DIR / 'missionCatalog.ts'


def _quoted_list(items: list[str] | tuple[str, ...]) -> str:
    return json.dumps(list(items), ensure_ascii=False)


def _pascal_from_report_key(report_key: str) -> str:
    return str(report_key[:1]).upper() + str(report_key[1:])


def _report_surface_schema_symbols() -> list[dict[str, str]]:
    symbols: list[dict[str, str]] = []
    for entry in report_surface_entries():
        stem = _pascal_from_report_key(entry.report_key)
        symbols.append({
            'reportKey': entry.report_key,
            'kind': entry.kind,
            'detailSchema': f'report{stem}DetailsSchema',
            'entrySchema': f'report{stem}EntrySchema',
        })
    return symbols


def _mode_transition_payload() -> dict[str, object]:
    return {
        'authority': 'backend_mode_catalog',
        'modes': list(MODE_SEQUENCE),
        'transitions': {mode: list(MODE_TRANSITION_TARGETS[mode]) for mode in MODE_SEQUENCE},
    }


def _render_mode_transitions_ts(payload: dict[str, object]) -> str:
    modes = list(payload['modes'])
    transitions = dict(payload['transitions'])
    return dedent(
        f"""
        import type {{ RobotMode }} from '@/types/robot';

        export const MODE_TRANSITION_AUTHORITY = {payload['authority']!r} as const;
        export const MODE_SEQUENCE = {_quoted_list(modes)} as const;
        export const MODE_TRANSITIONS: Record<RobotMode, readonly RobotMode[]> = {json.dumps(transitions, ensure_ascii=False, indent=2)} as const;

        export function locallyAllowsTransition(currentMode: RobotMode, targetMode: RobotMode): boolean {{
          return (MODE_TRANSITIONS[currentMode] ?? []).includes(targetMode);
        }}
        """
    ).strip() + "\n"


def _report_surface_contract_payload() -> dict[str, object]:
    registry_errors = validate_report_surface_registry()
    if registry_errors:
        raise RuntimeError(f'report surface registry invalid: {registry_errors}')
    return {
        'authority': 'generate_frontend_contract_artifacts',
        'reports': report_surface_registry_payload(),
    }


def _render_report_surface_contract_ts(payload: dict[str, object]) -> str:
    return dedent(
        f"""
        export const REPORT_SURFACE_CONTRACT_AUTHORITY = {payload['authority']!r} as const;
        export const REPORT_SURFACE_CONTRACT = {json.dumps(payload['reports'], ensure_ascii=False, indent=2)} as const;
        export type GeneratedReportSurfaceContractKey = keyof typeof REPORT_SURFACE_CONTRACT;
        """
    ).strip() + "\n"





def _frontend_stable_payload(payload: dict[str, object]) -> dict[str, object]:
    """Return a frontend-generated contract payload without local absolute build paths.

    Args:
        payload: Contract dictionary produced by backend registries.

    Returns:
        A shallow/deep-normalized dictionary that keeps functional contract data
        intact while replacing in-repository absolute ``catalogPath`` values with
        repo-relative paths.

    Raises:
        No exception is raised; non-dictionary nested values are preserved.

    Boundary behavior:
        Only ``catalogPath`` values inside the repository root are normalized.
        External paths remain unchanged because they identify an explicit runtime
        override outside this repository.
    """
    def normalize(value: object) -> object:
        if isinstance(value, dict):
            result: dict[str, object] = {}
            for key, nested in value.items():
                if key == 'catalogPath' and isinstance(nested, str):
                    try:
                        candidate = Path(nested).resolve()
                        result[key] = candidate.relative_to(ROOT).as_posix()
                    except Exception:
                        result[key] = nested
                else:
                    result[key] = normalize(nested)
            return result
        if isinstance(value, list):
            return [normalize(item) for item in value]
        return value

    normalized = normalize(payload)
    return normalized if isinstance(normalized, dict) else payload


def _product_interface_payload() -> dict[str, object]:
    config_root = ROOT / 'ros2_ws' / 'src' / 'robot_bringup' / 'config'
    return _frontend_stable_payload(product_interface_contract(api_prefix='/api/v1', config_root=config_root))


def _mission_catalog_payload() -> dict[str, object]:
    config_root = ROOT / 'ros2_ws' / 'src' / 'robot_bringup' / 'config'
    return _frontend_stable_payload(mission_catalog_payload(config_root))


def _render_json_constant_ts(const_name: str, payload: dict[str, object], extra_exports: str = '') -> str:
    return dedent(
        f"""
        export const {const_name} = {json.dumps(payload, ensure_ascii=False, indent=2)} as const;
        {extra_exports}
        """
    ).strip() + "\n"

def _render_generated_ts(payload: dict[str, object]) -> str:
    command_types = list(payload['commandTypes'])
    inbound_event_types = list(payload['inboundEventTypes'])
    compatibility_modes = list(payload['compatibilityModes'])
    bridge_capabilities = list(payload['bridgeCapabilities'])
    canonical_bridge_capabilities = list(payload['canonicalBridgeCapabilities'])
    deprecated_bridge_capability_aliases = dict(payload['deprecatedBridgeCapabilityAliases'])
    command_lifecycle_phases = list(payload['commandLifecyclePhases'])
    command_types_json = _quoted_list(command_types)
    command_lifecycle_phases_json = _quoted_list(command_lifecycle_phases)
    inbound_event_types_json = _quoted_list(inbound_event_types)
    compatibility_modes_json = _quoted_list(compatibility_modes)
    bridge_capabilities_json = _quoted_list(bridge_capabilities)
    canonical_bridge_capabilities_json = _quoted_list(canonical_bridge_capabilities)
    deprecated_bridge_capability_aliases_json = json.dumps(deprecated_bridge_capability_aliases, ensure_ascii=False)
    runtime_param_field_scopes_json = json.dumps(payload['runtimeParamFieldScopes'], ensure_ascii=False, indent=2)
    runtime_param_backend_authoritative_keys_json = _quoted_list(payload['runtimeParamBackendAuthoritativeKeys'])
    runtime_param_frontend_local_keys_json = _quoted_list(payload['runtimeParamFrontendLocalKeys'])
    report_kind_json = _quoted_list(report_surface_kind_list())
    report_key_json = _quoted_list([entry.report_key for entry in report_surface_entries()])
    report_kind_to_key_json = json.dumps({entry.kind: entry.report_key for entry in report_surface_entries()}, ensure_ascii=False, indent=2)
    report_key_to_kind_json = json.dumps({entry.report_key: entry.kind for entry in report_surface_entries()}, ensure_ascii=False, indent=2)
    report_schema_symbols = _report_surface_schema_symbols()
    report_entry_schema_declarations = '\n'.join(
        f"        export const {item['entrySchema']} = reportSurfaceEntryBaseSchema.extend({{\n          kind: z.literal({item['kind']!r}),\n          details: {item['detailSchema']},\n        }});"
        for item in report_schema_symbols
    )
    report_union_members = ',\n'.join(f"          {item['entrySchema']}" for item in report_schema_symbols)
    report_state_schema_lines = '\n'.join(
        f"          {item['reportKey']}: reportSurfaceEntrySchema.optional()," for item in report_schema_symbols
    )
    return dedent(
        f"""
        import {{ z }} from 'zod';

        export const WEB_PROTOCOL_VERSION = {payload['protocolVersion']!r} as const;
        export const WEB_SCHEMA_VERSION = {payload['schemaVersion']!r} as const;
        export const TRANSPORT_PROTOCOL_VERSION = {payload['transportProtocolVersion']!r} as const;
        export const UART_PROTOCOL_VERSION = {payload['uartProtocolVersion']!r} as const;
        export const PROTOCOL_VERSION = WEB_PROTOCOL_VERSION;
        export const SCHEMA_VERSION = WEB_SCHEMA_VERSION;
        export const COMPATIBILITY_MODES = {compatibility_modes_json} as const;
        export const BRIDGE_CAPABILITIES = {bridge_capabilities_json} as const;
        export const CANONICAL_BRIDGE_CAPABILITIES = {canonical_bridge_capabilities_json} as const;
        export const DEPRECATED_BRIDGE_CAPABILITY_ALIASES = {deprecated_bridge_capability_aliases_json} as const;
        export const COMMAND_TYPES = {command_types_json} as const;
        export const INBOUND_EVENT_TYPES = {inbound_event_types_json} as const;
        export const COMMAND_LIFECYCLE_PHASES = {command_lifecycle_phases_json} as const;
        export type GeneratedCommandType = typeof COMMAND_TYPES[number];
        export type GeneratedCommandLifecyclePhase = typeof COMMAND_LIFECYCLE_PHASES[number];
        export type GeneratedInboundEventType = typeof INBOUND_EVENT_TYPES[number];
        export const RUNTIME_PARAM_SCOPE_BACKEND_AUTHORITATIVE = {RUNTIME_PARAM_SCOPE_BACKEND_AUTHORITATIVE!r} as const;
        export const RUNTIME_PARAM_SCOPE_FRONTEND_LOCAL = {RUNTIME_PARAM_SCOPE_FRONTEND_LOCAL!r} as const;
        export const RUNTIME_PARAM_FIELD_SCOPES = {runtime_param_field_scopes_json} as const;
        export const RUNTIME_PARAM_BACKEND_AUTHORITATIVE_KEYS = {runtime_param_backend_authoritative_keys_json} as const;
        export const RUNTIME_PARAM_FRONTEND_LOCAL_KEYS = {runtime_param_frontend_local_keys_json} as const;
        export type GeneratedRuntimeParamFieldScope = typeof RUNTIME_PARAM_FIELD_SCOPES[keyof typeof RUNTIME_PARAM_FIELD_SCOPES];

        export const sourceSchema = z.enum(['frontend', 'bridge', 'ros2', 'esp32', 'stm32', 'mock']);
        export const robotModeSchema = z.enum(['BOOT', 'IDLE', 'MANUAL', 'PATROL', 'TRACK', 'SAFE_STOP', 'FAULT']);
        export const logLevelSchema = z.enum(['INFO', 'WARN', 'ERROR', 'CRITICAL']);
        export const logDomainSchema = z.enum(['SYSTEM', 'BRIDGE', 'CONTROL', 'VISION', 'VOICE', 'TASK', 'SAFETY', 'PARAM', 'REPLAY', 'INSPECTOR', 'REPORT']);
        export const commandAckStatusSchema = z.enum(['queued', 'ack', 'rejected', 'denied', 'timeout', 'cancelled']);
        export const commandLifecycleStatusSchema = z.enum(['queued', 'accepted', 'applied', 'completed', 'rejected', 'denied', 'timeout', 'cancelled']);
        export const commandLifecyclePhaseSchema = z.enum(COMMAND_LIFECYCLE_PHASES);
        export const commandPhaseSchema = z.enum(['idle', 'queued', 'accepted', 'running', 'completed', 'aborted', 'cancelled']);
        export const wakeStatusSchema = z.enum(['idle', 'listening', 'triggered']);
        export const compatibilityModeSchema = z.enum(COMPATIBILITY_MODES);
        export const runtimeHealthStateSchema = z.enum(['ready', 'degraded', 'unavailable']);
        export const faultLevelSchema = z.enum(['info', 'warning', 'critical']);
        export const commandSourceSchema = z.enum(['ui', 'voice', 'task', 'bridge', 'unknown']);
        export const transportTypeSchema = z.enum(['mock', 'websocket']);
        export const patrolStatusSchema = z.enum(['idle', 'running', 'paused', 'completed', 'aborted']);
        export const waypointStatusSchema = z.enum(['pending', 'running', 'done', 'failed']);
        export const runtimeTransactionStatusSchema = z.enum(['pending', 'applied', 'failed', 'timeout']);
        export const runtimeProjectionStateSchema = z.enum(['committed', 'provisional']);

        export const commandPermissionSchema = z.object({{
          allowed: z.boolean(),
          reason: z.string().optional(),
        }});

        export const paramProfileSchema = z.object({{
          maxLinearSpeed: z.number(),
          maxAngularSpeed: z.number(),
          teleopStep: z.number(),
          trackOffsetDeadband: z.number(),
          lowPowerThreshold: z.number(),
          reconnectTimeoutMs: z.number(),
        }});
        export type GeneratedParamProfile = z.infer<typeof paramProfileSchema>;
        export type GeneratedParamProfileKey = keyof GeneratedParamProfile;
        export const runtimeParamPatchSchema = paramProfileSchema.partial();

        export const runtimeParamApplyResultSchema = z.object({{
          ok: z.boolean().optional(),
          message: z.string().optional(),
          ts: z.string().optional(),
          reason: z.string().optional(),
          traceId: z.string().optional(),
          transactionId: z.string().optional(),
          state: runtimeTransactionStatusSchema.optional(),
          rollbackPerformed: z.boolean().optional(),
          authoritativeKeys: z.array(z.string()).optional(),
          ignoredFrontendLocalKeys: z.array(z.string()).optional(),
        }});
        export type GeneratedRuntimeParamApplyResult = z.infer<typeof runtimeParamApplyResultSchema>;

        export const runtimeParamConsumerStatusSchema = z.object({{
          consumer: z.string(),
          ok: z.boolean().nullable().optional(),
          message: z.string().optional(),
          state: runtimeTransactionStatusSchema.optional(),
          ts: z.string().optional(),
          traceId: z.string().optional(),
        }});
        export type GeneratedRuntimeParamConsumerStatus = z.infer<typeof runtimeParamConsumerStatusSchema>;

        export const runtimeParamTransactionStateSchema = z.object({{
          transactionId: z.string().default(''),
          ackMode: z.string().default(''),
          expectedConsumers: z.array(z.string()).default([]),
          consumerStatuses: z.record(z.string(), runtimeParamConsumerStatusSchema).default({{}}),
          deadlineTs: z.string().nullable().optional(),
          startedAt: z.string().nullable().optional(),
          completedAt: z.string().nullable().optional(),
          state: runtimeTransactionStatusSchema.optional(),
          rollbackPerformed: z.boolean().optional(),
          authoritativeKeys: z.array(z.string()).optional(),
          ignoredFrontendLocalKeys: z.array(z.string()).optional(),
        }});
        export type GeneratedRuntimeParamTransactionState = z.infer<typeof runtimeParamTransactionStateSchema>;

        export const visionEventSchema = z.object({{ id: z.string(), ts: z.string(), label: z.string() }});
        export const voiceEventSchema = z.object({{ id: z.string(), ts: z.string(), command: z.string(), confidence: z.number() }});
        export const waypointStatusItemSchema = z.object({{ id: z.string(), label: z.string(), status: waypointStatusSchema, note: z.string().optional() }});
        export const logItemSchema = z.object({{
          id: z.string().min(1),
          timestamp: z.string().min(1),
          level: logLevelSchema,
          domain: logDomainSchema,
          message: z.string().min(1),
          details: z.string().optional(),
        }});
        export type GeneratedLogItem = z.infer<typeof logItemSchema>;

        export const connectionStatePayloadSchema = z.object({{
          rosConnected: z.boolean().optional(),
          bridgeConnected: z.boolean().optional(),
          stm32Connected: z.boolean().optional(),
          videoConnected: z.boolean().optional(),
          voiceConnected: z.boolean().optional(),
          reconnecting: z.boolean().optional(),
          latencyMs: z.number().optional(),
          heartbeatAgeMs: z.number().optional(),
          lastHeartbeatAt: z.string().nullable().optional(),
          transportLabel: z.string().optional(),
          transportType: transportTypeSchema.optional(),
          reconnectAttempts: z.number().optional(),
          staleMotion: z.boolean().optional(),
          stalePower: z.boolean().optional(),
          staleVision: z.boolean().optional(),
          staleVoice: z.boolean().optional(),
          inboundRateHz: z.number().optional(),
          outboundRateHz: z.number().optional(),
          protocolVersion: z.string().optional(),
          schemaVersion: z.string().optional(),
          capabilities: z.array(z.string()).optional(),
          lastSnapshotVersion: z.string().nullable().optional(),
          lastTraceId: z.string().nullable().optional(),
          compatibilityMode: compatibilityModeSchema.optional(),
          allowedTargetModes: z.array(robotModeSchema).optional(),
          modeReasons: z.record(z.string(), z.string()).optional(),
          commandPermissions: z.record(z.string(), commandPermissionSchema).optional(),
          safeStopRecoverable: z.boolean().optional(),
          safeStopRequiresManualAck: z.boolean().optional(),
          safeStopBlockedReason: z.string().nullable().optional(),
          contractSource: z.string().optional(),
          contractAuthority: z.string().optional(),
          runtimeHealthState: runtimeHealthStateSchema.optional(),
          runtimeHealthReasons: z.array(z.string()).optional(),
          wifiTransportReady: z.boolean().optional(),
          uartBoardReady: z.boolean().optional(),
          motionHeartbeatReady: z.boolean().optional(),
          commandLinkReady: z.boolean().optional(),
          gatewayReady: z.boolean().optional(),
          gatewayReadyReasons: z.array(z.string()).optional(),
          gatewayReadyTopic: z.string().nullable().optional(),
          operatorSurfaceReady: z.boolean().optional(),
          operatorSurfaceReadyReasons: z.array(z.string()).optional(),
          operatorSurfaceReadyTopic: z.string().nullable().optional(),
          operatorReady: z.boolean().optional(),
          operatorReadyReasons: z.array(z.string()).optional(),
          operatorReadyTopic: z.string().nullable().optional(),
          surfaceId: z.string().optional(),
          surfaceLayers: z.array(z.string()).optional(),
          surfaceAuthorityModel: z.string().optional(),
          surfaceWriteEnabled: z.boolean().optional(),
          surfaceMachineGateAllowed: z.boolean().optional(),
          sessionRole: z.string().optional(),
          sessionRequestedRole: z.string().optional(),
          sessionWriteEnabled: z.boolean().optional(),
          sessionAccessReason: z.string().optional(),
          sessionId: z.string().optional(),
          sessionPolicySource: z.string().optional(),
        }});
        export type GeneratedConnectionStatePayload = z.infer<typeof connectionStatePayloadSchema>;

        export const motionStatePayloadSchema = z.object({{
          mode: robotModeSchema.optional(),
          linearVelocity: z.number().optional(),
          angularVelocity: z.number().optional(),
          leftWheelSpeed: z.number().optional(),
          rightWheelSpeed: z.number().optional(),
          odomX: z.number().optional(),
          odomY: z.number().optional(),
          odomYaw: z.number().optional(),
          isManualOverride: z.boolean().optional(),
          commandSource: commandSourceSchema.optional(),
          lastUpdateAt: z.string().nullable().optional(),
        }});
        export type GeneratedMotionStatePayload = z.infer<typeof motionStatePayloadSchema>;

        export const powerStatePayloadSchema = z.object({{
          batteryPercent: z.number().optional(),
          batteryVoltage: z.number().optional(),
          lowPowerWarning: z.boolean().optional(),
          charging: z.boolean().optional(),
          lastUpdateAt: z.string().nullable().optional(),
        }});
        export type GeneratedPowerStatePayload = z.infer<typeof powerStatePayloadSchema>;

        export const visionStatePayloadSchema = z.object({{
          streamUrl: z.string().optional(),
          targetType: z.string().nullable().optional(),
          targetOffsetX: z.number().optional(),
          targetOffsetY: z.number().optional(),
          qrcodeText: z.string().nullable().optional(),
          detectTimestamp: z.string().nullable().optional(),
          frameDrops: z.number().optional(),
          trackingReady: z.boolean().optional(),
          lastUpdateAt: z.string().nullable().optional(),
          qrcodeHistory: z.array(visionEventSchema).optional(),
        }});
        export type GeneratedVisionStatePayload = z.infer<typeof visionStatePayloadSchema>;

        export const visionQrPayloadSchema = z.object({{
          qrcodeText: z.string().nullable().optional(),
          detectTimestamp: z.string().nullable().optional(),
        }});
        export type GeneratedVisionQrPayload = z.infer<typeof visionQrPayloadSchema>;

        export const voiceStatePayloadSchema = z.object({{
          lastVoiceCommand: z.string().nullable().optional(),
          voiceConfidence: z.number().optional(),
          speaking: z.boolean().optional(),
          lastSpeakText: z.string().nullable().optional(),
          wakeStatus: wakeStatusSchema.optional(),
          lastUpdateAt: z.string().nullable().optional(),
          recentCommands: z.array(voiceEventSchema).optional(),
        }});
        export type GeneratedVoiceStatePayload = z.infer<typeof voiceStatePayloadSchema>;

        export const taskStatePayloadSchema = z.object({{
          patrolStatus: patrolStatusSchema.optional(),
          currentWaypoint: z.string().nullable().optional(),
          progress: z.number().optional(),
          totalPoints: z.number().optional(),
          completedPoints: z.number().optional(),
          trackEnabled: z.boolean().optional(),
          lastTaskEvent: z.string().nullable().optional(),
          actionName: z.string().nullable().optional(),
          actionPhase: commandPhaseSchema.optional(),
          commandId: z.string().nullable().optional(),
          commandType: z.enum(COMMAND_TYPES).optional(),
          lostTargetCount: z.number().optional(),
          currentTargetType: z.string().nullable().optional(),
          actionMessage: z.string().nullable().optional(),
          actionProgress: z.number().optional(),
          waypoints: z.array(waypointStatusItemSchema).optional(),
        }});
        export type GeneratedTaskStatePayload = z.infer<typeof taskStatePayloadSchema>;

        export const faultStatePayloadSchema = z.object({{
          level: faultLevelSchema.optional(),
          code: z.string().nullable().optional(),
          message: z.string().nullable().optional(),
          safeStopActive: z.boolean().optional(),
          estopActive: z.boolean().optional(),
          timeoutStopActive: z.boolean().optional(),
          lastUpdateAt: z.string().nullable().optional(),
        }});
        export type GeneratedFaultStatePayload = z.infer<typeof faultStatePayloadSchema>;

        export const runtimeParamMetadataSchema = z.object({{
          configDigest: z.string().optional(),
          activeProfileName: z.string().optional(),
          runtimeParamVersion: z.number().optional(),
          lastParamApplyResult: runtimeParamApplyResultSchema.nullable().optional(),
          lastTransaction: runtimeParamTransactionStateSchema.nullable().optional(),
          projectionState: runtimeProjectionStateSchema.optional(),
          committedConfigDigest: z.string().optional(),
          committedProfileName: z.string().optional(),
          committedRuntimeParamVersion: z.number().optional(),
        }});
        export type GeneratedRuntimeParamMetadata = z.infer<typeof runtimeParamMetadataSchema>;


        export const reportSeveritySchema = z.enum(['info', 'success', 'warn', 'error']);
        export const REPORT_SURFACE_KEYS = {report_key_json} as const;
        export const REPORT_SURFACE_KIND_TO_KEY = {report_kind_to_key_json} as const;
        export const REPORT_SURFACE_KEY_TO_KIND = {report_key_to_kind_json} as const;
        export const reportKindSchema = z.enum({report_kind_json});

        export const reportSelectedCommandSchema = z.object({{
          vx: z.number().nullable().optional(),
          wz: z.number().nullable().optional(),
        }});
        export const reportCandidateSchema = z.object({{
          source: z.string().nullable().optional(),
          reason: z.string().nullable().optional(),
          fresh: z.boolean().nullable().optional(),
          eligible: z.boolean().nullable().optional(),
          selected: z.boolean().optional(),
        }});
        export const reportControlSummaryDetailsSchema = z.object({{
          winner: z.string(),
          safetyReason: z.string(),
          powerReason: z.string(),
          selectedAgeSec: z.number().nullable().optional(),
          selectedCommand: reportSelectedCommandSchema.optional(),
          arbitration: z.object({{
            selectedSource: z.string().nullable().optional(),
            selectionReason: z.string().nullable().optional(),
            candidates: z.array(reportCandidateSchema).optional(),
          }}).passthrough().optional(),
          rejectedCandidates: z.array(reportCandidateSchema).optional(),
        }});
        export const reportMonitorSummaryDetailsSchema = z.object({{
          health: z.string(),
          readiness: z.string(),
          reason: z.string(),
          mode: z.string(),
          wifiOk: z.boolean(),
          bridgeOk: z.boolean(),
          cameraOk: z.boolean(),
          audioOk: z.boolean(),
          uartOk: z.boolean(),
          batteryVoltage: z.number(),
          leftRpm: z.number(),
          rightRpm: z.number(),
          controlSource: z.string(),
          lastQrcode: z.string(),
          lastVoiceCommand: z.string(),
          lastFault: z.string(),
          snapshotCount: z.number(),
          reconnectCount: z.number(),
          protocolErrors: z.number(),
          recentSummary: z.string(),
        }});
        export const reportRuntimeSupervisionLifecycleNodeSchema = z.object({{
          wrapperName: z.string().optional(),
          componentId: z.string().optional(),
          actualState: z.string().optional(),
          desiredState: z.string().optional(),
          bondState: z.string().optional(),
          optional: z.boolean().optional(),
          lastError: z.string().nullable().optional(),
        }}).passthrough();
        export const reportRuntimeSupervisionBondNodeSchema = z.object({{
          wrapperName: z.string().optional(),
          componentId: z.string().optional(),
          bondState: z.string().optional(),
        }}).passthrough();
        export const reportRuntimeSupervisionLifecycleSchema = z.object({{
          present: z.boolean().optional(),
          type: z.string().optional(),
          state: z.string().optional(),
          managedNodes: z.array(reportRuntimeSupervisionLifecycleNodeSchema).optional(),
          recentTransitions: z.array(z.object({{
            subject: z.string().optional(),
            fromState: z.string().optional(),
            toState: z.string().optional(),
            reason: z.string().optional(),
            ts: z.union([z.string(), z.number()]).optional(),
          }}).passthrough()).optional(),
        }}).passthrough();
        export const reportRuntimeSupervisionBondSchema = z.object({{
          present: z.boolean().optional(),
          type: z.string().optional(),
          state: z.string().optional(),
          managedNodes: z.array(reportRuntimeSupervisionBondNodeSchema).optional(),
        }}).passthrough();
        export const reportRuntimeSupervisionRecoveryPlanSchema = z.object({{
          strategy: z.string().nullable().optional(),
          reason: z.string().nullable().optional(),
          targetNodes: z.array(z.string()).optional(),
        }}).passthrough();
        export const reportMonitorDiagnosticsDetailsSchema = z.object({{
          componentStatusCount: z.number(),
          unhealthyCount: z.number(),
          unhealthyComponents: z.array(z.string()),
          systemStatus: z.object({{
            name: z.string(),
            level: z.string(),
            message: z.string(),
          }}),
          runtimeState: z.string(),
          runtimeReasons: z.array(z.string()),
        }});
        export const reportLocalizationPoseSchema = z.object({{
          x: z.number().optional(),
          y: z.number().optional(),
          yaw: z.number().optional(),
        }}).passthrough();
        export const reportLocalizationSummaryDetailsSchema = z.object({{
          feedbackAvailable: z.boolean(),
          stale: z.boolean(),
          pose: reportLocalizationPoseSchema.optional(),
          robotName: z.string().nullable().optional(),
          descriptionLoaded: z.boolean().nullable().optional(),
        }});
        export const reportHardwareInterfaceSummaryDetailsSchema = z.object({{
          jointStateAvailable: z.boolean(),
          batteryStateAvailable: z.boolean(),
          cmdObserved: z.boolean(),
          batteryPercent: z.number().nullable().optional(),
          batteryVoltage: z.number().nullable().optional(),
          missing: z.array(z.string()),
        }});
        export const reportNavigationStatusDetailsSchema = z.object({{
          routeName: z.string().nullable().optional(),
          goal: z.string().nullable().optional(),
          completedGoals: z.number(),
          totalGoals: z.number(),
          progress: z.number(),
          reason: z.string().nullable().optional(),
        }});
        export const reportVoiceIngressHealthDetailsSchema = z.object({{
          state: z.string(),
          reason: z.string().nullable().optional(),
          required: z.boolean(),
          expectedSourceId: z.string().nullable().optional(),
          lastSourceId: z.string().nullable().optional(),
          lastCommand: z.string().nullable().optional(),
          lastConfidence: z.number().nullable().optional(),
          lastIngressAgeSec: z.number().nullable().optional(),
          timeoutSec: z.number().nullable().optional(),
        }});
        export const reportNavigationPathDetailsSchema = z.object({{
          poseCount: z.number().nullable().optional(),
          hasPath: z.boolean().nullable().optional(),
        }}).passthrough();
        export const reportRuntimeSupervisionComponentSchema = z.object({{
          componentId: z.string(),
          requiredForMainline: z.boolean(),
          recoveryOwner: z.string(),
          runtimeTopics: z.array(z.string()),
          status: z.string(),
          missingFields: z.array(z.string()),
        }});
        export const reportRuntimeSupervisionDetailsSchema = z.object({{
          reasons: z.array(z.string()),
          startupBarrierReady: z.boolean(),
          readiness: z.string().nullable().optional(),
          recoveryMode: z.string().nullable().optional(),
          lifecycleManager: reportRuntimeSupervisionLifecycleSchema,
          bondSupervision: reportRuntimeSupervisionBondSchema,
          recoveryPlan: reportRuntimeSupervisionRecoveryPlanSchema,
          orchestrationComponents: z.record(z.string(), reportRuntimeSupervisionComponentSchema).optional(),
        }});

        export const reportSurfaceEntryBaseSchema = z.object({{
          topic: z.string().optional(),
          raw: z.string().optional(),
          parsed: z.unknown().optional(),
          updatedAt: z.string().nullable().optional(),
          severity: reportSeveritySchema.optional(),
          summary: z.string().optional(),
          status: z.string().optional(),
        }});
{report_entry_schema_declarations}
        export const reportSurfaceEntrySchema = z.discriminatedUnion('kind', [
{report_union_members}
        ]);
        export type GeneratedReportSurfaceEntry = z.infer<typeof reportSurfaceEntrySchema>;

        export const reportsStatePayloadSchema = z.object({{
{report_state_schema_lines}
        }});
        export type GeneratedReportsStatePayload = z.infer<typeof reportsStatePayloadSchema>;

        export const robotSnapshotSchema = z.object({{
          connection: connectionStatePayloadSchema.optional(),
          motion: motionStatePayloadSchema.optional(),
          power: powerStatePayloadSchema.optional(),
          vision: visionStatePayloadSchema.optional(),
          voice: voiceStatePayloadSchema.optional(),
          task: taskStatePayloadSchema.optional(),
          fault: faultStatePayloadSchema.optional(),
          reports: reportsStatePayloadSchema.optional(),
          params: paramProfileSchema.partial().optional(),
          paramMetadata: runtimeParamMetadataSchema.optional(),
          logs: z.array(logItemSchema).optional(),
        }});
        export type GeneratedRobotSnapshot = z.infer<typeof robotSnapshotSchema>;

        export const commandAckPayloadSchema = z.object({{
          commandId: z.string().min(1),
          status: commandAckStatusSchema,
          lifecycleStatus: commandLifecycleStatusSchema.optional(),
          lifecyclePhase: commandLifecyclePhaseSchema.optional(),
          message: z.string().optional(),
          detail: z.string().optional(),
        }});
        export type GeneratedCommandAckPayload = z.infer<typeof commandAckPayloadSchema>;

        export const inboundPayloadSchemas = {{
          heartbeat: connectionStatePayloadSchema,
          snapshot: robotSnapshotSchema,
          connection_state: connectionStatePayloadSchema,
          mode_state: motionStatePayloadSchema,
          chassis_state: motionStatePayloadSchema,
          power_state: powerStatePayloadSchema,
          vision_target: visionStatePayloadSchema,
          vision_qrcode: visionQrPayloadSchema,
          voice_cmd: voiceStatePayloadSchema,
          fault_event: faultStatePayloadSchema,
          system_log: logItemSchema,
          task_event: taskStatePayloadSchema,
          command_ack: commandAckPayloadSchema,
        }} as const satisfies Record<GeneratedInboundEventType, z.ZodTypeAny>;

        export type GeneratedBridgeInboundPayloadMap = {{
          heartbeat: GeneratedConnectionStatePayload;
          snapshot: GeneratedRobotSnapshot;
          connection_state: GeneratedConnectionStatePayload;
          mode_state: GeneratedMotionStatePayload;
          chassis_state: GeneratedMotionStatePayload;
          power_state: GeneratedPowerStatePayload;
          vision_target: GeneratedVisionStatePayload;
          vision_qrcode: GeneratedVisionQrPayload;
          voice_cmd: GeneratedVoiceStatePayload;
          fault_event: GeneratedFaultStatePayload;
          system_log: GeneratedLogItem;
          task_event: GeneratedTaskStatePayload;
          command_ack: GeneratedCommandAckPayload;
        }};

        export const inboundTypeSchema = z.enum(INBOUND_EVENT_TYPES);

        export const outboundPayloadSchemas = {{
          set_mode: z.object({{ mode: robotModeSchema, source: z.literal('frontend') }}),
          teleop_cmd: z.object({{ linear: z.number(), angular: z.number(), source: z.literal('frontend') }}),
          stop_now: z.object({{ source: z.literal('frontend') }}),
          estop: z.object({{ source: z.literal('frontend') }}),
          resume_from_safe_stop: z.object({{ source: z.literal('frontend') }}),
          start_patrol: z.object({{
            source: z.literal('frontend'),
            missionId: z.string().min(1).optional(),
            routeName: z.string().min(1).optional(),
            taskProfile: z.string().min(1).optional(),
          }}),
          pause_patrol: z.object({{ source: z.literal('frontend') }}),
          stop_patrol: z.object({{ source: z.literal('frontend') }}),
          apply_param_draft: z.object({{ params: runtimeParamPatchSchema.refine((value) => Object.keys(value).length > 0, 'runtime param patch must not be empty'), source: z.literal('frontend') }}),
          apply_param_profile: z.object({{ profileName: z.string(), source: z.literal('frontend') }}),
          speak_fixed_text: z.object({{ text: z.string(), source: z.literal('frontend') }}),
          reset_fault: z.object({{ source: z.literal('frontend') }}),
          save_snapshot: z.object({{ source: z.literal('frontend') }}),
        }} as const satisfies Record<GeneratedCommandType, z.ZodTypeAny>;

        export type GeneratedBridgeOutboundPayloadMap = {{
          set_mode: z.infer<typeof outboundPayloadSchemas.set_mode>;
          teleop_cmd: z.infer<typeof outboundPayloadSchemas.teleop_cmd>;
          stop_now: z.infer<typeof outboundPayloadSchemas.stop_now>;
          estop: z.infer<typeof outboundPayloadSchemas.estop>;
          resume_from_safe_stop: z.infer<typeof outboundPayloadSchemas.resume_from_safe_stop>;
          start_patrol: z.infer<typeof outboundPayloadSchemas.start_patrol>;
          pause_patrol: z.infer<typeof outboundPayloadSchemas.pause_patrol>;
          stop_patrol: z.infer<typeof outboundPayloadSchemas.stop_patrol>;
          apply_param_draft: z.infer<typeof outboundPayloadSchemas.apply_param_draft>;
          apply_param_profile: z.infer<typeof outboundPayloadSchemas.apply_param_profile>;
          speak_fixed_text: z.infer<typeof outboundPayloadSchemas.speak_fixed_text>;
          reset_fault: z.infer<typeof outboundPayloadSchemas.reset_fault>;
          save_snapshot: z.infer<typeof outboundPayloadSchemas.save_snapshot>;
        }};
        """
    ).strip() + "\n"


def main() -> int:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        'protocolVersion': PROTOCOL_VERSION,
        'schemaVersion': SCHEMA_VERSION,
        'transportProtocolVersion': str(TCP_PROTOCOL_VERSION),
        'uartProtocolVersion': str(UART_PROTOCOL_VERSION),
        'compatibilityModes': list(COMPATIBILITY_MODES),
        'bridgeCapabilities': list(BRIDGE_CAPABILITIES),
        'canonicalBridgeCapabilities': list(canonical_bridge_capabilities()),
        'deprecatedBridgeCapabilityAliases': dict(DEPRECATED_BRIDGE_CAPABILITY_ALIASES),
        'commandTypes': list(COMMAND_TYPES),
        'commandLifecyclePhases': list(COMMAND_LIFECYCLE_PHASES),
        'inboundEventTypes': list(INBOUND_EVENT_TYPES),
        'runtimeParamFieldScopes': {key: value['scope'] for key, value in runtime_param_field_contracts().items()},
        'runtimeParamBackendAuthoritativeKeys': list(RUNTIME_PARAM_BACKEND_AUTHORITATIVE_KEYS),
        'runtimeParamFrontendLocalKeys': list(RUNTIME_PARAM_FRONTEND_LOCAL_KEYS),
    }
    mode_payload = _mode_transition_payload()
    report_surface_contract_payload = _report_surface_contract_payload()
    product_interface_payload = _product_interface_payload()
    mission_catalog_payload_value = _mission_catalog_payload()
    JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    TS_PATH.write_text(_render_generated_ts(payload), encoding='utf-8')
    MODE_TRANSITIONS_JSON_PATH.write_text(json.dumps(mode_payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    MODE_TRANSITIONS_TS_PATH.write_text(_render_mode_transitions_ts(mode_payload), encoding='utf-8')
    REPORT_SURFACE_CONTRACT_JSON_PATH.write_text(json.dumps(report_surface_contract_payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    REPORT_SURFACE_CONTRACT_TS_PATH.write_text(_render_report_surface_contract_ts(report_surface_contract_payload), encoding='utf-8')
    PRODUCT_INTERFACE_JSON_PATH.write_text(json.dumps(product_interface_payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    PRODUCT_INTERFACE_TS_PATH.write_text(_render_json_constant_ts('PRODUCT_INTERFACE_CONTRACT', product_interface_payload, 'export type GeneratedProductInterfaceContract = typeof PRODUCT_INTERFACE_CONTRACT;'), encoding='utf-8')
    MISSION_CATALOG_JSON_PATH.write_text(json.dumps(mission_catalog_payload_value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    MISSION_CATALOG_TS_PATH.write_text(_render_json_constant_ts(
        'PRODUCT_MISSION_CATALOG',
        mission_catalog_payload_value,
        'export type GeneratedMissionCatalog = typeof PRODUCT_MISSION_CATALOG;\nexport type GeneratedMissionCatalogEntry = typeof PRODUCT_MISSION_CATALOG.missions[keyof typeof PRODUCT_MISSION_CATALOG.missions];',
    ), encoding='utf-8')
    print(json.dumps({'status': 'ok', 'ts': str(TS_PATH), 'json': str(JSON_PATH), 'modeTransitionsTs': str(MODE_TRANSITIONS_TS_PATH), 'modeTransitionsJson': str(MODE_TRANSITIONS_JSON_PATH), 'reportSurfaceContractTs': str(REPORT_SURFACE_CONTRACT_TS_PATH), 'reportSurfaceContractJson': str(REPORT_SURFACE_CONTRACT_JSON_PATH), 'productInterfaceTs': str(PRODUCT_INTERFACE_TS_PATH), 'productInterfaceJson': str(PRODUCT_INTERFACE_JSON_PATH), 'missionCatalogTs': str(MISSION_CATALOG_TS_PATH), 'missionCatalogJson': str(MISSION_CATALOG_JSON_PATH)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
