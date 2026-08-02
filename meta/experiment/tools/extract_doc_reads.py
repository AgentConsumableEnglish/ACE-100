#!/usr/bin/env python3
"""Extract every documentation-read event per run into one JSON file.

Companion to docs_recount.py (which aggregates counts): this emits the
underlying events so each run's documentation consumption is inspectable —
which corpus documents were touched, through which channel, by which command,
and how much content entered context.

Channels: read (Read tool), bash (reader command naming corpus docs),
grep (Grep tool targeting corpus docs), sidechain (subagent Read).
Bash events carry the command and a mixed-command flag (chars not attributed
when non-corpus files are also named — see docs_recount.py).

Output: data/doc-reads.json
  {generated_at, corpus_definition, runs: [{task_id, arm, trial,
    events: [{channel, paths, command?, output_chars, attributed, excerpt}]}]}

Usage: extract_doc_reads.py [--data-dir ...] [--arms-dir ...]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

import docs_recount as dr


def event_paths(matcher, text: str) -> list:
    """Corpus paths named in a string, normalized and deduplicated."""
    out = []
    for tok in dr.PATHISH.findall(text):
        norm = matcher._normalize(tok)
        if norm in matcher.corpus and norm not in out:
            out.append(norm)
    return out


def extract_run(transcript: Path, matcher) -> list:
    results = {}
    uses = []
    for line in open(transcript, errors="replace"):
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        content = (e.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        side = bool(e.get("isSidechain"))
        for b in content:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                uses.append((b.get("name"), b.get("input") or {}, b.get("id"), side))
            elif b.get("type") == "tool_result":
                results[b.get("tool_use_id")] = dr.result_text(b)

    events = []
    for name, inp, uid, side in uses:
        out = results.get(uid, "")
        if name == "Read":
            fp = str(inp.get("file_path", ""))
            paths = event_paths(matcher, fp)
            if paths:
                events.append({
                    "channel": "sidechain" if side else "read",
                    "paths": paths,
                    "output_chars": len(out),
                    "attributed": True,
                    "excerpt": out[:200],
                })
        elif name == "Bash" and not side:
            cmd = str(inp.get("command", ""))
            if not (dr.BASH_READERS.search(cmd) and matcher.search(cmd)):
                continue
            paths = event_paths(matcher, cmd)
            tokens = [matcher._normalize(x) for x in re.findall(r"[\w./-]+\.\w{1,5}\b", cmd)]
            noncorpus = [x for x in tokens if x not in matcher.corpus
                         and not x.endswith((".sh", ".go"))
                         and re.search(r"\.\w{1,5}$", x)]
            events.append({
                "channel": "bash",
                "paths": paths,
                "command": cmd[:300],
                "output_chars": len(out),
                "attributed": not noncorpus,
                "excerpt": out[:200],
            })
        elif name == "Grep" and not side:
            blob = " ".join(str(inp.get(k, "")) for k in ("path", "glob", "pattern"))
            paths = event_paths(matcher, blob)
            if paths:
                events.append({
                    "channel": "grep",
                    "paths": paths,
                    "output_chars": len(out),
                    "attributed": True,
                    "excerpt": out[:200],
                })
    return events


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=str(Path(__file__).resolve().parent.parent / "data"))
    ap.add_argument("--arms-dir", default=str(Path(__file__).resolve().parent.parent / "arms"))
    args = ap.parse_args()
    data = Path(args.data_dir)

    cm = json.load(open(Path(args.arms_dir) / "corpus-manifest.json"))
    matcher = dr.corpus_matcher(cm["files"])

    runs = []
    for transcript in sorted(data.glob("runs/*/*/trial-*/transcript.jsonl")):
        parts = transcript.parts
        runs.append({
            "task_id": parts[-4], "arm": parts[-3], "trial": parts[-2],
            "events": extract_run(transcript, matcher),
        })
    out = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "corpus_definition": cm.get("definition"),
        "runs": runs,
    }
    out_path = data / "doc-reads.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=1)
    n_events = sum(len(r["events"]) for r in runs)
    print(f"wrote {out_path}: {len(runs)} runs, {n_events} doc-read events")


if __name__ == "__main__":
    main()
