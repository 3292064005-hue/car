from __future__ import annotations

import pytest

launch_testing = pytest.importorskip('launch_testing')
launch_testing_ros = pytest.importorskip('launch_testing_ros')
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument


@pytest.mark.launch_test
def generate_test_description():
    ld = LaunchDescription([
        DeclareLaunchArgument('sanity_only', default_value='true'),
    ])
    return ld, {}
