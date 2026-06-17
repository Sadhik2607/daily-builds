from datetime import date, timedelta

import pytest

from cloudenv.config import EnvironmentConfig
from cloudenv.tagging import build_tags, is_expired, terraform_tags_block, validate_tags


def _cfg(**overrides):
    base = dict(environment="dev", cloud="aws", owner="jsmith", ttl_days=3)
    base.update(overrides)
    return EnvironmentConfig(**base)


def test_build_tags_contains_all_required_keys():
    tags = build_tags(_cfg())
    assert validate_tags(tags) == []


def test_build_tags_values():
    tags = build_tags(_cfg(owner="jsmith", environment="qa", cloud="azure"))
    assert tags["Environment"] == "qa"
    assert tags["Owner"] == "jsmith"
    assert tags["Cloud"] == "azure"
    assert tags["ManagedBy"] == "cloudenv-provisioner"


def test_build_tags_expiry_respects_ttl():
    tags = build_tags(_cfg(ttl_days=5))
    expected = (date.today() + timedelta(days=5)).isoformat()
    assert tags["ExpiryDate"] == expected


def test_validate_tags_flags_missing_keys():
    incomplete = {"Environment": "dev", "Owner": "jsmith"}
    missing = validate_tags(incomplete)
    assert "Project" in missing
    assert "ManagedBy" in missing
    assert "ExpiryDate" in missing
    assert "Environment" not in missing


def test_validate_tags_flags_empty_values():
    tags = build_tags(_cfg())
    tags["Owner"] = ""
    assert "Owner" in validate_tags(tags)


def test_is_expired_true_for_past_date():
    tags = {"ExpiryDate": "2020-01-01"}
    assert is_expired(tags, today_iso="2026-06-17") is True


def test_is_expired_false_for_future_date():
    tags = {"ExpiryDate": "2030-01-01"}
    assert is_expired(tags, today_iso="2026-06-17") is False


def test_is_expired_false_when_missing():
    assert is_expired({}) is False


def test_terraform_tags_block_renders_hcl_map():
    block = terraform_tags_block({"Environment": "dev", "Owner": "jsmith"})
    assert block.startswith("{")
    assert 'Environment = "dev"' in block
    assert block.endswith("}")


def test_invalid_environment_raises():
    with pytest.raises(ValueError):
        EnvironmentConfig(environment="prod", cloud="aws", owner="jsmith")


def test_invalid_cloud_raises():
    with pytest.raises(ValueError):
        EnvironmentConfig(environment="dev", cloud="gcp", owner="jsmith")


def test_name_is_slugified():
    cfg = EnvironmentConfig(environment="dev", cloud="aws", owner="J. Smith!!")
    assert cfg.name == "dev-jsmith"
