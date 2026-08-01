#!/usr/bin/env python3
"""Build and gate the three arm docs snapshots of the ACE-100 documentation experiment.

Implements the arm-construction procedure registered in
meta/experiment/PREREGISTRATION.md. Arms are built ONCE from a pinned commit C
of the target repository; run_cell.py later replays each task at its own base
commit with the docs corpus replaced by an arm snapshot built here.

Steps (in registered order):

    pin       clone the target repo, resolve the pinned commit C, record it
    original  capture the docs corpus at C  -> arms/corpus-manifest.json,
              arms/original-docs/
    ace       adopt the ACE-100 kit into a copy of the pinned checkout, run
              the ace-migrate skill under headless claude (claude-opus-5),
              capture the governed corpus -> arms/ace-docs/
    naive     token-matched compression of every original corpus file with
              claude-opus-5 (registered treatment string), original layout
              -> arms/naive-docs/
    gates     tools/check.sh must pass on the ace working copy; token totals
              of all three arms -> arms/gates/measure.json; assert the naive
              total is within +/-10% of the ace total
    preserve  an opus-5 judge compares original vs rewritten for BOTH the ace
              and naive arms and reports dropped factual/procedural content
              -> arms/gates/preservation-{arm}.json; any flag exits 1 with a
              repair worklist

    all       run every step above in order

Usage:

    build_arms.py --workdir /path/to/scratch --step pin [--pin <commit>]
    build_arms.py --workdir /path/to/scratch --step ace [--kit /path/to/ace-100] [--resume]
    build_arms.py --workdir /path/to/scratch --step all

Temporal firewall: the 'ace' and 'naive' steps REFUSE to run until
meta/experiment/manifest.json exists (select_tasks.py runs first), so the task
set is frozen before any treated docs exist and treatment construction cannot
chase the tasks.

Idempotency: every step either skips cleanly when its outputs exist or
rebuilds deterministically; --force rebuilds, --resume continues a multi-
session ace migration.

Network note: the pin/original steps talk to github.com (blob-filtered clone
lazily fetches file contents). The naive/gates/preserve steps talk to the
Anthropic API. The 'ace' step runs the claude CLI; --disallowed-tools removes
its WebFetch/WebSearch tools, but that flag is a convenience, not isolation —
run inside the registered sandbox if the migration must be network-free.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path, PurePosixPath

# The anthropic SDK is needed only by the naive/gates/preserve steps.
# pin/original/ace work without it (ace uses the claude CLI).
try:
    import anthropic
except ImportError:  # pragma: no cover - surfaced at use time with a clear message
    anthropic = None

try:
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request
except Exception:  # older SDK: plain dicts are accepted by the batches endpoint
    MessageCreateParamsNonStreaming = dict  # type: ignore
    Request = None  # type: ignore

# ---------------------------------------------------------------------------
# CONFIG: per-repo configuration. Every item marked CONFIG must be checked
# when adopting this tool for a different target repository.
# ---------------------------------------------------------------------------

# CONFIG: experiment directory holding arms/, data/, and the task manifest.
# Defaults to the parent of tools/ (i.e. meta/experiment when this file lives
# at meta/experiment/tools/build_arms.py). Override with ACE_EXPERIMENT_DIR.
EXPERIMENT_DIR = Path(
    os.environ.get("ACE_EXPERIMENT_DIR", str(Path(__file__).resolve().parent.parent))
)
ARMS_DIR = EXPERIMENT_DIR / "arms"
GATES_DIR = ARMS_DIR / "gates"
TASK_MANIFEST = EXPERIMENT_DIR / "manifest.json"

# CONFIG: target repository (pre-registered).
REPO_URL = "https://github.com/open-telemetry/opentelemetry-collector"

# CONFIG: ACE-100 kit repository root. Default: three levels above this file
# (repo-root/meta/experiment/tools/build_arms.py -> repo-root). Override with
# the --kit flag. The kit must have release tarballs under meta/dist/
# (run meta/publish.sh to build them) unless --kit-tarball/--skill-tarball
# point elsewhere.
DEFAULT_KIT_ROOT = Path(__file__).resolve().parents[3]

# CONFIG: claude CLI binary (headless Claude Code). Override with ACE_CLAUDE_BIN.
CLAUDE_BIN = os.environ.get("ACE_CLAUDE_BIN", "claude")

# ---------------------------------------------------------------------------
# Registered constants. Do not change without an amendment to the
# pre-registration (meta/experiment/PREREGISTRATION.md).
# ---------------------------------------------------------------------------

# Seed for all local randomness. This tool currently draws no random numbers,
# but the registration requires every tool to seed identically so any future
# tie-breaking is reproducible.
SEED = 20260801

# Migration / compression / judging model (registered).
OPUS_MODEL = "claude-opus-5"

# Tokenizer used for every token count in this tool: the SUBJECT model's
# (claude-sonnet-5), because arm sizes matter to the subject agent that reads
# the docs. Counting uses the API count_tokens endpoint (registered).
TOKEN_COUNT_MODEL = "claude-sonnet-5"

# The naive-arm total must land within this band of the ace-arm total.
NAIVE_BAND = 0.10

# STANDARD PRICES per MTok (registered), used for cost_usd_standard.
STANDARD_PRICES_PER_MTOK = {
    "claude-sonnet-5": {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75},
    "claude-opus-5": {"input": 5.00, "output": 25.00, "cache_read": 0.50, "cache_write": 6.25},
}

# The naive treatment string, VERBATIM from the pre-registration. Do not edit.
def treatment_text(n_tokens: int) -> str:
    return (
        f"rewrite to approximately {n_tokens} tokens; "
        "preserve all factual and procedural content; no other constraints"
    )

# ---------------------------------------------------------------------------
# Operational knobs (not registered; tune freely).
# ---------------------------------------------------------------------------

MIGRATION_MAX_TURNS = 800          # generous cap for one headless migration session
MIGRATION_TIMEOUT_S = 6 * 3600     # subprocess wall clock per migration session
JUDGE_MAX_TOKENS = 8192            # per preservation-judge response
BATCH_POLL_SECONDS = 30            # Message Batches poll interval

# Directories never captured into an arm snapshot (agent config, git internals,
# and the staging area for files the kit adoption displaced).
CAPTURE_EXCLUDED_SEGMENTS = {
    ".git", ".agents", ".claude", ".windsurf", ".continue", ".ace-migration-staging",
}

# Kit-owned doc trees: present only in the ace arm, never a rewrite of an
# original file, so the preservation judge skips them as mapping candidates.
KIT_DOC_PREFIXES = ("docs/standard/", "docs/dictionary/", "docs/templates/", "docs/example/")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def die(msg: str, code: int = 2) -> None:
    print(f"build_arms: error: {msg}", file=sys.stderr)
    sys.exit(code)


def log(msg: str) -> None:
    print(f"[build_arms] {msg}", flush=True)


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text())


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=False) + "\n")
    tmp.replace(path)


def run(cmd, cwd=None, check=True, timeout=None, capture=True):
    """Boring subprocess wrapper. Returns CompletedProcess with text output."""
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=capture,
        text=True,
        timeout=timeout,
    )
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()[-2000:]
        die(f"command failed ({proc.returncode}): {' '.join(map(str, cmd))}\n{detail}")
    return proc


def git(repo: Path, *args, check=True, timeout=None):
    return run(["git", "-C", str(repo), *args], check=check, timeout=timeout)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def read_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8", errors="replace")


def cost_usd_standard(usage: dict, model: str) -> float:
    """usage dict with API field names -> USD at the registered standard prices."""
    p = STANDARD_PRICES_PER_MTOK[model]
    return round(
        (
            usage.get("input_tokens", 0) * p["input"]
            + usage.get("output_tokens", 0) * p["output"]
            + usage.get("cache_read_input_tokens", 0) * p["cache_read"]
            + usage.get("cache_creation_input_tokens", 0) * p["cache_write"]
        )
        / 1_000_000.0,
        6,
    )


def add_usage(total: dict, usage_obj) -> None:
    """Accumulate an SDK Usage object (or dict) into a plain dict."""
    for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
        v = usage_obj.get(k, 0) if isinstance(usage_obj, dict) else getattr(usage_obj, k, 0)
        total[k] = total.get(k, 0) + (v or 0)


def require_sdk():
    if anthropic is None:
        die("the 'anthropic' package is not installed (pip install anthropic)")


def api_client():
    require_sdk()
    # Credentials resolve from the environment (ANTHROPIC_API_KEY / auth profile).
    return anthropic.Anthropic()


def temporal_firewall_check(step: str) -> None:
    """The ace/naive steps must not run before the task manifest exists."""
    if not TASK_MANIFEST.exists():
        die(
            f"refusing to run step '{step}': {TASK_MANIFEST} does not exist.\n"
            "The pre-registered order requires select_tasks.py to run FIRST\n"
            "(temporal firewall: the task set is frozen before any treated docs\n"
            "exist, so treatment construction cannot be influenced by knowledge\n"
            "of the evaluation tasks). Run select_tasks.py, commit the manifest,\n"
            "then re-run this step.",
            code=1,
        )


# ---------------------------------------------------------------------------
# Corpus definition (registered; constant everywhere in the experiment)
# ---------------------------------------------------------------------------

def is_corpus_path(rel: str) -> bool:
    """DOCS CORPUS DEFINITION: all *.md and *.mdx files EXCLUDING CHANGELOG*,
    files under testdata/, .github/, node_modules/, and LICENSE-like files.
    Registered; do not change without a pre-registration amendment."""
    p = PurePosixPath(rel)
    if p.suffix.lower() not in (".md", ".mdx"):
        return False
    for seg in p.parts[:-1]:
        if seg in ("testdata", "node_modules", ".github"):
            return False
    name_upper = p.name.upper()
    stem_upper = p.stem.upper()
    if name_upper.startswith("CHANGELOG"):
        return False
    if stem_upper in ("LICENSE", "LICENCE", "NOTICE", "COPYING", "PATENTS"):
        return False
    if stem_upper.startswith(("LICENSE-", "LICENCE-")):
        return False
    return True


def safe_relpath(rel: str) -> None:
    p = PurePosixPath(rel)
    if p.is_absolute() or ".." in p.parts:
        die(f"unsafe repository path from git: {rel}")


# ---------------------------------------------------------------------------
# Token counting (API count_tokens, cached by content hash)
# ---------------------------------------------------------------------------

class TokenCounter:
    """count_tokens with an on-disk cache keyed by (model, sha256(text))."""

    def __init__(self, client, cache_path: Path):
        self.client = client
        self.cache_path = cache_path
        self.cache: dict = load_json(cache_path, {}) or {}
        self._dirty = 0

    def count(self, text: str) -> int:
        if not text.strip():
            return 0
        key = f"{TOKEN_COUNT_MODEL}:{sha256_text(text)}"
        if key in self.cache:
            return self.cache[key]
        n = self._count_api(text)
        self.cache[key] = n
        self._dirty += 1
        if self._dirty >= 100:
            self.save()
        return n

    def _count_api(self, text: str) -> int:
        return api_retry(
            lambda: self.client.messages.count_tokens(
                model=TOKEN_COUNT_MODEL,
                messages=[{"role": "user", "content": text}],
            ).input_tokens,
            "count_tokens",
        )

    def tree_total(self, root: Path) -> tuple[int, int, dict]:
        """(file_count, token_total, per_file) over every file in a tree."""
        per_file = {}
        for f in sorted(p for p in root.rglob("*") if p.is_file()):
            rel = f.relative_to(root).as_posix()
            per_file[rel] = self.count(read_text(f))
        self.save()
        return len(per_file), sum(per_file.values()), per_file

    def save(self) -> None:
        if self._dirty or not self.cache_path.exists():
            save_json(self.cache_path, self.cache)
            self._dirty = 0


# ---------------------------------------------------------------------------
# Message Batches helpers
# ---------------------------------------------------------------------------

def make_batch_request(custom_id: str, params: dict):
    if Request is not None:
        return Request(custom_id=custom_id, params=params)
    return {"custom_id": custom_id, "params": params}


def api_retry(fn, label: str, attempts: int = 6):
    """Retry transient API failures (connection errors, rate limits, 5xx)
    with exponential backoff; non-retryable errors raise immediately."""
    delay = 5.0
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except (anthropic.APIConnectionError, anthropic.RateLimitError) as e:
            err = repr(e)
        except anthropic.APIStatusError as e:
            if e.status_code < 500:
                raise
            err = repr(e)
        if attempt == attempts:
            raise RuntimeError(f"{label}: retries exhausted ({err})")
        log(f"{label}: transient error, retry {attempt}/{attempts - 1} in {delay:.0f}s ({err[:100]})")
        time.sleep(delay)
        delay = min(120, delay * 2)


def run_message_batch(client, requests: list, label: str, poll_seconds: int):
    """Submit one Message Batch, poll to completion, return (batch_id, {custom_id: result})."""
    log(f"{label}: submitting batch of {len(requests)} request(s)")
    batch = api_retry(lambda: client.messages.batches.create(requests=requests),
                      f"{label} create")
    log(f"{label}: batch {batch.id} created; polling every {poll_seconds}s")
    while True:
        b = api_retry(lambda: client.messages.batches.retrieve(batch.id),
                      f"{label} poll")
        if b.processing_status == "ended":
            break
        rc = b.request_counts
        log(f"{label}: {batch.id} processing={rc.processing} succeeded={rc.succeeded} errored={rc.errored}")
        time.sleep(poll_seconds)
    results = {}
    for r in api_retry(lambda: list(client.messages.batches.results(batch.id)),
                       f"{label} results"):
        results[r.custom_id] = r  # results arrive in any order; key by custom_id
    log(f"{label}: batch {batch.id} ended with {len(results)} result(s)")
    return batch.id, results


def single_message(client, params: dict):
    """One non-batch call; streams when max_tokens is large (SDK timeout guard)."""
    def call():
        if params.get("max_tokens", 0) > 16000:
            with client.messages.stream(**params) as s:
                return s.get_final_message()
        return client.messages.create(**params)
    return api_retry(call, "single_message")


def message_text(msg) -> str:
    return "".join(b.text for b in msg.content if b.type == "text")


# ---------------------------------------------------------------------------
# Step: pin
# ---------------------------------------------------------------------------

def step_pin(args) -> None:
    workdir = Path(args.workdir).resolve()
    repo = workdir / "repo"
    workdir.mkdir(parents=True, exist_ok=True)
    ARMS_DIR.mkdir(parents=True, exist_ok=True)

    if not repo.exists():
        log(f"cloning {REPO_URL} (blob-filtered) into {repo}")
        run(["git", "clone", "--filter=blob:none", REPO_URL, str(repo)])
    else:
        log("repo exists; fetching origin")
        git(repo, "fetch", "origin", "--prune")

    # Resolve the pin. Default: current origin/main HEAD.
    ref = args.pin or "origin/main"
    proc = git(repo, "rev-parse", f"{ref}^{{commit}}", check=False)
    if proc.returncode != 0 and args.pin:
        # An arbitrary sha may need an explicit fetch on a filtered clone.
        git(repo, "fetch", "origin", args.pin, check=False)
        proc = git(repo, "rev-parse", f"{ref}^{{commit}}", check=False)
    if proc.returncode != 0:
        die(f"cannot resolve pin '{ref}' in {repo}")
    commit = proc.stdout.strip()

    pinned = load_json(ARMS_DIR / "pinned.json")
    if pinned and pinned.get("commit") != commit and not args.force:
        die(
            f"arms/pinned.json already pins {pinned.get('commit')}, which differs from "
            f"{commit}. Re-pinning invalidates every built arm; pass --force only if "
            "you intend to rebuild everything.",
            code=1,
        )

    # Checkout C (lazily fetches blobs for C's tree over the network).
    git(repo, "checkout", "--detach", commit)
    save_json(ARMS_DIR / "pinned.json", {"repo": REPO_URL, "commit": commit, "pinned_at": now_iso()})
    log(f"pinned {commit}")


def require_pin(args) -> tuple[Path, str]:
    workdir = Path(args.workdir).resolve()
    repo = workdir / "repo"
    pinned = load_json(ARMS_DIR / "pinned.json")
    if not pinned:
        die("arms/pinned.json missing: run --step pin first")
    if not repo.exists():
        die(f"{repo} missing: run --step pin first (same --workdir)")
    return repo, pinned["commit"]


# ---------------------------------------------------------------------------
# Step: original
# ---------------------------------------------------------------------------

def corpus_files_at(repo: Path, commit: str) -> list[str]:
    proc = git(repo, "ls-tree", "-r", "--name-only", commit)
    files = [ln for ln in proc.stdout.splitlines() if ln and is_corpus_path(ln)]
    files.sort()
    return files


def step_original(args) -> None:
    repo, commit = require_pin(args)
    dest = ARMS_DIR / "original-docs"
    manifest_path = ARMS_DIR / "corpus-manifest.json"

    if manifest_path.exists() and dest.exists() and not args.force:
        log("original arm exists; skipping (use --force to rebuild)")
        return

    files = corpus_files_at(repo, commit)
    if not files:
        die("the corpus definition matched no files at the pinned commit")
    log(f"corpus at {commit[:12]}: {len(files)} file(s)")

    if dest.exists():
        shutil.rmtree(dest)
    for rel in files:
        safe_relpath(rel)
        proc = subprocess.run(
            ["git", "-C", str(repo), "show", f"{commit}:{rel}"],
            capture_output=True,
        )
        if proc.returncode != 0:
            die(f"git show failed for {rel}")
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(proc.stdout)

    save_json(
        manifest_path,
        {
            "repo": REPO_URL,
            "commit": commit,
            "generated_at": now_iso(),
            "definition": (
                "all *.md and *.mdx files excluding CHANGELOG*, files under "
                "testdata/, .github/, node_modules/, and LICENSE-like files"
            ),
            "files": files,
        },
    )
    log(f"wrote {len(files)} file(s) to {dest} and {manifest_path}")


# ---------------------------------------------------------------------------
# Step: ace
# ---------------------------------------------------------------------------

def find_kit_tarball(kit_root: Path, pattern: str, override: str | None) -> Path:
    if override:
        p = Path(override).resolve()
        if not p.exists():
            die(f"tarball not found: {p}")
        return p
    dist = kit_root / "meta" / "dist"
    cands = sorted(dist.glob(pattern), key=lambda p: p.name)
    if not cands:
        die(
            f"no {pattern} under {dist}. Build release tarballs with the kit's "
            "meta/publish.sh, or pass --kit-tarball/--skill-tarball."
        )
    return cands[-1]


def kit_manifest_paths(kit_tar: Path) -> list[str]:
    """Read tools/kit-manifest.txt out of the kit tarball; return kit+seed paths."""
    with tarfile.open(kit_tar, "r:gz") as tf:
        member = None
        for m in tf.getmembers():
            if m.name.lstrip("./") == "tools/kit-manifest.txt":
                member = m
                break
        if member is None:
            die(f"{kit_tar} has no tools/kit-manifest.txt")
        text = tf.extractfile(member).read().decode("utf-8")
    paths = []
    for ln in text.splitlines():
        if ln.startswith(("kit ", "seed ")):
            paths.append(ln.split(" ", 1)[1])
    return paths


ACE_IGNORE_EXTRA = [
    "# Corpus exclusions mirrored from the experiment corpus definition",
    "CHANGELOG",
    "testdata/",
    "^\\.github/",
    "node_modules/",
    "LICENSE",
    "LICENCE",
    "NOTICE",
    "COPYING",
    "PATENTS",
    "^\\.ace-migration-staging/",
]


def append_ace_ignore(ace_work: Path) -> None:
    """Align the checkers' sweep scope with the registered corpus definition,
    so a full sweep of tools/check.sh in the migrated working copy judges
    exactly the governed corpus (plus kit files) and not CHANGELOGs/testdata.
    Note: grep patterns are case-sensitive; the corpus definition compares
    case-insensitively — acceptable because the exclusions in this repo are
    conventionally upper-case."""
    ig = ace_work / ".ace-ignore"
    existing = ig.read_text().splitlines() if ig.exists() else [
        "# Paths the ACE-100 checkers do not sweep. One pattern per line."
    ]
    for pat in ACE_IGNORE_EXTRA:
        if pat not in existing:
            existing.append(pat)
    ig.write_text("\n".join(existing) + "\n")


def build_migration_prompt(staged: list[str]) -> str:
    staged_note = ""
    if staged:
        staged_note = (
            "\nFiles displaced by the kit adoption were moved to "
            ".ace-migration-staging/ (same relative paths). Fold their content "
            "into the governed corpus at their original locations (or divided "
            "forms) and record any deviation in the ledger.\n"
        )
    return f"""Migrate this repository's documentation to ACE-100.

The ACE-100 kit is already adopted: docs/standard/, docs/dictionary/, and the
checkers (tools/check.sh, tools/lint.py) are in place, and the ace-migrate
skill is installed at .agents/skills/ace-migrate/SKILL.md.

First read .agents/skills/ace-migrate/SKILL.md and follow its phases exactly.

The migration surface is listed in ace-migration-worklist.txt at the
repository root (one path per line). Migrate every file on that list.
{staged_note}
Hard constraints:
- Do not modify source code, build files, or CI configuration, except the
  minimal repair of a first-line reader that ACE 18.2 requires in the same
  change as the document edit that breaks it.
- Preserve every factual and procedural claim of every document (ACE 18.5,
  18.4). A migration must not change what the repository asserts.
- Finish with a clean full sweep of both tools/check.sh and tools/lint.py.
- Commit your work with git in reviewable batches as you go.

When done, report: documents migrated, divisions made, deviations declared,
terms added, and anything you could not migrate (with the reason)."""


RESUME_PROMPT = (
    "Continue the ACE-100 migration of this repository per the ace-migrate "
    "skill (.agents/skills/ace-migrate/SKILL.md). Finish the remaining items "
    "in ace-migration-worklist.txt, fold any leftovers from "
    ".ace-migration-staging/ into the governed corpus, run the full sweep of "
    "tools/check.sh and tools/lint.py until clean, commit, and report status."
)


def repair_prompt(preservation_path: Path) -> str:
    """Build a repair prompt from a preservation report: every dropped item
    must be restored into the governed corpus, in conformant language."""
    report = json.loads(read_text(preservation_path))
    sections = []
    for rel, entry in sorted(report["files"].items()):
        items = entry.get("dropped") or []
        if not items:
            continue
        targets = ", ".join(entry.get("rewritten") or ["(unmapped)"])
        lines = "\n".join(f"  - ({it.get('kind', 'factual')}) {it['item']}" for it in items)
        sections.append(f"SOURCE {rel} (migrated into: {targets}):\n{lines}")
    worklist = "\n\n".join(sections)
    return (
        "A content-preservation review compared each original document of this "
        "repository against its migrated form and found the factual and "
        "procedural items below missing from the governed corpus. Restore every "
        "listed item into the most appropriate governed document (usually one of "
        "the files each source was migrated into). Re-express content in "
        "ACE-100-conformant language — restoring meaning, not original wording. "
        "Do not remove or rewrite unrelated content. When done, run the full "
        "sweep of tools/check.sh and tools/lint.py until clean, commit, and "
        "report which document received each restored item.\n\n" + worklist
    )


def find_transcript(session_id: str) -> Path | None:
    hits = sorted((Path.home() / ".claude" / "projects").glob(f"*/{session_id}.jsonl"))
    return hits[0] if hits else None


def run_migration_session(ace_work: Path, prompt: str, resume_session: str | None) -> dict:
    cmd = [
        CLAUDE_BIN,
        "-p", prompt,
        "--output-format", "json",
        "--model", OPUS_MODEL,
        "--max-turns", str(MIGRATION_MAX_TURNS),
        # Removes the harness's network tools; full network isolation is
        # enforced by the sandbox environment, NOT by this flag.
        "--disallowed-tools", "WebFetch,WebSearch",
        # The migration workspace is disposable and fully captured afterward,
        # so headless permission prompts are skipped.
        "--dangerously-skip-permissions",
    ]
    if resume_session:
        cmd += ["--resume", resume_session]
    log(f"running headless migration session (model {OPUS_MODEL}, cwd {ace_work})")
    started = now_iso()
    proc = subprocess.run(
        cmd, cwd=str(ace_work), capture_output=True, text=True, timeout=MIGRATION_TIMEOUT_S
    )
    ended = now_iso()
    raw = proc.stdout.strip()
    try:
        harness = json.loads(raw)
    except json.JSONDecodeError:
        try:
            harness = json.loads(raw.splitlines()[-1])
        except Exception:
            die(
                f"claude CLI produced no parseable JSON (exit {proc.returncode}).\n"
                f"stderr tail: {(proc.stderr or '')[-1000:]}"
            )
    usage = harness.get("usage") if isinstance(harness.get("usage"), dict) else {}
    record = {
        "started_at": started,
        "ended_at": ended,
        "exit_code": proc.returncode,
        "session_id": harness.get("session_id"),
        "subtype": harness.get("subtype"),
        "num_turns": harness.get("num_turns"),
        "total_cost_usd_harness": harness.get("total_cost_usd"),
        "usage": usage,
        # Approximation: prices the harness-reported aggregate usage at the
        # migration model's standard rates (subagent model mix, if any, is
        # not broken out here; total_cost_usd_harness is authoritative).
        "cost_usd_standard": cost_usd_standard(usage, OPUS_MODEL),
        "result_tail": str(harness.get("result", ""))[-4000:],
    }
    # Copy the transcript JSONL into the arms record.
    sid = record["session_id"]
    if sid:
        src = find_transcript(sid)
        if src:
            dest = GATES_DIR / "migration-transcripts" / f"{sid}.jsonl"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            record["transcript"] = str(dest.relative_to(EXPERIMENT_DIR))
        else:
            record["transcript"] = None
            log("warning: migration transcript not found under ~/.claude/projects")
    return record


def capture_docs_tree(src_root: Path, dest: Path) -> list[str]:
    """Capture the governed docs corpus of a working copy into an arm tree."""
    if dest.exists():
        shutil.rmtree(dest)
    captured = []
    files = set()
    for pat in ("*.md", "*.mdx"):
        files.update(src_root.rglob(pat))
    for f in sorted(files):
        if not f.is_file() or f.is_symlink():
            continue
        rel = f.relative_to(src_root).as_posix()
        parts = PurePosixPath(rel).parts
        if any(seg in CAPTURE_EXCLUDED_SEGMENTS for seg in parts):
            continue
        if not is_corpus_path(rel):
            continue
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(f.read_bytes())
        captured.append(rel)
    return captured


def step_ace(args) -> None:
    temporal_firewall_check("ace")
    repo, commit = require_pin(args)
    if not (ARMS_DIR / "corpus-manifest.json").exists():
        die("arms/corpus-manifest.json missing: run --step original first")
    workdir = Path(args.workdir).resolve()
    ace_work = workdir / "ace-work"
    kit_root = Path(args.kit).resolve() if args.kit else DEFAULT_KIT_ROOT
    GATES_DIR.mkdir(parents=True, exist_ok=True)

    cost_path = GATES_DIR / "migration-cost.json"
    cost = load_json(cost_path, {"sessions": [], "totals": {}}) or {"sessions": [], "totals": {}}
    staged: list[str] = []

    if args.resume:
        if not ace_work.exists():
            die("--resume given but no ace-work directory exists; run without --resume first")
        if not cost["sessions"] or not cost["sessions"][-1].get("session_id"):
            die("--resume given but no prior session recorded in arms/gates/migration-cost.json")
        resume_session = cost["sessions"][-1]["session_id"]
        prompt = RESUME_PROMPT
        if args.repair:
            prompt = repair_prompt(Path(args.repair))
            log(f"resume in repair mode: worklist from {args.repair}")
        record = run_migration_session(ace_work, prompt, resume_session)
    else:
        if ace_work.exists():
            if not args.force:
                die(
                    f"{ace_work} already exists. Use --resume to continue the "
                    "migration or --force to discard it and start over.",
                    code=1,
                )
            shutil.rmtree(ace_work)
            cost = {"sessions": [], "totals": {}}

        # 1) A fresh working copy of the pinned checkout. A local clone shares
        # objects with the blob-filtered clone; C's blobs were fetched at pin.
        log(f"cloning pinned checkout into {ace_work}")
        run(["git", "clone", str(repo), str(ace_work)])
        git(ace_work, "checkout", "--detach", commit)
        git(ace_work, "config", "user.name", "ACE-100 experiment")
        git(ace_work, "config", "user.email", "claude@owendelahoy.com")

        # 2) Adopt the kit via its own adopt flow (local tarballs, --migrate
        # installs the ace-migrate skill and seeds .ace-ignore).
        kit_tar = find_kit_tarball(kit_root, "ace-100-kit-issue-*.tar.gz", args.kit_tarball)
        skill_tar = find_kit_tarball(kit_root, "ace-100-skill-issue-*.tar.gz", args.skill_tarball)
        log(f"adopting kit from {kit_tar.name} + {skill_tar.name}")

        # Fresh-mode adopt refuses when a kit path already exists in the target,
        # so displace conflicts into a staging area the migration folds back in.
        for rel in kit_manifest_paths(kit_tar):
            target = ace_work / rel
            if target.exists():
                staged_dest = ace_work / ".ace-migration-staging" / rel
                staged_dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(target), str(staged_dest))
                staged.append(rel)
        save_json(GATES_DIR / "adopt-conflicts.json", {"generated_at": now_iso(), "staged": staged})

        env = dict(os.environ)
        env["ACE_ADOPT_KIT_TARBALL"] = str(kit_tar)
        env["ACE_ADOPT_SKILL_TARBALL"] = str(skill_tar)
        proc = subprocess.run(
            ["sh", str(kit_root / "meta" / "adopt.sh"), "--migrate"],
            cwd=str(ace_work), capture_output=True, text=True, env=env,
        )
        (GATES_DIR / "adopt-output.txt").write_text(proc.stdout + "\n" + proc.stderr)
        if proc.returncode != 0:
            die(f"kit adoption failed (see {GATES_DIR / 'adopt-output.txt'})")

        # 3) Align the checkers' sweep with the corpus definition, then write
        # the migration worklist (the frozen corpus of C).
        append_ace_ignore(ace_work)
        corpus = load_json(ARMS_DIR / "corpus-manifest.json")["files"]
        (ace_work / "ace-migration-worklist.txt").write_text("\n".join(corpus) + "\n")
        git(ace_work, "add", "-A")
        git(ace_work, "commit", "-m", "Adopt the ACE-100 kit for the migration arm", check=False)

        # 4) Headless migration session.
        record = run_migration_session(ace_work, build_migration_prompt(staged), None)

    cost["sessions"].append(record)
    totals_usage: dict = {}
    for s in cost["sessions"]:
        add_usage(totals_usage, s.get("usage") or {})
    cost["totals"] = {
        "sessions": len(cost["sessions"]),
        "num_turns": sum(s.get("num_turns") or 0 for s in cost["sessions"]),
        "total_cost_usd_harness": round(
            sum(s.get("total_cost_usd_harness") or 0.0 for s in cost["sessions"]), 6
        ),
        "usage": totals_usage,
        "cost_usd_standard": cost_usd_standard(totals_usage, OPUS_MODEL),
        "model": OPUS_MODEL,
    }
    save_json(cost_path, cost)
    log(f"migration session recorded (subtype={record.get('subtype')}); cost log at {cost_path}")
    if record.get("subtype") != "success":
        log("NOTE: the session did not report success; re-run with --resume, then re-run gates")

    # 5) Capture the governed corpus into the arm snapshot (idempotent; re-run
    # after any --resume session to refresh).
    captured = capture_docs_tree(ace_work, ARMS_DIR / "ace-docs")
    if not captured:
        die("ace capture produced no files; migration workspace looks wrong")
    log(f"captured {len(captured)} file(s) into arms/ace-docs")


# ---------------------------------------------------------------------------
# Step: naive
# ---------------------------------------------------------------------------

def naive_rewrite_pass(client, targets: dict, originals: dict, label: str, poll_seconds: int):
    """One batch pass: rewrite every file to its target token count.
    Returns (texts: {rel: text}, usage_totals: dict, batch_ids: list, notes: {rel: str})."""
    id_map, requests = {}, []
    texts, notes = {}, {}
    usage_totals: dict = {}
    for i, rel in enumerate(sorted(targets)):
        n = targets[rel]
        doc = originals[rel]
        if n <= 0 or not doc.strip():
            texts[rel] = doc  # empty/whitespace file: copy verbatim, no API call
            notes[rel] = "copied-verbatim"
            continue
        cid = f"f{i:05d}"
        id_map[cid] = rel
        # claude-opus-5 thinks by default and thinking counts against
        # max_tokens, so give generous headroom above the target length.
        mt = min(64000, max(4096, 2 * n + 2048))
        params = MessageCreateParamsNonStreaming(
            model=OPUS_MODEL,
            max_tokens=mt,
            messages=[{
                "role": "user",
                "content": [
                    # Block 1 is the registered treatment string, byte-exact.
                    {"type": "text", "text": treatment_text(n)},
                    # Block 2 is the document to rewrite.
                    {"type": "text", "text": doc},
                ],
            }],
        )
        requests.append(make_batch_request(cid, params))

    batch_ids = []
    if requests:
        batch_id, results = run_message_batch(client, requests, label, poll_seconds)
        batch_ids.append(batch_id)
        for cid, rel in id_map.items():
            res = results.get(cid)
            ok = res is not None and res.result.type == "succeeded"
            if ok:
                msg = res.result.message
            else:
                # One individual retry for errored/missing entries.
                log(f"{label}: retrying {rel} individually")
                req = requests[[r.custom_id if Request else r["custom_id"] for r in requests].index(cid)] \
                    if False else None  # (index trick unused; rebuild params below)
                n = targets[rel]
                params = dict(
                    model=OPUS_MODEL,
                    max_tokens=min(64000, max(4096, 2 * n + 2048)),
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": treatment_text(n)},
                            {"type": "text", "text": originals[rel]},
                        ],
                    }],
                )
                msg = single_message(client, params)
            add_usage(usage_totals, msg.usage)
            if msg.stop_reason == "refusal":
                die(f"{label}: rewrite of {rel} was refused; investigate before proceeding", code=1)
            texts[rel] = message_text(msg)
            notes[rel] = "truncated-at-max-tokens" if msg.stop_reason == "max_tokens" else "ok"
    return texts, usage_totals, batch_ids


def write_naive_tree(texts: dict) -> None:
    dest = ARMS_DIR / "naive-docs"
    if dest.exists():
        shutil.rmtree(dest)
    for rel, text in texts.items():
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)


def step_naive(args) -> None:
    temporal_firewall_check("naive")
    manifest = load_json(ARMS_DIR / "corpus-manifest.json")
    if not manifest:
        die("arms/corpus-manifest.json missing: run --step original first")
    orig_root = ARMS_DIR / "original-docs"
    ace_root = ARMS_DIR / "ace-docs"
    if not ace_root.exists() or not any(ace_root.rglob("*")):
        die("arms/ace-docs missing or empty: run --step ace first (naive is token-matched to ace)")
    if (ARMS_DIR / "naive-docs").exists() and not args.force:
        log("naive arm exists; skipping (use --force to rebuild)")
        return

    client = api_client()
    counter = TokenCounter(client, GATES_DIR / "token-cache.json")

    originals = {rel: read_text(orig_root / rel) for rel in manifest["files"]}
    log("counting original corpus tokens")
    orig_tokens = {rel: counter.count(t) for rel, t in originals.items()}
    counter.save()
    orig_total = sum(orig_tokens.values())

    log("counting ace corpus tokens")
    _, ace_total, _ = counter.tree_total(ace_root)
    if orig_total == 0:
        die("original corpus counts zero tokens; something is wrong")
    ratio = ace_total / orig_total
    log(f"original={orig_total} tokens, ace={ace_total} tokens, ratio={ratio:.4f}")

    # Pass 1: per-file target N = round(original_file_tokens * ace_total/original_total).
    targets1 = {rel: max(0, round(orig_tokens[rel] * ratio)) for rel in originals}
    texts, usage1, batches1 = naive_rewrite_pass(
        client, targets1, originals, "naive pass 1", args.poll_seconds
    )
    write_naive_tree(texts)
    _, naive_total1, out_tokens1 = counter.tree_total(ARMS_DIR / "naive-docs")
    log(f"pass 1 naive total = {naive_total1} (ace {ace_total})")

    passes = [{
        "pass": 1, "targets_total": sum(targets1.values()), "output_total": naive_total1,
        "batch_ids": batches1, "usage": usage1,
        "cost_usd_standard": cost_usd_standard(usage1, OPUS_MODEL),
    }]
    usage_all = dict(usage1)
    targets2, out_tokens2, naive_total_final = None, None, naive_total1

    # If the total misses the +/-10% band, iterate (the registered gate says
    # the naive arm "is rebuilt until matched"): rescale every per-file target
    # by the observed overshoot, aiming slightly below the ace total so the
    # model's systematic overshoot lands inside the band. Every pass rewrites
    # from the ORIGINALS (rewriting a rewrite would compound content loss).
    # Capped at MAX_NAIVE_PASSES total passes as a runaway stop.
    MAX_NAIVE_PASSES = 4
    AIM = 0.97  # aim point as a fraction of ace_total, countering overshoot
    prev_targets, prev_total = targets1, naive_total1
    pass_no = 1
    while (abs(naive_total_final - ace_total) > NAIVE_BAND * ace_total
           and pass_no < MAX_NAIVE_PASSES):
        pass_no += 1
        correction = (ace_total * AIM) / max(1, prev_total)
        log(f"outside band; pass {pass_no} with correction factor {correction:.4f}")
        targets2 = {rel: max(0, round(prev_targets[rel] * correction)) for rel in originals}
        texts, usage2, batches2 = naive_rewrite_pass(
            client, targets2, originals, f"naive pass {pass_no}", args.poll_seconds
        )
        write_naive_tree(texts)
        _, naive_total_final, out_tokens2 = counter.tree_total(ARMS_DIR / "naive-docs")
        add_usage(usage_all, usage2)
        passes.append({
            "pass": pass_no, "targets_total": sum(targets2.values()),
            "output_total": naive_total_final,
            "batch_ids": batches2, "usage": usage2,
            "cost_usd_standard": cost_usd_standard(usage2, OPUS_MODEL),
        })
        log(f"pass {pass_no} naive total = {naive_total_final} (ace {ace_total})")
        prev_targets, prev_total = targets2, naive_total_final

    record = {
        "generated_at": now_iso(),
        "rewrite_model": OPUS_MODEL,
        "token_count_model": TOKEN_COUNT_MODEL,
        "treatment": treatment_text(0).replace("approximately 0 tokens", "approximately N tokens"),
        "original_total_tokens": orig_total,
        "ace_total_tokens": ace_total,
        "ratio": ratio,
        "naive_total_tokens": naive_total_final,
        "within_band": abs(naive_total_final - ace_total) <= NAIVE_BAND * ace_total,
        "passes": passes,
        "usage_totals": usage_all,
        "cost_usd_standard": cost_usd_standard(usage_all, OPUS_MODEL),
        "files": {
            rel: {
                "orig_tokens": orig_tokens[rel],
                "target_pass1": targets1[rel],
                "out_tokens_pass1": out_tokens1.get(rel, 0),
                "target_pass2": (targets2 or {}).get(rel),
                "out_tokens_pass2": (out_tokens2 or {}).get(rel),
            }
            for rel in sorted(originals)
        },
    }
    save_json(GATES_DIR / "naive-build.json", record)
    save_json(GATES_DIR / "naive-cost.json", {
        "model": OPUS_MODEL, "usage": usage_all,
        "cost_usd_standard": cost_usd_standard(usage_all, OPUS_MODEL),
        "note": "Message Batches bill at 50% of standard; cost_usd_standard prices at standard rates per the registration.",
    })
    if not record["within_band"]:
        die(
            f"naive total {naive_total_final} still outside +/-{int(NAIVE_BAND*100)}% of "
            f"ace total {ace_total} after {MAX_NAIVE_PASSES} passes; the gates "
            "step will also fail. Investigate before proceeding.",
            code=1,
        )
    log(f"naive arm written; total {naive_total_final} tokens (band ok)")


# ---------------------------------------------------------------------------
# Step: gates
# ---------------------------------------------------------------------------

def step_gates(args) -> None:
    workdir = Path(args.workdir).resolve()
    ace_work = workdir / "ace-work"
    failures = []
    GATES_DIR.mkdir(parents=True, exist_ok=True)

    # 1) The kit's canonical checker must pass on the migrated working copy
    # (full sweep; .ace-ignore aligns its scope with the corpus definition).
    if not ace_work.exists():
        die(f"{ace_work} missing: gates needs the ace working copy (run --step ace, same --workdir)")
    proc = subprocess.run(["bash", "tools/check.sh"], cwd=str(ace_work), capture_output=True, text=True)
    (GATES_DIR / "check-ace.txt").write_text(proc.stdout + "\n" + proc.stderr)
    if proc.returncode != 0:
        failures.append(f"tools/check.sh failed (exit {proc.returncode}); see arms/gates/check-ace.txt")
    else:
        log("tools/check.sh: clean")

    # lint.py output is recorded for the audit trail. The registered gate names
    # check.sh only, so lint findings warn without failing this step.
    lint = subprocess.run(["python3", "tools/lint.py"], cwd=str(ace_work), capture_output=True, text=True)
    (GATES_DIR / "lint-ace.txt").write_text(lint.stdout + "\n" + lint.stderr)
    if lint.returncode != 0:
        log("warning: tools/lint.py reported findings (recorded, not gating); see arms/gates/lint-ace.txt")

    # 2) Token totals for all three arms.
    client = api_client()
    counter = TokenCounter(client, GATES_DIR / "token-cache.json")
    arms = {}
    for arm in ("original", "ace", "naive"):
        root = ARMS_DIR / f"{arm}-docs"
        if not root.exists():
            die(f"{root} missing: build the {arm} arm first")
        n, total, _ = counter.tree_total(root)
        arms[arm] = {"files": n, "tokens": total}
        log(f"{arm}: {n} file(s), {total} tokens")

    ratio = arms["naive"]["tokens"] / max(1, arms["ace"]["tokens"])
    within = abs(arms["naive"]["tokens"] - arms["ace"]["tokens"]) <= NAIVE_BAND * arms["ace"]["tokens"]
    save_json(GATES_DIR / "measure.json", {
        "generated_at": now_iso(),
        "counted_with": TOKEN_COUNT_MODEL,
        "band": NAIVE_BAND,
        "arms": arms,
        "naive_vs_ace_ratio": round(ratio, 4),
        "within_band": within,
        "check_sh_pass": proc.returncode == 0,
        "lint_py_pass": lint.returncode == 0,
    })

    # 3) Assert the band.
    if not within:
        failures.append(
            f"naive total {arms['naive']['tokens']} is outside +/-{int(NAIVE_BAND*100)}% "
            f"of ace total {arms['ace']['tokens']} (ratio {ratio:.4f})"
        )

    if failures:
        for f in failures:
            print(f"GATE FAILURE: {f}", file=sys.stderr)
        sys.exit(1)
    log("all gates pass; arms/gates/measure.json written")


# ---------------------------------------------------------------------------
# Step: preserve
# ---------------------------------------------------------------------------

PRESERVE_SCHEMA = {
    "type": "object",
    "properties": {
        "dropped": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item": {"type": "string"},
                    "kind": {"type": "string", "enum": ["factual", "procedural"]},
                },
                "required": ["item", "kind"],
                "additionalProperties": False,
            },
        },
        "notes": {"type": "string"},
    },
    "required": ["dropped", "notes"],
    "additionalProperties": False,
}

JUDGE_INSTRUCTIONS = (
    "You are auditing a documentation rewrite for content preservation. "
    "Compare the ORIGINAL document with its REWRITTEN form (the rewrite may be "
    "split across several files; all of them are shown). Report every factual "
    "or procedural item that appears in the ORIGINAL but is missing from the "
    "REWRITTEN version. A factual item is a concrete claim: a name, path, "
    "value, default, version, limit, or described behavior. A procedural item "
    "is a step or command the reader is told to perform. Ignore changes of "
    "wording, order, tone, formatting, or structure; report only content that "
    "is absent. If nothing is missing, return an empty dropped list."
)


def map_ace_targets(orig_rel: str, ace_files: set) -> list[str]:
    """Map an original corpus path to its rewritten form(s) in the ace arm.

    ACE migrations divide and relocate content: topic.md -> topic/README.md
    plus parts, and (commonly) package README.md -> sibling files in the same
    directory (client.md, server.md, best-practices.md, ...). An exact-path
    match therefore must NOT stop the search — content preserved in a sibling
    would be misjudged as dropped. Candidates are the union of: exact path,
    division-prefix files, every ace file in the original's own directory,
    and unique-stem moves. Anything unmapped is reported as a flag."""
    p = PurePosixPath(orig_rel)
    targets = set()
    if orig_rel in ace_files:
        targets.add(orig_rel)
    base = p.stem if str(p.parent) == "." else f"{p.parent.as_posix()}/{p.stem}"
    targets.update(f for f in ace_files if f.startswith(base + "/"))
    for f in ace_files:
        if (str(PurePosixPath(f).parent) == str(p.parent)
                and not f.startswith(KIT_DOC_PREFIXES)):
            targets.add(f)
    stem = p.stem.lower()
    if stem not in ("readme", "index"):
        targets.update(
            f for f in ace_files
            if PurePosixPath(f).stem.lower() == stem and not f.startswith(KIT_DOC_PREFIXES)
        )
    return sorted(targets)


def judge_arm(client, arm: str, originals: dict, mapping: dict, arm_root: Path, poll_seconds: int) -> dict:
    """Run the preservation judge over one arm. mapping: orig_rel -> [rewritten rels]."""
    id_map, requests = {}, []
    files_report = {}
    usage_totals: dict = {}
    for i, rel in enumerate(sorted(originals)):
        targets = mapping.get(rel, [])
        if not targets:
            files_report[rel] = {"rewritten": [], "status": "unmapped", "dropped": [], "notes": ""}
            continue
        rewritten_blob = "\n\n".join(
            f"===== REWRITTEN FILE: {t} =====\n{read_text(arm_root / t)}" for t in targets
        )
        cid = f"j{i:05d}"
        id_map[cid] = rel
        files_report[rel] = {"rewritten": targets, "status": "pending", "dropped": [], "notes": ""}
        params = MessageCreateParamsNonStreaming(
            model=OPUS_MODEL,
            max_tokens=JUDGE_MAX_TOKENS,
            output_config={"format": {"type": "json_schema", "schema": PRESERVE_SCHEMA}},
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": JUDGE_INSTRUCTIONS},
                    {"type": "text", "text": f"ORIGINAL ({rel}):\n{originals[rel]}"},
                    {"type": "text", "text": rewritten_blob},
                ],
            }],
        )
        requests.append(make_batch_request(cid, params))

    batch_ids = []
    if requests:
        batch_id, results = run_message_batch(client, requests, f"preserve {arm}", poll_seconds)
        batch_ids.append(batch_id)
        for cid, rel in id_map.items():
            res = results.get(cid)
            try:
                if res is not None and res.result.type == "succeeded":
                    msg = res.result.message
                else:
                    log(f"preserve {arm}: retrying {rel} individually")
                    targets = mapping[rel]
                    rewritten_blob = "\n\n".join(
                        f"===== REWRITTEN FILE: {t} =====\n{read_text(arm_root / t)}" for t in targets
                    )
                    msg = single_message(client, dict(
                        model=OPUS_MODEL,
                        max_tokens=JUDGE_MAX_TOKENS,
                        output_config={"format": {"type": "json_schema", "schema": PRESERVE_SCHEMA}},
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": JUDGE_INSTRUCTIONS},
                                {"type": "text", "text": f"ORIGINAL ({rel}):\n{originals[rel]}"},
                                {"type": "text", "text": rewritten_blob},
                            ],
                        }],
                    ))
                add_usage(usage_totals, msg.usage)
                if msg.stop_reason == "refusal":
                    files_report[rel]["status"] = "judge_error"
                    files_report[rel]["notes"] = "judge refusal"
                    continue
                verdict = json.loads(message_text(msg))
                files_report[rel]["dropped"] = verdict.get("dropped", [])
                files_report[rel]["notes"] = verdict.get("notes", "")
                files_report[rel]["status"] = "ok" if not verdict.get("dropped") else "dropped-content"
            except Exception as e:  # judge output unusable: flag, never pass silently
                files_report[rel]["status"] = "judge_error"
                files_report[rel]["notes"] = f"{type(e).__name__}: {e}"

    total_dropped = sum(len(v["dropped"]) for v in files_report.values())
    unmapped = sum(1 for v in files_report.values() if v["status"] == "unmapped")
    errors = sum(1 for v in files_report.values() if v["status"] == "judge_error")
    report = {
        "arm": arm,
        "judged_at": now_iso(),
        "model": OPUS_MODEL,
        "batch_ids": batch_ids,
        "usage": usage_totals,
        "cost_usd_standard": cost_usd_standard(usage_totals, OPUS_MODEL),
        "total_dropped_items": total_dropped,
        "unmapped_files": unmapped,
        "judge_errors": errors,
        "files": files_report,
    }
    save_json(GATES_DIR / f"preservation-{arm}.json", report)
    return report


def step_preserve(args) -> None:
    orig_root = ARMS_DIR / "original-docs"
    manifest = load_json(ARMS_DIR / "corpus-manifest.json")
    if not manifest or not orig_root.exists():
        die("original arm missing: run --step original first")
    for arm in ("ace", "naive"):
        if not (ARMS_DIR / f"{arm}-docs").exists():
            die(f"arms/{arm}-docs missing: build the {arm} arm first")

    # Skip only when both prior reports exist with zero flags.
    if not args.force:
        prior = [load_json(GATES_DIR / f"preservation-{a}.json") for a in ("ace", "naive")]
        if all(
            p and p.get("total_dropped_items") == 0
            and p.get("unmapped_files") == 0 and p.get("judge_errors") == 0
            for p in prior
        ):
            log("preservation reports exist with zero flags; skipping (use --force to re-judge)")
            return

    client = api_client()
    originals = {rel: read_text(orig_root / rel) for rel in manifest["files"]}

    ace_root = ARMS_DIR / "ace-docs"
    ace_files = {f.relative_to(ace_root).as_posix() for f in ace_root.rglob("*") if f.is_file()}
    ace_mapping = {rel: map_ace_targets(rel, ace_files) for rel in originals}
    # naive keeps the original layout: 1:1 by relpath.
    naive_mapping = {rel: [rel] for rel in originals}

    reports = [
        judge_arm(client, "ace", originals, ace_mapping, ace_root, args.poll_seconds),
        judge_arm(client, "naive", originals, naive_mapping, ARMS_DIR / "naive-docs", args.poll_seconds),
    ]

    flagged = False
    for rep in reports:
        n_flags = rep["total_dropped_items"] + rep["unmapped_files"] + rep["judge_errors"]
        if n_flags == 0:
            log(f"{rep['arm']}: preservation clean")
            continue
        flagged = True
        print(f"\nPRESERVATION FLAGS — {rep['arm']} arm "
              f"(dropped={rep['total_dropped_items']} unmapped={rep['unmapped_files']} "
              f"errors={rep['judge_errors']}). Repair worklist:", file=sys.stderr)
        for rel in sorted(rep["files"]):
            v = rep["files"][rel]
            if v["status"] in ("ok", "pending"):
                continue
            print(f"  [{v['status']}] {rel} -> {v['rewritten'] or '(no mapping)'}", file=sys.stderr)
            for d in v["dropped"][:5]:
                print(f"      - ({d.get('kind')}) {d.get('item', '')[:160]}", file=sys.stderr)
            if len(v["dropped"]) > 5:
                print(f"      ... and {len(v['dropped']) - 5} more (see preservation-{rep['arm']}.json)",
                      file=sys.stderr)
    if flagged:
        print("\nRepair the flagged files in the corresponding arm (re-run the "
              "migration with --step ace --resume, or rebuild naive with --step "
              "naive --force), then re-run --step preserve.", file=sys.stderr)
        sys.exit(1)
    log("preservation gate passes for both arms")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

STEPS = ["pin", "original", "ace", "naive", "gates", "preserve"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workdir", required=True, help="scratch directory for the clone and working copies")
    ap.add_argument("--pin", help="commit to pin (default: current origin/main HEAD)")
    ap.add_argument("--step", required=True, choices=STEPS + ["all"])
    ap.add_argument("--kit", help=f"ACE-100 kit repository root (default: {DEFAULT_KIT_ROOT})")
    ap.add_argument("--kit-tarball", help="explicit kit tarball path (default: newest under <kit>/meta/dist)")
    ap.add_argument("--skill-tarball", help="explicit skill tarball path (default: newest under <kit>/meta/dist)")
    ap.add_argument("--resume", action="store_true", help="ace: continue the migration in a new session")
    ap.add_argument("--repair", help="ace --resume: preservation report whose dropped items the session must restore")
    ap.add_argument("--force", action="store_true", help="rebuild a step's outputs from scratch")
    ap.add_argument("--poll-seconds", type=int, default=BATCH_POLL_SECONDS, help="Message Batches poll interval")
    args = ap.parse_args()

    random.seed(SEED)  # registered seed; no draws today, kept for reproducibility

    dispatch = {
        "pin": step_pin,
        "original": step_original,
        "ace": step_ace,
        "naive": step_naive,
        "gates": step_gates,
        "preserve": step_preserve,
    }
    if args.step == "all":
        for name in STEPS:
            log(f"=== step: {name} ===")
            dispatch[name](args)
    else:
        dispatch[args.step](args)
    log("done")


if __name__ == "__main__":
    main()
