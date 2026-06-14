# SecretSentinel — Enterprise Secrets Scanner

> **Day 02** of [daily-builds](https://github.com/Sadhik2607/daily-builds) — one production-quality DevOps/DevSecOps tool per day.

SecretSentinel is a **zero-dependency, production-grade** secrets scanner with **55+ patterns**, Shannon entropy analysis, SARIF v2.1.0, Docker, Terraform Azure IaC, GitHub Actions CI, and a pre-commit hook.

## Features

| Feature | Details |
|---------|---------|
| 55+ detection patterns | AWS, Azure, GCP, GitHub, Stripe, Slack, Twilio, Postgres, MongoDB, JWT, PEM keys, K8s secrets, Terraform tokens |
| Shannon entropy analysis | Catches high-entropy strings pattern-matching misses — Base64, hex, mixed charsets |
| 5 output formats | terminal, json, sarif (GitHub Advanced Security), html (dashboard), csv (BI/Data) |
| SARIF v2.1.0 | Upload to GitHub Advanced Security — findings in the Security tab |
| Baseline suppression | Accept known false-positives by fingerprint |
| Docker | Multi-stage image, non-root user, volume-mount any repo |
| Terraform (Azure) | ACR + ACI + Key Vault + Storage + Log Analytics + Monitor alerts |
| GitHub Actions | Push/PR trigger, nightly cron, PR comment with summary, SARIF upload, Docker build |
| Pre-commit hook | Blocks commits with HIGH+ secrets, scans staged files only |
| .secretsignore | Gitignore-style exclusions |

## Quick Start

```bash
git clone https://github.com/Sadhik2607/daily-builds
cd daily-builds/day-02-secrets-sentinel
pip install -r requirements.txt
python main.py .
python main.py . --format sarif -o results.sarif
python main.py . --format html -o report.html
python main.py . --severity HIGH --fail-on CRITICAL
```

## Docker

```bash
docker build -t secretsentinel .
docker run --rm -v $(pwd):/scan-target secretsentinel
docker run --rm -v $(pwd):/scan-target secretsentinel --format sarif -o /scan-target/results.sarif
docker compose run --rm scan
docker compose run --rm scan-html
docker compose run --rm scan-sarif
```

## Pre-commit Hook

```bash
cp hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

## Deploy to Azure (Terraform)

```bash
cd terraform
terraform init
terraform plan -var="environment=dev" -var="location=Canada Central" -var="notification_email=you@example.com" -var="github_token=$GITHUB_TOKEN"
terraform apply -auto-approve
terraform output acr_push_command
terraform output trigger_scan_command
```

**What gets deployed:** Resource Group, Azure Container Registry (ACR), Azure Container Instance (scan runner), Key Vault (credentials), Storage Account (SARIF + HTML reports), Log Analytics Workspace, Azure Monitor Alert (email on CRITICAL findings).

## Output Formats

- **terminal** — colourised table with severity badges
- **json** — machine-readable with stats and fingerprints
- **sarif** — SARIF v2.1.0 for GitHub Advanced Security
- **html** — self-contained dashboard
- **csv** — flat export for BI / Data Analyst workflows

## Pattern Coverage

| Category | Patterns |
|----------|---------|
| Cloud (AWS, Azure, GCP) | 7 |
| VCS / CI-CD (GitHub, GitLab, ADO, Bitbucket) | 5 |
| Databases (Postgres, MySQL, MongoDB, MSSQL, Redis) | 5 |
| SaaS APIs (Stripe, Slack, Twilio, SendGrid, OpenAI...) | 12 |
| Infrastructure (Terraform Cloud, Vault) | 2 |
| Certificates & Keys (PEM, SSH, PKCS12) | 3 |
| Generic (passwords, Bearer tokens, Basic Auth, JWT) | 5 |
| CI/CD Config (.env, K8s Secrets, Helm values) | 3 |
| Monitoring (Datadog, New Relic, PagerDuty) | 3 |
| Entropy analysis | adaptive |

## Architecture

```
main.py (CLI)
    ├── scanner/detector.py    ← orchestrates everything
    │       ├── patterns.py   ← 55+ compiled regex patterns
    │       └── entropy.py    ← Shannon entropy analysis
    └── scanner/reporter.py   ← terminal / JSON / SARIF / HTML / CSV
```

## Target Roles

| Role | Value |
|------|-------|
| DevSecOps | Shift-left secrets detection, SAST integration, SARIF output |
| DevOps | Pre-commit hooks, GitHub Actions CI gate, Docker deployment |
| Ops/SRE | Audit K8s manifests, Helm charts, infra config repos |
| Data Analyst | CSV export for BI dashboards, security metrics trending |
| BA/BSA | HTML dashboard for stakeholder security posture reporting |

## CLI Reference

```
python main.py [TARGET] [OPTIONS]

--format, -f    terminal | json | sarif | html | csv
--output, -o    Write output to file
--severity, -s  Minimum: CRITICAL | HIGH | MEDIUM | LOW
--no-entropy    Disable entropy analysis
--baseline, -b  JSON baseline of accepted fingerprints
--fail-on       Exit 2 on findings at this level (default: CRITICAL)
--no-color      Disable ANSI colours
--verbose, -v   Print scan progress

Exit codes: 0=clean 1=findings-below-threshold 2=findings-at/above-threshold 3=error
```

## License

MIT — built by [Sadhik Ahamed](https://sadhik2607.github.io) as part of the daily-builds series.
