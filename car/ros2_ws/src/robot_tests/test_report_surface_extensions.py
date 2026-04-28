from pathlib import Path
import json
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]


def test_frontend_report_panel_lists_platform_surfaces() -> None:
    panel = ROOT / 'robot_frontend' / 'src' / 'components' / 'ReportSummaryPanel.tsx'
    source = panel.read_text(encoding='utf-8')
    assert 'localizationSummary' in source
    assert 'hardwareInterfaceSummary' in source
    assert 'navigationStatus' in source
    assert 'voiceIngressHealth' in source
    assert 'navigationPath' in source
    assert 'runtimeSupervision' in source


def test_web_bridge_subscribes_platform_surface_reports() -> None:
    node_path = ROOT / 'ros2_ws' / 'src' / 'robot_web_bridge' / 'robot_web_bridge' / 'web_bridge_node.py'
    source = node_path.read_text(encoding='utf-8')
    assert '/robot/localization/summary' in source
    assert '/robot/hardware_interface/summary' in source
    assert '/robot/navigation/status' in source
    assert '/robot/voice/ingress_health' in source
    assert '/robot/navigation/path' in source
    assert '/robot/runtime/supervision' in source


def test_report_surface_kinds_and_runtime_supervision_fields_are_wired() -> None:
    node_path = ROOT / 'ros2_ws' / 'src' / 'robot_web_bridge' / 'robot_web_bridge' / 'web_bridge_node.py'
    node_source = node_path.read_text(encoding='utf-8')
    assert 'on_control_summary' in node_source
    assert 'on_monitor_summary' in node_source
    assert 'on_voice_ingress_health' in node_source
    assert 'on_runtime_supervision' in node_source

    surface_path = ROOT / 'ros2_ws' / 'src' / 'robot_web_bridge' / 'robot_web_bridge' / 'components' / 'observability_surface.py'
    surface_source = surface_path.read_text(encoding='utf-8')
    assert 'control_summary' in surface_source
    assert 'monitor_summary' in surface_source
    assert 'monitor_diagnostics' in surface_source
    assert 'localization_summary' in surface_source
    assert 'hardware_interface_summary' in surface_source
    assert 'voice_ingress_health' in surface_source
    assert 'runtimeSupervision' in surface_source
    assert 'lifecycleManager' in surface_source
    assert 'bondSupervision' in surface_source
    assert 'recoveryPlan' in surface_source
    assert 'orchestrationComponents' in surface_source


def test_generated_bridge_contract_declares_typed_report_kinds_and_registry_closure() -> None:
    source = (ROOT / 'robot_frontend' / 'src' / 'generated' / 'bridgeContract.ts').read_text(encoding='utf-8')
    contract_payload = json.loads((ROOT / 'robot_frontend' / 'src' / 'generated' / 'reportSurfaceContract.json').read_text(encoding='utf-8'))
    assert 'reportKindSchema' in source
    assert 'REPORT_SURFACE_KEYS' in source
    assert 'REPORT_SURFACE_KIND_TO_KEY' in source
    assert 'REPORT_SURFACE_KEY_TO_KIND' in source
    assert 'reportRuntimeSupervisionDetailsSchema' in source
    assert 'reportRuntimeSupervisionComponentSchema' in source
    assert 'reportHardwareInterfaceSummaryDetailsSchema' in source
    assert 'voice_ingress_health' in source
    assert 'surfaceId' in source
    assert 'surfaceAuthorityModel' in source
    report_kinds = sorted(str(item['kind']) for item in contract_payload['reports'].values())
    assert 'voice_ingress_health' in report_kinds
    assert 'orchestrationComponents' in contract_payload['reports']['runtimeSupervision']['detailPaths']


def test_report_kind_enum_closure_script_passes() -> None:
    script = ROOT / 'scripts' / 'check_report_kind_enum_closure.py'
    result = subprocess.run([sys.executable, str(script)], cwd=str(ROOT), check=True, text=True, capture_output=True)
    payload = json.loads(result.stdout)
    assert payload['status'] == 'ok'
    assert 'voice_ingress_health' in payload['registryKinds']
    assert payload['generatedEnumKinds'] == payload['registryKinds']


def test_runtime_supervision_consumer_closes_orchestration_components() -> None:
    panel = ROOT / 'robot_frontend' / 'src' / 'components' / 'ReportSummaryPanel.tsx'
    source = panel.read_text(encoding='utf-8')
    assert 'details.orchestrationComponents' in source
    assert 'orchestrationComponents.requiredForMainline' in source
    assert 'orchestrationComponents.missingFields' in source
