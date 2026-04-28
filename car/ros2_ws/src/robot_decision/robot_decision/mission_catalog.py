from __future__ import annotations

"""Mission-catalog contracts for single-robot task orchestration.

The catalog formalizes product-visible patrol/task options without letting the
frontend or scheduler bypass decision/navigation authority. Entries resolve into
one single-robot mission request that ultimately delegates route execution to
``robot_navigation``.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from robot_decision.stage_execution import admit_stage_payload


@dataclass(frozen=True)
class MissionStage:
    """One operator-visible stage in a patrol mission graph."""

    stage_id: str
    title: str
    kind: str
    route_name: str = ''
    expected_goal_count: int = 0
    success_message: str = ''
    timeout_sec: float = 0.0
    verification_rules: dict[str, Any] = field(default_factory=dict)

    def raw_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            'stageId': self.stage_id,
            'title': self.title,
            'kind': self.kind,
            'routeName': self.route_name or None,
            'expectedGoalCount': int(self.expected_goal_count),
            'successMessage': self.success_message or None,
            'timeoutSec': round(max(0.0, float(self.timeout_sec or 0.0)), 3),
        }
        if self.verification_rules:
            payload['verificationRules'] = dict(self.verification_rules)
        return payload

    def to_dict(self) -> dict[str, Any]:
        return admit_stage_payload(self.raw_dict())


@dataclass(frozen=True)
class MissionCatalogEntry:
    """One single-robot mission entry exported to product interfaces."""

    mission_id: str
    title: str
    route_name: str
    task_profile: str
    auto_track: bool
    resume_policy: str
    stages: tuple[MissionStage, ...]
    operator_notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            'missionId': self.mission_id,
            'title': self.title,
            'routeName': self.route_name,
            'taskProfile': self.task_profile,
            'autoTrack': bool(self.auto_track),
            'resumePolicy': self.resume_policy,
            'stages': [stage.to_dict() for stage in self.stages],
            'operatorNotes': list(self.operator_notes),
        }


@dataclass(frozen=True)
class MissionCatalog:
    """Resolved single-robot mission catalog."""

    default_mission_id: str
    entries: dict[str, MissionCatalogEntry]
    catalog_source: str = 'in_repo_default'
    catalog_path: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'schemaVersion': '1.1.0',
            'deploymentModel': 'single_robot_only',
            'defaultMissionId': self.default_mission_id,
            'catalogSource': self.catalog_source,
            'catalogPath': self.catalog_path or None,
            'missions': {mission_id: entry.to_dict() for mission_id, entry in self.entries.items()},
        }

    def resolve(self, mission_id: str | None = None, *, route_name: str = '') -> MissionCatalogEntry:
        normalized_mission_id = str(mission_id or '').strip() or self.default_mission_id
        if normalized_mission_id not in self.entries:
            raise ValueError(f'unsupported mission_id: {mission_id!r}')
        entry = self.entries[normalized_mission_id]
        override_route = str(route_name or '').strip()
        if not override_route:
            return entry
        stages: list[MissionStage] = []
        for index, stage in enumerate(entry.stages):
            stages.append(MissionStage(
                stage_id=stage.stage_id,
                title=stage.title,
                kind=stage.kind,
                route_name=override_route if index == 0 else stage.route_name,
                expected_goal_count=stage.expected_goal_count,
                success_message=stage.success_message,
                timeout_sec=stage.timeout_sec,
                verification_rules=dict(stage.verification_rules),
            ))
        return MissionCatalogEntry(
            mission_id=entry.mission_id,
            title=entry.title,
            route_name=override_route,
            task_profile=entry.task_profile,
            auto_track=entry.auto_track,
            resume_policy=entry.resume_policy,
            stages=tuple(stages),
            operator_notes=entry.operator_notes,
        )


def _coerce_stage(item: dict[str, Any], *, fallback_id: str) -> MissionStage:
    verification_rules = item.get('verification_rules', {}) if isinstance(item.get('verification_rules', {}), dict) else {}
    stage = MissionStage(
        stage_id=str(item.get('stage_id', fallback_id) or fallback_id),
        title=str(item.get('title', fallback_id) or fallback_id),
        kind=str(item.get('kind', 'route') or 'route'),
        route_name=str(item.get('route_name', '') or ''),
        expected_goal_count=max(0, int(item.get('expected_goal_count', 0) or 0)),
        success_message=str(item.get('success_message', '') or ''),
        timeout_sec=max(0.0, float(item.get('timeout_sec', 0.0) or 0.0)),
        verification_rules=dict(verification_rules),
    )
    admission = stage.to_dict()
    if not bool(admission.get('supported', False)):
        raise ValueError(f"unsupported mission stage {stage.stage_id!r}: {admission.get('reason', 'unsupported_stage')}")
    return stage


def _coerce_entry(mission_id: str, item: dict[str, Any]) -> MissionCatalogEntry:
    route_name = str(item.get('route_name', 'default') or 'default')
    raw_stages = item.get('stages', [])
    if not isinstance(raw_stages, list) or not raw_stages:
        raw_stages = [
            {
                'stage_id': 'route_execution',
                'title': '路径执行',
                'kind': 'route',
                'route_name': route_name,
                'expected_goal_count': int(item.get('expected_goal_count', 0) or 0),
                'success_message': 'route_complete',
            }
        ]
    stages = tuple(_coerce_stage(stage if isinstance(stage, dict) else {}, fallback_id=f'{mission_id}_stage_{index}') for index, stage in enumerate(raw_stages, start=1))
    if stages and str(stages[0].kind or 'route').strip().lower() != 'route':
        raise ValueError(f'mission {mission_id} first stage must be route for patrol mainline admission')
    return MissionCatalogEntry(
        mission_id=mission_id,
        title=str(item.get('title', mission_id) or mission_id),
        route_name=route_name,
        task_profile=str(item.get('task_profile', 'route_patrol') or 'route_patrol'),
        auto_track=bool(item.get('auto_track', True)),
        resume_policy=str(item.get('resume_policy', 'restart_route') or 'restart_route'),
        stages=stages,
        operator_notes=tuple(str(note) for note in item.get('operator_notes', []) if str(note).strip()),
    )


def default_mission_catalog() -> MissionCatalog:
    default_entry = MissionCatalogEntry(
        mission_id='default_patrol',
        title='默认巡检',
        route_name='default',
        task_profile='route_patrol',
        auto_track=True,
        resume_policy='restart_route',
        stages=(
            MissionStage('route_execution', '路径执行', 'route', route_name='default', success_message='route_complete', timeout_sec=300.0),
            MissionStage('verification', '巡检收尾', 'verification', success_message='mission_complete', timeout_sec=10.0, verification_rules={'requiredNavigationState': 'route_completed', 'minimumCompletedGoals': 1, 'requirePositiveProgress': True, 'requireRuntimeReady': True}),
        ),
        operator_notes=('单机任务编排通过 decision->navigation 主链执行，不允许外部调度直驱导航。',),
    )
    return MissionCatalog(default_mission_id=default_entry.mission_id, entries={default_entry.mission_id: default_entry}, catalog_source='in_repo_default')


def load_mission_catalog(path_value: str | Path | None) -> MissionCatalog:
    source = Path(str(path_value or '').strip()) if path_value else None
    if source is not None and source.is_dir():
        source = source / 'mission_catalog.yaml'
    if source is None or not source.is_file():
        return default_mission_catalog()
    payload = yaml.safe_load(source.read_text(encoding='utf-8')) or {}
    config = payload.get('robot_decision_mission_catalog', payload) if isinstance(payload, dict) else {}
    params = config.get('ros__parameters', {}) if isinstance(config, dict) and isinstance(config.get('ros__parameters', {}), dict) else {}
    missions_raw = params.get('missions', {}) if isinstance(params.get('missions', {}), dict) else {}
    if not missions_raw:
        return default_mission_catalog()
    entries: dict[str, MissionCatalogEntry] = {}
    for mission_id, item in missions_raw.items():
        if not isinstance(item, dict):
            continue
        entries[str(mission_id)] = _coerce_entry(str(mission_id), item)
    if not entries:
        return default_mission_catalog()
    default_mission_id = str(params.get('default_mission_id', '') or '').strip() or next(iter(entries))
    if default_mission_id not in entries:
        raise ValueError(f'default_mission_id not found in mission catalog: {default_mission_id}')
    return MissionCatalog(default_mission_id=default_mission_id, entries=entries, catalog_source='yaml_config', catalog_path=str(source))


def mission_catalog_payload(path_value: str | Path | None) -> dict[str, Any]:
    return load_mission_catalog(path_value).to_dict()
