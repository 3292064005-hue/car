import { StatusPill } from '@/components/StatusPill';
import { featureMarkers, getFeatureEntry, type FeatureId } from '@/governance/runtimeGovernance';

export function FeatureMaturityPills({ featureIds }: { featureIds: FeatureId[] }) {
  const seen = new Set<string>();
  const markers = featureIds.flatMap((featureId) => {
    const entry = getFeatureEntry(featureId);
    return featureMarkers(featureId).map((marker) => ({ key: `${featureId}:${marker.label}`, label: `${entry.title}·${marker.label}`, tone: marker.tone }));
  }).filter((marker) => {
    if (seen.has(marker.label)) return false;
    seen.add(marker.label);
    return true;
  });
  return (
    <div className="pill-row">
      {markers.map((marker) => (
        <StatusPill key={marker.key} label={marker.label} tone={marker.tone} />
      ))}
    </div>
  );
}
