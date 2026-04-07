from __future__ import annotations

import sys
import termios
import tty

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from robot_msgs.srv import ResetFault, SetMode
from robot_utils.qos_profiles import qos_for


KEY_BINDINGS = {
    'w': ('twist', (1.0, 0.0), '前进'),
    's': ('twist', (-1.0, 0.0), '后退'),
    'a': ('twist', (0.0, 1.0), '左转'),
    'd': ('twist', (0.0, -1.0), '右转'),
    'x': ('twist', (0.0, 0.0), '停车'),
    'm': ('mode', 'MANUAL', '切到 MANUAL'),
    'p': ('mode', 'PATROL', '切到 PATROL'),
    'i': ('mode', 'IDLE', '切到 IDLE'),
    'e': ('mode', 'SAFE_STOP', '进入 SAFE_STOP'),
    'c': ('mode', 'IDLE', '解除手动/安全停并回到 IDLE'),
    'r': ('reset', None, '复位 FAULT'),
    'q': ('quit', None, '退出'),
}

HELP = """
按键说明:
  w/s : 前进/后退
  a/d : 左转/右转
  x   : 停车
  m   : 切到 MANUAL
  p   : 切到 PATROL
  i   : 切到 IDLE
  e   : 进入 SAFE_STOP
  c   : 解除手动/安全停并回到 IDLE
  r   : 复位 FAULT
  q   : 退出
"""


class KeyboardTeleop(Node):
    def __init__(self) -> None:
        super().__init__('robot_keyboard_teleop')
        self.pub = self.create_publisher(Twist, '/robot/manual/cmd_vel', qos_for('control_cmd'))
        self.mode_client = self.create_client(SetMode, '/robot/set_mode')
        self.reset_client = self.create_client(ResetFault, '/robot/reset_fault')
        self.declare_parameter('linear_step', 0.20)
        self.declare_parameter('angular_step', 0.80)
        self.get_logger().info('keyboard teleop started')
        print(HELP)

    def send_twist(self, vx: float, wz: float) -> None:
        msg = Twist()
        msg.linear.x = vx
        msg.angular.z = wz
        self.pub.publish(msg)

    def request_mode(self, mode: str) -> None:
        if not self.mode_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().warn('set_mode service unavailable')
            return
        req = SetMode.Request()
        req.mode = mode
        req.requested_by = 'keyboard'
        req.reason = 'teleop_key'
        self.mode_client.call_async(req)

    def reset_fault(self) -> None:
        if not self.reset_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().warn('reset_fault service unavailable')
            return
        req = ResetFault.Request()
        req.requested_by = 'keyboard'
        req.reason = 'teleop_reset'
        self.reset_client.call_async(req)


def get_key() -> str:
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = KeyboardTeleop()
    linear_step = float(node.get_parameter('linear_step').value)
    angular_step = float(node.get_parameter('angular_step').value)

    try:
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.01)
            key = get_key()
            binding = KEY_BINDINGS.get(key)
            if not binding:
                continue
            action, payload, _label = binding
            if action == 'quit':
                break
            if action == 'twist':
                vx_scale, wz_scale = payload
                node.send_twist(vx_scale * linear_step, wz_scale * angular_step)
            elif action == 'mode':
                node.request_mode(str(payload))
            elif action == 'reset':
                node.reset_fault()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
