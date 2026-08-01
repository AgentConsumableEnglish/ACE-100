---
name: ace-migrate
description: Rewrite this repository's existing documentation into ACE-100, the controlled language for monorepo docs. Use when the user asks to migrate, convert, or rewrite docs to ACE-100, or to make the repo's documentation conform to the standard.
---

# ACE-100 migration

You are migrating a live repository's documentation into ACE-100. The kit is
already adopted (docs/standard/, docs/dictionary/, tools/ exist). Your job is
to rewrite the *pre-existing* documents so the whole corpus passes the
checkers and reads as governed prose.

A live repository is not a blank page. Documents are infrastructure: tests
read them, tools parse them, history points at them. Section 18 of the
standard (docs/standard/migration.md) exists because a migration broke these
things once. Follow it exactly.

## Ground rules (read before anything else)

Read these three documents first, in this order:

1. `docs/standard/agent-brief.md` — the whole standard in one file. Every
   writer (including every subagent you spawn) works from this.
2. `docs/standard/migration.md` — Section 18, the migration rules.
3. `docs/standard/checklist.md` — the per-document review sequence.

Non-negotiable constraints from Section 18:

- **Meaning first (ACE 18.5, 9.1).** If a rule and a document's claim
  conflict, keep the claim and report the conflict. A migration must not
  change what the repository asserts.
- **Verbatim data (ACE 18.4, 10.6).** Status lines, tracker fields, error
  strings, and code samples are values, not prose. Do not translate them.
- **First-line readers (ACE 18.2).** Before adding front matter to a file,
  search for tools and tests that read its first line or compare its title.
  Repair them in the same change.
- **Load-bearing paths (ACE 18.3, 14.8).** Before renaming or moving a
  document, search history trailers, tests, and external links for its path.
  If the path is load-bearing, keep it and declare it exempt.
- **Divide late (ACE 18.6).** Plan divisions only after the whole batch is
  known. Repair cross-batch links in one later pass.
- **Ledger as you go (ACE 18.7).** Record every deviation in
  docs/standard/deviations.md when you find it, not at the end.

## Phase 1 — inventory

Build the migration surface:

1. List every tracked `.md` file outside the kit's own trees.
2. Run `tools/check.sh` and `tools/lint.py` (full sweep) and collect the
   failing files. Files without front matter are unmigrated by definition.
3. For each file, note: its directory (which package owns it), rough size,
   and whether it contains verbatim/structured data.
4. Search for first-line readers and load-bearing paths across the corpus
   (ACE 18.2, 18.3) once, up front — not per file.

Write the inventory down (a scratch file is fine) — batch decisions in
phase 2 depend on seeing the whole surface at once.

## Phase 2 — plan

1. Group the surface into batches by directory or package. A batch should be
   small enough for one writer session and coherent enough that its internal
   links stay inside it.
2. Keep the repository green while you work: put not-yet-migrated trees in
   `.ace-ignore` (one pattern per line, at the repository root), and shrink
   that file as batches land. The checkers then gate each landed batch
   without drowning in pre-existing findings.
3. Plan divisions (files over 120 body lines) across the whole batch before
   rewriting any file in it (ACE 18.6). Use the canonical shape:
   `topic.md` becomes `topic/README.md` plus parts (ACE 15.2).
4. Decide the batch order. Start with a small, low-risk batch to calibrate;
   finish with the trees that other trees link into.

## Phase 3 — rewrite

Work batch by batch. For repositories with many documents, fan the work out:
spawn one subagent per batch, each instructed to read
`docs/standard/agent-brief.md` first and to obey the ground rules above.
Keep phase 2's division plan in the parent context so subagents do not make
conflicting structural choices.

Per document:

1. Add front matter (`"@type"`, `name`, `description`, `isPartOf`), H1 equal
   to `name`.
2. Rewrite the prose to the standard. Meaning first, verbatim data intact.
3. Declare technical terms in docs/dictionary/technical-terms.md in the same
   change (ACE 1.6).
4. Any deliberate deviation: `exempt` in the front matter plus a ledger row
   (ACE 13.7, 17.7).
5. Run both checkers on the file. Fix findings before moving on.

## Phase 4 — verify and close

1. When all batches have landed, do the one cross-batch link-repair pass
   (ACE 18.6), then run the full sweep of both checkers. It must be clean
   with every migration-staging entry removed from `.ace-ignore` — only the
   agent-skill patterns that adoption installed (`^\.agents/` and the vendor
   directories) may remain, since skill directories are agent configuration,
   not governed documents.
2. A clean run is necessary, not sufficient (ACE 17.3): re-read a sample of
   migrated documents for vocabulary choice, voice, meaning, and division
   quality against docs/standard/checklist.md.
3. Update docs/README.md so every package index is listed.
4. Report: documents migrated, divisions made, deviations declared, terms
   added, and anything you could not migrate (with the reason).

Commit in reviewable batches, not one giant change. Commit subjects are
imperative, 15 words max; bodies are descriptive text that tells why
(ACE 16.2). PR descriptions link every document the change adds or updates
(ACE 16.3).
