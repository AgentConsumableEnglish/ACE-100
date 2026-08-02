#!/usr/bin/env python3
"""tools/analyze.py -- final aggregation, estimation, and paper tables/figures
for the ACE-100 documentation experiment on open-telemetry/opentelemetry-collector.

Reads (all paths relative to EXPERIMENT_DIR, default meta/experiment/):
    data/runs.jsonl                                  -- one record per run (harness index)
    data/eval/<task_id>/<arm>/trial-<n>/tests.json   -- test outcomes per trial
    data/judge/scores.jsonl                          -- LLM-judge rubric scores
    data/judge/blinding.json                         -- blinded_id -> (task, arm, trial) map
    data/docs-consumption.jsonl                      -- Amendment-5 revision-2 recount
    audit/arm-gates/migration-cost.json              -- one-time ACE migration cost
    audit/network-sweep.json                         -- Amendment-5 sweep (leakage flags)

Writes (under --out, default <EXPERIMENT_DIR>/analysis/):
    summary.json      -- every number the paper needs, machine-readable
    tables.md         -- paper-ready markdown tables
    figures/*.png     -- matplotlib figures (skipped with a note if matplotlib
                         is unavailable)

Determinism: all randomness (hierarchical bootstrap resampling, strip-plot
jitter) comes from random.Random seeded with SEED = 20260801 plus a stable
per-statistic label. No timestamps are embedded in outputs, and JSON is
dumped with sorted keys, so identical inputs produce identical outputs.

Analysis conventions (documented here so reviewers can audit them):
  * Runs with status == "infra" are infrastructure failures and are excluded
    from ALL statistics (they reflect the harness, not the arm).
  * Cost / turns / wall-clock statistics are intention-to-treat over all
    non-infra runs (completed, failed, cap_turns, cap_wall) -- capped and
    failed runs consumed real tokens and belong in the cost picture.
  * completion_rate = completed / non-infra runs.
  * Test-pass and judge statistics are computed over the trials that have
    the corresponding artifact; missing artifacts are counted and reported,
    never silently imputed.
  * Pairwise comparisons are within-task: per task we compute the arm
    statistic (median cost, mean pass rate, mean judge score), form the
    ratio/delta per task, then summarize across tasks (median for cost
    ratios, mean for quality deltas).
  * Hierarchical bootstrap: resample tasks with replacement, then resample
    trials with replacement within each sampled task (independently per
    arm, fresh per occurrence of a task). Percentile 95% CIs.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SEED = 20260801  # registered seed for all local randomness

# CONFIG: root of the experiment data layout (relative to the repo root /
# wherever the tool is invoked from). Override with --experiment-dir.
DEFAULT_EXPERIMENT_DIR = Path("meta/experiment")

# CONFIG: the three registered arms, in canonical display order. H1/H2 and
# every pairwise comparison are defined over these three only.
ARMS = ["original", "ace", "naive"]

# CONFIG: all conditions including the Amendment-4 nodocs ablation, which is
# descriptive/exploratory only (arm summaries, manipulation check, value
# retention) and never enters the registered decision rules.
ALL_ARMS = ["original", "ace", "naive", "nodocs"]

# CONFIG: registered pairwise comparisons, each (numerator_arm, denominator_arm).
# Cost ratio = numerator / denominator; quality delta = numerator - denominator.
PAIRS = [("ace", "original"), ("ace", "naive"), ("naive", "original")]

# CONFIG: judge rubric dimensions as they appear in data/judge/scores.jsonl.
JUDGE_DIMS = ["correctness", "completeness", "convention"]

# Registered decision thresholds (from the pre-registration):
COST_RATIO_THRESHOLD = 0.80    # cost superiority: ace/original ratio <= 0.80
TESTPASS_NONINF_MARGIN = 0.05  # quality non-inferiority: within 5pp test-pass
RUBRIC_NONINF_MARGIN = 0.5     # quality non-inferiority: within 0.5 rubric pts

# Run statuses. "infra" is excluded from analysis entirely.
STATUS_COMPLETED = "completed"
STATUS_INFRA = "infra"


# ---------------------------------------------------------------------------
# Small numeric helpers (no numpy dependency for the statistics themselves)
# ---------------------------------------------------------------------------

def mean(xs):
    """Arithmetic mean; None on empty input."""
    xs = list(xs)
    if not xs:
        return None
    return sum(xs) / len(xs)


def median(xs):
    """Median; None on empty input."""
    xs = list(xs)
    if not xs:
        return None
    return float(statistics.median(xs))


def percentile(xs, p):
    """Linear-interpolation percentile (numpy 'linear' convention).

    p is in [0, 1]. Returns None on empty input.
    """
    xs = sorted(xs)
    if not xs:
        return None
    if len(xs) == 1:
        return float(xs[0])
    k = (len(xs) - 1) * p
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return float(xs[int(k)])
    return float(xs[lo] + (xs[hi] - xs[lo]) * (k - lo))


def iqr_bounds(xs):
    """Return (q25, q75) or (None, None) on empty input."""
    return percentile(xs, 0.25), percentile(xs, 0.75)


def rng_for(label):
    """Deterministic per-statistic RNG.

    random.Random seeded with a string is deterministic across runs and
    platforms (CPython hashes str seeds with SHA-512). Giving each statistic
    its own labeled stream means adding/removing one statistic does not
    perturb the resampling of the others.
    """
    return random.Random(f"{SEED}:{label}")


def normalize_trial(value):
    """Accept trial as int, numeric string, or 'trial-N'; return int or None."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    s = str(value)
    m = re.fullmatch(r"(?:trial-)?(\d+)", s)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_runs(runs_path, missing_notes):
    """Load data/runs.jsonl into {(task_id, arm, trial): record}.

    Duplicate keys keep the LAST record (a re-run supersedes an earlier
    attempt); duplicates are noted so the reader can audit them.
    """
    runs = {}
    n_dupes = 0
    n_bad = 0
    with open(runs_path, "r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                n_bad += 1
                continue
            task = rec.get("task_id")
            arm = rec.get("arm")
            trial = normalize_trial(rec.get("trial"))
            if task is None or arm not in ALL_ARMS or trial is None:
                n_bad += 1
                continue
            key = (task, arm, trial)
            if key in runs:
                n_dupes += 1
            runs[key] = rec
    if n_bad:
        missing_notes.append(f"runs.jsonl: skipped {n_bad} malformed/unrecognized line(s)")
    if n_dupes:
        missing_notes.append(f"runs.jsonl: {n_dupes} duplicate (task,arm,trial) record(s); kept last")
    return runs


def load_tests(eval_dir, missing_notes):
    """Load data/eval/<task>/<arm>/trial-<n>/tests.json into a dict by key."""
    tests = {}
    if not eval_dir.is_dir():
        missing_notes.append(f"eval directory missing: {eval_dir} (no test results at all)")
        return tests
    for path in sorted(eval_dir.glob("*/*/trial-*/tests.json")):
        # path parts: .../eval/<task>/<arm>/trial-<n>/tests.json
        task = path.parent.parent.parent.name
        arm = path.parent.parent.name
        trial = normalize_trial(path.parent.name)
        if arm not in ALL_ARMS or trial is None:
            missing_notes.append(f"eval: unrecognized path layout, skipped: {path}")
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                tests[(task, arm, trial)] = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            missing_notes.append(f"eval: unreadable tests.json skipped ({path}): {exc}")
    return tests


def load_blinding(blinding_path, missing_notes):
    """Load data/judge/blinding.json -> {blinded_id: (task, arm, trial)}.

    Accepts either {blinded_id: {task_id, arm, trial}} or a list of records
    (optionally wrapped in {"assignments": [...]}).
    """
    if not blinding_path.is_file():
        return {}
    try:
        with open(blinding_path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        missing_notes.append(f"judge: unreadable blinding.json ({exc}); blinded-only scores dropped")
        return {}
    if isinstance(raw, dict) and "assignments" in raw:
        raw = raw["assignments"]
    mapping = {}
    if isinstance(raw, dict):
        items = raw.items()
    elif isinstance(raw, list):
        items = ((rec.get("blinded_id"), rec) for rec in raw if isinstance(rec, dict))
    else:
        missing_notes.append("judge: blinding.json has an unrecognized shape; ignored")
        return {}
    for bid, rec in items:
        if bid is None or not isinstance(rec, dict):
            continue
        task = rec.get("task_id")
        arm = rec.get("arm")
        trial = normalize_trial(rec.get("trial"))
        if task is not None and arm in ALL_ARMS and trial is not None:
            mapping[bid] = (task, arm, trial)
    return mapping


def load_judge(scores_path, blinding_path, missing_notes):
    """Load data/judge/scores.jsonl -> {(task, arm, trial): {dim: mean-over-passes}}.

    Score records may identify the trial directly (task_id/arm/trial) or only
    via blinded_id, in which case blinding.json resolves the identity. Judge
    may run multiple passes per trial (pass_n); dimension scores are averaged
    across passes per trial.
    """
    if not scores_path.is_file():
        missing_notes.append(f"judge scores missing: {scores_path} (judge columns omitted)")
        return {}
    blinding = load_blinding(blinding_path, missing_notes)
    per_trial_lists = defaultdict(lambda: defaultdict(list))  # key -> dim -> [scores]
    n_unresolved = 0
    n_bad = 0
    with open(scores_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                n_bad += 1
                continue
            task = rec.get("task_id")
            arm = rec.get("arm")
            trial = normalize_trial(rec.get("trial"))
            if task is None or arm not in ALL_ARMS or trial is None:
                # fall back to the blinding map
                key = blinding.get(rec.get("blinded_id"))
                if key is None:
                    n_unresolved += 1
                    continue
            else:
                key = (task, arm, trial)
            for dim in JUDGE_DIMS:
                value = rec.get(dim)
                if isinstance(value, (int, float)):
                    per_trial_lists[key][dim].append(float(value))
    if n_bad:
        missing_notes.append(f"judge: skipped {n_bad} malformed score line(s)")
    if n_unresolved:
        missing_notes.append(
            f"judge: dropped {n_unresolved} score record(s) that could not be joined "
            "(no task/arm/trial and no blinding.json entry)"
        )
    # Average across passes per trial.
    judge = {}
    for key, dims in per_trial_lists.items():
        judge[key] = {dim: mean(vals) for dim, vals in dims.items() if vals}
    return judge


def load_migration_cost(path, missing_notes):
    """Read the migration ledger; return (standard_usd, harness_usd).

    The committed ledger (audit/arm-gates/migration-cost.json) carries
    per-session records plus a totals object. Registered analyses use the
    standard-priced total (the pre-registration fixes standard published
    prices); the harness-billed total is reported alongside. Accepts a bare
    number, top-level keys, or the nested totals object.
    """
    if not path.is_file():
        missing_notes.append(f"migration cost missing: {path} (break-even omitted)")
        return None, None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        missing_notes.append(f"migration cost unreadable ({exc}); break-even omitted")
        return None, None
    if isinstance(raw, (int, float)):
        return float(raw), None
    if isinstance(raw, dict):
        scopes = [raw]
        if isinstance(raw.get("totals"), dict):
            scopes.append(raw["totals"])
        standard = harness = None
        for scope in scopes:
            for key in ("total_cost_usd_standard", "cost_usd_standard"):
                value = scope.get(key)
                if standard is None and isinstance(value, (int, float)):
                    standard = float(value)
            value = scope.get("total_cost_usd_harness")
            if harness is None and isinstance(value, (int, float)):
                harness = float(value)
        if standard is None and isinstance(raw.get("sessions"), list):
            parts = [s.get("cost_usd_standard") for s in raw["sessions"]
                     if isinstance(s, dict)]
            if parts and all(isinstance(p, (int, float)) for p in parts):
                standard = float(sum(parts))
        if standard is not None or harness is not None:
            return standard, harness
    missing_notes.append("migration cost file has no recognized cost field; break-even omitted")
    return None, None


def load_consumption(path, missing_notes):
    """Load data/docs-consumption.jsonl (Amendment-5 revision-2 recount).

    Returns {(task, arm, trial): record}. The recount supersedes the
    collection-time per-run counters (Amendment 4), which are retained in
    runs.jsonl for comparison.
    """
    out = {}
    if not path.is_file():
        missing_notes.append(
            f"docs-consumption recount missing: {path}; manipulation check "
            "falls back to superseded collection-time counters")
        return out
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            task = rec.get("task_id")
            arm = rec.get("arm")
            trial = normalize_trial(rec.get("trial"))
            if task is None or arm not in ALL_ARMS or trial is None:
                continue
            out[(task, arm, trial)] = rec
    return out


def load_leakage_flags(path, missing_notes):
    """Class-(c) reference-solution-exposure flags from the Amendment-5 sweep.

    Reads audit/network-sweep.json; returns {(task, arm, trial), ...}. The
    registered analyses keep flagged runs (intention to treat); the flags
    drive the exploratory sensitivity re-analysis only.
    """
    if not path.is_file():
        missing_notes.append(
            f"network sweep missing: {path}; leakage sensitivity analysis omitted")
        return set()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            sweep = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        missing_notes.append(f"network sweep unreadable ({exc}); sensitivity omitted")
        return set()
    flags = set()
    for cell in sweep.get("cells", []):
        task = cell.get("task_id")
        arm = cell.get("arm")
        for trial_rec in cell.get("trials", []):
            trial = normalize_trial(trial_rec.get("trial"))
            if task is None or arm not in ALL_ARMS or trial is None:
                continue
            for ev in (trial_rec.get("events", [])
                       + trial_rec.get("missed_by_prepass", [])):
                if ev.get("classification") == "c":
                    flags.add((task, arm, trial))
                    break
    return flags


# ---------------------------------------------------------------------------
# Per (task x arm) aggregation
# ---------------------------------------------------------------------------

def aggregate(runs, tests, judge, consumption=None):
    """Build per-(task, arm) aggregates from the joined trial records.

    Returns (cells, tasks) where cells maps (task, arm) -> dict of raw lists
    and counts, and tasks is the sorted task list.
    """
    consumption = consumption or {}
    cells = {}
    for (task, arm, trial), rec in runs.items():
        cell = cells.setdefault((task, arm), {
            "n_total": 0, "n_infra": 0, "n_completed": 0,
            "costs": [], "turns": [], "walls": [],
            "docs_files": [], "docs_tokens": [],
            "explicit_doc_tokens": [], "total_doc_tokens": [],
            "suite": [], "ref": [],           # 0/1 per trial with a boolean result
            "n_with_tests": 0,
            "judge": {dim: [] for dim in JUDGE_DIMS},
            "n_with_judge": 0,
        })
        cell["n_total"] += 1
        if rec.get("status") == STATUS_INFRA:
            cell["n_infra"] += 1
            continue  # infra runs contribute to no statistic
        if rec.get("status") == STATUS_COMPLETED:
            cell["n_completed"] += 1
        for field, dest in (("cost_usd_standard", "costs"),
                            ("num_turns", "turns"),
                            ("wall_seconds", "walls"),
                            ("docs_files_read", "docs_files"),
                            ("docs_tokens_read_estimate", "docs_tokens")):
            value = rec.get(field)
            if isinstance(value, (int, float)):
                cell[dest].append(float(value))
        cons = consumption.get((task, arm, trial))
        if cons:
            for field, dest in (("explicit_doc_tokens", "explicit_doc_tokens"),
                                ("total_doc_tokens", "total_doc_tokens")):
                value = cons.get(field)
                if isinstance(value, (int, float)):
                    cell[dest].append(float(value))
        t = tests.get((task, arm, trial))
        if t is not None:
            got_any = False
            if isinstance(t.get("suite_pass"), bool):
                cell["suite"].append(1.0 if t["suite_pass"] else 0.0)
                got_any = True
            if isinstance(t.get("ref_tests_pass"), bool):
                cell["ref"].append(1.0 if t["ref_tests_pass"] else 0.0)
                got_any = True
            if got_any:
                cell["n_with_tests"] += 1
        j = judge.get((task, arm, trial))
        if j:
            cell["n_with_judge"] += 1
            for dim in JUDGE_DIMS:
                if j.get(dim) is not None:
                    cell["judge"][dim].append(j[dim])
    tasks = sorted({task for (task, _arm) in cells})
    return cells, tasks


def cell_stats(cell):
    """Summary statistics for one (task, arm) cell (JSON-serializable)."""
    q25, q75 = iqr_bounds(cell["costs"])
    n_analyzed = cell["n_total"] - cell["n_infra"]
    return {
        "n_total": cell["n_total"],
        "n_infra": cell["n_infra"],
        "n_analyzed": n_analyzed,
        "n_completed": cell["n_completed"],
        "completion_rate": (cell["n_completed"] / n_analyzed) if n_analyzed else None,
        "cost_median": median(cell["costs"]),
        "cost_q25": q25,
        "cost_q75": q75,
        "suite_pass_rate": mean(cell["suite"]),
        "ref_tests_pass_rate": mean(cell["ref"]),
        "n_with_tests": cell["n_with_tests"],
        "judge_means": {dim: mean(cell["judge"][dim]) for dim in JUDGE_DIMS},
        "n_with_judge": cell["n_with_judge"],
        "turns_median": median(cell["turns"]),
        "wall_seconds_median": median(cell["walls"]),
        "docs_files_read_median": median(cell["docs_files"]),
        "docs_tokens_read_median": median(cell["docs_tokens"]),
        "explicit_doc_tokens_median": median(cell["explicit_doc_tokens"]),
        "total_doc_tokens_median": median(cell["total_doc_tokens"]),
    }


# ---------------------------------------------------------------------------
# Pairwise comparisons + hierarchical bootstrap
# ---------------------------------------------------------------------------

def common_tasks(a_by_task, b_by_task):
    """Tasks with non-empty trial-level data in BOTH arms, sorted."""
    return sorted(t for t in a_by_task
                  if a_by_task.get(t) and b_by_task.get(t))


def paired_point(a_by_task, b_by_task, tasks, per_task_stat, combine, summarize):
    """Point estimate of a paired cross-task statistic.

    per_task_stat: list -> scalar (median for cost, mean for quality)
    combine:       (stat_a, stat_b) -> scalar or None (ratio or difference)
    summarize:     list of per-task values -> scalar (median or mean)
    Returns (summary, {task: per_task_value}).
    """
    per_task = {}
    for t in tasks:
        v = combine(per_task_stat(a_by_task[t]), per_task_stat(b_by_task[t]))
        if v is not None:
            per_task[t] = v
    values = [per_task[t] for t in sorted(per_task)]
    return (summarize(values) if values else None), per_task


def hierarchical_bootstrap(a_by_task, b_by_task, tasks, reps, rng,
                           per_task_stat, combine, summarize):
    """Two-level bootstrap replicates of a paired cross-task statistic.

    Level 1: resample tasks with replacement.
    Level 2: within each sampled task occurrence, independently resample the
             trial-level values with replacement, per arm.
    Returns the list of replicate statistics (length <= reps; a replicate is
    dropped only if every per-task value was undefined, e.g. zero denominators).
    """
    out = []
    n = len(tasks)
    if n == 0 or reps <= 0:
        return out
    for _ in range(reps):
        sampled = rng.choices(tasks, k=n)
        values = []
        for t in sampled:
            a = rng.choices(a_by_task[t], k=len(a_by_task[t]))
            b = rng.choices(b_by_task[t], k=len(b_by_task[t]))
            v = combine(per_task_stat(a), per_task_stat(b))
            if v is not None:
                values.append(v)
        if values:
            out.append(summarize(values))
    return out


def ratio(a, b):
    """a/b, guarding None and zero denominators."""
    if a is None or b is None or b == 0:
        return None
    return a / b


def diff(a, b):
    """a - b, guarding None."""
    if a is None or b is None:
        return None
    return a - b


def ci95(replicates):
    """Percentile 95% CI as [low, high], or [None, None] without replicates."""
    if not replicates:
        return [None, None]
    return [percentile(replicates, 0.025), percentile(replicates, 0.975)]


def build_pairwise(cells, tasks, reps):
    """All registered pairwise comparisons with point estimates and CIs.

    Returns (pairwise, bootstrap_reps) where bootstrap_reps keeps the raw
    replicate lists for the figures.
    """
    # Trial-level values per metric, per arm, per task.
    def by_task(arm, field):
        out = {}
        for t in tasks:
            cell = cells.get((t, arm))
            if cell and cell[field]:
                out[t] = list(cell[field])
        return out

    def judge_by_task(arm, dim):
        out = {}
        for t in tasks:
            cell = cells.get((t, arm))
            if cell and cell["judge"][dim]:
                out[t] = list(cell["judge"][dim])
        return out

    pairwise = {}
    replicate_store = {}
    for arm_a, arm_b in PAIRS:
        pair_name = f"{arm_a}_vs_{arm_b}"
        pair_out = {}

        # --- cost ratio of per-task medians, summarized as median over tasks
        a_costs = by_task(arm_a, "costs")
        b_costs = by_task(arm_b, "costs")
        cost_tasks = common_tasks(a_costs, b_costs)
        point, per_task = paired_point(a_costs, b_costs, cost_tasks,
                                       median, ratio, median)
        reps_list = hierarchical_bootstrap(
            a_costs, b_costs, cost_tasks, reps,
            rng_for(f"cost_ratio:{pair_name}"), median, ratio, median)
        pair_out["cost_ratio"] = {
            "definition": "median over tasks of (per-task median cost {a}) / (per-task median cost {b})".format(a=arm_a, b=arm_b),
            "point": point, "ci95": ci95(reps_list),
            "n_tasks": len(cost_tasks), "per_task": per_task,
        }
        replicate_store[(pair_name, "cost_ratio")] = reps_list

        # --- quality deltas (mean over tasks of per-task mean differences)
        for metric, field in (("suite_pass_delta", "suite"),
                              ("ref_tests_pass_delta", "ref")):
            a_vals = by_task(arm_a, field)
            b_vals = by_task(arm_b, field)
            m_tasks = common_tasks(a_vals, b_vals)
            point, per_task = paired_point(a_vals, b_vals, m_tasks, mean, diff, mean)
            reps_list = hierarchical_bootstrap(
                a_vals, b_vals, m_tasks, reps,
                rng_for(f"{metric}:{pair_name}"), mean, diff, mean)
            pair_out[metric] = {
                "definition": f"mean over tasks of (pass rate {arm_a} - pass rate {arm_b})",
                "point": point, "ci95": ci95(reps_list),
                "n_tasks": len(m_tasks), "per_task": per_task,
            }
            replicate_store[(pair_name, metric)] = reps_list

        for dim in JUDGE_DIMS:
            metric = f"judge_{dim}_delta"
            a_vals = judge_by_task(arm_a, dim)
            b_vals = judge_by_task(arm_b, dim)
            m_tasks = common_tasks(a_vals, b_vals)
            point, per_task = paired_point(a_vals, b_vals, m_tasks, mean, diff, mean)
            reps_list = hierarchical_bootstrap(
                a_vals, b_vals, m_tasks, reps,
                rng_for(f"{metric}:{pair_name}"), mean, diff, mean)
            pair_out[metric] = {
                "definition": f"mean over tasks of (mean {dim} {arm_a} - mean {dim} {arm_b})",
                "point": point, "ci95": ci95(reps_list),
                "n_tasks": len(m_tasks), "per_task": per_task,
            }
            replicate_store[(pair_name, metric)] = reps_list

        pairwise[pair_name] = pair_out
    return pairwise, replicate_store


# ---------------------------------------------------------------------------
# Decision rules, break-even, manipulation check
# ---------------------------------------------------------------------------

def build_decision(pairwise):
    """Evaluate the registered decision rules for ace vs original."""
    ace_orig = pairwise.get("ace_vs_original", {})

    cost = ace_orig.get("cost_ratio", {})
    cost_point = cost.get("point")
    cost_hi = (cost.get("ci95") or [None, None])[1]
    cost_out = {
        "criterion": f"ace/original task-median cost ratio <= {COST_RATIO_THRESHOLD}",
        "point_estimate": cost_point,
        "ci95": cost.get("ci95"),
        "point_meets": (cost_point is not None and cost_point <= COST_RATIO_THRESHOLD),
        "ci_upper_meets": (cost_hi is not None and cost_hi <= COST_RATIO_THRESHOLD),
    }

    # Quality non-inferiority: every component delta must be within its margin
    # (deltas are ace - original, so non-inferiority means delta >= -margin).
    components = {}
    for metric, margin in (("suite_pass_delta", TESTPASS_NONINF_MARGIN),
                           ("ref_tests_pass_delta", TESTPASS_NONINF_MARGIN),
                           *[(f"judge_{dim}_delta", RUBRIC_NONINF_MARGIN) for dim in JUDGE_DIMS]):
        comp = ace_orig.get(metric, {})
        point = comp.get("point")
        lo = (comp.get("ci95") or [None, None])[0]
        components[metric] = {
            "margin": margin,
            "point": point,
            "ci95": comp.get("ci95"),
            "point_meets": (point is not None and point >= -margin),
            "ci_lower_meets": (lo is not None and lo >= -margin),
        }
    evaluable = [c for c in components.values() if c["point"] is not None]
    quality_out = {
        "criterion": (f"ace vs original within {TESTPASS_NONINF_MARGIN*100:.0f}pp "
                      f"test-pass and {RUBRIC_NONINF_MARGIN} rubric points"),
        "components": components,
        # True only if every component with data meets its margin AND at least
        # one component had data; None when nothing is evaluable.
        "point_meets_all": (all(c["point_meets"] for c in evaluable) if evaluable else None),
        "ci_meets_all": (all(c["ci_lower_meets"] for c in evaluable) if evaluable else None),
        "n_components_evaluable": len(evaluable),
        "n_components_total": len(components),
    }
    return {"cost_superiority": cost_out, "quality_noninferiority": quality_out}


def build_break_even(cells, tasks, migration_cost_standard, migration_cost_harness):
    """Break-even: migration cost / per-run savings (original - ace medians).

    per_run_savings = median over tasks of (per-task original median cost -
    per-task ace median cost), over tasks with cost data in both arms. The
    registered basis is the standard-priced migration total; the
    harness-billed total is reported alongside.
    """
    savings_per_task = {}
    for t in tasks:
        orig = cells.get((t, "original"))
        ace = cells.get((t, "ace"))
        if orig and ace and orig["costs"] and ace["costs"]:
            savings_per_task[t] = median(orig["costs"]) - median(ace["costs"])
    savings = median([savings_per_task[t] for t in sorted(savings_per_task)]) if savings_per_task else None
    if migration_cost_standard is None or savings is None:
        runs_to_break_even = None
        note = "insufficient data (missing migration cost or paired cost data)"
    elif savings <= 0:
        runs_to_break_even = None
        note = ("does not break even: ace is not cheaper per run at the "
                "task-median level (negative per-run savings)")
    else:
        runs_to_break_even = migration_cost_standard / savings
        note = "runs_to_break_even = migration_cost_usd / per_run_savings_usd"
    return {
        "migration_cost_usd": migration_cost_standard,
        "migration_cost_usd_harness_billed": migration_cost_harness,
        "per_run_savings_usd": savings,
        "per_task_savings_usd": savings_per_task,
        "runs_to_break_even": runs_to_break_even,
        "note": note,
    }


def build_manipulation_check(cells, tasks, consumption):
    """Docs consumption per arm from the Amendment-5 revision-2 recount.

    The collection-time counters (docs_files_read / docs_tokens_read_estimate
    in runs.jsonl) are superseded by Amendment 4 but reported alongside for
    comparison.
    """
    by_arm_cons = defaultdict(list)
    for (task, arm, trial), rec in consumption.items():
        by_arm_cons[arm].append(rec)
    out = {}
    for arm in ALL_ARMS:
        legacy_tokens, n = [], 0
        for t in tasks:
            cell = cells.get((t, arm))
            if not cell:
                continue
            legacy_tokens.extend(cell["docs_tokens"])
            n += cell["n_total"] - cell["n_infra"]
        cons = by_arm_cons.get(arm, [])
        explicit = [r.get("explicit_doc_tokens", 0) for r in cons]
        ambient = [r.get("ambient_doc_tokens", 0) for r in cons]
        absent = [r.get("absent_at_start_calls", 0) for r in cons]
        out[arm] = {
            "n_runs": n,
            "n_runs_recounted": len(cons),
            "explicit_doc_tokens_mean": mean(explicit),
            "explicit_doc_tokens_median": median(explicit),
            "runs_with_contact": sum(1 for x in explicit if x > 0),
            "ambient_doc_tokens": (ambient[0] if ambient else None),
            "absent_at_start_events": sum(absent),
            "superseded_collection_tokens_mean": mean(legacy_tokens),
            "superseded_collection_tokens_median": median(legacy_tokens),
        }
    return out


def build_value_retention(cells, tasks):
    """Amendment-4 descriptive readout: per-task docs value and retention.

    docs_value = quality(original) - quality(nodocs) per task (the value the
    documentation adds over the no-docs floor); retention(arm) =
    (quality(arm) - quality(nodocs)) / docs_value where defined. Exploratory
    only; never enters the registered decision rules.
    """
    out = {"definition": ("per-task docs_value = metric(original) - "
                          "metric(nodocs); retention(arm) = (metric(arm) - "
                          "metric(nodocs)) / docs_value, reported only when "
                          "|docs_value| > 0"),
           "metrics": {}}
    for metric, field in (("suite_pass", "suite"), ("ref_tests_pass", "ref")):
        per_task = {}
        for t in tasks:
            row = {}
            vals = {}
            for arm in ALL_ARMS:
                cell = cells.get((t, arm))
                vals[arm] = mean(cell[field]) if cell and cell[field] else None
            row["by_arm"] = vals
            if vals.get("original") is not None and vals.get("nodocs") is not None:
                dv = vals["original"] - vals["nodocs"]
                row["docs_value"] = dv
                if abs(dv) > 0:
                    for arm in ("ace", "naive"):
                        if vals.get(arm) is not None:
                            row[f"retention_{arm}"] = (vals[arm] - vals["nodocs"]) / dv
            per_task[t] = row
        docs_values = [r["docs_value"] for r in per_task.values()
                       if r.get("docs_value") is not None]
        out["metrics"][metric] = {
            "per_task": per_task,
            "docs_value_mean": mean(docs_values),
            "n_tasks_with_floor": len(docs_values),
        }
    # Cost floor: nodocs vs original per-task median cost, descriptive.
    cost_rows = {}
    for t in tasks:
        row = {}
        for arm in ALL_ARMS:
            cell = cells.get((t, arm))
            row[arm] = median(cell["costs"]) if cell and cell["costs"] else None
        cost_rows[t] = row
    out["cost_medians_per_task"] = cost_rows
    return out


def build_arm_summary(cells, tasks):
    """Cross-task roll-up per arm (each task weighted equally).

    Includes the nodocs ablation (descriptive only; Amendment 4).
    """
    out = {}
    for arm in ALL_ARMS:
        task_cost_medians, completion, suite, ref = [], [], [], []
        judge_means = {dim: [] for dim in JUDGE_DIMS}
        n_runs = 0
        for t in tasks:
            cell = cells.get((t, arm))
            if not cell:
                continue
            n_analyzed = cell["n_total"] - cell["n_infra"]
            n_runs += n_analyzed
            if cell["costs"]:
                task_cost_medians.append(median(cell["costs"]))
            if n_analyzed:
                completion.append(cell["n_completed"] / n_analyzed)
            if cell["suite"]:
                suite.append(mean(cell["suite"]))
            if cell["ref"]:
                ref.append(mean(cell["ref"]))
            for dim in JUDGE_DIMS:
                if cell["judge"][dim]:
                    judge_means[dim].append(mean(cell["judge"][dim]))
        out[arm] = {
            "n_runs_analyzed": n_runs,
            "n_tasks_with_cost": len(task_cost_medians),
            "median_of_task_median_costs": median(task_cost_medians),
            "mean_completion_rate": mean(completion),
            "mean_task_suite_pass_rate": mean(suite),
            "mean_task_ref_tests_pass_rate": mean(ref),
            "mean_task_judge_means": {dim: mean(judge_means[dim]) for dim in JUDGE_DIMS},
        }
    return out


def build_sensitivity(runs, tests, judge, consumption, flags, reps):
    """Amendment-5 exploratory sensitivity: registered readouts with
    class-(c) reference-solution-exposure runs removed.

    The registered analyses keep every run (intention to treat); this block
    exists to show whether the leakage could have moved the readouts.
    """
    if not flags:
        return None
    kept = {k: v for k, v in runs.items() if k not in flags}
    cells, tasks = aggregate(kept, tests, judge, consumption)
    pairwise, _store = build_pairwise(cells, tasks, reps)
    decision = build_decision(pairwise)
    slim = {}
    for pair_name, pair in pairwise.items():
        slim[pair_name] = {
            metric: {"point": m["point"], "ci95": m["ci95"],
                     "n_tasks": m["n_tasks"]}
            for metric, m in pair.items()
        }
    return {
        "label": "exploratory sensitivity analysis (Amendment 5): runs with "
                 "class-(c) reference-solution exposure removed; registered "
                 "results are the intention-to-treat ones",
        "n_flagged_runs": len(flags),
        "flagged_runs": sorted(f"{t}/{a}/trial-{tr}" for (t, a, tr) in flags),
        "n_runs_analyzed": len(kept),
        "pairwise": slim,
        "decision": decision,
    }


# ---------------------------------------------------------------------------
# Output: tables.md
# ---------------------------------------------------------------------------

def fmt(x, nd=3, dash="--"):
    """Format a number for the markdown tables; dash for missing values."""
    if x is None:
        return dash
    return f"{x:.{nd}f}"


def fmt_pct(x, dash="--"):
    if x is None:
        return dash
    return f"{100 * x:.1f}%"


def fmt_ci(ci, nd=3):
    if not ci or ci[0] is None or ci[1] is None:
        return "--"
    return f"[{ci[0]:.{nd}f}, {ci[1]:.{nd}f}]"


def md_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)


def write_tables(out_dir, tasks, per_task_arm, arm_summary, pairwise,
                 decision, break_even, manipulation, value_retention,
                 sensitivity, missing_notes, args_reps):
    parts = []
    parts.append("# ACE-100 experiment: analysis tables")
    parts.append("")
    parts.append(f"Seed {SEED}; hierarchical bootstrap with {args_reps} replicates "
                 f"(percentile 95% CIs). Infra-failed runs excluded throughout; "
                 f"cost statistics are intention-to-treat over non-infra runs. "
                 f"The nodocs condition (Amendment 4) is descriptive only: H1/H2 "
                 f"and all pairwise comparisons are defined over the three "
                 f"registered arms.")
    parts.append("")

    # Table 1: arm-level summary
    parts.append("## Table 1. Arm-level summary (tasks weighted equally)")
    rows = []
    for arm in ALL_ARMS:
        s = arm_summary[arm]
        jm = s["mean_task_judge_means"]
        rows.append([
            arm, s["n_runs_analyzed"],
            fmt(s["median_of_task_median_costs"], 3),
            fmt_pct(s["mean_completion_rate"]),
            fmt_pct(s["mean_task_suite_pass_rate"]),
            fmt_pct(s["mean_task_ref_tests_pass_rate"]),
            *(fmt(jm[dim], 2) for dim in JUDGE_DIMS),
        ])
    parts.append(md_table(
        ["arm", "runs", "median task-median cost (USD)", "completion",
         "suite pass", "ref-tests pass", *[f"judge {d}" for d in JUDGE_DIMS]],
        rows))
    parts.append("")

    # Table 2: pairwise comparisons
    parts.append("## Table 2. Pairwise arm comparisons (within-task)")
    rows = []
    for arm_a, arm_b in PAIRS:
        pair_name = f"{arm_a}_vs_{arm_b}"
        pair = pairwise[pair_name]
        for metric in ["cost_ratio", "suite_pass_delta", "ref_tests_pass_delta",
                       *[f"judge_{d}_delta" for d in JUDGE_DIMS]]:
            m = pair[metric]
            if metric == "cost_ratio":
                point_s = fmt(m["point"], 3)
                ci_s = fmt_ci(m["ci95"], 3)
            elif metric.endswith("pass_delta"):
                point_s = (f"{100 * m['point']:+.1f}pp" if m["point"] is not None else "--")
                ci = m["ci95"]
                ci_s = (f"[{100*ci[0]:+.1f}pp, {100*ci[1]:+.1f}pp]"
                        if ci and ci[0] is not None else "--")
            else:
                point_s = (f"{m['point']:+.2f}" if m["point"] is not None else "--")
                ci_s = fmt_ci(m["ci95"], 2)
            rows.append([pair_name, metric, point_s, ci_s, m["n_tasks"]])
    parts.append(md_table(["comparison", "metric", "point", "95% CI", "n tasks"], rows))
    parts.append("")

    # Table 3: decision rules
    parts.append("## Table 3. Registered decision rules")
    cost = decision["cost_superiority"]
    quality = decision["quality_noninferiority"]
    rows = [[
        "cost superiority", cost["criterion"], fmt(cost["point_estimate"], 3),
        fmt_ci(cost["ci95"], 3),
        "MET" if cost["point_meets"] else "not met",
        "MET" if cost["ci_upper_meets"] else "not met",
    ]]
    parts.append(md_table(
        ["rule", "criterion", "point", "95% CI", "point verdict", "CI verdict"],
        rows))
    parts.append("")
    parts.append("Quality non-inferiority components (ace - original; "
                 "non-inferior when delta >= -margin):")
    rows = []
    for metric, comp in quality["components"].items():
        is_pp = metric.endswith("pass_delta")
        point_s = ((f"{100*comp['point']:+.1f}pp" if is_pp else f"{comp['point']:+.2f}")
                   if comp["point"] is not None else "--")
        margin_s = f"{100*comp['margin']:.0f}pp" if is_pp else f"{comp['margin']}"
        rows.append([
            metric, margin_s, point_s, fmt_ci(comp["ci95"], 3),
            "MET" if comp["point_meets"] else ("--" if comp["point"] is None else "not met"),
            "MET" if comp["ci_lower_meets"] else ("--" if comp["point"] is None else "not met"),
        ])
    parts.append(md_table(
        ["component", "margin", "delta (ace-original)", "95% CI",
         "point verdict", "CI verdict"], rows))
    overall = quality["point_meets_all"]
    parts.append("")
    parts.append(f"Quality non-inferiority overall (point estimates, "
                 f"{quality['n_components_evaluable']}/{quality['n_components_total']} "
                 f"components evaluable): "
                 f"{'MET' if overall else ('NOT MET' if overall is not None else 'not evaluable')}")
    parts.append("")

    # Table 4: break-even
    parts.append("## Table 4. Break-even")
    parts.append(md_table(
        ["migration cost (USD, standard prices)", "harness-billed (USD)",
         "per-run savings (USD, original - ace)", "runs to break even", "note"],
        [[fmt(break_even["migration_cost_usd"], 2),
          fmt(break_even["migration_cost_usd_harness_billed"], 2),
          fmt(break_even["per_run_savings_usd"], 4),
          fmt(break_even["runs_to_break_even"], 1),
          break_even["note"]]]))
    parts.append("")

    # Table 5: manipulation check (Amendment-5 revision-2 recount)
    parts.append("## Table 5. Manipulation check: docs consumption per arm "
                 "(revision-2 recount)")
    rows = []
    for arm in ALL_ARMS:
        m = manipulation[arm]
        rows.append([arm, m["n_runs"],
                     fmt(m["explicit_doc_tokens_mean"], 0),
                     fmt(m["explicit_doc_tokens_median"], 0),
                     f"{m['runs_with_contact']}/{m['n_runs_recounted']}",
                     fmt(m["ambient_doc_tokens"], 0),
                     m["absent_at_start_events"],
                     fmt(m["superseded_collection_tokens_mean"], 0)])
    parts.append(md_table(
        ["arm", "runs", "explicit doc tokens (mean)",
         "explicit doc tokens (median)", "runs w/ contact",
         "ambient tokens", "absent-at-start events",
         "superseded collection-time mean"], rows))
    parts.append("")
    parts.append("nodocs events are all flagged absent-at-start: content under "
                 "a doc path that did not exist when the run began (regenerated "
                 "by build tooling during the run, or audited solution-content "
                 "exposure).")
    parts.append("")

    # Table 6: full per (task x arm) detail
    parts.append("## Table 6. Per task x arm detail")
    rows = []
    for task in tasks:
        for arm in ALL_ARMS:
            s = per_task_arm.get(task, {}).get(arm)
            if s is None:
                continue
            cost_s = (f"{fmt(s['cost_median'], 3)} "
                      f"({fmt(s['cost_q25'], 3)}-{fmt(s['cost_q75'], 3)})"
                      if s["cost_median"] is not None else "--")
            jm = s["judge_means"]
            wall_min = (s["wall_seconds_median"] / 60.0
                        if s["wall_seconds_median"] is not None else None)
            rows.append([
                task, arm, f"{s['n_analyzed']}/{s['n_total']}",
                fmt_pct(s["completion_rate"]), cost_s,
                fmt_pct(s["suite_pass_rate"]), fmt_pct(s["ref_tests_pass_rate"]),
                *(fmt(jm[dim], 2) for dim in JUDGE_DIMS),
                fmt(s["turns_median"], 0), fmt(wall_min, 1),
                fmt(s["explicit_doc_tokens_median"], 0),
            ])
    parts.append(md_table(
        ["task", "arm", "n (analyzed/total)", "completion",
         "cost median (IQR) USD", "suite pass", "ref pass",
         *[f"judge {d}" for d in JUDGE_DIMS],
         "turns (med)", "wall min (med)", "docs tokens (med)"], rows))
    parts.append("")

    # Table 7: value retention vs the nodocs floor (Amendment 4, descriptive)
    parts.append("## Table 7. Value retention vs the nodocs floor "
                 "(descriptive; Amendment 4)")
    parts.append("")
    parts.append(value_retention["definition"])
    parts.append("")
    for metric, block in value_retention["metrics"].items():
        rows = []
        for t in tasks:
            row = block["per_task"].get(t, {})
            vals = row.get("by_arm", {})
            rows.append([
                t,
                *(fmt_pct(vals.get(arm)) for arm in ALL_ARMS),
                (f"{100 * row['docs_value']:+.1f}pp"
                 if row.get("docs_value") is not None else "--"),
                fmt(row.get("retention_ace"), 2),
                fmt(row.get("retention_naive"), 2),
            ])
        parts.append(f"### {metric}")
        parts.append(md_table(
            ["task", *ALL_ARMS, "docs value (orig-nodocs)",
             "retention ace", "retention naive"], rows))
        parts.append("")

    # Table 8: leakage sensitivity (Amendment 5, exploratory)
    if sensitivity is not None:
        parts.append("## Table 8. Sensitivity: class-(c) solution-exposure "
                     "runs removed (exploratory; Amendment 5)")
        parts.append("")
        parts.append(f"{sensitivity['n_flagged_runs']} flagged run(s): "
                     + ", ".join(sensitivity["flagged_runs"]))
        parts.append("")
        rows = []
        for pair_name, pair in sensitivity["pairwise"].items():
            for metric in ("cost_ratio", "suite_pass_delta",
                           "ref_tests_pass_delta"):
                m = pair.get(metric)
                if not m or m["point"] is None:
                    continue
                if metric == "cost_ratio":
                    point_s = fmt(m["point"], 3)
                    ci_s = fmt_ci(m["ci95"], 3)
                else:
                    point_s = f"{100 * m['point']:+.1f}pp"
                    ci = m["ci95"]
                    ci_s = (f"[{100*ci[0]:+.1f}pp, {100*ci[1]:+.1f}pp]"
                            if ci and ci[0] is not None else "--")
                rows.append([pair_name, metric, point_s, ci_s, m["n_tasks"]])
        parts.append(md_table(
            ["comparison", "metric", "point (flagged removed)", "95% CI",
             "n tasks"], rows))
        parts.append("")
        parts.append("Registered (intention-to-treat) results remain the "
                     "headline numbers in Tables 2-3.")
        parts.append("")

    # Missing-data appendix
    parts.append("## Missing data and caveats")
    if missing_notes:
        for note in missing_notes:
            parts.append(f"- {note}")
    else:
        parts.append("- none: all inputs present and well-formed")
    parts.append("")

    (out_dir / "tables.md").write_text("\n".join(parts), encoding="utf-8")


# ---------------------------------------------------------------------------
# Output: figures
# ---------------------------------------------------------------------------

def make_figures(out_dir, cells, tasks, arm_summary, replicate_store, missing_notes):
    """Write matplotlib PNGs; degrade gracefully if matplotlib is absent."""
    try:
        import matplotlib
        matplotlib.use("Agg")  # headless backend; never open a window
        import matplotlib.pyplot as plt
    except ImportError:
        missing_notes.append("matplotlib not installed; figures skipped")
        return

    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    jitter_rng = rng_for("figure-jitter")
    # Fixed metadata keeps PNG bytes stable across identical re-runs.
    save_kwargs = {"dpi": 150, "metadata": {"Software": "ace-100 analyze.py"}}

    # --- Figure 1: per-task cost by arm (box of task medians + strip of runs)
    fig, ax = plt.subplots(figsize=(7.0, 4.5))
    box_data = []
    for arm in ARMS:
        task_medians = [median(cells[(t, arm)]["costs"])
                        for t in tasks
                        if (t, arm) in cells and cells[(t, arm)]["costs"]]
        box_data.append(task_medians)
    ax.boxplot(box_data, showfliers=False)
    for i, arm in enumerate(ARMS, start=1):
        xs, ys = [], []
        for t in tasks:
            cell = cells.get((t, arm))
            if not cell:
                continue
            for c in cell["costs"]:
                xs.append(i + jitter_rng.uniform(-0.18, 0.18))
                ys.append(c)
        ax.plot(xs, ys, linestyle="", marker="o", markersize=3, alpha=0.35)
    ax.set_xticks(range(1, len(ARMS) + 1))
    ax.set_xticklabels(ARMS)
    ax.set_ylabel("cost_usd_standard per run (USD)")
    ax.set_title("Per-run cost by arm (box = per-task medians, dots = runs)")
    fig.tight_layout()
    fig.savefig(fig_dir / "cost_by_arm.png", **save_kwargs)
    plt.close(fig)

    # --- Figure 2: quality by arm (pass rates + judge means)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.0, 4.5))
    width = 0.8 / len(ARMS)
    pass_metrics = [("suite pass", "mean_task_suite_pass_rate"),
                    ("ref-tests pass", "mean_task_ref_tests_pass_rate")]
    for k, arm in enumerate(ARMS):
        xs = [i + k * width for i in range(len(pass_metrics))]
        ys = [arm_summary[arm][field] or 0.0 for _label, field in pass_metrics]
        ax1.bar(xs, ys, width=width, label=arm)
    ax1.set_xticks([i + width for i in range(len(pass_metrics))])
    ax1.set_xticklabels([label for label, _f in pass_metrics])
    ax1.set_ylim(0, 1)
    ax1.set_ylabel("mean per-task pass rate")
    ax1.set_title("Test outcomes by arm")
    ax1.legend()
    for k, arm in enumerate(ARMS):
        xs = [i + k * width for i in range(len(JUDGE_DIMS))]
        ys = [arm_summary[arm]["mean_task_judge_means"][dim] or 0.0
              for dim in JUDGE_DIMS]
        ax2.bar(xs, ys, width=width, label=arm)
    ax2.set_xticks([i + width for i in range(len(JUDGE_DIMS))])
    ax2.set_xticklabels(JUDGE_DIMS)
    ax2.set_ylabel("mean per-task judge score")
    ax2.set_title("Judge scores by arm")
    ax2.legend()
    fig.tight_layout()
    fig.savefig(fig_dir / "quality_by_arm.png", **save_kwargs)
    plt.close(fig)

    # --- Figure 3: bootstrap distributions of the cost ratio, per pair
    fig, axes = plt.subplots(1, len(PAIRS), figsize=(4.0 * len(PAIRS), 3.6),
                             squeeze=False)
    for ax, (arm_a, arm_b) in zip(axes[0], PAIRS):
        pair_name = f"{arm_a}_vs_{arm_b}"
        reps_list = replicate_store.get((pair_name, "cost_ratio"), [])
        if reps_list:
            ax.hist(reps_list, bins=50)
            lo, hi = percentile(reps_list, 0.025), percentile(reps_list, 0.975)
            ax.axvline(lo, linestyle="--", linewidth=1)
            ax.axvline(hi, linestyle="--", linewidth=1)
        ax.axvline(1.0, linestyle=":", linewidth=1)
        if pair_name == "ace_vs_original":
            ax.axvline(COST_RATIO_THRESHOLD, linestyle="-.", linewidth=1)
        ax.set_title(f"cost ratio {arm_a}/{arm_b}")
        ax.set_xlabel("bootstrap replicate")
    fig.tight_layout()
    fig.savefig(fig_dir / "bootstrap_cost_ratio.png", **save_kwargs)
    plt.close(fig)

    # --- Figure 4: bootstrap distributions of the ref-tests-pass delta, per pair
    fig, axes = plt.subplots(1, len(PAIRS), figsize=(4.0 * len(PAIRS), 3.6),
                             squeeze=False)
    for ax, (arm_a, arm_b) in zip(axes[0], PAIRS):
        pair_name = f"{arm_a}_vs_{arm_b}"
        reps_list = replicate_store.get((pair_name, "ref_tests_pass_delta"), [])
        if reps_list:
            ax.hist(reps_list, bins=50)
            lo, hi = percentile(reps_list, 0.025), percentile(reps_list, 0.975)
            ax.axvline(lo, linestyle="--", linewidth=1)
            ax.axvline(hi, linestyle="--", linewidth=1)
        ax.axvline(0.0, linestyle=":", linewidth=1)
        if pair_name == "ace_vs_original":
            ax.axvline(-TESTPASS_NONINF_MARGIN, linestyle="-.", linewidth=1)
        ax.set_title(f"ref-tests pass delta {arm_a}-{arm_b}")
        ax.set_xlabel("bootstrap replicate")
    fig.tight_layout()
    fig.savefig(fig_dir / "bootstrap_quality_delta.png", **save_kwargs)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Aggregate ACE-100 experiment runs into paper tables/figures.")
    parser.add_argument("--out", type=Path, default=None,
                        help="Output directory (default: <experiment-dir>/analysis)")
    parser.add_argument("--bootstrap", type=int, default=10000,
                        help="Bootstrap replicates (default 10000; 0 disables CIs)")
    parser.add_argument("--experiment-dir", type=Path, default=DEFAULT_EXPERIMENT_DIR,
                        help=f"Experiment data root (default {DEFAULT_EXPERIMENT_DIR})")
    args = parser.parse_args(argv)

    exp = args.experiment_dir
    out_dir = args.out if args.out is not None else exp / "analysis"
    runs_path = exp / "data" / "runs.jsonl"
    eval_dir = exp / "data" / "eval"
    scores_path = exp / "data" / "judge" / "scores.jsonl"
    blinding_path = exp / "data" / "judge" / "blinding.json"
    consumption_path = exp / "data" / "docs-consumption.jsonl"
    sweep_path = exp / "audit" / "network-sweep.json"
    # The committed ledger; the gitignored arms/gates copy is the fallback.
    migration_path = exp / "audit" / "arm-gates" / "migration-cost.json"
    if not migration_path.is_file():
        migration_path = exp / "arms" / "gates" / "migration-cost.json"

    if not runs_path.is_file():
        print(f"error: {runs_path} not found; nothing to analyze", file=sys.stderr)
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)

    missing_notes = []

    # --- load and join
    runs = load_runs(runs_path, missing_notes)
    if not runs:
        print("error: runs.jsonl contained no usable records", file=sys.stderr)
        return 1
    tests = load_tests(eval_dir, missing_notes)
    judge = load_judge(scores_path, blinding_path, missing_notes)
    consumption = load_consumption(consumption_path, missing_notes)
    leakage_flags = load_leakage_flags(sweep_path, missing_notes)

    # Orphan artifacts (tests/judge for trials absent from runs.jsonl) are
    # excluded from analysis but noted for auditing.
    orphan_tests = sorted(set(tests) - set(runs))
    if orphan_tests:
        missing_notes.append(
            f"{len(orphan_tests)} tests.json trial(s) have no runs.jsonl record; excluded")
    orphan_judge = sorted(set(judge) - set(runs))
    if orphan_judge:
        missing_notes.append(
            f"{len(orphan_judge)} judge-scored trial(s) have no runs.jsonl record; excluded")

    # Coverage notes for graceful degradation.
    analyzed_keys = [k for k, r in runs.items() if r.get("status") != STATUS_INFRA]
    n_missing_tests = sum(1 for k in analyzed_keys if k not in tests)
    if n_missing_tests:
        missing_notes.append(
            f"{n_missing_tests}/{len(analyzed_keys)} analyzed trial(s) lack tests.json; "
            "test-pass rates computed over trials with results")
    n_missing_judge = sum(1 for k in analyzed_keys if k not in judge)
    if n_missing_judge:
        missing_notes.append(
            f"{n_missing_judge}/{len(analyzed_keys)} analyzed trial(s) lack judge scores; "
            "judge means computed over scored trials")

    # --- aggregate
    cells, tasks = aggregate(runs, tests, judge, consumption)
    per_task_arm = {}
    for task in tasks:
        per_task_arm[task] = {}
        for arm in ALL_ARMS:
            cell = cells.get((task, arm))
            if cell is not None:
                per_task_arm[task][arm] = cell_stats(cell)
        missing_arms = [arm for arm in ALL_ARMS if (task, arm) not in cells]
        if missing_arms:
            missing_notes.append(f"task {task}: no runs at all for arm(s) {missing_arms}")

    arm_summary = build_arm_summary(cells, tasks)

    # --- pairwise comparisons + bootstrap
    pairwise, replicate_store = build_pairwise(cells, tasks, args.bootstrap)

    # --- decision rules, break-even, manipulation check, amendments 4/5
    decision = build_decision(pairwise)
    migration_std, migration_har = load_migration_cost(migration_path, missing_notes)
    break_even = build_break_even(cells, tasks, migration_std, migration_har)
    manipulation = build_manipulation_check(cells, tasks, consumption)
    value_retention = build_value_retention(cells, tasks)
    sensitivity = build_sensitivity(runs, tests, judge, consumption,
                                    leakage_flags, args.bootstrap)

    # --- figures (before summary so figure-skip notes land in the outputs)
    make_figures(out_dir, cells, tasks, arm_summary, replicate_store, missing_notes)

    # --- summary.json (all numbers; deterministic: sorted keys, no timestamps)
    summary = {
        "config": {
            "seed": SEED,
            "bootstrap_replicates": args.bootstrap,
            "arms": ARMS,
            "all_arms": ALL_ARMS,
            "pairs": [f"{a}_vs_{b}" for a, b in PAIRS],
            "judge_dimensions": JUDGE_DIMS,
            "thresholds": {
                "cost_ratio": COST_RATIO_THRESHOLD,
                "testpass_noninferiority_margin": TESTPASS_NONINF_MARGIN,
                "rubric_noninferiority_margin": RUBRIC_NONINF_MARGIN,
            },
            "experiment_dir": str(exp),
            "conventions": {
                "infra_runs": "excluded from all statistics",
                "cost_stats": "intention-to-treat over non-infra runs",
                "completion_rate": "completed / non-infra runs",
                "bootstrap": ("tasks resampled with replacement, then trials "
                              "resampled within each sampled task, per arm; "
                              "percentile 95% CIs"),
            },
        },
        "n_tasks": len(tasks),
        "tasks": tasks,
        "per_task_arm": per_task_arm,
        "arm_summary": arm_summary,
        "pairwise": pairwise,
        "decision": decision,
        "break_even": break_even,
        "manipulation_check": manipulation,
        "value_retention": value_retention,
        "sensitivity_excluding_leakage": sensitivity,
        "missing": missing_notes,
    }
    with open(out_dir / "summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
        fh.write("\n")

    # --- tables.md
    write_tables(out_dir, tasks, per_task_arm, arm_summary, pairwise,
                 decision, break_even, manipulation, value_retention,
                 sensitivity, missing_notes, args.bootstrap)

    # --- console recap
    print(f"analyzed {len(analyzed_keys)} runs ({len(runs) - len(analyzed_keys)} infra-excluded) "
          f"across {len(tasks)} tasks and {len(ARMS)} arms")
    cost_rule = decision["cost_superiority"]
    print(f"cost superiority (ace/original <= {COST_RATIO_THRESHOLD}): "
          f"point={fmt(cost_rule['point_estimate'], 3)} "
          f"CI={fmt_ci(cost_rule['ci95'], 3)} -> "
          f"{'MET' if cost_rule['point_meets'] else 'not met'} (point)")
    q = decision["quality_noninferiority"]
    verdict = ("MET" if q["point_meets_all"]
               else ("NOT MET" if q["point_meets_all"] is not None else "not evaluable"))
    print(f"quality non-inferiority (ace vs original): {verdict} "
          f"({q['n_components_evaluable']}/{q['n_components_total']} components evaluable)")
    if break_even["runs_to_break_even"] is not None:
        print(f"break-even: {break_even['runs_to_break_even']:.1f} runs "
              f"(migration ${break_even['migration_cost_usd']:.2f} / "
              f"savings ${break_even['per_run_savings_usd']:.4f} per run)")
    else:
        print(f"break-even: not computable ({break_even['note']})")
    if sensitivity is not None:
        sens_cost = sensitivity["pairwise"].get("ace_vs_original", {}).get("cost_ratio", {})
        print(f"leakage sensitivity ({sensitivity['n_flagged_runs']} run(s) removed): "
              f"ace/original cost ratio point={fmt(sens_cost.get('point'), 3)}")
    if missing_notes:
        print(f"{len(missing_notes)} missing-data note(s); see tables.md / summary.json")
    print(f"wrote {out_dir / 'summary.json'}, {out_dir / 'tables.md'}, "
          f"and figures under {out_dir / 'figures'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
