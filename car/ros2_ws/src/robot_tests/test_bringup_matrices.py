from robot_bringup.launch_profiles import get_launch_profile
from robot_bringup.matrix_contracts import load_bringup_matrices, profile_feature_matrix, startup_sequence_for_profile, surface_contract_for_profile


def test_bringup_matrices_load_expected_sections() -> None:
    matrices = load_bringup_matrices()
    assert 'phases' in matrices.capability_matrix
    assert 'surfaces' in matrices.surface_matrix
    assert 'startup' in matrices.failure_taxonomy


def test_profile_feature_matrix_uses_shared_contract() -> None:
    profile = get_launch_profile('hardware')
    matrix = profile_feature_matrix(profile)
    assert matrix['web_bridge'] is True
    assert matrix['mock_robot'] is False


def test_surface_contract_for_minimal_profile_disables_optional_surfaces() -> None:
    profile = get_launch_profile('minimal')
    contract = surface_contract_for_profile(profile)
    assert contract['backend']['enabled'] is True
    assert contract['web_bridge']['enabled'] is False
    assert contract['frontend']['enabled'] is False


def test_startup_sequence_is_derived_from_matrix_rules() -> None:
    profile = get_launch_profile('minimal')
    assert startup_sequence_for_profile(profile) == ('contracts', 'bridge', 'control', 'platform', 'lifecycle', 'decision')



def test_surface_contract_for_hardware_profile_exposes_frontend_health_probe() -> None:
    profile = get_launch_profile('hardware')
    contract = surface_contract_for_profile(profile)
    assert contract['frontend']['enabled'] is True
    assert contract['frontend']['required_nodes'] == ['robot_web_bridge']
    assert contract['frontend']['ready_topics'] == ['/robot/web_bridge/ready']
    assert contract['frontend']['require_operator_ready'] is True
    assert contract['frontend']['ready_http_urls'] == ['http://127.0.0.1:9100/api/v1/health']
