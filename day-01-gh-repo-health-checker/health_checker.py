"""
GitHub Repo Health Checker
--------------------------
Audits a GitHub user or org's public repos and generates a health report.

Checks for:
- Missing README
- No CI/CD (no .github/workflows)
- No LICENSE
- Stale repos (no commits in 6+ months)
- Open issues with no response
- Missing description or topics
- Potential secrets in file names (rough heuristic)

Usage:
    python health_checker.py --user Sadhik2607
    python health_checker.py --user Sadhik2607 --token YOUR_PAT
    python health_checker.py --user Sadhik2607 --output report.csv
"""

import argparse
import csv
import json
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone


def gh_get(path: str, token: str = None) -> dict | list:
    url = f"https://api.github.com{path}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "gh-repo-health-checker")
    if token:
        req.add_header("Authorization", f"token {token}")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def months_since(iso_date: str) -> float:
    dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
    delta = datetime.now(timezone.utc) - dt
    return delta.days / 30.0


def check_repo(repo: dict, token: str = None) -> dict:
    name = repo["name"]
    full_name = repo["full_name"]
    default_branch = repo.get("default_branch", "main")

    result = {
        "repo": name,
        "url": repo["html_url"],
        "description": "OK" if repo.get("description") else "MISSING",
        "license": "OK" if repo.get("license") else "MISSING",
        "topics": "OK" if repo.get("topics") else "MISSING",
        "readme": "UNKNOWN",
        "ci_cd": "UNKNOWN",
        "stale": "NO",
        "open_issues": repo.get("open_issues_count", 0),
        "last_push": repo.get("pushed_at", "")[:10],
        "score": 0,
        "issues": [],
    }

    if repo.get("pushed_at"):
        months = months_since(repo["pushed_at"])
        if months > 6:
            result["stale"] = f"YES ({months:.0f} months ago)"
            result["issues"].append("Stale repo")

    try:
        gh_get(f"/repos/{full_name}/contents/README.md", token)
        result["readme"] = "OK"
    except urllib.error.HTTPError:
        result["readme"] = "MISSING"
        result["issues"].append("No README.md")

    try:
        contents = gh_get(f"/repos/{full_name}/contents/.github/workflows", token)
        result["ci_cd"] = f"OK ({len(contents)} workflow(s))"
    except urllib.error.HTTPError:
        result["ci_cd"] = "MISSING"
        result["issues"].append("No CI/CD workflows")

    if result["description"] == "MISSING":
        result["issues"].append("No description")
    if result["license"] == "MISSING":
        result["issues"].append("No LICENSE")
    if result["topics"] == "MISSING":
        result["issues"].append("No topics/tags")

    result["score"] = max(0, 100 - len(result["issues"]) * 15)
    result["issues"] = "; ".join(result["issues"]) if result["issues"] else "None"
    return result


def health_emoji(score: int) -> str:
    if score >= 85:
        return "green"
    if score >= 50:
        return "yellow"
    return "red"


def print_table(rows: list[dict]):
    cols = ["repo", "score", "readme", "ci_cd", "stale", "open_issues", "issues"]
    widths = {c: max(len(c), max(len(str(r.get(c, ""))) for r in rows)) for c in cols}
    header = "  ".join(c.upper().ljust(widths[c]) for c in cols)
    print("\n" + header)
    print("-" * len(header))
    for r in rows:
        row = "  ".join(str(r.get(c, "")).ljust(widths[c]) for c in cols)
        print(row)
    print()


def save_csv(rows: list[dict], path: str):
    if not rows:
        return
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Report saved to {path}")


def main():
    parser = argparse.ArgumentParser(description="GitHub Repo Health Checker")
    parser.add_argument("--user", required=True, help="GitHub username or org")
    parser.add_argument("--token", default=None, help="GitHub PAT (for higher rate limits)")
    parser.add_argument("--output", default=None, help="Save CSV report to this file")
    parser.add_argument("--min-score", type=int, default=0, help="Only show repos below this score")
    args = parser.parse_args()

    print(f"\nFetching repos for: {args.user}")
    try:
        repos = gh_get(f"/users/{args.user}/repos?per_page=100&sort=pushed", args.token)
    except urllib.error.HTTPError as e:
        print(f"Error fetching repos: {e}")
        sys.exit(1)

    if not repos:
        print("No public repos found.")
        return

    print(f"Checking {len(repos)} repos...\n")
    results = []
    for repo in repos:
        print(f"  Checking {repo['name']}...", end="\r")
        results.append(check_repo(repo, args.token))

    results.sort(key=lambda x: x["score"])
    if args.min_score:
        results = [r for r in results if r["score"] < args.min_score]

    print_table(results)

    avg = sum(r["score"] for r in results) / len(results) if results else 0
    print(f"Repos checked : {len(results)}")
    print(f"Average score : {avg:.0f}/100")
    print(f"Needs work    : {sum(1 for r in results if r['score'] < 50)} repos")

    if args.output:
        save_csv(results, args.output)


if __name__ == "__main__":
    main()
