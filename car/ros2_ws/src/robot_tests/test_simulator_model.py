from robot_simulator.simulator_model import DifferentialDriveState, step_simulation


def test_step_simulation_advances_pose_and_drains_battery() -> None:
    state = step_simulation(
        state=DifferentialDriveState(),
        linear_cmd=0.5,
        angular_cmd=0.2,
        dt_sec=1.0,
        moving_drain_per_sec=1.0,
        idle_drain_per_sec=0.1,
    )
    assert state.x != 0.0 or state.y != 0.0
    assert state.battery_percent < 100.0


def test_step_simulation_idle_drain_is_smaller() -> None:
    moving = step_simulation(state=DifferentialDriveState(), linear_cmd=0.5, angular_cmd=0.0, dt_sec=1.0, moving_drain_per_sec=1.0, idle_drain_per_sec=0.1)
    idle = step_simulation(state=DifferentialDriveState(), linear_cmd=0.0, angular_cmd=0.0, dt_sec=1.0, moving_drain_per_sec=1.0, idle_drain_per_sec=0.1)
    assert moving.battery_percent < idle.battery_percent
