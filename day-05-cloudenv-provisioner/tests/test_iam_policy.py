from cloudenv.config import EnvironmentConfig
from cloudenv.iam_policy import generate_aws_policy, generate_azure_role_definition, write_policy_files


def _cfg(**overrides):
    base = dict(environment="dev", cloud="aws", owner="jsmith")
    base.update(overrides)
    return EnvironmentConfig(**base)


def test_aws_policy_scopes_to_environment_and_owner_tags():
    policy = generate_aws_policy(_cfg(environment="qa", owner="jsmith"))
    allow_stmt = policy["Statement"][0]
    condition = allow_stmt["Condition"]["StringEquals"]
    assert condition["aws:RequestTag/Environment"] == "qa"
    assert condition["aws:RequestTag/Owner"] == "jsmith"


def test_aws_policy_includes_required_service_actions():
    policy = generate_aws_policy(_cfg())
    actions = policy["Statement"][0]["Action"]
    assert "ec2:RunInstances" in actions
    assert "s3:CreateBucket" in actions
    assert "iam:PassRole" in actions


def test_aws_policy_denies_untagged_resource_creation():
    policy = generate_aws_policy(_cfg())
    deny_stmt = next(s for s in policy["Statement"] if s["Effect"] == "Deny")
    assert "ec2:RunInstances" in deny_stmt["Action"]


def test_aws_policy_does_not_grant_wildcard_iam_admin():
    policy = generate_aws_policy(_cfg())
    actions = policy["Statement"][0]["Action"]
    assert "iam:*" not in actions
    assert "iam:CreateUser" not in actions
    assert "iam:AttachUserPolicy" not in actions


def test_azure_role_scoped_to_single_resource_group():
    role = generate_azure_role_definition(_cfg(environment="dev", owner="jsmith"), subscription_id="sub-123")
    assert role["AssignableScopes"] == ["/subscriptions/sub-123/resourceGroups/rg-dev-jsmith"]


def test_azure_role_excludes_authorization_management():
    role = generate_azure_role_definition(_cfg())
    assert "Microsoft.Authorization/*/Write" in role["NotActions"]


def test_azure_role_is_custom():
    role = generate_azure_role_definition(_cfg())
    assert role["IsCustom"] is True


def test_write_policy_files_creates_both_outputs(tmp_path):
    cfg = _cfg(environment="dev", owner="jsmith")
    aws_path, azure_path = write_policy_files(cfg, str(tmp_path))
    assert (tmp_path / "dev-jsmith-aws-policy.json").exists()
    assert (tmp_path / "dev-jsmith-azure-role.json").exists()
    assert aws_path.endswith("dev-jsmith-aws-policy.json")
    assert azure_path.endswith("dev-jsmith-azure-role.json")
