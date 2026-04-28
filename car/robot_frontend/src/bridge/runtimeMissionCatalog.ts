import { API_BASE_URL } from '@/shared/constants';
import { PRODUCT_INTERFACE_CONTRACT } from '@/generated/productInterface';
import type { GeneratedMissionCatalog } from '@/generated/missionCatalog';

export type RuntimeMissionCatalog = GeneratedMissionCatalog;

function isAbsoluteUrl(value: string): boolean {
  return /^https?:\/\//i.test(value);
}

function normalizeBaseUrl(value: string): string {
  return String(value || '').trim().replace(/\/+$/, '');
}

export function resolveProductApiUrl(pathOrUrl: string): string {
  const candidate = String(pathOrUrl || '').trim();
  if (!candidate) return '';
  if (isAbsoluteUrl(candidate)) return candidate;
  const base = normalizeBaseUrl(API_BASE_URL);
  if (!base) return candidate;
  const origin = (() => {
    try {
      return new URL(base).origin;
    } catch {
      return '';
    }
  })();
  if (candidate.startsWith('/')) {
    return origin ? `${origin}${candidate}` : candidate;
  }
  return `${base}/${candidate.replace(/^\/+/, '')}`;
}

function assertMissionCatalog(payload: unknown): asserts payload is RuntimeMissionCatalog {
  if (!payload || typeof payload !== 'object') throw new Error('mission catalog payload must be an object');
  const record = payload as Record<string, unknown>;
  if (typeof record.defaultMissionId !== 'string' || !record.defaultMissionId) throw new Error('mission catalog defaultMissionId missing');
  if (!record.missions || typeof record.missions !== 'object') throw new Error('mission catalog missions missing');
}

export async function fetchRuntimeMissionCatalog(signal?: AbortSignal): Promise<RuntimeMissionCatalog> {
  const productInterfaceUrl = resolveProductApiUrl(PRODUCT_INTERFACE_CONTRACT.httpEndpoints.productInterface);
  const productInterfaceResponse = await fetch(productInterfaceUrl, { method: 'GET', signal, headers: { Accept: 'application/json' } });
  if (!productInterfaceResponse.ok) {
    throw new Error(`product interface request failed: HTTP ${productInterfaceResponse.status}`);
  }
  const productInterface = await productInterfaceResponse.json() as { httpEndpoints?: { missions?: string } };
  const missionsEndpoint = String(productInterface.httpEndpoints?.missions || PRODUCT_INTERFACE_CONTRACT.httpEndpoints.missions || '').trim();
  if (!missionsEndpoint) throw new Error('product interface missions endpoint missing');
  const missionsUrl = resolveProductApiUrl(missionsEndpoint);
  const response = await fetch(missionsUrl, { method: 'GET', signal, headers: { Accept: 'application/json' } });
  if (!response.ok) {
    throw new Error(`mission catalog request failed: HTTP ${response.status}`);
  }
  const payload = await response.json();
  assertMissionCatalog(payload);
  return payload;
}
