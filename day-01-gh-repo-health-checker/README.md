# GitHub Repo Health Checker

A CLI tool that audits a GitHub user or org's public repositories and produces a scored health report.

## What it checks

| Check | What it looks for |
|---|---|
| README | Is there a README.md? |
| CI/CD | Are there GitHub Actions workflows? |
| LICENSE | Does the repo have a license file? |
| Description | Is the repo description filled in? |
| Topics | Does the repo have tags/topics? |
| Staleness | No commits in the last 6 months? |
| Open issues | How many open issues are unresolved? |

Each repo gets a **health score out of 100** - minus 15 points per failed check.

## Usage

```bash
# Basic scan
python health_checker.py --user Sadhik2607

# With PAT for higher rate limits (5000 req/hr vs 60)
python health_checker.py --user Sadhik2607 --token YOUR_PAT

# Export to CSV
python health_checker.py --user Sadhik2607 --output report.csv

# Only show repos below 70 score
python health_checker.py --user Sadhik2607 --min-score 70
```

## Requirements

- Python 3.9+
- No external dependencies (uses stdlib only)

## Relevance

| Role | How this applies |
|---|---|
| DevOps | CI/CD coverage analysis across repos |
| DevSecOps | Flags repos missing security hygiene (license, secrets patterns) |
| Ops | Identifies stale/abandoned services |
| BA/BSA | Generates CSV reports for stakeholder review |
| Data Analyst | Output feeds directly into dashboards or Excel |
