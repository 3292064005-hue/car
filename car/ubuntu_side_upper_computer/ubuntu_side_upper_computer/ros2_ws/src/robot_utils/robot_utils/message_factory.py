from __future__ import annotations

from robot_msgs.msg import EventLog, Fault, SpeakRequest


def _set_if_attr(msg, name: str, value) -> None:
    if hasattr(msg, name):
        setattr(msg, name, value)


def make_event(node, category: str, name: str, detail: str, level: str = 'info', source: str = '', **extra_fields) -> EventLog:
    msg = EventLog()
    msg.category = category
    msg.name = name
    msg.detail = detail
    msg.level = level
    msg.source = source or node.get_name()
    msg.stamp = node.get_clock().now().to_msg()
    for field_name, value in extra_fields.items():
        _set_if_attr(msg, field_name, value)
    return msg


def make_fault(node, code: str, level: str, source: str, description: str, recoverable: bool = True, **extra_fields) -> Fault:
    msg = Fault()
    msg.code = code
    msg.level = level
    msg.source = source
    msg.description = description
    msg.recoverable = recoverable
    msg.stamp = node.get_clock().now().to_msg()
    for field_name, value in extra_fields.items():
        _set_if_attr(msg, field_name, value)
    return msg


def make_speak(text_id: str, priority: int = 1, requested_by: str = 'system', **extra_fields) -> SpeakRequest:
    msg = SpeakRequest()
    msg.text_id = text_id
    msg.priority = priority
    msg.requested_by = requested_by
    for field_name, value in extra_fields.items():
        _set_if_attr(msg, field_name, value)
    return msg
