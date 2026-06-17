"""Least-privilege IAM policy / role generation for AWS and Azure.

Every environment gets its own scoped principal rather than reusing a broad
"DevQA" role: permissions are constrained to resources carrying that
environment's `Environment` + `Owner` tags, and to the specific service
actions the provisioner actually needs (EC2, S3, IAM passrole for AWS;
VM/storage/RG actions for Azure).
"""

from __future__ import annotations

import json

from .config import EnvironmentConfig

AWS_BASE_ACTIONS = {
    "ec2": [
        "ec2:RunInstances",
        "ec2:TerminateInstances",
        "ec2:StartInstances",
        "ec2:StopInstances",
        "ec2:DescribeInstances",
        "ec2:CreateTags",
    ],
    "s3": [
        "s3:CreateBucket",
        "s3:DeleteBucket",
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:PutBucketTagging",
    ],
    "iam": [
        "iam:PassRole",
        "iam:GetRole",
    ],
}


def generate_aws_policy(cfg: EnvironmentConfig) -> dict:
    """Build an AWS IAM policy document scoped to one environment via tag
    conditions, so a `dev-jsmith` principal cannot touch `qa-*` resources or
    anything outside this environment's tag set even though the action list
    is shared across environments.
    """
    actions = [a for group in AWS_BASE_ACTIONS.values() for a in group]
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": f"CloudEnv{cfg.environment.capitalize()}ScopedAccess",
                "Effect": "Allow",
                "Action": actions,
                "Resource": "*",
                "Condition": {
                    "StringEquals": {
                        "aws:RequestTag/Environment": cfg.environment,
                        "aws:RequestTag/Owner": cfg.owner,
                    }
                },
            },
            {
                "Sid": "CloudEnvDenyUntaggedCreate",
                "Effect": "Deny",
                "Action": ["ec2:RunInstances", "s3:CreateBucket"],
                "Resource": "*",
                "Condition": {
                    "Null": {
                        "aws:RequestTag/Environment": "true"
                    }
                },
            },
        ],
    }


def generate_azure_role_definition(cfg: EnvironmentConfig, subscription_id: str = "<subscription-id>") -> dict:
    """Build an Azure custom role definition scoped to a single resource
    group (one per environment), granting only VM/storage/network actions —
    no RBAC, policy, or subscription-level management permissions.
    """
    scope = f"/subscriptions/{subscription_id}/resourceGroups/rg-{cfg.name}"
    return {
        "Name": f"CloudEnv-{cfg.name}-Contributor",
        "IsCustom": True,
        "Description": f"Least-privilege role for the {cfg.environment} environment owned by {cfg.owner}.",
        "Actions": [
            "Microsoft.Compute/virtualMachines/*",
            "Microsoft.Storage/storageAccounts/*",
            "Microsoft.Network/virtualNetworks/*",
            "Microsoft.Network/networkInterfaces/*",
            "Microsoft.Resources/subscriptions/resourceGroups/read",
        ],
        "NotActions": [
            "Microsoft.Authorization/*/Write",
            "Microsoft.Authorization/*/Delete",
        ],
        "DataActions": [],
        "NotDataActions": [],
        "AssignableScopes": [scope],
    }


def write_policy_files(cfg: EnvironmentConfig, output_dir: str) -> tuple[str, str]:
    """Write the generated AWS policy and Azure role definition to disk as
    JSON, returning the two file paths. Terraform's `aws_iam_policy` and
    `azurerm_role_definition` resources both accept a JSON-string body, so
    these files are consumed directly via `file()`/`templatefile()`.
    """
    import os

    os.makedirs(output_dir, exist_ok=True)
    aws_path = os.path.join(output_dir, f"{cfg.name}-aws-policy.json")
    azure_path = os.path.join(output_dir, f"{cfg.name}-azure-role.json")

    with open(aws_path, "w") as f:
        json.dump(generate_aws_policy(cfg), f, indent=2)
    with open(azure_path, "w") as f:
        json.dump(generate_azure_role_definition(cfg), f, indent=2)

    return aws_path, azure_path
