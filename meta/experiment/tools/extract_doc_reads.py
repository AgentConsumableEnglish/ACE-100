#!/usr/bin/env python3
"""Extract every documentation-read event per run into one JSON file.

Companion to docs_recount.py (which aggregates counts): this emits the
underlying events so each run's documentation consumption is inspectable --
which arm documents were touched, through which channel, by which command,
and how much content entered context.

Instrument revision 2 (Amendment 5): shares docs_recount.py's extraction
engine -- arm-relative matching, suffix path resolution, the attribution
corrections, the git/diff/od channels, sidechain Bash -- and merges the
audited supplement from audit/doc-read-audit.json (events hand-verified by
the audit that path-based extraction cannot see). The full audit is
preserved verbatim under the agent_audit key.

Output: data/doc-reads.json
  {generated_at, instrument, corpus_definition, reconciliation,
   runs: [{task_id, arm, trial, events: [...]}], agent_audit}

Usage: extract_doc_reads.py [--data-dir ...] [--arms-dir ...] [--audit-file ...]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

import docs_recount as dr


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    base = Path(__file__).resolve().parent.parent
    ap.add_argument("--data-dir", default=str(base / "data"))
    ap.add_argument("--arms-dir", default=str(base / "arms"))
    ap.add_argument("--audit-file",
                    default=str(base / "audit" / "doc-read-audit.json"))
    args = ap.parse_args()
    data = Path(args.data_dir)

    matchers = dr.build_matchers(Path(args.arms_dir))
    supplement = dr.load_audit_supplement(Path(args.audit_file))

    out_path = data / "doc-reads.json"
    prior_audit = None
    if out_path.is_file():
        try:
            prior_audit = json.load(open(out_path)).get("agent_audit")
        except json.JSONDecodeError:
            prior_audit = None
    if prior_audit is None and Path(args.audit_file).is_file():
        # The committed archive carries the audit when data/ is fresh.
        prior_audit = json.load(open(args.audit_file))

    runs = []
    recon = {"captured": 0, "supplemented": 0, "superseded": 0}
    for transcript in sorted(data.glob("runs/*/*/trial-*/transcript.jsonl")):
        parts = transcript.parts
        task_id, arm, trial = parts[-4], parts[-3], parts[-2]
        events = dr.extract_run_events(transcript, matchers[arm])
        captured, extra, superseded = dr.reconcile_supplement(
            events, supplement.get((task_id, arm, trial), []))
        recon["captured"] += len(captured)
        recon["supplemented"] += len(extra)
        recon["superseded"] += len(superseded)
        for i in superseded:
            events[i]["superseded_by_supplement"] = True
        runs.append({
            "task_id": task_id, "arm": arm, "trial": trial,
            "events": events + extra,
        })
    cm_path = Path(args.arms_dir) / "corpus-manifest.json"
    corpus_definition = None
    if cm_path.is_file():
        corpus_definition = json.load(open(cm_path)).get("definition")
    out = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(
            timespec="seconds"),
        "instrument": "revision-2 (Amendment 5): arm-relative matching over "
                      "arms/<arm>-docs, suffix resolution, attribution "
                      "corrections, git/diff/od channels, sidechain Bash, "
                      "audited supplement",
        "corpus_definition": corpus_definition,
        "reconciliation": recon,
        "runs": runs,
    }
    if prior_audit is not None:
        out["agent_audit"] = prior_audit
    with open(out_path, "w") as f:
        json.dump(out, f, indent=1)
    n_events = sum(len(r["events"]) for r in runs)
    print(f"wrote {out_path}: {len(runs)} runs, {n_events} doc-read events "
          f"(reconciliation: {recon})")


if __name__ == "__main__":
    main()
