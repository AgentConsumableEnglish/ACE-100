#!/usr/bin/env bash
# ACE-100 release publisher. Development-side tooling — never part of the kit.
#
#   meta/publish.sh issue-N [--dry-run]
#
# Gates first, then builds the release artifacts into meta/dist/, then tags
# and publishes a GitHub Release. --dry-run stops after the build.
#
# Gates (all must pass):
#   - on main, clean worktree, local main == origin/main after a fetch
#   - tag issue-N does not exist yet (a note, not a failure, under --dry-run)
#   - tools/check.sh and tools/lint.py sweep clean
#   - no "draft" wording anywhere in kit prose (README.md, docs/)
#   - changes.md has a dated "## Issue N — YYYY-MM-DD" heading
#   - tools/measurements/issue-N.txt exists
#   - meta/adopt.sh parses under both bash -n and sh -n
#   - meta/skill/ace-migrate/SKILL.md exists
#   - gh CLI is authenticated (skipped under --dry-run)
#
# Artifacts:
#   meta/dist/ace-100-kit-issue-N.tar.gz    the kit + generated tools/kit-manifest.txt
#   meta/dist/ace-100-skill-issue-N.tar.gz  the ace-migrate skill
#   meta/dist/adopt.sh                      stable-named entry point (evergreen URL)
#   meta/dist/notes.md                      release notes cut from changes.md

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

# The env override exists for scratch-clone tests only (see meta/RELEASING.md).
REPO_SLUG=${ACE_PUBLISH_REPO_SLUG:-AgentConsumableEnglish/ACE-100}
KIT_PATHS=(README.md docs tools)
# Files the adopter extends: adopt.sh copies each once, then never overwrites it.
SEEDS=(docs/README.md docs/dictionary/technical-terms.md docs/standard/deviations.md)

usage() { echo "usage: meta/publish.sh issue-N [--dry-run]" >&2; exit 2; }

TAG='' DRY=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    issue-*)   TAG=$arg ;;
    *)         usage ;;
  esac
done
[[ "$TAG" =~ ^issue-[0-9]+$ ]] || usage
N=${TAG#issue-}

# --- gates ---------------------------------------------------------------
failures=()
gate() { failures+=("$1"); }

branch=$(git rev-parse --abbrev-ref HEAD)
[ "$branch" = "main" ] || gate "not on main (on $branch)"
[ -z "$(git status --porcelain)" ] || gate "the worktree is not clean"
git remote get-url origin | grep -q "$REPO_SLUG" \
  || gate "origin does not point at $REPO_SLUG — the release would target the wrong repository"
git fetch -q origin
[ "$(git rev-parse main)" = "$(git rev-parse origin/main)" ] \
  || gate "main and origin/main differ — push or pull first"

# A failed `gh release create` leaves the tag with no release. Such a run is
# resumable: same tag, same HEAD, no release yet — skip tagging, publish.
resume=0
if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
  if [ "$DRY" -eq 1 ]; then
    echo "note: tag $TAG already exists (allowed in a dry run)"
  elif [ "$(git rev-parse "$TAG^{commit}")" = "$(git rev-parse HEAD)" ] \
      && ! gh release view "$TAG" --repo "$REPO_SLUG" >/dev/null 2>&1; then
    resume=1
    echo "note: tag $TAG already points at HEAD and has no release — resuming a failed publish"
  else
    gate "tag $TAG already exists (and does not look like a resumable failed publish)"
  fi
fi

tools/check.sh >/dev/null 2>&1 || gate "tools/check.sh reports findings — run it for the list"
python3 tools/lint.py >/dev/null 2>&1 || gate "tools/lint.py reports findings — run it for the list"

# Every kit path is scanned (the checker headers in tools/ ship too), and
# inflections count: "drafts" and "drafted" are as unreleased as "draft".
drafts=$(grep -rniE 'draft' "${KIT_PATHS[@]}" 2>/dev/null || true)
[ -z "$drafts" ] || gate $'kit files still say "draft":\n'"$drafts"

grep -Eq "^## Issue $N — [0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$" docs/standard/changes.md \
  || gate "docs/standard/changes.md has no dated '## Issue $N — YYYY-MM-DD' heading"

[ -f "tools/measurements/issue-$N.txt" ] || gate "tools/measurements/issue-$N.txt is missing"

bash -n meta/adopt.sh 2>/dev/null || gate "meta/adopt.sh does not parse (bash -n)"
sh   -n meta/adopt.sh 2>/dev/null || gate "meta/adopt.sh does not parse (sh -n)"
[ -f meta/skill/ace-migrate/SKILL.md ] || gate "meta/skill/ace-migrate/SKILL.md is missing"

if [ "$DRY" -eq 0 ]; then
  gh auth status >/dev/null 2>&1 || gate "gh is not authenticated (run: gh auth login)"
fi

if [ "${#failures[@]}" -gt 0 ]; then
  echo "publish blocked — ${#failures[@]} gate(s) failed:" >&2
  for f in "${failures[@]}"; do printf -- '- %s\n' "$f" >&2; done
  exit 1
fi
echo "gates pass for $TAG"

# --- build ---------------------------------------------------------------
DIST=meta/dist
rm -rf "$DIST"
mkdir -p "$DIST/kit"
git archive HEAD -- "${KIT_PATHS[@]}" | tar -x -C "$DIST/kit"

manifest="$DIST/kit/tools/kit-manifest.txt"
{
  echo "# ACE-100 kit manifest — $TAG"
  echo "# kit  = a file of the standard; adopt.sh overwrites it on an upgrade"
  echo "# seed = a file the adopter extends; adopt.sh copies it once, then never touches it"
  while IFS= read -r p; do
    [ "$p" = "README.md" ] && continue   # the kit's root index never lands in an adopter repo
    cls=kit
    for s in "${SEEDS[@]}"; do [ "$p" = "$s" ] && cls=seed; done
    echo "$cls $p"
  done < <(git -c core.quotePath=false ls-tree -r --name-only HEAD -- "${KIT_PATHS[@]}")
  echo "kit tools/kit-manifest.txt"
} > "$manifest"

# The manifest must cover exactly the tree: every tracked kit file, minus
# README.md, plus the manifest itself — and all three seeds must be present.
# A short manifest would make adopt.sh delete kit files from adopter repos.
expected=$(git -c core.quotePath=false ls-tree -r --name-only HEAD -- "${KIT_PATHS[@]}" | wc -l | tr -d ' ')
entries=$(grep -cE '^(kit|seed) ' "$manifest")
[ "$entries" -eq "$expected" ] \
  || { echo "manifest entry count $entries != expected $expected" >&2; exit 1; }
[ "$(grep -c '^seed ' "$manifest")" -eq "${#SEEDS[@]}" ] \
  || { echo "a seed file is missing from the tree — check the SEEDS list" >&2; exit 1; }

tar -czf "$DIST/ace-100-kit-$TAG.tar.gz" -C "$DIST/kit" "${KIT_PATHS[@]}"
tar --exclude '.DS_Store' -czf "$DIST/ace-100-skill-$TAG.tar.gz" -C meta/skill ace-migrate
cp meta/adopt.sh "$DIST/adopt.sh"

awk -v pat="^## Issue $N — " \
  '$0 ~ pat {on=1; next} /^## / {on=0} on' \
  docs/standard/changes.md > "$DIST/notes.md"
[ -s "$DIST/notes.md" ] || { echo "the release notes are empty — check changes.md" >&2; exit 1; }

echo "built into $DIST:"
(cd "$DIST" && ls -l ./*.tar.gz adopt.sh notes.md)

if [ "$DRY" -eq 1 ]; then
  echo "dry run — no tag, no push, no release"
  exit 0
fi

# --- publish -------------------------------------------------------------
[ "$resume" -eq 1 ] || git tag "$TAG"
git push origin main "$TAG"
gh release create "$TAG" \
  --repo "$REPO_SLUG" \
  --title "ACE-100 Issue $N" \
  --notes-file "$DIST/notes.md" \
  "$DIST/ace-100-kit-$TAG.tar.gz" \
  "$DIST/ace-100-skill-$TAG.tar.gz" \
  "$DIST/adopt.sh"
echo "released $TAG"
