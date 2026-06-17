"""Environment configuration model shared by tagging, IAM, and cost modules."""

from dataclasses import dataclass, field
from datetime import date, timedelta

REQUIRED_TAG_KEYS = ["Environment", "Owner", "Project", "ManagedBy", "ExpiryDate"]

VALID_ENVIRONMENTS = ("dev", "qa")
VALID_CLOUDS = ("aws", "azure")


@dataclass
class EnvironmentConfig:
    """Describes a single isolated Dev/QA environment request."""

    environment: str           # "dev" or "qa"
    cloud: str                 # "aws" or "azure"
    owner: str                 # PR author / requester, used for tagging + IAM scoping
    project: str = "cloudenv-provisioner"
    ttl_days: int = 3          # auto-expiry window enforced by teardown workflow
    cost_threshold_usd: float = 25.0
    region: str = "us-east-1"  # AWS region or Azure location depending on `cloud`

    def __post_init__(self) -> None:
        if self.environment not in VALID_ENVIRONMENTS:
            raise ValueError(f"environment must be one of {VALID_ENVIRONMENTS}, got {self.environment!r}")
        if self.cloud not in VALID_CLOUDS:
            raise ValueError(f"cloud must be one of {VALID_CLOUDS}, got {self.cloud!r}")
        if self.ttl_days <= 0:
            raise ValueError("ttl_days must be positive")
        if self.cost_threshold_usd <= 0:
            raise ValueError("cost_threshold_usd must be positive")

    @property
    def expiry_date(self) -> date:
        return date.today() + timedelta(days=self.ttl_days)

    @property
    def name(self) -> str:
        """Resource-name-safe identifier, e.g. dev-jsmith or qa-jsmith."""
        safe_owner = "".join(c for c in self.owner.lower() if c.isalnum() or c == "-") or "anon"
        return f"{self.environment}-{safe_owner}"
