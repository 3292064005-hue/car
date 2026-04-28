from __future__ import annotations

from robot_utils.system_replay_bundle import build_system_replay_bundle, validate_system_replay_bundle


def test_system_replay_bundle_builds_and_validates() -> None:
    payload = build_system_replay_bundle(
        source_name='robot-runtime',
        session_metadata={'sessionId': 's1', 'profileName': 'mock', 'providerName': 'nav2_provider', 'hardwareRole': 'ros_soft_driver', 'evidenceClass': 'host_harness'},
        topics=[{'topic': '/odom'}],
        service_action_events=[{'type': 'command_ack'}],
        trace_correlation=[{'traceId': 't1'}],
        logs=[{'id': '1'}],
        history={'latency': [], 'battery': [], 'leftWheel': [], 'rightWheel': [], 'frameDrops': [], 'ackLatency': []},
        params={},
        exported_at='2026-04-18T00:00:00Z',
    )
    validation = validate_system_replay_bundle(payload)
    assert validation.valid is True
    assert payload['kind'] == 'system-replay-bundle'


def test_system_replay_bundle_rejects_missing_members() -> None:
    validation = validate_system_replay_bundle({'kind': 'system-replay-bundle', 'exportScope': 'system-evidence', 'sourceName': 'x', 'version': '1'})
    assert validation.valid is False
    assert 'missing_topics' in validation.errors


def test_system_replay_bundle_rejects_missing_session_metadata_fields() -> None:
    validation = validate_system_replay_bundle({
        'kind': 'system-replay-bundle',
        'exportScope': 'system-evidence',
        'sourceName': 'x',
        'version': '1',
        'sessionMetadata': {'sessionId': 's1'},
        'topics': [],
        'serviceActionEvents': [],
        'traceCorrelation': [],
        'logs': [],
        'history': {'latency': [], 'battery': [], 'leftWheel': [], 'rightWheel': [], 'frameDrops': [], 'ackLatency': []},
        'params': {},
    })
    assert validation.valid is False
    assert 'missing_session_metadata_profileName' in validation.errors


def test_system_replay_bundle_rejects_missing_history_vectors() -> None:
    validation = validate_system_replay_bundle({
        'kind': 'system-replay-bundle',
        'exportScope': 'system-evidence',
        'sourceName': 'x',
        'version': '1',
        'sessionMetadata': {
            'sessionId': 's1',
            'profileName': 'mock',
            'providerName': 'nav2_provider',
            'hardwareRole': 'ros_soft_driver',
            'evidenceClass': 'target_environment',
        },
        'topics': [],
        'serviceActionEvents': [],
        'traceCorrelation': [],
        'logs': [],
        'history': {},
        'params': {},
    })
    assert validation.valid is False
    assert 'missing_history_ackLatency' in validation.errors
