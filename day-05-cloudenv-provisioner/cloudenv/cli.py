"""CloudEnv Provisioner CLI.

    cloudenv tag      --env dev --owner jsmith --cloud aws
    cloudenv iam      --env qa  --owner jsmith --cloud azure --out ./generated
    cloudenv cost     --env dev --owner jsmith --cloud aws --threshold 25
    cloudenv tfvars   --env dev --owner jsmith --cloud aws --out ./terraform/aws

Designed to be called both by a developer locally and by the GitHub Actions
spin-up / teardown / cost-alert workflows.
"""

from __future__ import annotations

import json
import sys

import click

from .config import EnvironmentConfig
from .cost_report import check_threshold
from .iam_policy import generate_aws_policy, generate_azure_role_definition, write_policy_files
from .tagging import build_tags, validate_tags


@click.group()
@click.version_option()
def main() -> None:
    """CloudEnv Provisioner — Dev/QA cloud environment manager."""


def _build_cfg(env, owner, cloud, region, ttl, threshold) -> EnvironmentConfig:
    return EnvironmentConfig(
        environment=env,
        cloud=cloud,
        owner=owner,
        region=region,
        ttl_days=ttl,
        cost_threshold_usd=threshold,
    )


@main.command()
@click.option("--env", "env", required=True, type=click.Choice(["dev", "qa"]))
@click.option("--owner", required=True)
@click.option("--cloud", required=True, type=click.Choice(["aws", "azure"]))
@click.option("--region", default="us-east-1")
@click.option("--ttl", default=3, help="Days until ExpiryDate tag.")
def tag(env, owner, cloud, region, ttl) -> None:
    """Print the canonical tag set for an environment as JSON."""
    cfg = _build_cfg(env, owner, cloud, region, ttl, 25.0)
    tags = build_tags(cfg)
    missing = validate_tags(tags)
    click.echo(json.dumps(tags, indent=2))
    if missing:
        click.echo(f"WARNING: missing required tags: {missing}", err=True)
        sys.exit(1)


@main.command()
@click.option("--env", "env", required=True, type=click.Choice(["dev", "qa"]))
@click.option("--owner", required=True)
@click.option("--cloud", required=True, type=click.Choice(["aws", "azure"]))
@click.option("--out", default="./generated", help="Output directory for generated policy JSON.")
def iam(env, owner, cloud, out) -> None:
    """Generate the least-privilege IAM policy (AWS) or role definition (Azure)."""
    cfg = _build_cfg(env, owner, cloud, "us-east-1", 3, 25.0)
    aws_path, azure_path = write_policy_files(cfg, out)
    if cloud == "aws":
        click.echo(f"Wrote AWS IAM policy -> {aws_path}")
        click.echo(json.dumps(generate_aws_policy(cfg), indent=2))
    else:
        click.echo(f"Wrote Azure role definition -> {azure_path}")
        click.echo(json.dumps(generate_azure_role_definition(cfg), indent=2))


@main.command()
@click.option("--env", "env", required=True, type=click.Choice(["dev", "qa"]))
@click.option("--owner", required=True)
@click.option("--cloud", required=True, type=click.Choice(["aws", "azure"]))
@click.option("--amount", type=float, required=True, help="Cost amount in USD (normally pulled live via boto3 / Azure SDK).")
@click.option("--threshold", type=float, default=25.0)
@click.option("--fail-on-breach/--no-fail-on-breach", default=True)
def cost(env, owner, cloud, amount, threshold, fail_on_breach) -> None:
    """Evaluate a cost amount against the environment's threshold and emit an alert line."""
    result = check_threshold(cloud=cloud, environment=env, amount_usd=amount, threshold_usd=threshold)
    click.echo(result.to_alert_message())
    if result.over_threshold and fail_on_breach:
        sys.exit(1)


@main.command()
@click.option("--env", "env", required=True, type=click.Choice(["dev", "qa"]))
@click.option("--owner", required=True)
@click.option("--cloud", required=True, type=click.Choice(["aws", "azure"]))
@click.option("--region", default="us-east-1")
@click.option("--ttl", default=3)
@click.option("--threshold", type=float, default=25.0)
@click.option("--out", default=None, help="Output .tfvars.json path; defaults to terraform/<cloud>/generated.auto.tfvars.json")
def tfvars(env, owner, cloud, region, ttl, threshold, out) -> None:
    """Generate a Terraform .tfvars.json file (vars + tags) for one environment."""
    cfg = _build_cfg(env, owner, cloud, region, ttl, threshold)
    tags = build_tags(cfg)
    payload = {
        "environment": cfg.environment,
        "owner": cfg.owner,
        "project": cfg.project,
        "region": cfg.region if cloud == "aws" else None,
        "location": cfg.region if cloud == "azure" else None,
        "cost_threshold_usd": cfg.cost_threshold_usd,
        "tags": tags,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    out_path = out or f"terraform/{cloud}/generated.auto.tfvars.json"
    import os

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)
    click.echo(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
