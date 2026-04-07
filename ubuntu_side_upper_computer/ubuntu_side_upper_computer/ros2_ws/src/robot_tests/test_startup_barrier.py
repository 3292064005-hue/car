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
