"""Resource tagging helpers — every provisioned resource on AWS and Azure
carries the same tag schema so cost reports, IAM scoping, and the teardown
workflow can all key off of it consistently.
"""

from __future__ import annotations

from .config import REQUIRED_TAG_KEYS, EnvironmentConfig


def build_tags(cfg: EnvironmentConfig) -> dict:
    """Return the canonical tag set for a given environment.

    AWS consumes this dict as-is (Key/Value tags). Azure consumes the same
    dict shape (ARM tags are also a flat string-to-string map), so one
    function serves both clouds.
    """
    return {
        "Environment": cfg.environment,
        "Owner": cfg.owner,
        "Project": cfg.project,
        "ManagedBy": "cloudenv-provisioner",
        "ExpiryDate": cfg.expiry_date.isoformat(),
        "Cloud": cfg.cloud,
    }


def validate_tags(tags: dict) -> list[str]:
    """Return the list of required tag keys missing from `tags`.

    An empty list means the resource is compliant. Used both as a unit-level
    check and as the basis for a CI/CD policy gate (e.g. fail terraform plan
    output that creates untagged resources).
    """
    return [key for key in REQUIRED_TAG_KEYS if key not in tags or not tags[key]]


def is_expired(tags: dict, today_iso: str | None = None) -> bool:
    """Check whether a resource's ExpiryDate tag has passed.

    Used by the teardown workflow as a belt-and-suspenders sweep in addition
    to the PR-merge trigger, so abandoned environments don't outlive their TTL.
    """
    from datetime import date

    expiry = tags.get("ExpiryDate")
    if not expiry:
        return False
    today = date.fromisoformat(today_iso) if today_iso else date.today()
    return date.fromisoformat(expiry) < today


def terraform_tags_block(tags: dict) -> str:
    """Render tags as an HCL map literal for injection into generated .tfvars."""
    lines = ["{"]
    for key, value in tags.items():
        lines.append(f'  {key} = "{value}"')
    lines.append("}")
    return "\n".join(lines)
