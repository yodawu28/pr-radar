from typing import Literal, NamedTuple


RadarPillarKey = Literal[
    "security_supply_chain",
    "deployment_downtime",
    "blast_radius_downstream",
    "performance_footprint",
    "anti_bloat_dry",
    "test_integrity",
    "rollback_feature_flags",
]


class RadarPillarDefinition(NamedTuple):
    key: RadarPillarKey
    label: str


RADAR_PILLARS: tuple[RadarPillarDefinition, ...] = (
    RadarPillarDefinition("security_supply_chain", "Security & Supply Chain"),
    RadarPillarDefinition("deployment_downtime", "Deployment & Downtime"),
    RadarPillarDefinition("blast_radius_downstream", "Blast Radius & Downstream"),
    RadarPillarDefinition("performance_footprint", "Performance & Footprint"),
    RadarPillarDefinition("anti_bloat_dry", "Anti-Bloat & DRY"),
    RadarPillarDefinition("test_integrity", "Test Integrity & Edge Cases"),
    RadarPillarDefinition("rollback_feature_flags", "Rollback & Feature Flags"),
)
