from __future__ import annotations

"""Shared verification-evidence taxonomy for release and acceptance reporting."""

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class EvidenceClass:
    key: str
    label: str
    supported_claims: tuple[str, ...]


EVIDENCE_CLASSES: dict[str, EvidenceClass] = {
    'unit_stubbed': EvidenceClass(
        key='unit_stubbed',
        label='Unit / stubbed verification',
        supported_claims=(
            'contracts_parse',
            'config_schema_valid',
            'logic_regression_checked',
        ),
    ),
    'integration_mocked_transport': EvidenceClass(
        key='integration_mocked_transport',
        label='Integration / mocked transport',
        supported_claims=(
            'frontend_bridge_contract_compatible',
            'operator_command_ack_path_verified',
            'release_gate_scripts_execute',
        ),
    ),
    'integration_live_ros_mock_robot': EvidenceClass(
        key='integration_live_ros_mock_robot',
        label='Integration / live ROS graph with mock robot',
        supported_claims=(
            'ros_graph_launches',
            'web_bridge_enters_ros_graph',
            'frontend_websocket_live_path_verified',
            'host_harness_runtime_ready',
        ),
    ),
    'hardware_probe_observational': EvidenceClass(
        key='hardware_probe_observational',
        label='Hardware probe / observational',
        supported_claims=(
            'live_runtime_topics_present',
            'services_and_actions_present',
            'operator_stream_endpoint_reachable',
            'hardware_probe_observational_only',
        ),
    ),
    'hardware_in_loop': EvidenceClass(
        key='hardware_in_loop',
        label='Hardware in the loop',
        supported_claims=(
            'command_behavior_verified_against_live_hardware',
            'safety_interlocks_verified',
            'real_board_verified',
        ),
    ),
}

EVIDENCE_ORDER: tuple[str, ...] = tuple(EVIDENCE_CLASSES.keys())


def evidence_class_payload(key: str) -> dict[str, object]:
    item = EVIDENCE_CLASSES[key]
    return {
        'key': item.key,
        'label': item.label,
        'supportedClaims': list(item.supported_claims),
    }


def strongest_evidence_class(classes: Iterable[str]) -> str:
    highest_index = -1
    best = 'unit_stubbed'
    for key in classes:
        if key not in EVIDENCE_CLASSES:
            continue
        index = EVIDENCE_ORDER.index(key)
        if index > highest_index:
            highest_index = index
            best = key
    return best
