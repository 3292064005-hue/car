from __future__ import annotations

import robot_bringup.startup_barrier as startup_barrier


def test_wait_for_ros_graph_requires_services_and_actions(monkeypatch) -> None:
    listings = {
        ('ros2', 'node', 'list'): {'/robot_decision'},
        ('ros2', 'topic', 'list'): {'/robot/decision/summary'},
        ('ros2', 'service', 'list'): {'/robot/set_mode', '/robot/reset_fault'},
        ('ros2', 'action', 'list'): {'/robot/actions/start_patrol', '/robot/actions/track_target'},
    }

    monkeypatch.setattr(startup_barrier, '_cli_listing', lambda *args: set(listings.get(args, set())))
    result = startup_barrier.wait_for_ros_graph(
        label='decision_phase',
        expected_nodes=['/robot_decision'],
        expected_topics=['/robot/decision/summary'],
        expected_services=['/robot/set_mode', '/robot/reset_fault'],
        expected_actions=['/robot/actions/start_patrol', '/robot/actions/track_target'],
        expected_node_groups=[],
        timeout_sec=0.1,
        poll_interval_sec=0.01,
    )
    assert result == 0


def test_wait_for_ros_graph_times_out_when_service_missing(monkeypatch) -> None:
    listings = {
        ('ros2', 'node', 'list'): {'/robot_decision'},
        ('ros2', 'topic', 'list'): {'/robot/decision/summary'},
        ('ros2', 'service', 'list'): {'/robot/set_mode'},
        ('ros2', 'action', 'list'): {'/robot/actions/start_patrol', '/robot/actions/track_target'},
    }

    monkeypatch.setattr(startup_barrier, '_cli_listing', lambda *args: set(listings.get(args, set())))
    result = startup_barrier.wait_for_ros_graph(
        label='decision_phase',
        expected_nodes=['/robot_decision'],
        expected_topics=['/robot/decision/summary'],
        expected_services=['/robot/set_mode', '/robot/reset_fault'],
        expected_actions=['/robot/actions/start_patrol', '/robot/actions/track_target'],
        expected_node_groups=[],
        timeout_sec=0.05,
        poll_interval_sec=0.01,
    )
    assert result == 1


def test_wait_for_ros_graph_requires_ready_topics_with_semantic_probe(monkeypatch) -> None:
    listings = {
        ('ros2', 'node', 'list'): {'/robot_decision'},
        ('ros2', 'topic', 'list'): {'/robot/decision/summary', '/robot/decision/ready'},
        ('ros2', 'service', 'list'): {'/robot/set_mode'},
        ('ros2', 'action', 'list'): set(),
    }

    monkeypatch.setattr(startup_barrier, '_cli_listing', lambda *args: set(listings.get(args, set())))
    monkeypatch.setattr(startup_barrier, '_ready_topic_probe', lambda topic_name, timeout_sec=startup_barrier.DEFAULT_READY_TOPIC_ECHO_TIMEOUT_SEC: (True, '{"ready":true}'))
    result = startup_barrier.wait_for_ros_graph(
        label='decision_ready_phase',
        expected_nodes=['/robot_decision'],
        expected_topics=['/robot/decision/summary'],
        expected_services=['/robot/set_mode'],
        expected_actions=[],
        expected_node_groups=[],
        expected_ready_topics=['/robot/decision/ready'],
        timeout_sec=0.1,
        poll_interval_sec=0.01,
    )
    assert result == 0


def test_wait_for_ros_graph_times_out_when_ready_topic_never_publishes(monkeypatch) -> None:
    listings = {
        ('ros2', 'node', 'list'): {'/robot_web_bridge'},
        ('ros2', 'topic', 'list'): {'/robot/web_bridge/ready'},
    }

    monkeypatch.setattr(startup_barrier, '_cli_listing', lambda *args: set(listings.get(args, set())))
    monkeypatch.setattr(startup_barrier, '_ready_topic_probe', lambda topic_name, timeout_sec=startup_barrier.DEFAULT_READY_TOPIC_ECHO_TIMEOUT_SEC: (False, 'timeout'))
    result = startup_barrier.wait_for_ros_graph(
        label='frontend_phase',
        expected_nodes=['/robot_web_bridge'],
        expected_topics=[],
        expected_services=[],
        expected_actions=[],
        expected_node_groups=[],
        expected_ready_topics=['/robot/web_bridge/ready'],
        timeout_sec=0.05,
        poll_interval_sec=0.01,
    )
    assert result == 1


def test_wait_for_ros_graph_requires_http_health_probe(monkeypatch) -> None:
    listings = {
        ('ros2', 'node', 'list'): {'/robot_web_bridge'},
        ('ros2', 'topic', 'list'): {'/robot/web_bridge/ready'},
        ('ros2', 'service', 'list'): set(),
        ('ros2', 'action', 'list'): set(),
    }
    monkeypatch.setattr(startup_barrier, '_cli_listing', lambda *args: set(listings.get(args, set())))
    monkeypatch.setattr(startup_barrier, '_ready_topic_probe', lambda topic_name, timeout_sec=startup_barrier.DEFAULT_READY_TOPIC_ECHO_TIMEOUT_SEC: (True, '{"ready":true}'))
    monkeypatch.setattr(startup_barrier, '_http_probe', lambda url, ready_fields, timeout_sec=startup_barrier.DEFAULT_READY_TOPIC_ECHO_TIMEOUT_SEC: (ready_fields == ['ok', 'operatorReady'], '{"ok":true,"operatorReady":true}'))
    result = startup_barrier.wait_for_ros_graph(
        label='operator_phase',
        expected_nodes=['/robot_web_bridge'],
        expected_topics=[],
        expected_services=[],
        expected_actions=[],
        expected_node_groups=[],
        expected_ready_topics=['/robot/web_bridge/ready'],
        expected_http_urls=['http://127.0.0.1:9100/api/v1/health'],
        expected_http_ready_fields=['ok', 'operatorReady'],
        timeout_sec=0.1,
        poll_interval_sec=0.01,
    )
    assert result == 0


def test_http_probe_decodes_json_payload() -> None:
    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return b'{"ok": true, "operatorReady": true}'

    monkeypatch_urlopen = startup_barrier.urllib.request.urlopen
    startup_barrier.urllib.request.urlopen = lambda url, timeout=0.0: _Response()
    try:
        ready, detail = startup_barrier._http_probe('http://127.0.0.1:9100/api/v1/health', ready_fields=['ok', 'operatorReady'])
    finally:
        startup_barrier.urllib.request.urlopen = monkeypatch_urlopen
    assert ready is True
    assert 'operatorReady' in detail


def test_main_forwards_http_probe_arguments(monkeypatch) -> None:
    captured = {}

    def _fake_wait_for_ros_graph(**kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(startup_barrier, 'wait_for_ros_graph', _fake_wait_for_ros_graph)
    result = startup_barrier.main([
        '--label', 'operator_phase',
        '--expected-node', '/robot_web_bridge',
        '--expected-ready-topic', '/robot/web_bridge/ready',
        '--expected-http-url', 'http://127.0.0.1:9100/api/v1/health',
        '--expected-http-ready-field', 'ok',
        '--expected-http-ready-field', 'operatorReady',
    ])
    assert result == 0
    assert captured['expected_http_urls'] == ['http://127.0.0.1:9100/api/v1/health']
    assert captured['expected_http_ready_fields'] == ['ok', 'operatorReady']
