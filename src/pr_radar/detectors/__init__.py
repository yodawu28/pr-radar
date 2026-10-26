"""Deterministic detector implementations."""

from pr_radar.detectors.deployment_downtime.migrations import detect_migration_risks
from pr_radar.detectors.security_supply_chain.dependencies import (
    detect_dependency_additions,
)
from pr_radar.detectors.static_risk import StaticDetector
from pr_radar.detectors.test_integrity.test_shape import detect_test_shape_risks


def get_default_static_detectors() -> tuple[StaticDetector, ...]:
    """Return the default Sprint 3 deterministic detector set."""
    return (
        detect_dependency_additions,
        detect_migration_risks,
        detect_test_shape_risks,
    )


__all__ = (
    "StaticDetector",
    "get_default_static_detectors",
)
