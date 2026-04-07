from robot_monitor.status_aggregator import StatusSnapshot
from robot_utils.constants import HEALTH_GOOD


def render_text(snapshot: StatusSnapshot, health: str = HEALTH_GOOD) -> str:
    recent = ' | '.join(snapshot.recent_events) if snapshot.recent_events else '-'
    return (
        f'health={health} readiness={snapshot.readiness} reason={snapshot.readiness_reason} mode={snapshot.mode} '
        f'wifi={snapshot.wifi_ok} bridge={snapshot.bridge_ok} camera={snapshot.camera_ok} '
        f'audio={snapshot.audio_ok} uart={snapshot.uart_ok} '
        f'battery={snapshot.battery_voltage:.2f}V '
        f'left={snapshot.left_rpm:.1f} right={snapshot.right_rpm:.1f} '
        f'source={snapshot.control_source or "-"} '
        f'qrcode={snapshot.last_qrcode or "-"} voice={snapshot.last_voice_cmd or "-"} '
        f'fault={snapshot.last_fault or "-"} snaps={snapshot.snapshot_count} '
        f'reconnects={snapshot.reconnect_count} proto_err={snapshot.protocol_errors} recent={recent}'
    )
