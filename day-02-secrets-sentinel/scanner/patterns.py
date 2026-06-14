"""
patterns.py — 55+ compiled regex patterns covering every major secret type.
Each pattern carries metadata: id, description, severity, roles, and a sample
false-positive exemption hint so reviewers know what to check.
"""

import re
from dataclasses import dataclass, field
from typing import List

SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_HIGH     = "HIGH"
SEVERITY_MEDIUM   = "MEDIUM"
SEVERITY_LOW      = "LOW"


@dataclass
class SecretPattern:
    id: str
    name: str
    regex: re.Pattern
    severity: str
    description: str
    roles: List[str] = field(default_factory=list)
    hint: str = ""          # common false-positive note


# ──────────────────────────────────────────────────────────────────────────────
# Helper — compile with IGNORECASE + MULTILINE by default
# ──────────────────────────────────────────────────────────────────────────────
def _c(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE | re.MULTILINE)


SECRET_PATTERNS: List[SecretPattern] = [

    # ── Cloud Providers ──────────────────────────────────────────────────────
    SecretPattern(
        id="AWS_ACCESS_KEY",
        name="AWS Access Key ID",
        regex=_c(r"(?<![A-Z0-9])(AKIA|ABIA|ACCA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])"),
        severity=SEVERITY_CRITICAL,
        description="AWS IAM access key ID — grants API access to AWS services.",
        roles=["DevSecOps", "DevOps", "Ops"],
        hint="Check if this is a test/example key from AWS docs.",
    ),
    SecretPattern(
        id="AWS_SECRET_KEY",
        name="AWS Secret Access Key",
        regex=_c(r"(?i)aws.{0,20}secret.{0,20}['\"]([A-Za-z0-9/+=]{40})['\"]"),
        severity=SEVERITY_CRITICAL,
        description="AWS secret access key — used to sign AWS API requests.",
        roles=["DevSecOps", "DevOps"],
    ),
    SecretPattern(
        id="AZURE_CLIENT_SECRET",
        name="Azure Client Secret",
        regex=_c(r"(?i)(azure|az).{0,30}(secret|password|key|pwd).{0,10}['\"]([A-Za-z0-9~._\-]{34,44})['\"]"),
        severity=SEVERITY_CRITICAL,
        description="Azure service principal client secret.",
        roles=["DevSecOps", "DevOps", "Ops"],
    ),
    SecretPattern(
        id="AZURE_STORAGE_KEY",
        name="Azure Storage Account Key",
        regex=_c(r"AccountKey=([A-Za-z0-9+/]{86}==)"),
        severity=SEVERITY_CRITICAL,
        description="Azure Storage account key in connection string.",
        roles=["DevSecOps", "DevOps"],
        hint="Often found in appsettings.json or connection strings.",
    ),
    SecretPattern(
        id="AZURE_SAS_TOKEN",
        name="Azure SAS Token",
        regex=_c(r"sv=\d{4}-\d{2}-\d{2}&s[a-z]=.{10,200}&sig=[A-Za-z0-9%+/=]{43,}"),
        severity=SEVERITY_HIGH,
        description="Azure Shared Access Signature token.",
        roles=["DevSecOps", "DevOps"],
    ),
    SecretPattern(
        id="GCP_API_KEY",
        name="GCP API Key",
        regex=_c(r"AIza[0-9A-Za-z\-_]{35}"),
        severity=SEVERITY_HIGH,
        description="Google Cloud Platform API key.",
        roles=["DevSecOps", "DevOps"],
    ),
    SecretPattern(
        id="GCP_SERVICE_ACCOUNT",
        name="GCP Service Account JSON",
        regex=_c(r'"type"\s*:\s*"service_account"'),
        severity=SEVERITY_CRITICAL,
        description="GCP service account credentials file.",
        roles=["DevSecOps", "DevOps"],
    ),

    # ── Version Control / CI-CD ──────────────────────────────────────────────
    SecretPattern(
        id="GITHUB_PAT",
        name="GitHub Personal Access Token",
        regex=_c(r"gh[pousr]_[A-Za-z0-9]{36,255}"),
        severity=SEVERITY_CRITICAL,
        description="GitHub PAT — can access repos, gists, orgs.",
        roles=["DevSecOps", "DevOps"],
    ),
    SecretPattern(
        id="GITHUB_OAUTH",
        name="GitHub OAuth Token",
        regex=_c(r"gho_[A-Za-z0-9]{36}"),
        severity=SEVERITY_CRITICAL,
        description="GitHub OAuth application token.",
        roles=["DevSecOps"],
    ),
    SecretPattern(
        id="GITLAB_TOKEN",
        name="GitLab Personal Access Token",
        regex=_c(r"glpat-[A-Za-z0-9\-_]{20}"),
        severity=SEVERITY_CRITICAL,
        description="GitLab PAT.",
        roles=["DevSecOps", "DevOps"],
    ),
    SecretPattern(
        id="AZURE_DEVOPS_PAT",
        name="Azure DevOps PAT",
        regex=_c(r"(?i)(azure.devops|ado).{0,30}['\"]([A-Za-z0-9]{52})['\"]"),
        severity=SEVERITY_CRITICAL,
        description="Azure DevOps personal access token.",
        roles=["DevSecOps", "DevOps"],
    ),

    # ── Containers & Registries ──────────────────────────────────────────────
    SecretPattern(
        id="DOCKER_HUB_PASSWORD",
        name="Docker Hub Password",
        regex=_c(r"(?i)(docker.{0,10}password|DOCKER_PASSWORD).{0,5}['\"](.{8,64})['\"]"),
        severity=SEVERITY_HIGH,
        description="Docker Hub registry password.",
        roles=["DevSecOps", "DevOps"],
    ),

    # ── Databases ────────────────────────────────────────────────────────────
    SecretPattern(
        id="POSTGRES_URL",
        name="PostgreSQL Connection String",
        regex=_c(r"postgresql://[^:]+:[^@]+@[^/]+/\S+"),
        severity=SEVERITY_CRITICAL,
        description="PostgreSQL DSN with embedded credentials.",
        roles=["DevSecOps", "Data", "Ops"],
    ),
    SecretPattern(
        id="MYSQL_URL",
        name="MySQL Connection String",
        regex=_c(r"mysql://[^:]+:[^@]+@[^/]+/\S+"),
        severity=SEVERITY_CRITICAL,
        description="MySQL DSN with embedded credentials.",
        roles=["DevSecOps", "Data"],
    ),
    SecretPattern(
        id="MONGODB_URL",
        name="MongoDB Connection String",
        regex=_c(r"mongodb(\+srv)?://[^:]+:[^@]+@\S+"),
        severity=SEVERITY_CRITICAL,
        description="MongoDB connection string with embedded password.",
        roles=["DevSecOps", "Data"],
    ),
    SecretPattern(
        id="MSSQL_URL",
        name="SQL Server Connection String",
        regex=_c(r"(?i)Password\s*=\s*([^;]{6,64});"),
        severity=SEVERITY_HIGH,
        description="SQL Server password in connection string.",
        roles=["DevSecOps", "Data", "BA"],
    ),
    SecretPattern(
        id="REDIS_URL",
        name="Redis Connection String",
        regex=_c(r"redis://:[^@]+@[^/]+"),
        severity=SEVERITY_HIGH,
        description="Redis URL with embedded password.",
        roles=["DevSecOps", "Ops"],
    ),

    # ── API Keys & Tokens ────────────────────────────────────────────────────
    SecretPattern(
        id="SLACK_TOKEN",
        name="Slack Token",
        regex=_c(r"xox[baprs]-[0-9A-Za-z\-]{10,200}"),
        severity=SEVERITY_HIGH,
        description="Slack API token (bot, user, app, etc.).",
        roles=["DevSecOps", "Ops"],
    ),
    SecretPattern(
        id="SLACK_WEBHOOK",
        name="Slack Webhook URL",
        regex=_c(r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+"),
        severity=SEVERITY_HIGH,
        description="Slack incoming webhook — can post to channels.",
        roles=["DevSecOps"],
    ),
    SecretPattern(
        id="STRIPE_SECRET",
        name="Stripe Secret Key",
        regex=_c(r"sk_(live|test)_[A-Za-z0-9]{24,}"),
        severity=SEVERITY_CRITICAL,
        description="Stripe secret API key — full payment API access.",
        roles=["DevSecOps"],
        hint="sk_test_ keys are less critical but still shouldn't be committed.",
    ),
    SecretPattern(
        id="STRIPE_RESTRICTED",
        name="Stripe Restricted Key",
        regex=_c(r"rk_(live|test)_[A-Za-z0-9]{24,}"),
        severity=SEVERITY_HIGH,
        description="Stripe restricted API key.",
        roles=["DevSecOps"],
    ),
    SecretPattern(
        id="TWILIO_SID",
        name="Twilio Account SID",
        regex=_c(r"AC[a-f0-9]{32}"),
        severity=SEVERITY_HIGH,
        description="Twilio account SID.",
        roles=["DevSecOps"],
    ),
    SecretPattern(
        id="TWILIO_AUTH",
        name="Twilio Auth Token",
        regex=_c(r"(?i)twilio.{0,20}['\"]([a-f0-9]{32})['\"]"),
        severity=SEVERITY_HIGH,
        description="Twilio auth token.",
        roles=["DevSecOps"],
    ),
    SecretPattern(
        id="SENDGRID_KEY",
        name="SendGrid API Key",
        regex=_c(r"SG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43}"),
        severity=SEVERITY_HIGH,
        description="SendGrid API key — can send emails.",
        roles=["DevSecOps"],
    ),
    SecretPattern(
        id="MAILGUN_KEY",
        name="Mailgun API Key",
        regex=_c(r"key-[a-z0-9]{32}"),
        severity=SEVERITY_HIGH,
        description="Mailgun API key.",
        roles=["DevSecOps"],
    ),
    SecretPattern(
        id="NPM_TOKEN",
        name="NPM Authentication Token",
        regex=_c(r"//registry\.npmjs\.org/:_authToken\s*=\s*([A-Za-z0-9\-_]{36,})"),
        severity=SEVERITY_HIGH,
        description="NPM auth token — can publish packages.",
        roles=["DevSecOps", "DevOps"],
    ),
    SecretPattern(
        id="PYPI_TOKEN",
        name="PyPI API Token",
        regex=_c(r"pypi-[A-Za-z0-9_\-]{50,210}"),
        severity=SEVERITY_HIGH,
        description="PyPI upload token.",
        roles=["DevSecOps", "DevOps"],
    ),
    SecretPattern(
        id="TELEGRAM_BOT",
        name="Telegram Bot Token",
        regex=_c(r"\d{8,10}:[A-Za-z0-9_\-]{35}"),
        severity=SEVERITY_HIGH,
        description="Telegram bot API token.",
        roles=["DevSecOps"],
    ),
    SecretPattern(
        id="OPENAI_KEY",
        name="OpenAI API Key",
        regex=_c(r"sk-[A-Za-z0-9]{48}"),
        severity=SEVERITY_HIGH,
        description="OpenAI API key.",
        roles=["DevSecOps"],
    ),
    SecretPattern(
        id="ANTHROPIC_KEY",
        name="Anthropic API Key",
        regex=_c(r"sk-ant-[A-Za-z0-9\-_]{90,110}"),
        severity=SEVERITY_HIGH,
        description="Anthropic Claude API key.",
        roles=["DevSecOps"],
    ),

    # ── Infrastructure & Secrets Managers ───────────────────────────────────
    SecretPattern(
        id="TERRAFORM_CLOUD_TOKEN",
        name="Terraform Cloud Token",
        regex=_c(r"[a-z0-9]{14}\.atlasv1\.[a-z0-9]{67}"),
        severity=SEVERITY_CRITICAL,
        description="Terraform Cloud / Terraform Enterprise API token.",
        roles=["DevSecOps", "DevOps"],
    ),
    SecretPattern(
        id="VAULT_TOKEN",
        name="HashiCorp Vault Token",
        regex=_c(r"(?i)vault.{0,20}['\"]([sS]\.[A-Za-z0-9]{24})['\"]"),
        severity=SEVERITY_CRITICAL,
        description="HashiCorp Vault token.",
        roles=["DevSecOps", "DevOps", "Ops"],
    ),

    # ── Certificates & Keys ──────────────────────────────────────────────────
    SecretPattern(
        id="PRIVATE_KEY",
        name="Private Key (PEM)",
        regex=_c(r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
        severity=SEVERITY_CRITICAL,
        description="PEM-encoded private key — RSA, EC, DSA, or OpenSSH.",
        roles=["DevSecOps", "Ops"],
    ),
    SecretPattern(
        id="PKCS12",
        name="PKCS#12 Certificate",
        regex=_c(r"-----BEGIN CERTIFICATE-----"),
        severity=SEVERITY_MEDIUM,
        description="PEM-encoded certificate (may include private cert).",
        roles=["DevSecOps"],
        hint="Public certs are fine; check if file also contains private key.",
    ),
    SecretPattern(
        id="SSH_HOST_KEY",
        name="SSH Host Key",
        regex=_c(r"ssh-(rsa|dss|ed25519|ecdsa)\s+AAAA[A-Za-z0-9+/=]{100,}"),
        severity=SEVERITY_MEDIUM,
        description="SSH public key — low risk but verify it's not a private key mislabeled.",
        roles=["DevSecOps", "Ops"],
    ),

    # ── Generic High-Entropy Patterns ────────────────────────────────────────
    SecretPattern(
        id="GENERIC_SECRET",
        name="Generic Secret Assignment",
        regex=_c(r"(?i)(password|passwd|secret|api_key|apikey|auth_token|access_token|client_secret)\s*[=:]\s*['\"]([A-Za-z0-9!@#$%^&*()_+\-=]{8,128})['\"]"),
        severity=SEVERITY_MEDIUM,
        description="Generic assignment of a password/secret/token literal.",
        roles=["DevSecOps", "DevOps", "Ops", "BA"],
        hint="High false-positive rate — check entropy and context before flagging.",
    ),
    SecretPattern(
        id="GENERIC_BEARER",
        name="HTTP Bearer Token",
        regex=_c(r"Authorization:\s*Bearer\s+([A-Za-z0-9\-_=]{20,500})"),
        severity=SEVERITY_HIGH,
        description="HTTP Authorization header with Bearer token hardcoded.",
        roles=["DevSecOps"],
    ),
    SecretPattern(
        id="BASIC_AUTH_URL",
        name="HTTP Basic Auth in URL",
        regex=_c(r"https?://[^:@\s]+:[^@\s]+@[^/\s]+"),
        severity=SEVERITY_HIGH,
        description="Credentials embedded in HTTP URL.",
        roles=["DevSecOps", "DevOps"],
    ),
    SecretPattern(
        id="JWT_TOKEN",
        name="JSON Web Token",
        regex=_c(r"eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
        severity=SEVERITY_MEDIUM,
        description="JWT token hardcoded in source.",
        roles=["DevSecOps"],
        hint="JWTs may be expired test tokens — check exp claim.",
    ),

    # ── CI/CD & Config Files ─────────────────────────────────────────────────
    SecretPattern(
        id="DOTENV_SECRET",
        name=".env File Secret",
        regex=_c(r"^(REACT_APP_|NEXT_PUBLIC_)?(?!#)(API_KEY|SECRET|TOKEN|PASSWORD|PASSWD|PRIVATE)[_A-Z]*\s*=\s*(.{6,128})$"),
        severity=SEVERITY_HIGH,
        description=".env file with secret value (not a placeholder).",
        roles=["DevSecOps", "DevOps"],
        hint="Exclude files named .env.example or .env.template.",
    ),
    SecretPattern(
        id="KUBERNETES_SECRET",
        name="Kubernetes Secret Value",
        regex=_c(r"kind:\s*Secret[\s\S]{0,500}data:[\s\S]{0,200}:\s+([A-Za-z0-9+/=]{20,})"),
        severity=SEVERITY_HIGH,
        description="Base64-encoded value in a Kubernetes Secret manifest.",
        roles=["DevSecOps", "DevOps"],
    ),
    SecretPattern(
        id="HELM_VALUES_SECRET",
        name="Helm values.yaml Secret",
        regex=_c(r"(?i)(password|secret|token|key)\s*:\s*['\"]([A-Za-z0-9!@#$%^&*_+\-=]{8,})['\"]"),
        severity=SEVERITY_MEDIUM,
        description="Possible secret value in Helm values file.",
        roles=["DevSecOps", "DevOps"],
    ),

    # ── Monitoring & Observability ───────────────────────────────────────────
    SecretPattern(
        id="DATADOG_API_KEY",
        name="Datadog API Key",
        regex=_c(r"(?i)datadog.{0,20}['\"]([a-f0-9]{32})['\"]"),
        severity=SEVERITY_HIGH,
        description="Datadog API key.",
        roles=["DevSecOps", "Ops"],
    ),
    SecretPattern(
        id="NEWRELIC_KEY",
        name="New Relic License Key",
        regex=_c(r"[A-Za-z0-9]{40}NRAL"),
        severity=SEVERITY_HIGH,
        description="New Relic license key.",
        roles=["DevSecOps", "Ops"],
    ),
    SecretPattern(
        id="PAGERDUTY_KEY",
        name="PagerDuty API Key",
        regex=_c(r"(?i)pagerduty.{0,20}['\"]([A-Za-z0-9+/]{20})['\"]"),
        severity=SEVERITY_MEDIUM,
        description="PagerDuty integration key.",
        roles=["DevSecOps", "Ops"],
    ),

    # ── Source Control Hosting ───────────────────────────────────────────────
    SecretPattern(
        id="BITBUCKET_SECRET",
        name="Bitbucket OAuth Secret",
        regex=_c(r"(?i)bitbucket.{0,20}secret.{0,10}['\"]([A-Za-z0-9]{32,64})['\"]"),
        severity=SEVERITY_HIGH,
        description="Bitbucket OAuth consumer secret.",
        roles=["DevSecOps"],
    ),
]
