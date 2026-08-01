#!/usr/bin/env python3
"""Score completed experiment runs: test outcomes + blinded LLM judge.

Implements the quality-evaluation hierarchy registered in
meta/experiment/PREREGISTRATION.md (section 6):

  1. Primary  - test outcomes:
       (a) the repo's existing suite (regressions), and
       (b) tests added by the reference PR, run against the agent's diff.
  2. Secondary - blinded LLM judge (Claude Opus 5, Batches API):
       correctness / completeness / convention, each 1-5, with a seeded
       double-scored subset for reliability.

Subcommands
-----------
  evaluate.py tests --manifest meta/experiment/manifest.json [--task pr-NNNN]...
      Re-materialize each completed run's workspace (base commit + arm docs,
      exactly as run_cell built it), apply the run's diff.patch, then run
      (a) the task's test_command suite and (b) the reference PR's changed
      *_test.go files copied in from the reference merge commit. Results go
      to meta/experiment/data/eval/<task>/<arm>/trial-<n>/tests.json.

  evaluate.py judge --manifest meta/experiment/manifest.json [--double-fraction 0.2]
      Build a blinded judging request set, submit it to the Anthropic
      Batches API (model claude-opus-5), poll to completion, and write
      meta/experiment/data/judge/scores.jsonl. Blinded ids are salted hashes
      of (task, arm, trial); the mapping lives only in
      meta/experiment/data/judge/blinding.json. Request order is shuffled and
      a seeded subset is scored twice (pass_n=2). Use --dry-run to write the
      request set without submitting, --resume BATCH_ID to collect results
      from an already-submitted batch.

  evaluate.py judge-report
      Agreement statistics (exact and within-1, per dimension) on the
      double-scored subset. Written to
      meta/experiment/analysis/judge-agreement.json and printed.

Requirements: python 3.11+, git, go toolchain, `anthropic` SDK (judge only).
The target-repo clone must be a FULL clone (all commits reachable): base and
reference-merge commits are checked out / diffed locally. Go module cache
should be pre-warmed (run `go mod download` per module once) so `go test`
does not depend on the network at evaluation time.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Directory anchors. This file lives at meta/experiment/tools/evaluate.py.
EXP_DIR = Path(__file__).resolve().parents[1]          # meta/experiment/
ARMS_DIR = EXP_DIR / "arms"
DATA_DIR = EXP_DIR / "data"
RUNS_DIR = DATA_DIR / "runs"
RUNS_INDEX = DATA_DIR / "runs.jsonl"
EVAL_DIR = DATA_DIR / "eval"
JUDGE_DIR = DATA_DIR / "judge"
ANALYSIS_DIR = EXP_DIR / "analysis"

# CONFIG: path to the local FULL clone of the target repository
# (open-telemetry/opentelemetry-collector). Override with the
# ACE_EXPERIMENT_REPO environment variable. Must contain every task's
# base_commit and reference_merge_commit.
TARGET_REPO_DIR = Path(os.environ.get("ACE_EXPERIMENT_REPO", str(EXP_DIR / "repo")))

# The three documentation states, keyed to arms/<arm>-docs/ trees built at
# the pinned commit C by build_arms.
# "nodocs" (Experiment 1 Amendment 4): ablation floor — corpus deleted,
# nothing overlaid.
ARM_NAMES = ("original", "ace", "naive", "nodocs")

# Seed for all local randomness (pre-registration). Derived sub-seeds keep
# the salt, the double-score sample, and the shuffle independent of each
# other but fully reproducible.
SEED = 20260801

# CONFIG: judging model (pre-registration: Claude Opus 5). Exact model id per
# the Anthropic model catalog.
JUDGE_MODEL = "claude-opus-5"
# Generous cap: on claude-opus-5 max_tokens bounds thinking + response text.
JUDGE_MAX_TOKENS = 16000

# CONFIG: per-package `go test` timeout (also passed as go's -timeout flag),
# and the overall timeout for a task-level test_command suite.
GO_TEST_TIMEOUT_S = 600
SUITE_TIMEOUT_S = 2700

# CONFIG: character caps for the diffs embedded in a judge prompt. Diffs
# beyond the cap are truncated with an explicit marker (recorded in the
# request file so truncation is auditable).
MAX_REF_DIFF_CHARS = 60_000
MAX_CAND_DIFF_CHARS = 60_000

# CONFIG: strip documentation-corpus files from BOTH diffs shown to the
# judge. The ace arm's migrated docs have a different file layout than the
# original/naive arms, so doc paths in a diff could unblind the arm. The
# judge prompt states that documentation changes were removed and must not
# be penalized. Set to False only with a pre-registration amendment.
EXCLUDE_DOCS_FROM_JUDGE = True

# How many bytes of process output to keep in detail records.
OUTPUT_TAIL_CHARS = 4000

# Statuses (from runs.jsonl) that count as evaluable. Pre-registration
# evaluates completed runs; --include-capped adds cap_turns/cap_wall.
COMPLETED_STATUSES = {"completed"}
CAPPED_STATUSES = {"cap_turns", "cap_wall"}


# ---------------------------------------------------------------------------
# Documentation-corpus rule
# ---------------------------------------------------------------------------
# MUST match build_arms / run_cell exactly (DOCS CORPUS DEFINITION in the
# pre-registration): all *.md and *.mdx files, excluding CHANGELOG*, files
# under testdata/, .github/, node_modules/, and LICENSE-like files.

_EXCLUDED_DIR_PARTS = {"testdata", ".github", "node_modules"}
_LICENSE_LIKE_PREFIXES = ("LICENSE", "LICENCE", "COPYING", "NOTICE", "PATENTS")


def is_corpus_doc(relpath: str) -> bool:
    """True if a repo-relative path belongs to the documentation corpus."""
    p = relpath.replace("\\", "/").lstrip("./")
    name = p.rsplit("/", 1)[-1]
    if not name.lower().endswith((".md", ".mdx")):
        return False
    parts = p.split("/")
    if any(part in _EXCLUDED_DIR_PARTS for part in parts[:-1]):
        return False
    upper = name.upper()
    if upper.startswith("CHANGELOG"):
        return False
    if upper.startswith(_LICENSE_LIKE_PREFIXES):
        return False
    return True


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def tail(text: str, limit: int = OUTPUT_TAIL_CHARS) -> str:
    return text if len(text) <= limit else "[...]" + text[-limit:]


def git(args: list[str], cwd: Path, check: bool = True,
        binary: bool = False) -> subprocess.CompletedProcess:
    """Run a git command; text output unless binary=True."""
    proc = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=not binary)
    if check and proc.returncode != 0:
        err = proc.stderr if isinstance(proc.stderr, str) else proc.stderr.decode(
            "utf-8", "replace")
        raise RuntimeError(f"git {' '.join(args[:4])}... failed in {cwd}: {err.strip()}")
    return proc


def load_manifest(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    if "tasks" not in manifest:
        sys.exit(f"{path} does not look like a task manifest (no 'tasks' key)")
    return manifest


def load_run_statuses() -> dict[tuple[str, str, int], str]:
    """(task_id, arm, trial) -> status from the append-only runs index.

    Later records win (a re-run of a cell supersedes an earlier record).
    """
    statuses: dict[tuple[str, str, int], str] = {}
    if not RUNS_INDEX.exists():
        return statuses
    with open(RUNS_INDEX, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            statuses[(rec["task_id"], rec["arm"], int(rec["trial"]))] = rec["status"]
    return statuses


@dataclasses.dataclass
class Run:
    task_id: str
    arm: str
    trial: int
    run_dir: Path
    status: str


def discover_runs(tasks: list[dict], statuses: dict, include_capped: bool,
                  task_filter: list[str] | None) -> list[Run]:
    """Enumerate evaluable run directories under data/runs/."""
    wanted = COMPLETED_STATUSES | (CAPPED_STATUSES if include_capped else set())
    runs: list[Run] = []
    for task in tasks:
        task_id = task["task_id"]
        if task_filter and task_id not in task_filter:
            continue
        for arm in ARM_NAMES:
            arm_dir = RUNS_DIR / task_id / arm
            if not arm_dir.is_dir():
                continue
            for trial_dir in sorted(arm_dir.glob("trial-*")):
                m = re.fullmatch(r"trial-(\d+)", trial_dir.name)
                if not m or not (trial_dir / "result.json").exists():
                    continue
                trial = int(m.group(1))
                status = statuses.get((task_id, arm, trial), "unknown")
                if status not in wanted:
                    print(f"  skip {task_id}/{arm}/trial-{trial}: status={status}")
                    continue
                runs.append(Run(task_id, arm, trial, trial_dir, status))
    return runs


# ---------------------------------------------------------------------------
# Workspace materialization (mirror of run_cell)
# ---------------------------------------------------------------------------


def replace_docs_corpus(workspace: Path, arm: str) -> None:
    """Delete the docs corpus at B_i and install the arm's snapshot from C.

    This mirrors run_cell's ARM/TASK COMPOSITION RULE: the corpus is defined
    by the rule (not the manifest list) so docs present at B_i but absent at
    C are removed too, keeping the docs state byte-identical to the run.
    """
    # 1. Delete every corpus file currently in the workspace.
    for path in workspace.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(workspace).as_posix()
        if rel.startswith(".git/"):
            continue
        if is_corpus_doc(rel):
            path.unlink()
    # 2. Copy the arm's docs tree in at its corpus-relative paths.
    #    The "nodocs" ablation floor overlays nothing.
    if arm == "nodocs":
        return
    arm_docs = ARMS_DIR / f"{arm}-docs"
    if not arm_docs.is_dir():
        raise RuntimeError(f"arm docs tree missing: {arm_docs}")
    for src in arm_docs.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(arm_docs)
        dest = workspace / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


class Workspace:
    """Context manager: git worktree at base_commit with arm docs installed."""

    def __init__(self, base_commit: str, arm: str):
        self.base_commit = base_commit
        self.arm = arm
        self.path: Path | None = None

    def __enter__(self) -> Path:
        ws = Path(tempfile.mkdtemp(prefix="ace-eval-"))
        # mkdtemp creates the dir; worktree add wants to create it itself.
        ws.rmdir()
        git(["worktree", "add", "--detach", str(ws), self.base_commit],
            cwd=TARGET_REPO_DIR)
        self.path = ws
        replace_docs_corpus(ws, self.arm)
        return ws

    def __exit__(self, *exc) -> None:
        if self.path is None:
            return
        try:
            git(["worktree", "remove", "--force", str(self.path)],
                cwd=TARGET_REPO_DIR, check=False)
        finally:
            if self.path.exists():
                shutil.rmtree(self.path, ignore_errors=True)
            git(["worktree", "prune"], cwd=TARGET_REPO_DIR, check=False)


def apply_candidate_patch(workspace: Path, patch_file: Path) -> tuple[bool, str]:
    """Apply the run's diff.patch. Returns (ok, detail)."""
    text = patch_file.read_text(encoding="utf-8", errors="replace") \
        if patch_file.exists() else ""
    if not text.strip():
        return True, "empty diff (no changes made by the agent)"
    proc = git(["apply", "--whitespace=nowarn", str(patch_file)],
               cwd=workspace, check=False)
    if proc.returncode != 0:
        return False, f"git apply failed: {tail(proc.stderr)}"
    return True, "applied"


# ---------------------------------------------------------------------------
# Go test execution
# ---------------------------------------------------------------------------


def find_module_root(workspace: Path, pkg_dir: Path) -> Path | None:
    """Walk up from a package dir to the nearest go.mod (multi-module repo)."""
    cur = pkg_dir
    while True:
        if (cur / "go.mod").exists():
            return cur
        if cur == workspace:
            return None
        cur = cur.parent


def go_test_package(workspace: Path, pkg_rel: str) -> dict:
    """Run `go test` for one package dir (workspace-relative). Returns detail."""
    pkg_dir = workspace / pkg_rel
    detail: dict = {"package": pkg_rel}
    if not pkg_dir.is_dir():
        detail.update(passed=None, note="package dir missing after patch")
        return detail
    module_root = find_module_root(workspace, pkg_dir)
    if module_root is None:
        detail.update(passed=None, note="no go.mod found above package")
        return detail
    rel_in_module = os.path.relpath(pkg_dir, module_root).replace(os.sep, "/")
    target = "." if rel_in_module == "." else f"./{rel_in_module}"
    detail["module"] = str(module_root.relative_to(workspace)) or "."
    cmd = ["go", "test", "-count=1", f"-timeout={GO_TEST_TIMEOUT_S}s", target]
    start = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=str(module_root), capture_output=True,
                              text=True, timeout=GO_TEST_TIMEOUT_S + 60)
        detail.update(passed=proc.returncode == 0, returncode=proc.returncode,
                      output_tail=tail(proc.stdout + proc.stderr))
    except subprocess.TimeoutExpired:
        detail.update(passed=False, returncode=None, note="subprocess timeout")
    detail["seconds"] = round(time.monotonic() - start, 1)
    return detail


def go_packages_from_diff(diff_text: str) -> list[str]:
    """Workspace-relative package dirs whose .go files a unified diff touches."""
    dirs: set[str] = set()
    for line in diff_text.splitlines():
        for prefix in ("+++ b/", "--- a/"):
            if line.startswith(prefix):
                path = line[len(prefix):].strip()
                if path.endswith(".go") and path != "/dev/null":
                    d = path.rsplit("/", 1)[0] if "/" in path else "."
                    dirs.add(d)
    return sorted(dirs)


def reference_test_files(base_commit: str, ref_commit: str) -> list[tuple[str, str]]:
    """Changed *_test.go files in base..ref as (status, path); D excluded."""
    proc = git(["diff", "--name-status", "--no-renames",
                f"{base_commit}..{ref_commit}"], cwd=TARGET_REPO_DIR)
    files: list[tuple[str, str]] = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        status, _, path = line.partition("\t")
        if status.strip().startswith("D"):
            continue
        if path.endswith("_test.go"):
            files.append((status.strip(), path))
    return files


def copy_reference_tests(workspace: Path, ref_commit: str,
                         files: list[tuple[str, str]]) -> list[str]:
    """Copy the reference merge commit's version of each test file into the
    workspace (overwriting whatever the candidate wrote). Returns paths."""
    copied = []
    for _status, path in files:
        proc = git(["show", f"{ref_commit}:{path}"], cwd=TARGET_REPO_DIR,
                   binary=True)
        dest = workspace / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(proc.stdout)
        copied.append(path)
    return copied


# ---------------------------------------------------------------------------
# `tests` subcommand
# ---------------------------------------------------------------------------


def evaluate_tests_for_run(task: dict, run: Run) -> dict:
    """Materialize, apply, run suite + reference tests. Returns tests.json."""
    base = task["base_commit"]
    ref = task["reference_merge_commit"]
    result: dict = {
        "suite_pass": None, "suite_detail": None,
        "ref_tests_pass": None, "ref_detail": None,
        "meta": {"evaluated_at": now_iso(), "base_commit": base,
                 "reference_merge_commit": ref, "status": run.status},
    }
    patch_file = run.run_dir / "diff.patch"
    diff_text = patch_file.read_text(encoding="utf-8", errors="replace") \
        if patch_file.exists() else ""

    with Workspace(base, run.arm) as ws:
        ok, apply_detail = apply_candidate_patch(ws, patch_file)
        result["meta"]["apply"] = apply_detail
        if not ok:
            # A patch that fails on an identical re-materialization is an
            # infrastructure problem, not an agent failure: record and bail.
            result["suite_detail"] = {"error": apply_detail}
            result["ref_detail"] = {"error": apply_detail}
            return result

        # (a) Task suite. test_command comes from the manifest (filled in
        # per-repo after selection). When null, fall back to `go test` on the
        # packages the candidate diff touched — registered fallback for this
        # Go monorepo, where a full-repo suite is impractical per run.
        test_command = task.get("test_command")
        if test_command:
            start = time.monotonic()
            try:
                proc = subprocess.run(test_command, shell=True, cwd=str(ws),
                                      capture_output=True, text=True,
                                      timeout=SUITE_TIMEOUT_S)
                result["suite_pass"] = proc.returncode == 0
                result["suite_detail"] = {
                    "mode": "test_command", "command": test_command,
                    "returncode": proc.returncode,
                    "seconds": round(time.monotonic() - start, 1),
                    "output_tail": tail(proc.stdout + proc.stderr),
                }
            except subprocess.TimeoutExpired:
                result["suite_pass"] = False
                result["suite_detail"] = {"mode": "test_command",
                                          "command": test_command,
                                          "note": "suite timeout"}
        else:
            pkgs = go_packages_from_diff(diff_text)
            if not pkgs:
                result["suite_detail"] = {
                    "mode": "go-test-fallback", "packages": [],
                    "note": "no test_command and no .go files in candidate diff",
                }
            else:
                details = [go_test_package(ws, p) for p in pkgs]
                decided = [d["passed"] for d in details if d["passed"] is not None]
                result["suite_pass"] = bool(decided) and all(decided)
                result["suite_detail"] = {"mode": "go-test-fallback",
                                          "packages": details}

        # (b) Reference tests: the reference PR's changed *_test.go files,
        # taken from the reference merge commit, run against the candidate.
        ref_files = reference_test_files(base, ref)
        if not ref_files:
            result["ref_detail"] = {"files": [],
                                    "note": "reference PR changed no *_test.go files"}
        else:
            copied = copy_reference_tests(ws, ref, ref_files)
            pkg_dirs = sorted({p.rsplit("/", 1)[0] if "/" in p else "."
                               for p in copied})
            details = [go_test_package(ws, p) for p in pkg_dirs]
            decided = [d["passed"] for d in details if d["passed"] is not None]
            result["ref_tests_pass"] = bool(decided) and all(decided)
            result["ref_detail"] = {"files": copied, "packages": details}

    return result


def cmd_tests(args: argparse.Namespace) -> None:
    manifest = load_manifest(Path(args.manifest))
    if not TARGET_REPO_DIR.is_dir() or not (TARGET_REPO_DIR / ".git").exists():
        sys.exit(f"target repo clone not found at {TARGET_REPO_DIR} "
                 "(set ACE_EXPERIMENT_REPO)")
    statuses = load_run_statuses()
    runs = discover_runs(manifest["tasks"], statuses, args.include_capped,
                         args.task or None)
    tasks_by_id = {t["task_id"]: t for t in manifest["tasks"]}
    print(f"tests: {len(runs)} run(s) to evaluate")
    for run in runs:
        out_dir = EVAL_DIR / run.task_id / run.arm / f"trial-{run.trial}"
        out_file = out_dir / "tests.json"
        if out_file.exists() and not args.rerun:
            print(f"  keep {run.task_id}/{run.arm}/trial-{run.trial} (exists)")
            continue
        print(f"  eval {run.task_id}/{run.arm}/trial-{run.trial} ...", flush=True)
        try:
            record = evaluate_tests_for_run(tasks_by_id[run.task_id], run)
        except Exception as exc:  # keep going; record the failure
            record = {"suite_pass": None, "suite_detail": {"error": str(exc)},
                      "ref_tests_pass": None, "ref_detail": {"error": str(exc)},
                      "meta": {"evaluated_at": now_iso(), "status": run.status}}
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(f"       suite_pass={record['suite_pass']} "
              f"ref_tests_pass={record['ref_tests_pass']}")


# ---------------------------------------------------------------------------
# `judge` subcommand
# ---------------------------------------------------------------------------

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        # Numerical min/max constraints are unsupported in structured-output
        # schemas; an integer enum pins the 1-5 scale exactly.
        "correctness": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
        "completeness": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
        "convention": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
        "notes": {"type": "string"},
    },
    "required": ["correctness", "completeness", "convention", "notes"],
    "additionalProperties": False,
}

JUDGE_RUBRIC = """\
You are grading a candidate code change for a software task in a Go monorepo.
You are given the task description, the REFERENCE diff (the change that was
actually merged for this task), and the CANDIDATE diff. Grade the candidate
against the task and the reference on three dimensions, each an integer 1-5:

- correctness: does the candidate implement behavior that satisfies the task
  without introducing bugs? (5 = clearly correct; 3 = plausible but with
  likely defects or unhandled cases; 1 = wrong or no meaningful attempt)
- completeness: does it cover the full scope of the task, including edge
  cases and tests where the reference added them? (5 = full scope;
  3 = core covered, notable gaps; 1 = mostly missing)
- convention: does it follow the codebase's conventions as evidenced by the
  reference and surrounding context — naming, structure, error handling,
  registration patterns? (5 = idiomatic; 3 = workable but off-style;
  1 = ignores conventions)

Rules:
- The reference is ONE acceptable solution, not the only one. A different
  but sound approach can score 5 on every dimension.
- Documentation-file changes were removed from BOTH diffs before you saw
  them. Do not reward or penalize documentation edits or their absence.
- Judge only what is in the diffs and the task text. Do not speculate about
  how or under what conditions the candidate was produced.
- An empty candidate diff scores 1 on all dimensions.
- Put a brief justification (2-4 sentences) in "notes".

Respond with a single JSON object matching the required schema.
"""


def build_task_description(task: dict) -> str:
    """The same prompt material the subject agent saw, per the manifest."""
    prompt = task.get("prompt") or {}
    parts = []
    issue = prompt.get("issue")
    if issue:
        parts.append(f"Issue #{issue.get('number')}: {issue.get('title', '')}\n\n"
                     f"{issue.get('body') or ''}")
    parts.append(f"Task title: {prompt.get('pr_title', '')}\n\n"
                 f"{prompt.get('pr_body') or ''}")
    return "\n\n---\n\n".join(p.strip() for p in parts if p.strip())


def filter_docs_from_diff(diff_text: str) -> tuple[str, int]:
    """Drop per-file chunks that touch documentation-corpus paths.

    Returns (filtered_text, dropped_file_count). Chunk boundaries are the
    'diff --git a/X b/Y' headers of a unified git diff.
    """
    if not diff_text:
        return diff_text, 0
    lines = diff_text.splitlines(keepends=True)
    out: list[str] = []
    dropped = 0
    keep_current = True
    for line in lines:
        if line.startswith("diff --git "):
            # Best-effort path parse; paths with spaces are absent from this
            # corpus. On parse failure we keep the chunk (safe default).
            keep_current = True
            m = re.match(r"diff --git a/(.*?) b/(.*)\n?$", line)
            if m and (is_corpus_doc(m.group(1)) or is_corpus_doc(m.group(2))):
                keep_current = False
                dropped += 1
        if keep_current:
            out.append(line)
    return "".join(out), dropped


def truncate(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return (text[:limit]
            + f"\n[... diff truncated: {len(text) - limit} characters removed ...]\n",
            True)


def reference_diff(task: dict) -> str:
    proc = git(["diff", "--no-color",
                f"{task['base_commit']}..{task['reference_merge_commit']}"],
               cwd=TARGET_REPO_DIR)
    return proc.stdout


def build_judge_prompt(task: dict, candidate_diff: str) -> tuple[str, dict]:
    """Assemble the blinded judging prompt. Returns (prompt, audit_info)."""
    audit: dict = {}
    ref = reference_diff(task)
    cand = candidate_diff
    if EXCLUDE_DOCS_FROM_JUDGE:
        ref, audit["ref_docs_files_dropped"] = filter_docs_from_diff(ref)
        cand, audit["cand_docs_files_dropped"] = filter_docs_from_diff(cand)
    ref, audit["ref_truncated"] = truncate(ref, MAX_REF_DIFF_CHARS)
    cand, audit["cand_truncated"] = truncate(cand, MAX_CAND_DIFF_CHARS)
    if not cand.strip():
        cand = "(empty diff - the candidate made no changes)"
    prompt = (
        f"{JUDGE_RUBRIC}\n"
        f"<task_description>\n{build_task_description(task)}\n</task_description>\n\n"
        f"<reference_diff>\n{ref}\n</reference_diff>\n\n"
        f"<candidate_diff>\n{cand}\n</candidate_diff>\n"
    )
    return prompt, audit


def make_blinding(runs: list[Run]) -> dict:
    """Deterministic salted blinded ids; mapping stays local in blinding.json."""
    salt_rng = random.Random(f"{SEED}-salt")
    salt = "".join(salt_rng.choice("0123456789abcdef") for _ in range(32))
    mapping = {}
    for run in runs:
        digest = hashlib.sha256(
            f"{salt}|{run.task_id}|{run.arm}|{run.trial}".encode()).hexdigest()
        mapping[digest[:16]] = {"task_id": run.task_id, "arm": run.arm,
                                "trial": run.trial}
    if len(mapping) != len(runs):
        raise RuntimeError("blinded id collision - increase id length")
    return {"seed": SEED, "salt": salt, "mapping": mapping}


def cmd_judge(args: argparse.Namespace) -> None:
    # The anthropic SDK is only needed for this subcommand.
    import anthropic
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    manifest = load_manifest(Path(args.manifest))
    if not TARGET_REPO_DIR.is_dir():
        sys.exit(f"target repo clone not found at {TARGET_REPO_DIR}")
    tasks_by_id = {t["task_id"]: t for t in manifest["tasks"]}
    statuses = load_run_statuses()
    runs = discover_runs(manifest["tasks"], statuses, args.include_capped,
                         args.task or None)
    if not runs:
        sys.exit("judge: no evaluable runs found")
    JUDGE_DIR.mkdir(parents=True, exist_ok=True)

    client = anthropic.Anthropic()

    if args.resume:
        # Collection-only path for an already-submitted batch.
        collect_judge_results(client, args.resume)
        return

    # --- blinding -----------------------------------------------------------
    blinding = make_blinding(runs)
    (JUDGE_DIR / "blinding.json").write_text(
        json.dumps(blinding, indent=2) + "\n", encoding="utf-8")
    id_of = {(v["task_id"], v["arm"], v["trial"]): k
             for k, v in blinding["mapping"].items()}

    # --- double-scored subset (seeded, over the sorted run list) ------------
    keys = sorted((r.task_id, r.arm, r.trial) for r in runs)
    n_double = round(args.double_fraction * len(keys))
    double_keys = set(random.Random(f"{SEED}-double").sample(keys, n_double))

    # --- build requests -----------------------------------------------------
    requests = []
    request_audit = []
    for run in sorted(runs, key=lambda r: (r.task_id, r.arm, r.trial)):
        patch_file = run.run_dir / "diff.patch"
        cand = patch_file.read_text(encoding="utf-8", errors="replace") \
            if patch_file.exists() else ""
        prompt, audit = build_judge_prompt(tasks_by_id[run.task_id], cand)
        blinded = id_of[(run.task_id, run.arm, run.trial)]
        passes = [1, 2] if (run.task_id, run.arm, run.trial) in double_keys else [1]
        for pass_n in passes:
            custom_id = f"{blinded}-p{pass_n}"
            requests.append(Request(
                custom_id=custom_id,
                params=MessageCreateParamsNonStreaming(
                    model=JUDGE_MODEL,
                    max_tokens=JUDGE_MAX_TOKENS,
                    # Structured output: enforce the rubric JSON via
                    # output_config.format json_schema.
                    output_config={"format": {"type": "json_schema",
                                              "schema": JUDGE_SCHEMA}},
                    messages=[{"role": "user", "content": prompt}],
                ),
            ))
            request_audit.append({"custom_id": custom_id, "pass_n": pass_n,
                                  "prompt_chars": len(prompt), **audit})

    # Randomize request order (seeded) so batch position carries no signal.
    order_rng = random.Random(f"{SEED}-order")
    order_rng.shuffle(requests)

    (JUDGE_DIR / "batch-requests.json").write_text(json.dumps({
        "generated_at": now_iso(), "model": JUDGE_MODEL, "seed": SEED,
        "double_fraction": args.double_fraction, "n_runs": len(runs),
        "n_requests": len(requests),
        "order": [r["custom_id"] for r in requests],
        "audit": request_audit,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"judge: {len(runs)} runs -> {len(requests)} requests "
          f"({n_double} double-scored)")

    if args.dry_run:
        print("judge: --dry-run, not submitting")
        return

    # --- submit and poll ----------------------------------------------------
    batch = client.messages.batches.create(requests=requests)
    (JUDGE_DIR / "batch-submitted.json").write_text(json.dumps({
        "batch_id": batch.id, "submitted_at": now_iso(),
        "processing_status": batch.processing_status,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"judge: submitted batch {batch.id}")
    collect_judge_results(client, batch.id)


def collect_judge_results(client, batch_id: str) -> None:
    """Poll a batch to completion, then unblind and append to scores.jsonl."""
    blinding_file = JUDGE_DIR / "blinding.json"
    if not blinding_file.exists():
        sys.exit("judge: blinding.json missing - cannot unblind results")
    mapping = json.loads(blinding_file.read_text(encoding="utf-8"))["mapping"]

    while True:
        batch = client.messages.batches.retrieve(batch_id)
        if batch.processing_status == "ended":
            break
        counts = batch.request_counts
        print(f"  batch {batch_id}: {batch.processing_status} "
              f"(processing={counts.processing} succeeded={counts.succeeded} "
              f"errored={counts.errored})", flush=True)
        time.sleep(60)

    scores_file = JUDGE_DIR / "scores.jsonl"
    raw_file = JUDGE_DIR / f"batch-{batch_id}-results.jsonl"
    errors_file = JUDGE_DIR / "judge-errors.jsonl"

    # Idempotent collection: skip (blinded_id, pass_n) pairs already scored.
    seen: set[tuple[str, int]] = set()
    if scores_file.exists():
        with open(scores_file, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    rec = json.loads(line)
                    seen.add((rec["blinded_id"], rec["pass_n"]))

    n_ok = n_err = 0
    with open(scores_file, "a", encoding="utf-8") as scores, \
            open(raw_file, "a", encoding="utf-8") as raw, \
            open(errors_file, "a", encoding="utf-8") as errs:
        # Results arrive in arbitrary order - always key by custom_id.
        for result in client.messages.batches.results(batch_id):
            custom_id = result.custom_id
            blinded_id, _, pass_tag = custom_id.rpartition("-p")
            pass_n = int(pass_tag)
            if result.result.type != "succeeded":
                n_err += 1
                errs.write(json.dumps({"custom_id": custom_id,
                                       "result_type": result.result.type,
                                       "collected_at": now_iso()}) + "\n")
                continue
            msg = result.result.message
            text = next((b.text for b in msg.content if b.type == "text"), None)
            raw.write(json.dumps({
                "custom_id": custom_id, "stop_reason": msg.stop_reason,
                "usage": {"input_tokens": msg.usage.input_tokens,
                          "output_tokens": msg.usage.output_tokens},
                "text": text,
            }) + "\n")
            if msg.stop_reason == "refusal" or not text:
                n_err += 1
                errs.write(json.dumps({"custom_id": custom_id,
                                       "result_type": "refusal_or_empty",
                                       "collected_at": now_iso()}) + "\n")
                continue
            try:
                scored = json.loads(text)
            except json.JSONDecodeError:
                n_err += 1
                errs.write(json.dumps({"custom_id": custom_id,
                                       "result_type": "bad_json",
                                       "collected_at": now_iso()}) + "\n")
                continue
            ident = mapping.get(blinded_id)
            if ident is None:
                n_err += 1
                errs.write(json.dumps({"custom_id": custom_id,
                                       "result_type": "unknown_blinded_id",
                                       "collected_at": now_iso()}) + "\n")
                continue
            if (blinded_id, pass_n) in seen:
                continue
            seen.add((blinded_id, pass_n))
            scores.write(json.dumps({
                "task_id": ident["task_id"], "arm": ident["arm"],
                "trial": ident["trial"],
                "correctness": scored["correctness"],
                "completeness": scored["completeness"],
                "convention": scored["convention"],
                "judge_notes": scored.get("notes", ""),
                "blinded_id": blinded_id, "pass_n": pass_n,
            }) + "\n")
            n_ok += 1
    print(f"judge: collected {n_ok} score(s), {n_err} error(s) "
          f"-> {scores_file}")


# ---------------------------------------------------------------------------
# `judge-report` subcommand
# ---------------------------------------------------------------------------


def cmd_judge_report(args: argparse.Namespace) -> None:
    scores_file = JUDGE_DIR / "scores.jsonl"
    if not scores_file.exists():
        sys.exit(f"no scores at {scores_file} - run `judge` first")
    by_run: dict[tuple[str, str, int], dict[int, dict]] = {}
    with open(scores_file, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            key = (rec["task_id"], rec["arm"], rec["trial"])
            by_run.setdefault(key, {})[rec["pass_n"]] = rec

    pairs = [(v[1], v[2]) for v in by_run.values() if 1 in v and 2 in v]
    report: dict = {"generated_at": now_iso(), "n_runs_scored": len(by_run),
                    "n_double_scored": len(pairs), "dimensions": {}}
    dims = ("correctness", "completeness", "convention")
    if pairs:
        for dim in dims:
            exact = sum(1 for a, b in pairs if a[dim] == b[dim])
            within1 = sum(1 for a, b in pairs if abs(a[dim] - b[dim]) <= 1)
            report["dimensions"][dim] = {
                "exact_agreement": round(exact / len(pairs), 3),
                "within_1_agreement": round(within1 / len(pairs), 3),
            }
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    out = ANALYSIS_DIR / "judge-agreement.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"judge-report: {len(by_run)} run(s) scored, "
          f"{len(pairs)} double-scored")
    if pairs:
        print(f"  {'dimension':<14} {'exact':>7} {'within-1':>9}")
        for dim in dims:
            d = report["dimensions"][dim]
            print(f"  {dim:<14} {d['exact_agreement']:>7.3f} "
                  f"{d['within_1_agreement']:>9.3f}")
    else:
        print("  no double-scored pairs found")
    print(f"  written to {out}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Score completed runs: test outcomes + blinded LLM judge.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_tests = sub.add_parser("tests", help="run suite + reference tests")
    p_tests.add_argument("--manifest", required=True)
    p_tests.add_argument("--task", action="append",
                         help="restrict to a task id (repeatable)")
    p_tests.add_argument("--include-capped", action="store_true",
                         help="also evaluate cap_turns/cap_wall runs")
    p_tests.add_argument("--rerun", action="store_true",
                         help="overwrite existing tests.json records")
    p_tests.set_defaults(func=cmd_tests)

    p_judge = sub.add_parser("judge", help="blinded LLM-judge batch")
    p_judge.add_argument("--manifest", required=True)
    p_judge.add_argument("--task", action="append")
    p_judge.add_argument("--double-fraction", type=float, default=0.2,
                         help="seeded fraction scored twice (default 0.2)")
    p_judge.add_argument("--include-capped", action="store_true")
    p_judge.add_argument("--dry-run", action="store_true",
                         help="write blinding + request set, do not submit")
    p_judge.add_argument("--resume", metavar="BATCH_ID",
                         help="skip submission; poll and collect this batch")
    p_judge.set_defaults(func=cmd_judge)

    p_report = sub.add_parser("judge-report",
                              help="agreement stats on the double-scored subset")
    p_report.set_defaults(func=cmd_judge_report)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
