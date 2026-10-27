from typing import Literal, TypeAlias

from pydantic import Field

from pr_radar.contracts.base import StrictContract


BlastRadiusAvailability: TypeAlias = Literal["available", "partial", "unavailable"]


class BlastRadiusDependent(StrictContract):
    changed_path: str
    dependent_path: str
    import_ref: str


class BlastRadiusBudget(StrictContract):
    max_dependents: int = Field(ge=0)
    emitted_dependents: int = Field(ge=0)
    omitted_dependents: int = Field(ge=0)


class BlastRadiusSummary(StrictContract):
    availability: BlastRadiusAvailability
    reason_code: str
    changed_paths: tuple[str, ...]
    direct_dependents: tuple[BlastRadiusDependent, ...] = ()
    dependent_count: int = Field(ge=0)
    budget: BlastRadiusBudget
    truncated: bool
