from pydantic import Field

from pr_radar.contracts.base import StrictContract


class ScanPolicy(StrictContract):
    static_context_max_chars: int = Field(ge=0)
    blast_radius_max_dependents: int = Field(ge=0)
    include_file_contents: bool


DEFAULT_SCAN_POLICY = ScanPolicy(
    static_context_max_chars=12_000,
    blast_radius_max_dependents=25,
    include_file_contents=True,
)
