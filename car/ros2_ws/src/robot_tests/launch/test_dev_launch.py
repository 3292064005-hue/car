from __future__ import annotations

import pytest

launch_testing = pytest.importorskip('launch_testing')
launch_testing_ros = pytest.importorskip('launch_testing_ros')
from launch import LaunchDescription
from launch_ros.actions import Node


@pytest.mark.launch_test
def generate_test_description():
    ld = LaunchDescription([
        Node(package='robot_monitor', executable='monitor_node', name='robot_monitor_test', output='screen')
    ])
    return ld, {}
