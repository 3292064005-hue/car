#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'ros2_ws' / 'src'
for pkg in ROOT.iterdir():
    if pkg.is_dir():
        sys.path.insert(0, str(pkg))

from robot_contracts.capability_registry import capability_registry_payload
from robot_contracts.feature_admission import feature_admission_payload
from robot_contracts.lane_registry import lane_registry_payload
from robot_contracts.signal_ownership import governance_signal_registry_payload
from robot_contracts.command_route_registry import command_route_registry_payload
from robot_contracts.command_interface_manifest import command_interface_manifest_payload
from robot_contracts.surface_registry import surface_registry_payload
from robot_contracts.runtime_orchestration_registry import runtime_orchestration_registry_payload
from robot_contracts.navigation_adapter_boundary_registry import navigation_adapter_boundary_registry_payload
from robot_contracts.release_gate_registry import release_gate_registry_payload
from robot_bringup.launch_profiles import get_launch_profile, supported_profiles
from robot_bringup.matrix_contracts import profile_feature_matrix, startup_sequence_for_profile, surface_contract_for_profile


def _profile_registry_payload() -> dict[str, dict[str, object]]:
    payload: dict[str, dict[str, object]] = {}
    for profile_name in supported_profiles():
        profile = get_launch_profile(profile_name)
        payload[profile_name] = {
            'profileName': profile_name,
            'profile': profile.to_dict(),
            'startupSequence': list(startup_sequence_for_profile(profile)),
            'capabilityMatrix': profile_feature_matrix(profile),
            'surfaceContract': surface_contract_for_profile(profile),
        }
    return payload



def build_artifacts() -> tuple[str, str]:
    capability_registry = capability_registry_payload()
    lane_registry = lane_registry_payload(include_experimental=True)
    signal_registry = governance_signal_registry_payload()
    feature_registry = feature_admission_payload()
    command_route_registry = command_route_registry_payload()
    command_interface_manifest = command_interface_manifest_payload()
    surface_registry = surface_registry_payload()
    runtime_orchestration_registry = runtime_orchestration_registry_payload()
    navigation_adapter_boundary_registry = navigation_adapter_boundary_registry_payload()
    release_gate_registry = release_gate_registry_payload()
    profile_registry = _profile_registry_payload()
    payload = {
        'capabilityRegistry': capability_registry,
        'laneRegistry': lane_registry,
        'signalRegistry': signal_registry,
        'featureAdmissionRegistry': feature_registry,
        'commandRouteRegistry': command_route_registry,
        'commandInterfaceManifest': command_interface_manifest,
        'surfaceRegistry': surface_registry,
        'runtimeOrchestrationRegistry': runtime_orchestration_registry,
        'navigationAdapterBoundaryRegistry': navigation_adapter_boundary_registry,
        'releaseGateRegistry': release_gate_registry,
        'profileRegistry': profile_registry,
    }
    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    ts_text = textwrap.dedent(
        f"""
        import {{ z }} from 'zod';

        export const capabilityRegistry = {json.dumps(capability_registry, ensure_ascii=False, indent=2)} as const;
        export const laneRegistry = {json.dumps(lane_registry, ensure_ascii=False, indent=2)} as const;
        export const signalRegistry = {json.dumps(signal_registry, ensure_ascii=False, indent=2)} as const;
        export const featureAdmissionRegistry = {json.dumps(feature_registry, ensure_ascii=False, indent=2)} as const;
        export const commandRouteRegistry = {json.dumps(command_route_registry, ensure_ascii=False, indent=2)} as const;
        export const surfaceRegistry = {json.dumps(surface_registry, ensure_ascii=False, indent=2)} as const;
        export const runtimeOrchestrationRegistry = {json.dumps(runtime_orchestration_registry, ensure_ascii=False, indent=2)} as const;
        export const navigationAdapterBoundaryRegistry = {json.dumps(navigation_adapter_boundary_registry, ensure_ascii=False, indent=2)} as const;
        export const releaseGateRegistry = {json.dumps(release_gate_registry, ensure_ascii=False, indent=2)} as const;
        export const profileRegistry = {json.dumps(profile_registry, ensure_ascii=False, indent=2)} as const;

        export const capabilityRegistrySchema = z.record(z.string(), z.object({{
          capabilityId: z.string(),
          title: z.string(),
          domain: z.string(),
          implementationStatus: z.string(),
          governanceStage: z.string(),
          acceptanceStage: z.string(),
          uiExposurePolicy: z.string(),
          frontendMaturity: z.string(),
          releaseNotePolicy: z.string(),
          truthSourcePaths: z.array(z.string()),
          evidenceArtifacts: z.array(z.string()),
          externalDependencies: z.array(z.string()),
          entrySurfaces: z.array(z.string()),
          runtimeClaims: z.array(z.string()),
          nonClaims: z.array(z.string()),
          operatorNotes: z.array(z.string()),
        }}));

        export const laneRegistrySchema = z.record(z.string(), z.object({{
          laneId: z.string(),
          capabilityId: z.string().nullable(),
          domain: z.string(),
          owner: z.string(),
          packageName: z.string(),
          executable: z.string(),
          childFactory: z.string(),
          activationDecision: z.string(),
          rollbackPolicy: z.string(),
          evidenceRequired: z.array(z.string()),
          upgradeCondition: z.string(),
          description: z.string(),
          visibility: z.string(),
          lifecycleStage: z.string(),
          defaultSurfaceExposure: z.string(),
          retentionCondition: z.string(),
          exitCondition: z.string(),
        }}));

        export const governanceSignalEntrySchema = z.object({{
          kind: z.string(),
          producer: z.string(),
          runtimeConsumers: z.array(z.string()).optional(),
          uiConsumers: z.array(z.string()).optional(),
          evidenceConsumers: z.array(z.string()).optional(),
          ackOwners: z.array(z.string()).optional(),
          notes: z.string().optional(),
          scope: z.string().optional(),
          evidenceLayer: z.string(),
          machineEvidenceAllowed: z.boolean(),
        }});

        export const governanceSignalRegistrySchema = z.object({{
          topics: z.record(z.string(), governanceSignalEntrySchema),
          commands: z.record(z.string(), governanceSignalEntrySchema),
          runtimeParameters: z.record(z.string(), governanceSignalEntrySchema),
          reports: z.record(z.string(), governanceSignalEntrySchema),
          validationErrors: z.array(z.string()),
        }});

        export const featureAdmissionEntrySchema = z.object({{
          featureId: z.string(),
          capabilityIds: z.array(z.string()),
          title: z.string(),
          maturity: z.string(),
          entrySurfaces: z.array(z.string()),
          commands: z.array(z.string()),
          authoritativeNodes: z.array(z.string()),
          runtimeProducers: z.array(z.string()),
          runtimeConsumers: z.array(z.string()),
          uiConsumers: z.array(z.string()),
          configPaths: z.array(z.string()),
          verificationTargets: z.array(z.string()),
          acceptanceArtifacts: z.array(z.string()),
          rollbackPaths: z.array(z.string()),
          externalDependencies: z.array(z.string()),
          nonClaims: z.array(z.string()),
          operatorNotes: z.array(z.string()),
        }});

        export const featureAdmissionRegistrySchema = z.record(z.string(), featureAdmissionEntrySchema);

        export const commandRouteEntrySchema = z.object({{
          commandType: z.string(),
          entrySurfaces: z.array(z.string()),
          sessionPolicy: z.string(),
          dispatchTransport: z.string(),
          bridgeHandler: z.string(),
          targetNodes: z.array(z.string()),
          timeoutBudgetMs: z.number(),
          fallbackPaths: z.array(z.string()),
          denyConditions: z.array(z.string()),
          rollbackPaths: z.array(z.string()),
          allowedModes: z.array(z.string()),
          targetMode: z.string().nullable(),
          terminalLifecycleStatuses: z.array(z.string()),
          notes: z.array(z.string()),
        }});
        export const commandRouteRegistrySchema = z.record(z.string(), commandRouteEntrySchema);

        export const surfaceRegistryEntrySchema = z.object({{
          surfaceId: z.string(),
          surfaceLayers: z.array(z.string()),
          authorityModel: z.string(),
          defaultTransport: z.string(),
          writeEnabled: z.boolean(),
          machineGateAllowed: z.boolean(),
          truthSourcePaths: z.array(z.string()),
          notes: z.array(z.string()),
        }});
        export const surfaceRegistrySchema = z.record(z.string(), surfaceRegistryEntrySchema);

        export const runtimeOrchestrationEntrySchema = z.object({{
          componentId: z.string(),
          reportKey: z.string(),
          requiredForMainline: z.boolean(),
          runtimeTopics: z.array(z.string()),
          operatorVisibleFields: z.array(z.string()),
          truthSourcePaths: z.array(z.string()),
          recoveryOwner: z.string(),
          notes: z.array(z.string()),
        }});
        export const runtimeOrchestrationRegistrySchema = z.record(z.string(), runtimeOrchestrationEntrySchema);

        export const navigationAdapterBoundaryEntrySchema = z.object({{
          laneId: z.string(),
          providerName: z.string(),
          boundaryRole: z.string(),
          packageName: z.string(),
          executable: z.string(),
          adapterRuntime: z.boolean(),
          defaultMainline: z.boolean(),
          promotionChecklist: z.array(z.string()),
          rollbackBaseline: z.string(),
          nonClaims: z.array(z.string()),
          truthSourcePaths: z.array(z.string()),
        }});
        export const navigationAdapterBoundaryRegistrySchema = z.record(z.string(), navigationAdapterBoundaryEntrySchema);

        export const releaseGateEntrySchema = z.object({{
          gateId: z.string(),
          title: z.string(),
          scriptPaths: z.array(z.string()),
          stage: z.string(),
          blockingByDefault: z.boolean(),
          notes: z.array(z.string()),
        }});
        export const releaseGateRegistrySchema = z.record(z.string(), releaseGateEntrySchema);

        export const profileRegistryEntrySchema = z.object({{
          profileName: z.string(),
          profile: z.record(z.string(), z.unknown()),
          startupSequence: z.array(z.string()),
          capabilityMatrix: z.record(z.string(), z.boolean()),
          surfaceContract: z.record(z.string(), z.object({{
            enabled: z.boolean(),
            required_nodes: z.array(z.string()),
            ready_topics: z.array(z.string()),
            ready_http_urls: z.array(z.string()),
            require_operator_ready: z.boolean(),
          }})),
        }});
        export const profileRegistrySchema = z.record(z.string(), profileRegistryEntrySchema);

        export type GeneratedCapabilityRegistry = typeof capabilityRegistry;
        export type GeneratedLaneRegistry = typeof laneRegistry;
        export type GeneratedSignalRegistry = typeof signalRegistry;
        export type GeneratedFeatureAdmissionRegistry = typeof featureAdmissionRegistry;
        export type GeneratedCommandRouteRegistry = typeof commandRouteRegistry;
        export type GeneratedSurfaceRegistry = typeof surfaceRegistry;
        export type GeneratedRuntimeOrchestrationRegistry = typeof runtimeOrchestrationRegistry;
        export type GeneratedNavigationAdapterBoundaryRegistry = typeof navigationAdapterBoundaryRegistry;
        export type GeneratedReleaseGateRegistry = typeof releaseGateRegistry;
        export type GeneratedProfileRegistry = typeof profileRegistry;
        """
    ).strip() + "\n"
    return json_text, ts_text


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    out_dir = repo_root / 'robot_frontend' / 'src' / 'generated'
    out_dir.mkdir(parents=True, exist_ok=True)
    json_text, ts_text = build_artifacts()
    (out_dir / 'governanceContract.json').write_text(json_text, encoding='utf-8')
    (out_dir / 'governanceContract.ts').write_text(ts_text, encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
