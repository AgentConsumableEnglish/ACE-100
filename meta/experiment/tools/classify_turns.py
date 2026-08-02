#!/usr/bin/env python3
"""Classify every agent turn by what it did, per run.

POST-HOC EXPLORATORY. Not registered in the pre-registration and not part of
any H1/H2 readout. Added after the registered analysis was complete, to
explain a descriptive observation: per-run cost tracks turn count almost
exactly ($/turn is near-constant across arms), so "why did an arm cost more"
reduces to "why did it take more turns". This tool decomposes the turn gap.
Any paper text derived from it must be labeled post-hoc.

Turn accounting: a run's num_turns equals 1 + the number of tool-use rounds
(each tool_result returns as a user-role record). Classifying every tool_use
block therefore decomposes the turn count directly. Runs where assistant
messages carry parallel tool_use blocks are reported separately so the 1:1
assumption stays auditable.

Categories (a tool_use block gets exactly one):
  doc-read     read of a file in the arm's own docs snapshot (any channel)
  code-read    read of a non-doc file (source, config, testdata)
  search       discovery without opening a named file (grep/glob/find/ls)
  edit         Edit/Write/MultiEdit, or a shell redirect that writes a file
  test         go test / test-running make targets
  build        go build / go vet / compile-only make targets
  generate     go run of a generator (mdatagen, chloggen, schemagen)
  vcs          git commands that are not reads of file content
  network      outbound access (curl/wget/gh) - see audit/network-sweep.json
  orient       pure navigation or environment probing (pwd, cd, env, go env)
               with no other act in the command
  subagent     Task/Agent delegation
  plan         agent self-management: todo-list bookkeeping (TaskCreate/
               TaskUpdate/TodoWrite) and tool-schema lookup (ToolSearch)
  other        anything unmatched

Output: data/turn-classes.jsonl (one record per run) and a per-arm summary
plus the ace-vs-original decomposition on stdout.

Usage: classify_turns.py [--data-dir ...] [--arms-dir ...]
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

import docs_recount as dr

SEED = 20260801  # same seed as the registered analysis

CATEGORIES = ["doc-read", "code-read", "search", "edit", "test", "build",
              "lint", "deps", "generate", "vcs", "network", "orient",
              "subagent", "plan", "other"]

NET = re.compile(r"\b(curl|wget|gh)\b")
GIT = re.compile(r"\bgit\b")
GIT_READ = re.compile(r"\bgit\s+(show|diff|log|cat-file|blame|status)\b")
GO_TEST = re.compile(r"\bgo\s+test\b|\bmake\s+[\w-]*test[\w-]*\b|\bgotestsum\b")
GO_BUILD = re.compile(r"\bgo\s+(build|vet)\b|\bmake\s+(build|all|otelcorecol)\b")
LINT = re.compile(r"\bgofmt\b|\bgolangci-lint\b|\bgoimports\b|\bmake\s+(lint|fmt|impi|misspell)\b")
DEPS = re.compile(r"\bgo\s+(mod|get|list\s+-m)\b|\bmake\s+gotidy\b")
GENERATE = re.compile(r"\bgo\s+run\b|\bmdatagen\b|\bchloggen\b|\bschemagen\b"
                      r"|\bmake\s+(gen[\w-]*|chlog[\w-]*|genotelcorecol|update-otel)\b")
SEARCH_CMD = re.compile(r"^(grep|rg|find|fd|tree|wc|which|ls)\b")
READER_CMD = re.compile(r"^(cat|head|tail|less|more|sed|awk|od|diff|nl)\b")
ORIENT_CMD = re.compile(r"^(pwd|cd|echo|env|export|true|date|uname|whoami)\b")
WRITE_REDIR = re.compile(r"(?<![>\d])>(?!>)\s*[\w./-]+|>>\s*[\w./-]+|\btee\b")
SED_INPLACE = re.compile(r"\bsed\s+[^|;]*-i\b")
# Prefixes that hide the real command: env assignments, `timeout N`, `cd X &&`,
# `sudo`, `time`. Head-based matching must see past them.
ENV_PREFIX = re.compile(r"^(?:\w+=(?:\"[^\"]*\"|'[^']*'|\S*)\s+)+")
RUN_PREFIX = re.compile(r"^(?:(?:timeout|sudo|time|nice|env|xargs(?:\s+-\S+)*)\s+"
                        r"(?:\d+\s+)?)+")


def strip_prefixes(unit: str) -> str:
    """Remove env assignments and runner prefixes so the head is the real cmd."""
    prev = None
    while prev != unit:
        prev = unit
        unit = ENV_PREFIX.sub("", unit).strip()
        unit = RUN_PREFIX.sub("", unit).strip()
    return unit


def effective_units(cmd: str) -> list:
    """Pipeline units with prefixes stripped, and bare `cd` chains dropped.

    `cd /ws && gofmt -l x.go` must classify as the gofmt, not the cd; but a
    command that is *only* `cd`/`pwd` is genuine orientation.
    """
    out = []
    for u in dr.split_units(cmd):
        u = strip_prefixes(u)
        # Only the first pipeline stage determines the act; later stages are
        # usually head/tail/grep filters on its output.
        head_stage = strip_prefixes(u.split("|")[0].strip())
        if head_stage:
            out.append(head_stage)
    return out


def classify_bash(cmd: str, matcher, touched_docs: bool) -> str:
    """Classify one Bash command. First match wins, most-specific first."""
    units = effective_units(cmd)
    # Drop pure-navigation units when the command does something else too.
    substantive = [u for u in units if not re.match(r"^(cd|pwd|echo|true)\b", u)]
    scope = " ; ".join(substantive) if substantive else cmd

    # Network first: an outbound fetch is the salient act regardless of what
    # else the compound command does.
    if NET.search(scope):
        return "network"
    if GO_TEST.search(scope):
        return "test"
    if LINT.search(scope):
        return "lint"
    if DEPS.search(scope):
        return "deps"
    if GENERATE.search(scope):
        return "generate"
    if GO_BUILD.search(scope):
        return "build"
    # A doc read is a doc read even when issued through git show/sed/cat.
    if touched_docs:
        return "doc-read"
    if GIT.search(scope):
        # git show/diff/log of file content is a read; other git is vcs.
        return "code-read" if GIT_READ.search(scope) else "vcs"
    if SED_INPLACE.search(scope) or WRITE_REDIR.search(scope):
        return "edit"
    if any(READER_CMD.match(u) for u in substantive):
        return "code-read"
    if any(SEARCH_CMD.match(u) for u in substantive):
        return "search"
    if not substantive and any(ORIENT_CMD.match(u) for u in units):
        return "orient"
    return "other"


def classify_run(transcript: Path, matcher) -> dict:
    """Return per-category tool_use counts for one run."""
    results, uses = {}, []
    parallel_msgs = 0
    for line in open(transcript, errors="replace"):
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = e.get("message") or {}
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        side = bool(e.get("isSidechain"))
        n_in_msg = 0
        for b in content:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                uses.append((b.get("name"), b.get("input") or {}, b.get("id"), side))
                n_in_msg += 1
            elif b.get("type") == "tool_result":
                results[b.get("tool_use_id")] = dr.result_text(b)
        if n_in_msg > 1:
            parallel_msgs += 1

    counts = defaultdict(int)
    for name, inp, uid, side in uses:
        out = results.get(uid, "")
        if name == "Read":
            fp = str(inp.get("file_path", ""))
            counts["doc-read" if matcher.resolve(fp) else "code-read"] += 1
        elif name in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
            counts["edit"] += 1
        elif name in ("Grep", "Glob"):
            blob = " ".join(str(inp.get(k, "")) for k in ("path", "glob", "pattern"))
            counts["doc-read" if matcher.paths_in(blob) else "search"] += 1
        elif name in ("Task", "Agent"):
            counts["subagent"] += 1
        elif name in ("TodoWrite", "ExitPlanMode", "TaskCreate", "TaskUpdate",
                      "TaskList", "TaskGet", "ToolSearch"):
            # Agent self-management: todo-list bookkeeping and tool-schema
            # lookup. Work about the work, not work on the repository.
            counts["plan"] += 1
        elif name in ("WebFetch", "WebSearch"):
            counts["network"] += 1
        elif name == "Bash":
            cmd = str(inp.get("command", ""))
            att = dr.attribute_bash(cmd, out, matcher)
            touched = bool(att) and att.get("attributed_chars", 0) > 0
            counts[classify_bash(cmd, matcher, touched)] += 1
        else:
            counts["other"] += 1
    return {"counts": dict(counts), "n_tool_uses": len(uses),
            "n_parallel_messages": parallel_msgs}


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    base = Path(__file__).resolve().parent.parent
    ap.add_argument("--data-dir", default=str(base / "data"))
    ap.add_argument("--arms-dir", default=str(base / "arms"))
    ap.add_argument("--bootstrap", type=int, default=10000,
                    help="bootstrap replicates for paired CIs")
    args = ap.parse_args()
    data = Path(args.data_dir)

    reps_n = args.bootstrap
    matchers = dr.build_matchers(Path(args.arms_dir))

    # Join to runs.jsonl for the harness turn count (audit of the 1:1 rule).
    turns = {}
    runs_path = data / "runs.jsonl"
    if runs_path.is_file():
        for line in open(runs_path):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            turns[(r["task_id"], r["arm"], int(r["trial"]))] = r["num_turns"]

    records = []
    for transcript in sorted(data.glob("runs/*/*/trial-*/transcript.jsonl")):
        parts = transcript.parts
        task_id, arm, trial = parts[-4], parts[-3], parts[-2]
        rec = classify_run(transcript, matchers[arm])
        tno = int(trial.split("-")[1])
        records.append({
            "task_id": task_id, "arm": arm, "trial": trial,
            "num_turns_harness": turns.get((task_id, arm, tno)),
            **rec,
        })
    out_path = data / "turn-classes.jsonl"
    with open(out_path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    by_arm = defaultdict(list)
    for r in records:
        by_arm[r["arm"]].append(r)

    def mean(xs):
        xs = list(xs)
        return sum(xs) / len(xs) if xs else 0.0

    print(f"classified {len(records)} runs -> {out_path}  (POST-HOC EXPLORATORY)")
    par = sum(r["n_parallel_messages"] for r in records)
    print(f"assistant messages carrying parallel tool_use blocks: {par} "
          f"(1 tool_use ~ 1 turn assumption)")
    print()
    hdr = f"{'arm':9} {'turns':>6} {'tools':>6} " + " ".join(f"{c[:8]:>8}" for c in CATEGORIES)
    print(hdr)
    for arm in ("original", "ace", "naive", "nodocs"):
        rs = by_arm.get(arm)
        if not rs:
            continue
        row = f"{arm:9} {mean(r['num_turns_harness'] or 0 for r in rs):>6.1f} " \
              f"{mean(r['n_tool_uses'] for r in rs):>6.1f} "
        row += " ".join(f"{mean(r['counts'].get(c, 0) for r in rs):>8.2f}"
                        for c in CATEGORIES)
        print(row)

    # ---- within-task paired deltas with hierarchical bootstrap CIs --------
    # Same estimation convention as analyze.py: resample tasks, then trials
    # within each sampled task, per arm; percentile 95% CI.
    tasks = sorted({r["task_id"] for r in records})
    cell = defaultdict(list)
    for r in records:
        cell[(r["task_id"], r["arm"])].append(r)

    def paired(metric, a, b, reps):
        """metric: record -> number. Returns (point, lo, hi, per_task)."""
        rng = random.Random(f"{SEED}:{metric.__name__ if hasattr(metric,'__name__') else 'm'}:{a}:{b}")

        def delta(sample, resample):
            acc = []
            for t in sample:
                A = [metric(x) for x in cell[(t, a)]]
                B = [metric(x) for x in cell[(t, b)]]
                if not A or not B:
                    continue
                if resample:
                    A = rng.choices(A, k=len(A))
                    B = rng.choices(B, k=len(B))
                acc.append(sum(A) / len(A) - sum(B) / len(B))
            return sum(acc) / len(acc) if acc else 0.0

        point = delta(tasks, False)
        reps_out = sorted(delta(rng.choices(tasks, k=len(tasks)), True)
                          for _ in range(reps))
        lo = reps_out[int(0.025 * reps)] if reps else None
        hi = reps_out[int(0.975 * reps)] if reps else None
        per_task = {}
        for t in tasks:
            A = [metric(x) for x in cell[(t, a)]]
            B = [metric(x) for x in cell[(t, b)]]
            if A and B:
                per_task[t] = sum(A) / len(A) - sum(B) / len(B)
        return point, lo, hi, per_task

    out: dict = {
        "status": "POST-HOC EXPLORATORY - not registered; not an H1/H2 readout",
        "seed": SEED, "bootstrap_replicates": reps_n,
        "turn_accounting": {
            "rule": "num_turns = 1 + tool_use blocks",
            "parallel_tool_use_messages": par,
        },
        "per_arm_mean": {
            arm: {"turns": mean(r["num_turns_harness"] or 0 for r in by_arm[arm]),
                  "tool_uses": mean(r["n_tool_uses"] for r in by_arm[arm]),
                  **{c: mean(r["counts"].get(c, 0) for r in by_arm[arm])
                     for c in CATEGORIES}}
            for arm in by_arm},
        "pairwise": {},
    }
    for a, b in (("ace", "original"), ("ace", "naive"),
                 ("naive", "original"), ("nodocs", "original")):
        turns = lambda r: r["num_turns_harness"] or 0
        p, lo, hi, pt = paired(turns, a, b, reps_n)
        block = {"total_turns": {"point": p, "ci95": [lo, hi], "per_task": pt,
                                 "excludes_zero": bool(lo is not None and (lo > 0 or hi < 0))},
                 "categories": {}}
        for c in CATEGORIES:
            cp, clo, chi, cpt = paired(lambda r, c=c: r["counts"].get(c, 0), a, b, reps_n)
            block["categories"][c] = {
                "point": cp, "ci95": [clo, chi], "per_task": cpt,
                "excludes_zero": bool(clo is not None and (clo > 0 or chi < 0))}
        out["pairwise"][f"{a}_vs_{b}"] = block

    ana = Path(args.data_dir).parent / "analysis"
    ana.mkdir(parents=True, exist_ok=True)
    (ana / "turn-decomposition.json").write_text(
        json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print()
    for pair, block in out["pairwise"].items():
        t = block["total_turns"]
        mark = "EXCLUDES 0" if t["excludes_zero"] else "includes 0"
        print(f"{pair:22} total turns {t['point']:+7.2f} "
              f"[{t['ci95'][0]:+.2f},{t['ci95'][1]:+.2f}]  {mark}")
        sig = [(c, v) for c, v in block["categories"].items() if v["excludes_zero"]]
        if sig:
            for c, v in sorted(sig, key=lambda kv: -abs(kv[1]["point"])):
                print(f"    {c:11} {v['point']:+6.2f} "
                      f"[{v['ci95'][0]:+.2f},{v['ci95'][1]:+.2f}]  excludes 0")
        else:
            print("    no individual category CI excludes zero")
    print(f"\nwrote {ana / 'turn-decomposition.json'}")


if __name__ == "__main__":
    main()
