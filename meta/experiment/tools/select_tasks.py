#!/usr/bin/env python3
"""Select experimental tasks from a repository's merged-PR history.

Implements the mechanical task-selection procedure registered in
meta/experiment/PREREGISTRATION.md (section 4). The procedure is deterministic
given the same repository state, filters, and seed; every filter decision is
recorded in the audit log so the paper's appendix can be generated from it.

Requires an authenticated `gh` CLI (https://cli.github.com).

Usage:
    select_tasks.py --repo OWNER/NAME [--n 6] [--seed 20260801]
                    [--window-months 18] [--out manifest.json]
                    [--drop PR_NUMBER --reason "..."]...

Output: a task manifest (JSON) with one entry per selected task, plus an audit
log of every candidate PR and the filter that excluded it. The `test_command`
field of each task is left null and must be filled in per-repository before
runs begin (a manifest with null test commands fails validation in run-cell).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import re
import subprocess
import sys
import time

# Filters registered in PREREGISTRATION.md §4. Do not change without an
# amendment to the pre-registration.
MIN_CHANGED_FILES = 2
MIN_CHANGED_LINES = 30
MAX_CHANGED_LINES = 400
MIN_BODY_CHARS = 200          # "self-contained description" floor when no linked issue
DOCS_ONLY_THRESHOLD = 0.8     # >80% of changed files being docs => "primarily documentation"
DOC_PATH_RE = re.compile(r"(^|/)(docs?|documentation|website)(/|$)|\.mdx?$", re.IGNORECASE)

STRATA = ("feature", "bugfix", "config-integration", "other")
FEATURE_RE = re.compile(r"\b(feat|feature|add|implement|support|introduce)\b", re.IGNORECASE)
BUGFIX_RE = re.compile(r"\b(fix|bug|regression|crash|incorrect|broken)\b", re.IGNORECASE)
CONFIG_RE = re.compile(r"\b(config|configuration|integration|plugin|option|setting|env)\b", re.IGNORECASE)


def gh_json(args: list[str], attempts: int = 4) -> object:
    """Run a gh command and parse its JSON output.

    Transient failures (network timeouts, 5xx, secondary rate limits) are
    retried with exponential backoff; only a persistent failure aborts."""
    delay = 5.0
    for attempt in range(1, attempts + 1):
        proc = subprocess.run(["gh", *args], capture_output=True, text=True)
        if proc.returncode == 0:
            return json.loads(proc.stdout)
        err = proc.stderr.strip()
        if attempt == attempts:
            sys.exit(f"gh {' '.join(args[:3])}... failed after {attempts} attempts: {err}")
        print(f"  retry {attempt}/{attempts - 1} after error: {err[:120]}", file=sys.stderr)
        time.sleep(delay)
        delay *= 2
    raise AssertionError("unreachable")


def list_merged_prs(repo: str, since: dt.date, limit: int) -> list[dict]:
    """First pass: list merged PRs in the window with cheap fields only."""
    return gh_json([
        "pr", "list", "-R", repo, "--state", "merged", "--limit", str(limit),
        "--search", f"merged:>={since.isoformat()}",
        "--json", "number,title,mergedAt,additions,deletions,labels,url",
    ])


def pr_detail(repo: str, number: int) -> dict:
    """Second pass: full detail for one PR."""
    return gh_json([
        "pr", "view", str(number), "-R", repo,
        "--json", ("number,title,body,url,files,labels,mergeCommit,"
                   "closingIssuesReferences,statusCheckRollup,baseRefName"),
    ])


def issue_detail(repo: str, number: int) -> dict:
    return gh_json(["issue", "view", str(number), "-R", repo, "--json", "number,title,body,url"])


def base_commit_of_merge(repo: str, merge_sha: str) -> str:
    """The task's starting state: first parent of the merge/squash commit."""
    data = gh_json(["api", f"repos/{repo}/commits/{merge_sha}"])
    parents = data.get("parents", [])
    if not parents:
        sys.exit(f"merge commit {merge_sha} has no parents")
    return parents[0]["sha"]


def ci_passed(rollup: list[dict]) -> str:
    """'pass' | 'fail' | 'unknown' from a statusCheckRollup list."""
    if not rollup:
        return "unknown"
    ok = {"SUCCESS", "NEUTRAL", "SKIPPED"}
    for check in rollup:
        state = check.get("conclusion") or check.get("state") or ""
        if state.upper() not in ok:
            return "fail"
    return "pass"


def docs_fraction(files: list[dict]) -> float:
    if not files:
        return 0.0
    doc_files = sum(1 for f in files if DOC_PATH_RE.search(f.get("path", "")))
    return doc_files / len(files)


def classify(title: str, labels: list[str], files: list[dict]) -> str:
    """Assign a stratum. Labels win over title keywords; config check runs first
    on file paths since config work often hides under feat/fix titles."""
    label_text = " ".join(labels).lower()
    config_paths = sum(
        1 for f in files
        if re.search(r"\.(ya?ml|toml|ini|json5?)$|(^|/)config", f.get("path", ""), re.IGNORECASE)
    )
    if BUGFIX_RE.search(label_text) or BUGFIX_RE.search(title.split(":")[0]):
        return "bugfix"
    if FEATURE_RE.search(label_text) or FEATURE_RE.search(title.split(":")[0]):
        return "feature"
    if config_paths >= len(files) / 2 or CONFIG_RE.search(title):
        return "config-integration"
    if BUGFIX_RE.search(title):
        return "bugfix"
    if FEATURE_RE.search(title):
        return "feature"
    return "other"


def clean_body(body: str, pr_url: str) -> str:
    """Strip spoilers: links to the PR itself, commit links, and inline diff hunks."""
    if not body:
        return ""
    body = body.replace(pr_url, "")
    body = re.sub(r"https://github\.com/\S+/(pull|commit)/\S+", "", body)
    body = re.sub(r"```diff.*?```", "", body, flags=re.DOTALL)
    return body.strip()


def stratified_sample(candidates: dict[str, list[dict]], n: int, rng: random.Random) -> list[dict]:
    """Round-robin across non-empty strata, seeded shuffle within each."""
    pools = {s: sorted(candidates.get(s, []), key=lambda p: p["number"]) for s in STRATA}
    for pool in pools.values():
        rng.shuffle(pool)
    picked: list[dict] = []
    order = [s for s in STRATA if pools[s]]
    i = 0
    while len(picked) < n and any(pools[s] for s in order):
        stratum = order[i % len(order)]
        if pools[stratum]:
            picked.append(pools[stratum].pop())
        i += 1
    return picked


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True, help="OWNER/NAME")
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--seed", type=int, default=20260801)
    ap.add_argument("--window-months", type=int, default=18)
    ap.add_argument("--limit", type=int, default=500, help="max merged PRs to consider in the first pass")
    ap.add_argument("--allow-unknown-ci", action="store_true",
                    help="treat PRs with no recorded checks as passing (log it)")
    ap.add_argument("--drop", type=int, action="append", default=[],
                    help="PR number to exclude (requires a matching --reason)")
    ap.add_argument("--reason", action="append", default=[],
                    help="logged reason for the corresponding --drop")
    ap.add_argument("--out", default="manifest.json")
    args = ap.parse_args()

    if len(args.drop) != len(args.reason):
        sys.exit("each --drop requires a matching --reason")
    drops = dict(zip(args.drop, args.reason))

    since = dt.date.today() - dt.timedelta(days=args.window_months * 30)
    audit: list[dict] = []

    print(f"Listing merged PRs in {args.repo} since {since} ...", file=sys.stderr)
    prs = list_merged_prs(args.repo, since, args.limit)
    print(f"  {len(prs)} merged PRs in window", file=sys.stderr)

    # Cheap first-pass filter on total changed lines before fetching detail.
    survivors = []
    for pr in prs:
        lines = pr["additions"] + pr["deletions"]
        if not (MIN_CHANGED_LINES <= lines <= MAX_CHANGED_LINES):
            audit.append({"pr": pr["number"], "excluded_by": "changed-lines", "value": lines})
            continue
        survivors.append(pr)
    print(f"  {len(survivors)} within {MIN_CHANGED_LINES}-{MAX_CHANGED_LINES} changed lines", file=sys.stderr)

    by_stratum: dict[str, list[dict]] = {s: [] for s in STRATA}
    for pr in survivors:
        d = pr_detail(args.repo, pr["number"])
        files = d.get("files", [])
        labels = [l["name"] for l in d.get("labels", [])]
        issues = d.get("closingIssuesReferences", [])
        body = d.get("body") or ""

        if pr["number"] in drops:
            audit.append({"pr": pr["number"], "excluded_by": "manual-drop", "reason": drops[pr["number"]]})
            continue
        if len(files) < MIN_CHANGED_FILES:
            audit.append({"pr": pr["number"], "excluded_by": "changed-files", "value": len(files)})
            continue
        if docs_fraction(files) > DOCS_ONLY_THRESHOLD:
            audit.append({"pr": pr["number"], "excluded_by": "primarily-docs"})
            continue
        if not issues and len(body.strip()) < MIN_BODY_CHARS:
            audit.append({"pr": pr["number"], "excluded_by": "no-issue-thin-body"})
            continue
        ci = ci_passed(d.get("statusCheckRollup") or [])
        if ci == "fail" or (ci == "unknown" and not args.allow_unknown_ci):
            audit.append({"pr": pr["number"], "excluded_by": f"ci-{ci}"})
            continue

        stratum = classify(d["title"], labels, files)
        d["_stratum"] = stratum
        d["_issues"] = issues
        by_stratum[stratum].append(d)

    counts = {s: len(v) for s, v in by_stratum.items()}
    print(f"  eligible by stratum: {counts}", file=sys.stderr)

    rng = random.Random(args.seed)
    picked = stratified_sample(by_stratum, args.n, rng)
    if len(picked) < args.n:
        print(f"WARNING: only {len(picked)} eligible tasks (wanted {args.n})", file=sys.stderr)

    tasks = []
    for d in picked:
        merge_sha = (d.get("mergeCommit") or {}).get("oid")
        if not merge_sha:
            sys.exit(f"PR #{d['number']} has no merge commit oid")
        issue_block = None
        if d["_issues"]:
            ref = d["_issues"][0]
            issue = issue_detail(args.repo, ref["number"])
            issue_block = {
                "number": issue["number"],
                "title": issue["title"],
                "body": clean_body(issue.get("body") or "", d["url"]),
            }
        tasks.append({
            "task_id": f"pr-{d['number']}",
            "pr_number": d["number"],
            "pr_url": d["url"],
            "stratum": d["_stratum"],
            "base_commit": base_commit_of_merge(args.repo, merge_sha),
            "reference_merge_commit": merge_sha,
            "prompt": {
                "issue": issue_block,
                "pr_title": d["title"],
                "pr_body": clean_body(d.get("body") or "", d["url"]),
            },
            "changed_files": len(d.get("files", [])),
            "changed_lines": sum(f.get("additions", 0) + f.get("deletions", 0) for f in d.get("files", [])),
            "test_command": None,
        })

    manifest = {
        "repo": args.repo,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "selection": {
            "seed": args.seed,
            "window_months": args.window_months,
            "n_requested": args.n,
            "filters": {
                "min_changed_files": MIN_CHANGED_FILES,
                "changed_lines": [MIN_CHANGED_LINES, MAX_CHANGED_LINES],
                "docs_only_threshold": DOCS_ONLY_THRESHOLD,
                "min_body_chars": MIN_BODY_CHARS,
                "allow_unknown_ci": args.allow_unknown_ci,
            },
            "eligible_by_stratum": counts,
        },
        "tasks": tasks,
        "audit_log": audit,
    }
    with open(args.out, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Wrote {len(tasks)} tasks to {args.out} ({len(audit)} exclusions logged)", file=sys.stderr)


if __name__ == "__main__":
    main()
