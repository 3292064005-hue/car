from robot_bridge.odometry import OdomState, integrate_odometry, yaw_to_quaternion


def test_integrate_odometry_moves_forward_and_turns():
    state = integrate_odometry(OdomState(), linear_velocity=0.2, angular_velocity=0.1, dt=1.0)
    assert state.x > 0.19
    assert abs(state.y) < 0.02
    assert round(state.yaw, 3) == 0.1


def test_yaw_to_quaternion_identity_and_half_turn():
    assert yaw_to_quaternion(0.0) == (0.0, 0.0, 0.0, 1.0)
    _, _, z, w = yaw_to_quaternion(3.1415926)
    assert round(abs(z), 3) == 1.0
    assert round(abs(w), 3) == 0.0
