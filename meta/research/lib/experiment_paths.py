#!/usr/bin/env python3
"""Locate an experiment tree, load its config, and stamp artifact provenance.

Shared by every tool in this directory. Before the repository was restructured
to hold more than one experiment, each tool derived its experiment root from
its own file location (`Path(__file__).parent.parent`), which silently bound
the whole pipeline to a single experiment. Tools now live in `meta/research/lib`
and are told which experiment to operate on, explicitly.

Resolution order for the experiment root:
  1. an explicit argument (a tool's --experiment-dir)
  2. $ACE_EXPERIMENT_DIR
  3. error

There is deliberately no default. A tool that silently picked an experiment
could write Experiment 2's numbers into Experiment 1's tree.

Provenance: `stamp()` returns the tooling commit that produced an artifact, so
a reader of the paper can check out that exact revision and re-run. Artifacts
record it under a `provenance` key; a dirty working tree is recorded as such
rather than hidden, because an artifact produced from uncommitted code is not
reproducible from a commit hash alone.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

LIB_DIR = Path(__file__).resolve().parent
RESEARCH_DIR = LIB_DIR.parent


class ExperimentNotSpecified(SystemExit):
    pass


def resolve_experiment_dir(explicit=None) -> Path:
    """Return the experiment root, or exit with an actionable message."""
    candidate = explicit or os.environ.get("ACE_EXPERIMENT_DIR")
    if not candidate:
        available = sorted(
            p.name for p in (RESEARCH_DIR / "experiments").glob("*")
            if p.is_dir())
        raise ExperimentNotSpecified(
            "no experiment specified. Pass --experiment-dir, or set "
            "ACE_EXPERIMENT_DIR.\n"
            f"  available: {', '.join(available) or '(none found)'}\n"
            f"  e.g. ACE_EXPERIMENT_DIR={RESEARCH_DIR}/experiments/exp1")
    path = Path(candidate).expanduser().resolve()
    if not path.is_dir():
        raise ExperimentNotSpecified(f"experiment dir not found: {path}")
    return path


def add_experiment_arg(parser) -> None:
    """Register the standard --experiment-dir flag on an ArgumentParser."""
    parser.add_argument(
        "--experiment-dir", default=None,
        help="experiment root (or set ACE_EXPERIMENT_DIR); no default")


def load_config(experiment_dir: Path) -> dict:
    """Load experiment.json: the per-experiment settings that used to be
    hardcoded CONFIG constants inside individual tools.

    Missing file is not fatal — tools fall back to their own defaults — so an
    experiment tree written before this file existed still works.
    """
    cfg_path = experiment_dir / "experiment.json"
    if not cfg_path.is_file():
        return {}
    with open(cfg_path, encoding="utf-8") as fh:
        return json.load(fh)


def _git(args: list) -> str:
    try:
        p = subprocess.run(["git", "-C", str(LIB_DIR), *args],
                           capture_output=True, text=True, timeout=15)
        return p.stdout.strip() if p.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def tooling_commit() -> dict:
    """Identify the exact tooling revision that produced an artifact.

    Two hashes, because they answer different questions:

      head      the repository commit checked out when the tool ran. Moves
                whenever anything in the repo is committed, including the
                artifact this stamp is embedded in.
      lib       the last commit that actually modified meta/research/lib.
                This is the one a replicator wants: checking it out
                reproduces the tooling that computed the artifact, and it is
                stable across later commits that do not touch the tools.

    `lib_dirty` reports uncommitted changes under lib/ at run time. An
    artifact produced from a dirty tree is not reproducible from any commit
    hash, so this is recorded rather than hidden.
    """
    head = _git(["rev-parse", "HEAD"])
    lib = _git(["log", "-1", "--format=%H", "--", str(LIB_DIR)])
    dirty = bool(_git(["status", "--porcelain", "--", str(LIB_DIR)]))
    return {"head": head or None, "lib": lib or None, "lib_dirty": dirty}


def stamp(tool: str, extra: dict = None) -> dict:
    """Provenance block to embed in a generated artifact."""
    tc = tooling_commit()
    out = {
        "tool": tool,
        "tooling_commit": tc["lib"],
        "repo_head_at_run": tc["head"],
        "tooling_dirty": tc["lib_dirty"],
        "generated_at": dt.datetime.now(dt.timezone.utc)
                          .isoformat(timespec="seconds"),
        "argv": " ".join(sys.argv[1:]),
    }
    if extra:
        out.update(extra)
    return out


def stamp_line(tool: str) -> str:
    """One-line provenance for markdown artifacts."""
    tc = tooling_commit()
    sha = (tc["lib"] or "unknown")[:12]
    dirty = " (working tree dirty — not reproducible from this commit alone)" \
        if tc["lib_dirty"] else ""
    return f"Generated by `{tool}` at tooling commit `{sha}`{dirty}."
