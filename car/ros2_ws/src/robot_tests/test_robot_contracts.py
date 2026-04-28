import pytest

from robot_contracts.bridge_contract import (
    BridgeEnvelope,
    CommandAck,
    EnvelopeValidationError,
    contract_version_snapshot,
    resolve_compatibility_mode,
    validate_envelope_dict,
    validate_outbound_command_type,
    validate_transport_proto_version,
)
from robot_contracts.faults import fault_definition, normalize_fault_level, normalize_log_level, recommended_action
from robot_contracts.launch_contract import resolve_runtime


def test_bridge_envelope_serialization():
    envelope = BridgeEnvelope(type='heartbeat', payload={'ok': True}, seq=7).to_dict()
    assert envelope['type'] == 'heartbeat'
    assert envelope['payload']['ok'] is True
    assert envelope['seq'] == 7
    assert envelope['protocolVersion'] == '4.1.0'
    assert 'command-ack' in envelope['capabilities']
    assert 'odom-bridge' in envelope['capabilities']
    assert 'stale-flags' in envelope['capabilities']


def test_command_ack_payload():
    payload = CommandAck(command_id='cmd-1', status='ack', lifecycle_status='completed', message='done', detail='ok').to_payload()
    assert payload == {
        'commandId': 'cmd-1',
        'status': 'ack',
        'message': 'done',
        'lifecycleStatus': 'completed',
        'lifecyclePhase': 'business_completed',
        'detail': 'ok',
    }


def test_command_ack_accepts_explicit_lifecycle_phase():
    payload = CommandAck(
        command_id='cmd-2',
        status='ack',
        lifecycle_status='applied',
        lifecycle_phase='ros_accepted',
        message='applied',
    ).to_payload()
    assert payload['lifecyclePhase'] == 'ros_accepted'


def test_command_ack_rejects_invalid_lifecycle_phase():
    with pytest.raises(EnvelopeValidationError):
        CommandAck(
            command_id='cmd-3',
            status='ack',
            lifecycle_status='applied',
            lifecycle_phase='legacy_done',
            message='bad',
        ).to_payload()


def test_fault_and_log_level_normalization():
    assert normalize_fault_level('error') == 'critical'
    assert normalize_fault_level('warn') == 'warning'
    assert normalize_log_level('fatal') == 'CRITICAL'
    assert normalize_log_level('info') == 'INFO'
    assert fault_definition('ESTOP').latched is True
    assert 'clear' in recommended_action('ESTOP')


def test_launch_runtime_resolves_mock_and_hardware_defaults():
    mock_runtime = resolve_runtime(use_mock_robot=True)
    hw_runtime = resolve_runtime(use_mock_robot=False)
    assert mock_runtime.mock_enabled is True
    assert mock_runtime.bridge.host == '127.0.0.1'
    assert mock_runtime.bridge.stream_url == mock_runtime.bridge.mjpeg_url
    assert hw_runtime.mock_enabled is False
    assert hw_runtime.bridge.host == '192.168.4.1'


def test_launch_runtime_accepts_stream_alias():
    runtime = resolve_runtime(use_mock_robot=False, stream_url='http://10.0.0.2:81/stream')
    assert runtime.bridge.mjpeg_url == 'http://10.0.0.2:81/stream'
    assert runtime.bridge.stream_url == 'http://10.0.0.2:81/stream'


def test_validate_envelope_and_command_type():
    result = validate_envelope_dict({
        'eventId': 'evt-1',
        'type': 'heartbeat',
        'ts': '2026-03-31T00:00:00Z',
        'source': 'bridge',
        'sessionId': 'robot-web-bridge',
        'seq': 1,
        'payload': {},
        'protocolVersion': '4.1.0',
        'schemaVersion': '2026-03-31',
    })
    assert result.ok is True
    assert validate_outbound_command_type('set_mode').ok is True
    assert validate_outbound_command_type('totally_invalid').ok is False


def test_contract_versions_and_transport_versions():
    snapshot = contract_version_snapshot()
    assert snapshot['tcp_transport'] == 1
    assert snapshot['uart_transport'] == 1
    assert resolve_compatibility_mode('4.1.0') == 'native-v4'
    assert resolve_compatibility_mode('3.0.0') == 'native-v4'
    assert validate_transport_proto_version(1, transport='tcp') is True
    assert validate_transport_proto_version(2, transport='tcp') is False


def test_command_ack_includes_trace_id_when_present():
    from robot_web_bridge.envelope import EnvelopeFactory

    factory = EnvelopeFactory(session_id='robot-web-bridge')
    envelope = factory.ack('cmd-1', 'ack', 'done', trace_id='trace-123')

    assert envelope['traceId'] == 'trace-123'
    assert envelope['payload']['commandId'] == 'cmd-1'


def test_contract_versions_expose_command_lifecycle_statuses():
    snapshot = contract_version_snapshot()
    assert 'completed' in snapshot['command_lifecycle_statuses']
    assert 'business_completed' in snapshot['command_lifecycle_phases']
    assert 'command-lifecycle-v2' in snapshot['capabilities']
