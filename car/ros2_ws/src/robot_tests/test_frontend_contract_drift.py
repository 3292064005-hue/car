from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_frontend_types_alias_generated_transport_contracts() -> None:
    text = (ROOT / 'robot_frontend' / 'src' / 'types' / 'robot.ts').read_text(encoding='utf-8')
    assert 'GeneratedCommandType' in text
    assert 'GeneratedInboundEventType' in text
    assert 'GeneratedBridgeInboundPayloadMap' in text
    assert 'GeneratedBridgeOutboundPayloadMap' in text
    assert 'export type CommandType = GeneratedCommandType;' in text
    assert 'export type InboundEventType = GeneratedInboundEventType;' in text
    assert 'Record<InboundEventType, unknown> & GeneratedBridgeInboundPayloadMap' in text
    assert 'Record<CommandType, unknown> & GeneratedBridgeOutboundPayloadMap' in text


def test_frontend_schema_uses_generated_transport_schemas_and_shared_constants() -> None:
    text = (ROOT / 'robot_frontend' / 'src' / 'bridge' / 'schemas.ts').read_text(encoding='utf-8')
    assert "import { PROTOCOL_VERSION, SCHEMA_VERSION } from '@/shared/constants';" in text
    assert 'protocolVersion: z.string().default(PROTOCOL_VERSION)' in text
    assert 'schemaVersion: z.string().default(SCHEMA_VERSION)' in text
    assert 'inboundPayloadSchemas' in text
    assert 'outboundPayloadSchemas' in text
    assert 'legacyPayloadSchemas' in text
