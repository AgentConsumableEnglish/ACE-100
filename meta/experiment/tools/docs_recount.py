#!/usr/bin/env python3
"""Uniform, all-channel recount of documentation consumption per run.

Registered by Experiment 1 Amendment 4: the collection-time per-run counters
(Read-tool-only) are superseded by this analysis-time recount, applied
identically to every run. Channels:

  read      Read tool calls whose file_path is a corpus document
  bash      Bash commands invoking a reader (cat/grep/rg/head/tail/less/more/
            sed/awk) and naming a corpus document; the command's output chars
            are attributed (heuristic: output may include non-doc content when
            a command touches multiple files — recorded, and flagged)
  grep      Grep tool calls targeting corpus documents (path/glob/pattern)
  sidechain Subagent (sidechain) Read calls on corpus documents
  ambient   The arm's CLAUDE.md import-closure tokens (constant per arm),
            present in context in every run regardless of tool activity

Output: data/docs-consumption.jsonl (one record per run) and a per-arm summary
on stdout. Token estimates are chars/4. Idempotent; safe to re-run.

Usage: docs_recount.py [--data-dir meta/experiment/data] [--arms-dir meta/experiment/arms]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

BASH_READERS = re.compile(r"\b(cat|grep|rg|head|tail|less|more|sed|awk)\b")

# Ambient (auto-loaded) tokens per arm: chars/4 of the CLAUDE.md import
# closure, measured from the arm snapshots. The nodocs arm has no corpus and
# therefore no ambient docs.
def ambient_tokens(arms_dir: Path) -> dict:
    out = {"nodocs": 0}
    for arm in ("original", "ace", "naive"):
        total = 0
        seen = set()
        def walk(rel: str, depth: int = 0):
            nonlocal total
            if rel in seen or depth > 5:
                return
            seen.add(rel)
            p = arms_dir / f"{arm}-docs" / rel
            if not p.is_file():
                return
            text = p.read_text(errors="replace")
            total += len(text)
            for m in re.finditer(r"(?m)(?:^|\s)@([\w./-]+\.(?:md|txt))", text):
                walk(m.group(1), depth + 1)
        walk("CLAUDE.md")
        out[arm] = total // 4
    return out


PATHISH = re.compile(r"[\w./-]+\.mdx?\b")


class CorpusMatcher:
    """Exact-membership matching of path-like tokens against the corpus.

    Substring regexes over-attribute: a read of internal/testdata/README.md
    (excluded from the corpus, so present even in the nodocs arm) would match
    the corpus entry "README.md". Tokens are extracted, normalized to
    workspace-relative form, and tested for exact membership.
    """

    def __init__(self, corpus_paths: list):
        self.corpus = set(corpus_paths)

    def _normalize(self, token: str) -> str:
        token = token.lstrip("\"'")
        if "/ws/" in token:
            token = token.split("/ws/", 1)[1]
        while token.startswith("./"):
            token = token[2:]
        return token

    def search(self, text: str) -> bool:
        return any(self._normalize(t) in self.corpus for t in PATHISH.findall(text))


def corpus_matcher(corpus_paths: list) -> CorpusMatcher:
    return CorpusMatcher(corpus_paths)


def result_text(block) -> str:
    c = block.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "".join(x.get("text", "") for x in c if isinstance(x, dict))
    return ""


def recount_run(transcript: Path, corpus_re: re.Pattern) -> dict:
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
                results[b.get("tool_use_id")] = len(result_text(b))

    rec = defaultdict(int)
    flagged_multifile = 0
    for name, inp, uid, side in uses:
        chars = results.get(uid, 0)
        if name == "Read":
            fp = str(inp.get("file_path", ""))
            if corpus_re.search(fp):
                key = "sidechain" if side else "read"
                rec[f"{key}_calls"] += 1
                rec[f"{key}_chars"] += chars
        elif name == "Bash" and not side:
            cmd = str(inp.get("command", ""))
            if BASH_READERS.search(cmd) and corpus_re.search(cmd):
                # Attribute output chars only when every file-like token in
                # the command is a corpus path; a command mixing corpus and
                # non-corpus targets (cat metadata.yaml; cat README.md) would
                # otherwise attribute non-doc content to docs. Mixed commands
                # are counted as events without char attribution —
                # conservative, identically in every arm.
                tokens = [corpus_re._normalize(x) for x in
                          re.findall(r"[\w./-]+\.\w{1,5}\b", cmd)]
                file_tokens = [x for x in tokens if not x.endswith((".sh", ".go"))]
                noncorpus = [x for x in file_tokens if x not in corpus_re.corpus
                             and re.search(r"\.\w{1,5}$", x)]
                rec["bash_calls"] += 1
                if noncorpus:
                    rec["bash_mixed_calls"] += 1
                    flagged_multifile += 1
                else:
                    rec["bash_chars"] += chars
        elif name == "Grep" and not side:
            blob = " ".join(str(inp.get(k, "")) for k in ("path", "glob", "pattern"))
            if corpus_re.search(blob):
                rec["grep_calls"] += 1
                rec["grep_chars"] += chars
    rec["bash_multifile_flagged"] = flagged_multifile
    return dict(rec)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=str(Path(__file__).resolve().parent.parent / "data"))
    ap.add_argument("--arms-dir", default=str(Path(__file__).resolve().parent.parent / "arms"))
    args = ap.parse_args()
    data = Path(args.data_dir)
    arms_dir = Path(args.arms_dir)

    cm = json.load(open(arms_dir / "corpus-manifest.json"))
    corpus_paths = cm["files"] if isinstance(cm, dict) else cm
    corpus_re = corpus_matcher(corpus_paths)
    ambient = ambient_tokens(arms_dir)

    out_path = data / "docs-consumption.jsonl"
    records = []
    for transcript in sorted(data.glob("runs/*/*/trial-*/transcript.jsonl")):
        parts = transcript.parts
        task_id, arm, trial = parts[-4], parts[-3], parts[-2]
        rec = recount_run(transcript, corpus_re)
        explicit_tokens = sum(rec.get(f"{c}_chars", 0) for c in ("read", "bash", "grep", "sidechain")) // 4
        records.append({
            "task_id": task_id, "arm": arm, "trial": trial,
            **rec,
            "explicit_doc_tokens": explicit_tokens,
            "ambient_doc_tokens": ambient.get(arm, 0),
            "total_doc_tokens": explicit_tokens + ambient.get(arm, 0),
        })
    with open(out_path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    by_arm = defaultdict(list)
    for r in records:
        by_arm[r["arm"]].append(r)
    print(f"recounted {len(records)} runs -> {out_path}")
    print(f"{'arm':10} {'runs':>4} {'mean explicit tok':>17} {'median':>7} {'runs w/ contact':>15} {'ambient':>8}")
    for arm, rs in sorted(by_arm.items()):
        toks = sorted(r["explicit_doc_tokens"] for r in rs)
        contact = sum(1 for t in toks if t > 0)
        print(f"{arm:10} {len(rs):>4} {sum(toks)//len(toks):>17} {toks[len(toks)//2]:>7} "
              f"{contact:>10}/{len(rs):<4} {ambient.get(arm, 0):>8}")


if __name__ == "__main__":
    main()
