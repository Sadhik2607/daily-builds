## ☁️ CloudEnv Provisioner — Dev/QA Cloud Environment Manager

Provisions isolated, auto-expiring Dev/QA environments on **AWS** (EC2, S3, IAM) and **Azure**
(VM, Storage, custom roles) with **Terraform**, wires their full lifecycle into **GitHub Actions**
(spin up on PR open, tear down on merge), and enforces resource tagging + environment-scoped
least-privilege IAM/RBAC on both clouds so a `dev-jsmith` environment can never read or touch
`qa-anyone-else`'s resources.

### What It Does

| Capability | Detail |
|---|---|
| Multi-cloud provisioning | Terraform modules for AWS (EC2, S3, IAM, CloudWatch, Budgets) and Azure (VM, Storage, custom role, Monitor budget) |
| Lifecycle automation | GitHub Actions spin-up on `pull_request: opened`, teardown on `pull_request: closed` (covers merge and abandon) |
| Cost guardrails | AWS Budgets + CloudWatch billing alarm, Azure Consumption Budget + Monitor action group — both alert at 80% (forecast) and 100% (actual) of a configurable threshold |
| Tagging enforcement | `cloudenv.tagging` generates and validates a canonical `Environment / Owner / Project / ManagedBy / ExpiryDate / Cloud` tag set, shared by both clouds |
| Least-privilege IAM | `cloudenv.iam_policy` generates an AWS IAM policy scoped by `aws:RequestTag` conditions and an Azure custom role scoped to a single resource group — no environment can act outside its own tags/scope |
| CLI | `cloudenv tag / iam / cost / tfvars` — used by a developer locally and by every workflow above |

### Architecture

```
                    ┌────────────────────────────┐
                    │   Pull Request opened       │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────▼───────────────┐
                    │  cloudenv CLI (Python)        │
                    │  tag → iam → tfvars            │
                    └──────────────┬───────────────┘
                                   │ generated policies + .tfvars.json
              ┌────────────────────┼────────────────────┐
              │                                          │
   ┌──────────▼──────────┐                  ┌────────────▼───────────┐
   │ terraform/aws         │                  │ terraform/azure          │
   │ EC2 · S3 · IAM         │                  │ VM · Storage · Role     │
   │ Budgets · CloudWatch   │                  │ Consumption Budget      │
   └──────────┬──────────┘                  └────────────┬───────────┘
              │                                          │
              └────────────────────┬────────────────────┘
                                   │
                    ┌──────────────▼───────────────┐
                    │   PR merged / closed          │
                    │   → teardown.yml destroys      │
                    │     both clouds                │
                    └────────────────────────────────┘

           cost-alert.yml (daily, scheduled) ──► AWS Cost Explorer
                                              └──► Azure Cost Management
```

### Tag Schema (enforced on every resource, both clouds)

| Key | Example | Purpose |
|---|---|---|
| `Environment` | `dev` / `qa` | Drives IAM/RBAC scoping and cost grouping |
| `Owner` | `jsmith` | The PR author — also scopes IAM/RBAC |
| `Project` | `cloudenv-provisioner` | Groups cost across environments |
| `ManagedBy` | `cloudenv-provisioner` | Marks the resource as tool-managed (vs. hand-created) |
| `ExpiryDate` | `2026-06-20` | TTL backstop — swept by teardown even if the PR-merge trigger is missed |
| `Cloud` | `aws` / `azure` | Disambiguates resources with the same name across providers |

`cloudenv.tagging.validate_tags()` returns the list of missing required keys — wired into CI as a
gate so a PR can't introduce an untagged resource.

### Least-Privilege IAM, Concretely

**AWS** — the generated policy only allows EC2/S3/IAM actions when the target resource is being
created with matching `Environment`/`Owner` request tags, and explicitly **denies** EC2/S3 create
calls that omit the `Environment` tag entirely:

```json
{
  "Effect": "Allow",
  "Action": ["ec2:RunInstances", "s3:CreateBucket", "..."],
  "Condition": {
    "StringEquals": {
      "aws:RequestTag/Environment": "dev",
      "aws:RequestTag/Owner": "jsmith"
    }
  }
}
```

**Azure** — the generated custom role is assignable only at a single resource group's scope
(`rg-dev-jsmith`), with `Microsoft.Authorization/*` write/delete explicitly excluded so an
environment's role can never grant or escalate permissions for another environment.

### Quick Start

```bash
git clone https://github.com/Sadhik2607/daily-builds
cd daily-builds/day-05-cloudenv-provisioner
pip install -r requirements-dev.txt

# Generate the canonical tag set for a new Dev environment
python -m cloudenv.cli tag --env dev --owner jsmith --cloud aws

# Generate the scoped IAM policy (AWS) / role definition (Azure)
python -m cloudenv.cli iam --env dev --owner jsmith --cloud aws   --out ./generated
python -m cloudenv.cli iam --env dev --owner jsmith --cloud azure --out ./generated

# Generate terraform.tfvars.json from the same inputs
python -m cloudenv.cli tfvars --env dev --owner jsmith --cloud aws

# Provision (after configuring AWS/Azure credentials — see terraform/<cloud>/variables.tf)
cd terraform/aws && terraform init && terraform apply
```

### CLI Reference

```
Usage: cloudenv [OPTIONS] COMMAND [ARGS]...

Commands:
  tag      Print the canonical tag set for an environment as JSON
  iam      Generate the least-privilege IAM policy / Azure role definition
  cost     Evaluate a cost amount against the environment's threshold
  tfvars   Generate a Terraform .tfvars.json file (vars + tags)
```

### GitHub Actions

| Workflow | Trigger | Does |
|---|---|---|
| `spin-up.yml` | `pull_request: opened, reopened` | Generates tags/IAM via the CLI, `terraform apply` on AWS and Azure in parallel, comments on the PR |
| `teardown.yml` | `pull_request: closed` | `terraform destroy` on both clouds — runs whether the PR was merged or just closed |
| `cost-alert.yml` | Daily schedule + manual dispatch | Pulls live AWS Cost Explorer and Azure Cost Management data, fails the run if any environment is over threshold |
| `ci.yml` | Push/PR touching this folder | pytest + coverage, `terraform fmt`/`validate` for both clouds, Docker build smoke test |

Authentication uses OIDC federation (`aws-actions/configure-aws-credentials`, `azure/login`) —
no long-lived cloud keys stored as repository secrets.

### Tests

```bash
python -m pytest -v --cov=cloudenv
```

27 tests covering tag generation/validation, expiry logic, AWS policy/Azure role scoping
(including the "no wildcard IAM admin" and "no cross-environment access" assertions), and cost
threshold evaluation against mocked Cost Explorer / Cost Management responses.

### Stack

Terraform (AWS + Azure providers) · Python 3.11 · boto3 · Azure SDK (`azure-identity`,
`azure-mgmt-costmanagement`) · Click · pytest · GitHub Actions (OIDC) · Docker

### License

MIT
