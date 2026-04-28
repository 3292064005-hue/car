from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExternalContractEntry:
    contract_id: str
    version: str
    owner: str
    scope: str
    promotion_gate: str
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'contractId': self.contract_id,
            'version': self.version,
            'owner': self.owner,
            'scope': self.scope,
            'promotionGate': self.promotion_gate,
            'notes': self.notes,
        }


_EXTERNAL_CONTRACTS: dict[str, ExternalContractEntry] = {
    'bridge.transport_schema': ExternalContractEntry(
        contract_id='bridge.transport_schema',
        version='1.0.0',
        owner='robot_bridge + board_boundary_contract_or_verified_board_runtime',
        scope='tcp_json_bridge / serial_framed transport schema',
        promotion_gate='target_environment_acceptance',
        notes='Any incompatible change must be accompanied by target acceptance evidence.',
    ),
    'fault.schema': ExternalContractEntry(
        contract_id='fault.schema',
        version='1.0.0',
        owner='robot_monitor + board_boundary_contract_or_verified_board_runtime',
        scope='fault code / severity / latched state semantics',
        promotion_gate='release_quality_manifest',
        notes='Fault payload producers and consumers must migrate in lockstep.',
    ),
    'acceptance.target_environment': ExternalContractEntry(
        contract_id='acceptance.target_environment',
        version='2.0.0',
        owner='board_boundary_contract_or_verified_board_runtime + ubuntu_runtime',
        scope='cross-repo delivery evidence bundle',
        promotion_gate='release_audit',
        notes='No cross-environment release-grade board-execution claim may bypass this artifact; default in-repo runtime activation is bound to hardware_in_loop_acceptance.',
    ),
    'observability.system_replay_bundle': ExternalContractEntry(
        contract_id='observability.system_replay_bundle',
        version='1.0.0',
        owner='robot_utils + release tooling',
        scope='system replay bundle schema',
        promotion_gate='acceptance_review',
        notes='The JSON bundle is a normalized evidence container alongside rosbag2/MCAP.',
    ),
}


def external_contract_registry_payload() -> dict[str, dict[str, Any]]:
    return {key: entry.to_dict() for key, entry in _EXTERNAL_CONTRACTS.items()}
