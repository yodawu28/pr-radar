from typing import Literal, TypeAlias

from pydantic import Field

from pr_radar.contracts.base import StrictContract


PrDeployment: TypeAlias = Literal["github_com", "github_self_hosted"]


class PrInput(StrictContract):
    provider: Literal["github"]
    deployment: PrDeployment
    repository: str
    pull_request_number: int = Field(ge=1)
    url: str
