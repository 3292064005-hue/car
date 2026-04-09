from __future__ import annotations

from pathlib import Path


def test_generated_bridge_contract_uses_discriminated_report_union() -> None:
    root = Path(__file__).resolve().parents[3]
    source = (root / 'robot_frontend' / 'src' / 'generated' / 'bridgeContract.ts').read_text(encoding='utf-8')
    assert "z.discriminatedUnion('kind'" in source
    assert 'reportJsonSummaryEntrySchema' not in source
    assert 'reportRuntimeSupervisionEntrySchema' in source
    assert "'raw'" not in source
    assert 'json_summary' not in source


def test_inbound_store_uses_generated_report_schema_safe_parse() -> None:
    root = Path(__file__).resolve().parents[3]
    source = (root / 'robot_frontend' / 'src' / 'store' / 'inbound.ts').read_text(encoding='utf-8')
    assert 'reportSurfaceEntrySchema.safeParse' in source
