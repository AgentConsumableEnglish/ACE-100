#!/usr/bin/env python3
"""Execute one (task, arm, trial) cell of the ACE-100 documentation experiment.

Implements the run procedure registered in meta/experiment/PREREGISTRATION.md:
materialize a workspace at the task's base commit with the arm's docs snapshot
installed, run the subject model headlessly under the registered caps, and
collect every per-run artifact into the data layout.

Two subcommands:

    run_cell.py one --manifest meta/experiment/manifest.json \
                    --task pr-15296 --arm ace --trial 1 [--model claude-sonnet-5]

    run_cell.py schedule --manifest meta/experiment/manifest.json \
                         [--trials 4] [--arms original,ace,naive] [--dry-run]

'one' executes a single cell and is idempotent: if the cell's result.json
already exists the cell is skipped unless --force is given. 'schedule'
enumerates tasks x arms x trials, shuffles the cells with the registered seed,
and runs them sequentially, skipping completed cells and stopping on the first
infrastructure error.

Statuses written to data/runs.jsonl:
    completed  harness finished normally (subtype "success")
    failed     harness returned valid JSON reporting an error (task failure)
    cap_turns  harness hit the 200-turn cap (subtype "error_max_turns")
    cap_wall   we killed the process at the 45-minute wall clock
    infra      claude exited abnormally without a parseable harness JSON;
               no result.json is written so the cell is retried on rerun

Network isolation note: --disallowed-tools "WebFetch,WebSearch" removes the
harness's network tools, but full network isolation is enforced by the sandbox
environment the runner executes in, NOT by this flag. Run this tool inside the
registered sandbox.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# CONFIG: per-repo configuration. Everything below marked CONFIG must be
# checked when adopting this tool for a different target repository.
# ---------------------------------------------------------------------------

# CONFIG: experiment directory holding arms/, data/, and the manifest.
# Defaults to the parent of tools/ (i.e. meta/experiment when this file lives
# at meta/experiment/tools/run_cell.py). Override with ACE_EXPERIMENT_DIR.
EXPERIMENT_DIR = Path(
    os.environ.get("ACE_EXPERIMENT_DIR", str(Path(__file__).resolve().parent.parent))
)

# CONFIG: full local clone of the target repository. Must contain every
# base_commit in the manifest (clone with full history; run `git fetch --all`
# if a commit is missing). Override with ACE_REPO_CLONE.
REPO_CLONE = Path(
    os.environ.get("ACE_REPO_CLONE", str(EXPERIMENT_DIR / "repo" / "opentelemetry-collector"))
)

# CONFIG: claude CLI binary (headless Claude Code). Override with ACE_CLAUDE_BIN.
CLAUDE_BIN = os.environ.get("ACE_CLAUDE_BIN", "claude")

# CONFIG: parent directory for temporary run workspaces.
WORKSPACE_BASE = Path(os.environ.get("ACE_WORKSPACE_BASE", tempfile.gettempdir()))

# ---------------------------------------------------------------------------
# Registered constants. Do not change without an amendment to the
# pre-registration (meta/experiment/PREREGISTRATION.md).
# ---------------------------------------------------------------------------

SEED = 20260801                 # seed for all local randomness (schedule shuffle)
MAX_TURNS = 200                 # per-run turn cap
WALL_CLOCK_SECONDS = 45 * 60    # per-run wall-clock cap
DEFAULT_MODEL = "claude-sonnet-5"
ARMS = ("original", "ace", "naive")

# The FIXED prompt template. Identical bytes across arms by construction: the
# template never varies, and the interpolated title/body come from the task
# manifest, which is shared across arms. The template never mentions
# documentation. Do not edit.
PROMPT_TEMPLATE = (
    "{title}\n"
    "\n"
    "{body}\n"
    "\n"
    "Implement this change in this repository. Work until the change is complete.\n"
)

# Standard prices in USD per million tokens, used for cost_usd_standard.
# These are the registered standard rates (the harness's own total_cost_usd may
# reflect discounts or cache-pricing differences and is kept in result.json).
PRICES_PER_MTOK = {
    "claude-sonnet-5": {
        "input_tokens": 3.00,
        "output_tokens": 15.00,
        "cache_read_input_tokens": 0.30,
        "cache_creation_input_tokens": 3.75,
    },
    "claude-opus-5": {
        "input_tokens": 5.00,
        "output_tokens": 25.00,
        "cache_read_input_tokens": 0.50,
        "cache_creation_input_tokens": 6.25,
    },
}

USAGE_KEYS = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)

# Identity used for the workspace baseline commit. Never pushed anywhere.
GIT_IDENT = [
    "-c", "user.name=ace-100 harness",
    "-c", "user.email=harness@ace-100.invalid",
    "-c", "commit.gpgsign=false",
]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def run_git(args: list[str], cwd: Path | None = None) -> str:
    """Run a git command; exit loudly on failure (all git failures are infra)."""
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"git {' '.join(args[:4])}... failed: {proc.stderr.strip()}")
    return proc.stdout


def load_json(path: Path) -> object:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_manifest(path: Path) -> dict:
    manifest = load_json(path)
    if not isinstance(manifest, dict) or "tasks" not in manifest:
        sys.exit(f"{path}: not a task manifest (no 'tasks' key)")
    return manifest


def find_task(manifest: dict, task_id: str) -> dict:
    for task in manifest["tasks"]:
        if task["task_id"] == task_id:
            return task
    sys.exit(f"task {task_id!r} not found in manifest")


def load_corpus_paths() -> list[str]:
    """Corpus manifest: the registered list of docs-corpus relative paths.

    Accepts either a bare JSON list or an object with a 'paths' key, so the
    arm-building tool has some latitude in its output format.
    """
    path = EXPERIMENT_DIR / "arms" / "corpus-manifest.json"
    if not path.exists():
        sys.exit(f"corpus manifest missing: {path} (build the arms first)")
    data = load_json(path)
    if isinstance(data, dict):
        data = data.get("paths", data.get("files"))
    if not isinstance(data, list):
        sys.exit(f"{path}: unrecognized corpus manifest format")
    return [str(p) for p in data]


def arm_docs_dir(arm: str) -> Path:
    d = EXPERIMENT_DIR / "arms" / f"{arm}-docs"
    if not d.is_dir():
        sys.exit(f"arm docs snapshot missing: {d} (build the arms first)")
    return d


def price_table(model: str) -> dict:
    """Look up the standard price row for a model id (substring match so that
    e.g. a dated model id still resolves)."""
    for key, row in PRICES_PER_MTOK.items():
        if key in model:
            return row
    sys.exit(f"no standard price registered for model {model!r}; "
             f"add it to PRICES_PER_MTOK")


def compute_cost_usd_standard(usage: dict, model: str) -> float:
    row = price_table(model)
    cost = 0.0
    for key in USAGE_KEYS:
        cost += (usage.get(key, 0) or 0) * row[key] / 1_000_000
    return round(cost, 6)


# ---------------------------------------------------------------------------
# Workspace materialization
# ---------------------------------------------------------------------------

def materialize_workspace(base_commit: str, arm: str, corpus_paths: list[str]) -> Path:
    """Create a run workspace: checkout of base_commit with the arm's docs
    snapshot (taken at the pinned commit C) replacing the docs corpus.

    Returns the workspace path. The caller is responsible for calling
    remove_workspace() afterwards.
    """
    if not (REPO_CLONE / ".git").exists() and not (REPO_CLONE / "HEAD").exists():
        sys.exit(f"repo clone not found at {REPO_CLONE} (CONFIG: REPO_CLONE / "
                 f"ACE_REPO_CLONE)")

    # Verify the base commit exists locally before creating the worktree.
    proc = subprocess.run(
        ["git", "-C", str(REPO_CLONE), "rev-parse", "--verify", f"{base_commit}^{{commit}}"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        sys.exit(f"base commit {base_commit} not in {REPO_CLONE}; "
                 f"run `git -C {REPO_CLONE} fetch --all` and retry")

    parent = Path(tempfile.mkdtemp(prefix="ace100-run-", dir=WORKSPACE_BASE))
    ws = parent / "ws"

    # Detached worktree: cheap, shares the object store, isolated working tree.
    run_git(["-C", str(REPO_CLONE), "worktree", "add", "--detach", str(ws), base_commit])

    # 1) Delete every corpus-manifest path that exists at the base commit.
    #    (Docs files created between C and B_i that are NOT in the corpus
    #    manifest are deliberately left alone, per the registered procedure.)
    for rel in corpus_paths:
        target = ws / rel
        if target.is_file():
            target.unlink()

    # 2) Copy the arm's docs tree in, keyed by corpus-relative path.
    src_root = arm_docs_dir(arm)
    for src in sorted(src_root.rglob("*")):
        if src.is_file():
            rel = src.relative_to(src_root)
            dest = ws / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

    # 3) Commit so the run starts from a clean tree and the produced diff is
    #    recoverable with plain `git diff`. --allow-empty keeps the procedure
    #    uniform even if the arm snapshot happens to match the checkout.
    run_git(["-C", str(ws), *GIT_IDENT, "add", "-A"])
    run_git(["-C", str(ws), *GIT_IDENT, "commit", "--allow-empty", "--no-verify",
             "-m", f"ace-100: install {arm} docs snapshot"])
    return ws


def remove_workspace(ws: Path) -> None:
    """Tear down a worktree created by materialize_workspace()."""
    try:
        subprocess.run(
            ["git", "-C", str(REPO_CLONE), "worktree", "remove", "--force", str(ws)],
            capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "-C", str(REPO_CLONE), "worktree", "prune"],
            capture_output=True, text=True,
        )
        shutil.rmtree(ws.parent, ignore_errors=True)
    except OSError:
        pass  # best-effort cleanup; leftover temp dirs are harmless


# ---------------------------------------------------------------------------
# Prompt composition
# ---------------------------------------------------------------------------

def compose_prompt(task: dict) -> str:
    """Fill the fixed template: issue title/body when present, falling back
    per-field to the PR title/body (a linked issue can be a cross-repo stub
    with no fetchable content — see the manifest's fetch_failed marker).
    Never mentions documentation."""
    prompt_src = task.get("prompt") or {}
    issue = prompt_src.get("issue") or {}
    title = (issue.get("title") or "").strip() or (prompt_src.get("pr_title") or "").strip()
    body = (issue.get("body") or "").strip() or (prompt_src.get("pr_body") or "").strip()
    if not title and not body:
        sys.exit(f"{task.get('task_id')}: task prompt is empty; refusing to run the cell")
    return PROMPT_TEMPLATE.format(title=title, body=body)


# ---------------------------------------------------------------------------
# Headless claude invocation
# ---------------------------------------------------------------------------

def invoke_claude(prompt: str, workspace: Path, model: str) -> dict:
    """Run headless claude in the workspace under the registered caps.

    Returns a dict with: returncode, stdout, stderr, wall_seconds, timed_out.
    The 45-minute wall clock is enforced here by killing the process;
    the 200-turn cap is enforced by the harness via --max-turns.

    Session hygiene: runs use the operator's normal harness config — a
    pristine CLAUDE_CONFIG_DIR breaks authentication (macOS keeps the OAuth
    in the Keychain but login state in the config dir). The contamination
    surface was audited instead and is recorded in
    audit/harness-environment.json: no user-level CLAUDE.md, no hooks,
    preference-only settings, and project memory is keyed by cwd so fresh
    temp workspaces load none.
    """
    env = dict(os.environ)
    cmd = [
        CLAUDE_BIN,
        "-p", prompt,
        "--output-format", "json",
        "--model", model,
        "--max-turns", str(MAX_TURNS),
        # Removes the harness's network tools. Full network isolation is
        # enforced by the sandbox environment, not by this flag.
        "--disallowed-tools", "WebFetch,WebSearch",
        # Required for unattended runs (file edits / bash without prompts).
        # Safe only because the runner executes inside the registered sandbox.
        "--dangerously-skip-permissions",
    ]
    started = dt.datetime.now(dt.timezone.utc)
    proc = subprocess.Popen(
        cmd, cwd=workspace, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=WALL_CLOCK_SECONDS)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        stdout, stderr = proc.communicate()
    wall_seconds = (dt.datetime.now(dt.timezone.utc) - started).total_seconds()
    return {
        "returncode": proc.returncode,
        "stdout": stdout or "",
        "stderr": stderr or "",
        "wall_seconds": round(wall_seconds, 1),
        "timed_out": timed_out,
        "started_at": started.isoformat(timespec="seconds"),
    }


def parse_harness_json(stdout: str) -> dict | None:
    """Parse the harness result JSON from stdout. Returns None if absent or
    malformed (which the caller treats as an infra failure unless the wall
    clock killed the process)."""
    stdout = stdout.strip()
    if not stdout:
        return None
    # The result is the last JSON object on stdout; normally stdout IS the
    # object, but be tolerant of stray leading lines.
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        pass
    last_brace = stdout.rfind("\n{")
    if last_brace != -1:
        try:
            return json.loads(stdout[last_brace:])
        except json.JSONDecodeError:
            return None
    return None


# ---------------------------------------------------------------------------
# Transcript location and analysis
# ---------------------------------------------------------------------------

def munge_cwd(path: Path) -> str:
    """Claude Code munges the workspace cwd into a project directory name by
    replacing non-alphanumeric characters with '-'."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def locate_transcript(workspace: Path, session_id: str | None,
                      started_at_iso: str) -> Path | None:
    """Find the transcript JSONL under ~/.claude/projects.

    Primary: <projects>/<munged-cwd>/<session_id>.jsonl. Fallbacks: glob for
    the session id anywhere under projects/, then (for wall-clock kills where
    no session id was reported) the newest .jsonl in the munged project dir
    modified after the run started.
    """
    projects = Path.home() / ".claude" / "projects"
    if not projects.is_dir():
        return None
    project_dir = projects / munge_cwd(workspace)
    if session_id:
        direct = project_dir / f"{session_id}.jsonl"
        if direct.is_file():
            return direct
        hits = list(projects.glob(f"*/{session_id}.jsonl"))
        if hits:
            return hits[0]
    if project_dir.is_dir():
        started = dt.datetime.fromisoformat(started_at_iso).timestamp()
        candidates = [
            p for p in project_dir.glob("*.jsonl")
            if p.stat().st_mtime >= started - 5
        ]
        if candidates:
            return max(candidates, key=lambda p: p.stat().st_mtime)
    return None


def iter_transcript(path: Path):
    """Yield parsed JSONL entries, skipping malformed lines (the final line
    can be truncated when the process was killed at the wall clock)."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _result_char_count(content: object) -> int:
    """Character count of a tool_result content field, which is either a
    string or a list of content blocks."""
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        total = 0
        for block in content:
            if isinstance(block, dict):
                total += len(block.get("text") or "")
            elif isinstance(block, str):
                total += len(block)
        return total
    return 0


def analyze_transcript(transcript: Path, workspace: Path,
                       corpus_paths: list[str]) -> dict:
    """Extract Read/Grep/Glob tool activity from the transcript.

    Returns the files_read.json payload:
      reads: one record per Read/Grep/Glob tool call
      docs_files_read: number of DISTINCT corpus paths opened via Read
      docs_tokens_read_estimate: sum(chars of Read results on corpus paths)/4

    Limitation (documented, applies identically across arms): docs content
    consumed through Bash (e.g. `cat README.md`) is not attributed here.
    """
    corpus_set = set(corpus_paths)
    tracked = {"Read", "Grep", "Glob"}

    # Pass 1: tool_use blocks (assistant messages) -> id -> (name, input)
    tool_uses: dict[str, tuple[str, dict]] = {}
    entries = list(iter_transcript(transcript))
    for entry in entries:
        message = entry.get("message") or {}
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use" \
                    and block.get("name") in tracked:
                tool_uses[block.get("id", "")] = (
                    block["name"], block.get("input") or {}
                )

    # Pass 2: tool_result blocks (user messages) -> id -> chars
    result_chars: dict[str, int] = {}
    for entry in entries:
        message = entry.get("message") or {}
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                tid = block.get("tool_use_id", "")
                if tid in tool_uses:
                    result_chars[tid] = result_chars.get(tid, 0) + \
                        _result_char_count(block.get("content"))

    def to_corpus_rel(raw_path: str | None) -> str | None:
        """Map an absolute (or workspace-relative) tool path to a
        corpus-relative path, or None if it is not a corpus file."""
        if not raw_path:
            return None
        p = Path(raw_path)
        if not p.is_absolute():
            p = workspace / p
        try:
            rel = str(p.resolve().relative_to(workspace.resolve()))
        except ValueError:
            return None
        return rel if rel in corpus_set else None

    reads = []
    docs_read_paths: set[str] = set()
    docs_chars = 0
    for tid, (name, tool_input) in tool_uses.items():
        raw_path = tool_input.get("file_path") or tool_input.get("path")
        rel = to_corpus_rel(raw_path)
        chars = result_chars.get(tid, 0)
        reads.append({
            "tool": name,
            "input_path": raw_path,
            "pattern": tool_input.get("pattern"),
            "corpus_path": rel,
            "result_chars": chars,
        })
        # Headline metrics count only direct Read calls on corpus files.
        if name == "Read" and rel is not None:
            docs_read_paths.add(rel)
            docs_chars += chars

    return {
        "reads": reads,
        "distinct_docs_paths": sorted(docs_read_paths),
        "docs_files_read": len(docs_read_paths),
        "docs_tokens_read_estimate": docs_chars // 4,
    }


def usage_from_transcript(transcript: Path) -> tuple[dict, int]:
    """Reconstruct (usage, num_turns) by summing per-request usage across all
    assistant messages. Used when the harness JSON is unavailable (cap_wall).
    Each assistant message's usage is per-API-request, so summing gives the
    billed total; retried requests may cause slight overcounting."""
    usage = {k: 0 for k in USAGE_KEYS}
    num_turns = 0
    for entry in iter_transcript(transcript):
        if entry.get("type") != "assistant":
            continue
        num_turns += 1
        message_usage = (entry.get("message") or {}).get("usage") or {}
        for key in USAGE_KEYS:
            usage[key] += int(message_usage.get(key) or 0)
    return usage, num_turns


# ---------------------------------------------------------------------------
# One cell
# ---------------------------------------------------------------------------

def run_one_cell(manifest: dict, task_id: str, arm: str, trial: int,
                 model: str, force: bool = False,
                 keep_workspace: bool = False) -> str:
    """Execute one cell end to end. Returns the run status string.
    Returns "skipped" without side effects when the cell is already done."""
    if arm not in ARMS:
        sys.exit(f"unknown arm {arm!r}; expected one of {ARMS}")
    task = find_task(manifest, task_id)
    corpus_paths = load_corpus_paths()

    trial_dir = EXPERIMENT_DIR / "data" / "runs" / task_id / arm / f"trial-{trial}"
    result_path = trial_dir / "result.json"

    # Idempotence: a written result.json means the cell ran to a recorded
    # outcome (including cap_turns / cap_wall / failed). Infra errors do not
    # write result.json, so they are retried on rerun.
    if result_path.exists() and not force:
        print(f"[skip] {task_id}/{arm}/trial-{trial}: result.json exists "
              f"(use --force to rerun)")
        return "skipped"

    trial_dir.mkdir(parents=True, exist_ok=True)
    prompt = compose_prompt(task)
    (trial_dir / "prompt.txt").write_text(prompt, encoding="utf-8")

    print(f"[run ] {task_id}/{arm}/trial-{trial}: materializing workspace at "
          f"{task['base_commit'][:12]}")
    ws = materialize_workspace(task["base_commit"], arm, corpus_paths)
    try:
        print(f"[run ] {task_id}/{arm}/trial-{trial}: invoking {CLAUDE_BIN} "
              f"(model={model}, max_turns={MAX_TURNS}, "
              f"wall_cap={WALL_CLOCK_SECONDS}s)")
        invocation = invoke_claude(prompt, ws, model)
        ended_at = utc_now_iso()

        # Keep stderr for debugging regardless of outcome.
        (trial_dir / "claude-stderr.log").write_text(
            invocation["stderr"], encoding="utf-8")

        harness = parse_harness_json(invocation["stdout"])

        # Classify the outcome.
        if invocation["timed_out"]:
            status = "cap_wall"
        elif harness is None:
            status = "infra"
        elif harness.get("subtype") == "error_max_turns":
            status = "cap_turns"
        elif harness.get("is_error") or harness.get("subtype") not in (None, "success"):
            # No model work at all (zero tokens) means the harness never got
            # off the ground — auth, config, or environment trouble. That is
            # an infrastructure failure (retryable), not a task failure.
            u = harness.get("usage") or {}
            spent = sum(u.get(k, 0) or 0 for k in (
                "input_tokens", "output_tokens",
                "cache_read_input_tokens", "cache_creation_input_tokens"))
            status = "infra" if spent == 0 else "failed"
        else:
            status = "completed"

        # Collect the diff: stage everything the agent left behind (including
        # untracked new files), then diff against the baseline commit.
        run_git(["-C", str(ws), *GIT_IDENT, "add", "-A"])
        diff = run_git(["-C", str(ws), "diff", "--cached", "--binary"])
        (trial_dir / "diff.patch").write_text(diff, encoding="utf-8")

        # Copy the transcript into the data layout.
        session_id = (harness or {}).get("session_id")
        transcript_src = locate_transcript(ws, session_id, invocation["started_at"])
        transcript_dst = trial_dir / "transcript.jsonl"
        if transcript_src is not None:
            shutil.copy2(transcript_src, transcript_dst)
        else:
            print(f"[warn] {task_id}/{arm}/trial-{trial}: transcript not found "
                  f"under ~/.claude/projects", file=sys.stderr)

        # Docs-read instrumentation from the transcript.
        if transcript_dst.exists():
            files_read = analyze_transcript(transcript_dst, ws, corpus_paths)
        else:
            files_read = {"reads": [], "distinct_docs_paths": [],
                          "docs_files_read": 0, "docs_tokens_read_estimate": 0,
                          "note": "transcript missing"}
        (trial_dir / "files_read.json").write_text(
            json.dumps(files_read, indent=2), encoding="utf-8")

        # Usage and turn count: harness JSON first, transcript reconstruction
        # as the fallback (cap_wall kills lose the harness JSON).
        if harness is not None and isinstance(harness.get("usage"), dict):
            usage = {k: int(harness["usage"].get(k) or 0) for k in USAGE_KEYS}
            num_turns = int(harness.get("num_turns") or 0)
        elif transcript_dst.exists():
            usage, num_turns = usage_from_transcript(transcript_dst)
        else:
            usage, num_turns = {k: 0 for k in USAGE_KEYS}, 0

        cost = compute_cost_usd_standard(usage, model)

        # result.json: the harness JSON verbatim when we have it; a synthetic
        # stub for cap_wall (a legitimate recorded outcome). Infra errors get
        # infra-error.json instead so the cell is retried.
        if status == "infra":
            (trial_dir / "infra-error.json").write_text(json.dumps({
                "returncode": invocation["returncode"],
                "stdout_tail": invocation["stdout"][-4000:],
                "stderr_tail": invocation["stderr"][-4000:],
                "recorded_at": ended_at,
            }, indent=2), encoding="utf-8")
        elif harness is not None:
            result_path.write_text(json.dumps(harness, indent=2), encoding="utf-8")
        else:  # cap_wall without harness JSON
            result_path.write_text(json.dumps({
                "harness_json_missing": True,
                "reason": "process killed at wall-clock cap",
                "returncode": invocation["returncode"],
                "session_id": session_id,
            }, indent=2), encoding="utf-8")

        # Append the run record to the run index.
        record = {
            "task_id": task_id,
            "arm": arm,
            "trial": trial,
            "started_at": invocation["started_at"],
            "ended_at": ended_at,
            "status": status,
            "model": model,
            "num_turns": num_turns,
            "wall_seconds": invocation["wall_seconds"],
            "usage": usage,
            "cost_usd_standard": cost,
            "docs_files_read": files_read["docs_files_read"],
            "docs_tokens_read_estimate": files_read["docs_tokens_read_estimate"],
        }
        runs_index = EXPERIMENT_DIR / "data" / "runs.jsonl"
        runs_index.parent.mkdir(parents=True, exist_ok=True)
        with open(runs_index, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

        print(f"[done] {task_id}/{arm}/trial-{trial}: status={status} "
              f"turns={num_turns} wall={invocation['wall_seconds']}s "
              f"cost=${cost}")
        return status
    finally:
        if keep_workspace:
            print(f"[keep] workspace retained at {ws}")
        else:
            remove_workspace(ws)


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

def cmd_schedule(args: argparse.Namespace) -> None:
    manifest = load_manifest(Path(args.manifest))

    # Refuse to start unless every task has a registered test command: the
    # evaluation stage depends on it, and discovering a missing command after
    # burning run budget would be unrecoverable.
    missing = [t["task_id"] for t in manifest["tasks"] if not t.get("test_command")]
    if missing:
        sys.exit("refusing to schedule: test_command is null for tasks: "
                 + ", ".join(missing)
                 + "\nFill in test_command in the manifest before running.")

    arms = tuple(a.strip() for a in args.arms.split(",") if a.strip())
    for arm in arms:
        if arm not in ARMS:
            sys.exit(f"unknown arm {arm!r}; expected subset of {ARMS}")
        arm_docs_dir(arm)  # fail early if the arm snapshot is missing
    load_corpus_paths()    # fail early if the corpus manifest is missing

    # Enumerate cells in deterministic order, then seeded-shuffle.
    cells = [
        (task["task_id"], arm, trial)
        for task in manifest["tasks"]
        for arm in arms
        for trial in range(1, args.trials + 1)
    ]
    random.Random(SEED).shuffle(cells)

    print(f"schedule: {len(cells)} cells "
          f"({len(manifest['tasks'])} tasks x {len(arms)} arms x "
          f"{args.trials} trials), seed={SEED}")

    if args.dry_run:
        for i, (task_id, arm, trial) in enumerate(cells, 1):
            done = (EXPERIMENT_DIR / "data" / "runs" / task_id / arm
                    / f"trial-{trial}" / "result.json").exists()
            print(f"  {i:3d}. {task_id}/{arm}/trial-{trial}"
                  + ("  [already done]" if done else ""))
        return

    counts: dict[str, int] = {}
    for task_id, arm, trial in cells:
        status = run_one_cell(manifest, task_id, arm, trial,
                              model=args.model)
        counts[status] = counts.get(status, 0) + 1
        if status == "infra":
            # Infrastructure failure: stop rather than burn budget on a broken
            # environment. Task failures (status "failed") do NOT stop the
            # schedule -- they are legitimate experimental outcomes.
            print("schedule: stopping on infra error; fix the environment and "
                  "rerun (completed cells are skipped automatically)",
                  file=sys.stderr)
            sys.exit(1)

    print("schedule: finished. " +
          ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))


def cmd_one(args: argparse.Namespace) -> None:
    manifest = load_manifest(Path(args.manifest))
    status = run_one_cell(manifest, args.task, args.arm, args.trial,
                          model=args.model, force=args.force,
                          keep_workspace=args.keep_workspace)
    if status == "infra":
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_one = sub.add_parser("one", help="run a single (task, arm, trial) cell")
    p_one.add_argument("--manifest", required=True, help="path to manifest.json")
    p_one.add_argument("--task", required=True, help="task_id, e.g. pr-15296")
    p_one.add_argument("--arm", required=True, choices=ARMS)
    p_one.add_argument("--trial", required=True, type=int, help="1-based trial number")
    p_one.add_argument("--model", default=DEFAULT_MODEL)
    p_one.add_argument("--force", action="store_true",
                       help="rerun even if result.json exists")
    p_one.add_argument("--keep-workspace", action="store_true",
                       help="retain the temp workspace for debugging")
    p_one.set_defaults(func=cmd_one)

    p_sched = sub.add_parser("schedule", help="run all cells sequentially")
    p_sched.add_argument("--manifest", required=True, help="path to manifest.json")
    p_sched.add_argument("--trials", type=int, default=4)
    p_sched.add_argument("--arms", default=",".join(ARMS),
                         help="comma-separated arm list (default: all three)")
    p_sched.add_argument("--model", default=DEFAULT_MODEL)
    p_sched.add_argument("--dry-run", action="store_true",
                         help="print the shuffled cell order and exit")
    p_sched.set_defaults(func=cmd_schedule)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
