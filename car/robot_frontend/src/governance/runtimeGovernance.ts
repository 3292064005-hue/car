import { capabilityRegistry, commandRouteRegistry, featureAdmissionRegistry, laneRegistry, navigationAdapterBoundaryRegistry, profileRegistry, releaseGateRegistry, runtimeOrchestrationRegistry, surfaceRegistry } from '@/generated/governanceContract';

export type GovernanceTone = 'neutral' | 'success' | 'warning' | 'danger';
export type CapabilityId = keyof typeof capabilityRegistry;
export type FeatureId = keyof typeof featureAdmissionRegistry;
export type LaneId = keyof typeof laneRegistry;

export type CommandRouteId = keyof typeof commandRouteRegistry;
export type SurfaceId = keyof typeof surfaceRegistry;
export type RuntimeOrchestrationId = keyof typeof runtimeOrchestrationRegistry;
export type NavigationAdapterBoundaryId = keyof typeof navigationAdapterBoundaryRegistry;
export type ReleaseGateId = keyof typeof releaseGateRegistry;
export type ProfileId = keyof typeof profileRegistry;


type CapabilityEntry = (typeof capabilityRegistry)[CapabilityId];
type FeatureEntry = (typeof featureAdmissionRegistry)[FeatureId];
type LaneEntry = (typeof laneRegistry)[LaneId];
type CommandRouteEntry = (typeof commandRouteRegistry)[CommandRouteId];
type SurfaceEntry = (typeof surfaceRegistry)[SurfaceId];
type RuntimeOrchestrationEntry = (typeof runtimeOrchestrationRegistry)[RuntimeOrchestrationId];
type NavigationAdapterBoundaryEntry = (typeof navigationAdapterBoundaryRegistry)[NavigationAdapterBoundaryId];
type ReleaseGateEntry = (typeof releaseGateRegistry)[ReleaseGateId];
type ProfileEntry = (typeof profileRegistry)[ProfileId];

function sortedEntries<T extends Record<string, object>>(payload: T): Array<T[keyof T]> {
  return Object.values(payload) as Array<T[keyof T]>;
}

export function getCapabilityEntry(capabilityId: CapabilityId): CapabilityEntry {
  return capabilityRegistry[capabilityId];
}

export function getFeatureEntry(featureId: FeatureId): FeatureEntry {
  return featureAdmissionRegistry[featureId];
}

export function getFeatureCapabilityEntries(featureId: FeatureId): CapabilityEntry[] {
  return getFeatureEntry(featureId).capabilityIds.map((capabilityId) => getCapabilityEntry(capabilityId as CapabilityId));
}

export function featureMaturityLabel(maturity: string): string {
  switch (maturity) {
    case 'mainline':
      return '主线';
    case 'mainline_observability':
      return '主线观测';
    case 'mainline_with_experimental_lane_isolation':
      return '主线 / 实验隔离';
    case 'evidence_only':
      return '证据专用';
    case 'experimental_gated':
      return '实验隔离';
    default:
      return maturity;
  }
}

export function featureMaturityTone(maturity: string): GovernanceTone {
  switch (maturity) {
    case 'mainline':
    case 'mainline_observability':
      return 'success';
    case 'mainline_with_experimental_lane_isolation':
    case 'experimental_gated':
      return 'warning';
    case 'evidence_only':
      return 'neutral';
    default:
      return 'warning';
  }
}

function deriveFeatureMaturity(entries: CapabilityEntry[]): string {
  const maturities = new Set<string>(entries.map((entry) => String(entry.frontendMaturity)));
  if (maturities.size === 0) return 'experimental_gated';
  if (maturities.size === 1) return Array.from(maturities)[0] as string;
  if (maturities.has('mainline_with_experimental_lane_isolation')) return 'mainline_with_experimental_lane_isolation';
  if (maturities.has('mainline') && maturities.has('experimental_gated')) return 'mainline_with_experimental_lane_isolation';
  if (maturities.has('mainline')) return 'mainline';
  return Array.from(maturities).sort()[0] as string;
}

export interface FeatureMarker {
  label: string;
  tone: GovernanceTone;
}

export function featureMarkers(featureId: FeatureId): FeatureMarker[] {
  const capabilityEntries = getFeatureCapabilityEntries(featureId);
  const maturity = deriveFeatureMaturity(capabilityEntries);
  const markers: FeatureMarker[] = [{ label: featureMaturityLabel(maturity), tone: featureMaturityTone(maturity) }];
  const acceptanceStages = capabilityEntries.map((entry) => entry.acceptanceStage);
  const externalDependencies = capabilityEntries.flatMap((entry) => [...entry.externalDependencies] as string[]);
  const entrySurfaces = capabilityEntries.flatMap((entry) => [...entry.entrySurfaces] as string[]);
  if (acceptanceStages.some((stage) => stage.includes('target_environment'))) {
    markers.push({ label: '需目标环境验收', tone: 'warning' });
  }
  if (externalDependencies.length > 0) {
    markers.push({ label: '含仓外依赖', tone: 'neutral' });
  }
  if (entrySurfaces.includes('bridge_observer_surface')) {
    markers.push({ label: '9001 只读可见', tone: 'neutral' });
  }
  return markers;
}


export function getCommandRouteEntry(commandType: CommandRouteId): CommandRouteEntry {
  return commandRouteRegistry[commandType];
}

export function getSurfaceEntry(surfaceId: SurfaceId): SurfaceEntry {
  return surfaceRegistry[surfaceId];
}

export function getRuntimeOrchestrationEntry(componentId: RuntimeOrchestrationId): RuntimeOrchestrationEntry {
  return runtimeOrchestrationRegistry[componentId];
}

export function getNavigationAdapterBoundaryEntry(boundaryId: NavigationAdapterBoundaryId): NavigationAdapterBoundaryEntry {
  return navigationAdapterBoundaryRegistry[boundaryId];
}

export function getReleaseGateEntry(gateId: ReleaseGateId): ReleaseGateEntry {
  return releaseGateRegistry[gateId];
}

export function getProfileEntry(profileId: ProfileId): ProfileEntry {
  return profileRegistry[profileId];
}

export function surfaceLayerLabel(layer: string): string {
  switch (layer) {
    case 'command_control':
      return '命令控制';
    case 'live_state_projection':
      return '运行时投影';
    case 'observability_report':
      return '观测报告';
    case 'replay_export':
      return '回放/导出';
    default:
      return layer;
  }
}

export function releaseGateTone(stage: string): GovernanceTone {
  switch (stage) {
    case 'governance':
      return 'warning';
    case 'package':
      return 'success';
    default:
      return 'neutral';
  }
}

export function defaultVisibleLaneEntries(): LaneEntry[] {
  return sortedEntries(laneRegistry).filter((entry) => entry.defaultSurfaceExposure === 'default_visible');
}

export function hiddenByDefaultLaneEntries(): LaneEntry[] {
  return sortedEntries(laneRegistry).filter((entry) => entry.defaultSurfaceExposure === 'hidden_by_default');
}

export function lifecycleLabel(stage: string): string {
  switch (stage) {
    case 'mainline':
      return '主线';
    case 'experimental':
      return '实验';
    case 'rollback_only':
      return '回滚专用';
    default:
      return stage;
  }
}

export function lifecycleTone(stage: string): GovernanceTone {
  switch (stage) {
    case 'mainline':
      return 'success';
    case 'experimental':
      return 'warning';
    case 'rollback_only':
      return 'danger';
    default:
      return 'neutral';
  }
}
