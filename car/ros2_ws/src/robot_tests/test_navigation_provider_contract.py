from __future__ import annotations

from robot_navigation.provider_contract import (
    ensure_provider_runtime_supported,
    navigation_provider_activation,
    navigation_provider_registry_payload,
    resolve_navigation_provider,
)


def test_nav2_provider_runs_from_separate_adapter_package() -> None:
    provider = resolve_navigation_provider('nav2_provider')
    activation = navigation_provider_activation('nav2_provider')
    assert ensure_provider_runtime_supported(provider) is provider
    assert activation['providerVisibility'] == 'experimental'
    assert activation['runtimeSupported'] is True
    assert activation['activationDecision'] == 'activate'
    assert activation['governanceLane']['packageName'] == 'robot_nav2_adapter'
    assert activation['governanceLane']['laneId'] == 'navigation.nav2_provider'


def test_simple_provider_remains_runtime_supported() -> None:
    provider = resolve_navigation_provider('simple_nav_provider')
    assert ensure_provider_runtime_supported(provider) is provider


def test_navigation_provider_activation_reports_packaged_experimental_provider() -> None:
    activation = navigation_provider_activation('nav2_provider')
    assert activation['runtimeSupported'] is True
    assert activation['activationDecision'] == 'activate'
    assert activation['blockingReason'] is None
    assert activation['mainlineEligible'] is False
    assert activation['rollbackEligible'] is True


def test_navigation_provider_registry_only_exposes_mainline_supported_backends() -> None:
    registry = navigation_provider_registry_payload()
    assert set(registry) == {'simple_nav_provider'}
