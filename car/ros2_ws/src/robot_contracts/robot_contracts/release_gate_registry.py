from __future__ import annotations

"""Authoritative registry for release gates used by CI and source-release verification."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True, slots=True)
class ReleaseGateEntry:
    """One release gate tracked across CI, scripts, and docs.

    Attributes:
        gate_id: Stable internal identifier.
        title: Human-readable CI/doc title.
        entrypoint: Canonical entry command for the gate.
        script_paths: Supporting scripts that must exist and remain aligned.
        workflow_markers: Strings that must exist in the CI workflow.
        readme_markers: Strings that must exist in README/docs.
        stage: Gate stage label used by governance UI.
        risk_surface: Quality surface protected by the gate.
        blocking_by_default: Whether the gate blocks releases by default.
        notes: Human-readable notes.
    """

    gate_id: str
    title: str
    entrypoint: str
    script_paths: tuple[str, ...]
    workflow_markers: tuple[str, ...]
    readme_markers: tuple[str, ...]
    stage: str
    risk_surface: str
    blocking_by_default: bool
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            'gateId': self.gate_id,
            'title': self.title,
            'entrypoint': self.entrypoint,
            'scriptPaths': list(self.script_paths),
            'workflowMarkers': list(self.workflow_markers),
            'readmeMarkers': list(self.readme_markers),
            'stage': self.stage,
            'riskSurface': self.risk_surface,
            'blockingByDefault': self.blocking_by_default,
            'notes': list(self.notes),
        }


_VERIFY_WORKFLOW_ENTRYPOINT = './scripts/run_release_verification.sh --with-frontend --with-ros-smoke --with-integrated-frontend-smoke'


_REGISTRY: dict[str, ReleaseGateEntry] = {
    'source_release_cleanliness': ReleaseGateEntry(
        gate_id='source_release_cleanliness',
        title='干净源码树与打包审计',
        entrypoint='python3 scripts/package_source_release.py --clean-transient-source-artifacts',
        script_paths=(
            'scripts/package_source_release.py',
            'scripts/refresh_validation_evidence_metadata.py',
        ),
        workflow_markers=(
            'Source release package audit',
            'python3 scripts/package_source_release.py --clean-transient-source-artifacts',
            'Clean source tree gate (pre-frontend)',
            'Clean source tree gate (post-frontend)',
        ),
        readme_markers=(
            'canonical-only source release',
            'check_validation_evidence_binding.py',
        ),
        stage='package',
        risk_surface='source_package_cleanliness',
        blocking_by_default=True,
        notes=(
            '打包前后均应阻止 build/dist/node_modules 等污染进入交付包。',
            '打包过程必须刷新 validation evidence 元数据，避免旧源码树哈希复用。',
        ),
    ),
    'validation_evidence_binding': ReleaseGateEntry(
        gate_id='validation_evidence_binding',
        title='验证证据绑定',
        entrypoint='python3 scripts/check_validation_evidence_binding.py',
        script_paths=(
            'scripts/check_validation_evidence_binding.py',
            'scripts/refresh_validation_evidence_metadata.py',
        ),
        workflow_markers=(
            'Validation evidence binding',
            'python3 scripts/check_validation_evidence_binding.py',
        ),
        readme_markers=(
            'check_validation_evidence_binding.py',
            'VALIDATION_EVIDENCE.md',
        ),
        stage='governance',
        risk_surface='validation_truthfulness',
        blocking_by_default=True,
        notes=(
            '交付包中的 validation evidence 必须绑定当前源码树与 workspace manifest。',
        ),
    ),
    'contract_consistency': ReleaseGateEntry(
        gate_id='contract_consistency',
        title='跨表面合同一致性',
        entrypoint='python3 scripts/check_contract_consistency.py',
        script_paths=(
            'scripts/check_contract_consistency.py',
            'scripts/check_report_surface_closure.py',
            'scripts/check_report_kind_enum_closure.py',
        ),
        workflow_markers=(
            'Contract consistency',
            'Report surface closure',
            'Report kind enum closure',
        ),
        readme_markers=(
            'check_contract_consistency.py',
            'check_report_surface_closure.py',
            'check_report_kind_enum_closure.py',
        ),
        stage='governance',
        risk_surface='contract_drift',
        blocking_by_default=True,
        notes=(
            '协议版本、生成工件、报告面枚举闭包必须来自同一真源。',
        ),
    ),
    'command_route_governance': ReleaseGateEntry(
        gate_id='command_route_governance',
        title='命令路由权威矩阵',
        entrypoint='python3 scripts/check_command_route_registry.py',
        script_paths=('scripts/check_command_route_registry.py',),
        workflow_markers=(
            'Command route registry',
            'python3 scripts/check_command_route_registry.py',
        ),
        readme_markers=('check_command_route_registry.py',),
        stage='governance',
        risk_surface='command_path_truth',
        blocking_by_default=True,
        notes=(
            '命令入口、权限、目标节点、超时与回滚路径必须完整覆盖全部命令。',
        ),
    ),
    'lane_alignment': ReleaseGateEntry(
        gate_id='lane_alignment',
        title='实验 lane 与 adapter 边界一致性',
        entrypoint='python3 scripts/check_lane_implementation_alignment.py',
        script_paths=('scripts/check_lane_implementation_alignment.py',),
        workflow_markers=(
            'Lane implementation alignment',
            'python3 scripts/check_lane_implementation_alignment.py',
        ),
        readme_markers=('check_lane_implementation_alignment.py',),
        stage='governance',
        risk_surface='adapter_boundary_truth',
        blocking_by_default=True,
        notes=(
            '实验 Nav2 lane 只能按受控适配器边界宣称能力。',
        ),
    ),
    'feature_admission': ReleaseGateEntry(
        gate_id='feature_admission',
        title='功能准入与 UI 绑定',
        entrypoint='python3 scripts/check_feature_admission.py',
        script_paths=('scripts/check_feature_admission.py',),
        workflow_markers=(
            'Feature admission registry',
            'python3 scripts/check_feature_admission.py',
        ),
        readme_markers=('check_feature_admission.py',),
        stage='governance',
        risk_surface='feature_ui_alignment',
        blocking_by_default=True,
        notes=(
            '命令、能力、UI 消费者和验收证据必须同源。',
        ),
    ),
    'frontend_e2e': ReleaseGateEntry(
        gate_id='frontend_e2e',
        title='Frontend E2E',
        entrypoint='./scripts/run_release_verification.sh --with-frontend',
        script_paths=('scripts/run_release_verification.sh', 'scripts/run_frontend_workspace_command.py'),
        workflow_markers=(
            'Install Playwright browsers (isolated workspace)',
            'python3 scripts/run_frontend_workspace_command.py -- npm exec playwright install --with-deps chromium',
            'Frontend E2E',
            'python3 scripts/run_frontend_workspace_command.py -- npm run test:e2e:ci',
        ),
        readme_markers=('run_release_verification.sh --with-frontend', 'Frontend E2E'),
        stage='verification',
        risk_surface='frontend_health',
        blocking_by_default=True,
        notes=('前端 E2E 是操作面最小健康门。',),
    ),
    'ros_smoke': ReleaseGateEntry(
        gate_id='ros_smoke',
        title='Mock system web bridge launch smoke',
        entrypoint='./scripts/run_release_verification.sh --with-ros-smoke',
        script_paths=('scripts/run_release_verification.sh',),
        workflow_markers=(
            'Mock system web bridge launch smoke',
            '--launch-file mock_system.launch.py',
            '--expected-node /robot_web_bridge',
        ),
        readme_markers=('Mock system web bridge launch smoke',),
        stage='verification',
        risk_surface='bridge_integration',
        blocking_by_default=True,
        notes=('ROS mock smoke 用于确认 web bridge 入口仍可起。',),
    ),
    'integrated_frontend_bridge_smoke': ReleaseGateEntry(
        gate_id='integrated_frontend_bridge_smoke',
        title='Integrated frontend + web bridge smoke',
        entrypoint='./scripts/run_release_verification.sh --with-integrated-frontend-smoke --skip-npm-ci',
        script_paths=('scripts/run_release_verification.sh',),
        workflow_markers=(
            'integrated_frontend_bridge_smoke:',
            'Integrated frontend + web bridge smoke',
            './scripts/run_release_verification.sh --with-integrated-frontend-smoke --skip-npm-ci',
        ),
        readme_markers=('Integrated frontend + web bridge smoke',),
        stage='verification',
        risk_surface='end_to_end_operator_path',
        blocking_by_default=True,
        notes=('前端与 bridge 集成烟测覆盖 9100/9001 入口的最小操作路径。',),
    ),
    'target_environment_acceptance': ReleaseGateEntry(
        gate_id='target_environment_acceptance',
        title='Target environment acceptance capture',
        entrypoint='./scripts/run_target_environment_acceptance.sh --allow-incomplete --output /tmp/target_environment_acceptance.json',
        script_paths=('scripts/run_target_environment_acceptance.sh',),
        workflow_markers=(
            'Target environment acceptance capture',
            './scripts/run_target_environment_acceptance.sh --allow-incomplete --output /tmp/target_environment_acceptance.json',
        ),
        readme_markers=('--config-path',),
        stage='verification',
        risk_surface='target_environment_evidence',
        blocking_by_default=False,
        notes=('目标环境验收采集存在环境依赖，默认不作为 PR 阻断。',),
    ),
}


def release_gate_entry(gate_id: str) -> ReleaseGateEntry | None:
    """Return one release-gate entry by stable identifier."""
    return _REGISTRY.get(str(gate_id or '').strip())



def release_gate_registry_payload() -> dict[str, dict[str, Any]]:
    return {gate_id: entry.to_dict() for gate_id, entry in sorted(_REGISTRY.items())}



def release_gate_workflow_required_strings() -> tuple[str, ...]:
    values: list[str] = [_VERIFY_WORKFLOW_ENTRYPOINT]
    for entry in _REGISTRY.values():
        values.extend(entry.workflow_markers)
    return tuple(dict.fromkeys(values))



def release_gate_readme_required_strings() -> tuple[str, ...]:
    values: list[str] = []
    for entry in _REGISTRY.values():
        values.extend(entry.readme_markers)
    return tuple(dict.fromkeys(values))



def validate_release_gate_registry() -> list[str]:
    errors: list[str] = []
    titles: set[str] = set()
    for gate_id, entry in sorted(_REGISTRY.items()):
        if not entry.script_paths:
            errors.append(f'{gate_id}:missing_script_paths')
        if entry.title in titles:
            errors.append(f'{gate_id}:duplicate_title:{entry.title}')
        titles.add(entry.title)
        for path in entry.script_paths:
            if not (ROOT / path).is_file():
                errors.append(f'{gate_id}:missing_script:{path}')
        if not entry.workflow_markers:
            errors.append(f'{gate_id}:missing_workflow_markers')
        if not entry.readme_markers:
            errors.append(f'{gate_id}:missing_readme_markers')
    return errors
