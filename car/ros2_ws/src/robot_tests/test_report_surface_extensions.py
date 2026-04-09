from pathlib import Path


def test_frontend_report_panel_lists_platform_surfaces() -> None:
    panel = Path(__file__).resolve().parents[3] / 'robot_frontend' / 'src' / 'components' / 'ReportSummaryPanel.tsx'
    source = panel.read_text(encoding='utf-8')
    assert 'localizationSummary' in source
    assert 'hardwareInterfaceSummary' in source
    assert 'navigationStatus' in source
    assert 'navigationPath' in source
    assert 'runtimeSupervision' in source


def test_web_bridge_subscribes_platform_surface_reports() -> None:
    node_path = Path(__file__).resolve().parents[3] / 'ros2_ws' / 'src' / 'robot_web_bridge' / 'robot_web_bridge' / 'web_bridge_node.py'
    source = node_path.read_text(encoding='utf-8')
    assert '/robot/localization/summary' in source
    assert '/robot/hardware_interface/summary' in source
    assert '/robot/navigation/status' in source
    assert '/robot/navigation/path' in source
    assert '/robot/runtime/supervision' in source


def test_report_panel_mentions_typed_surface_kinds() -> None:
    node_path = Path(__file__).resolve().parents[3] / 'ros2_ws' / 'src' / 'robot_web_bridge' / 'robot_web_bridge' / 'web_bridge_node.py'
    source = node_path.read_text(encoding='utf-8')
    assert 'control_summary' in source
    assert 'monitor_summary' in source
    assert 'monitor_diagnostics' in source
    assert 'localization_summary' in source
    assert 'hardware_interface_summary' in source
    assert 'lifecycleManager' in source
    assert 'bondSupervision' in source
    assert 'recoveryPlan' in source


def test_generated_bridge_contract_declares_typed_report_kinds() -> None:
    root = Path(__file__).resolve().parents[3]
    source = (root / 'robot_frontend' / 'src' / 'generated' / 'bridgeContract.ts').read_text(encoding='utf-8')
    assert 'reportKindSchema' in source
    assert 'reportRuntimeSupervisionDetailsSchema' in source
    assert 'reportHardwareInterfaceSummaryDetailsSchema' in source
