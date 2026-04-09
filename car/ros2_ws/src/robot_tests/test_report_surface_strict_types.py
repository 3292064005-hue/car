from pathlib import Path


def test_web_bridge_report_surface_no_longer_emits_raw_kind() -> None:
    root = Path(__file__).resolve().parents[3]
    source = (root / 'ros2_ws' / 'src' / 'robot_web_bridge' / 'robot_web_bridge' / 'web_bridge_node.py').read_text(encoding='utf-8')
    assert "'kind': 'raw'" not in source


def test_generated_bridge_contract_no_longer_contains_raw_report_kind() -> None:
    root = Path(__file__).resolve().parents[3]
    source = (root / 'robot_frontend' / 'src' / 'generated' / 'bridgeContract.ts').read_text(encoding='utf-8')
    assert 'reportRawEntrySchema' not in source
    assert "'raw'" not in source
