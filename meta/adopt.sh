#!/bin/sh
# ACE-100 adopter. Copies the kit into the current repository, or upgrades it.
#
#   curl -fsSL https://github.com/AgentConsumableEnglish/ACE-100/releases/latest/download/adopt.sh | sh
#   curl -fsSL .../adopt.sh | sh -s -- issue-2 --owners "@org/docs-team" --migrate
#
# Arguments:
#   issue-N     pin one issue (default: the newest release)
#   --owners X  write the docs/dictionary/ CODEOWNERS entry with these owners
#   --migrate   install the ace-migrate skill into .agents/skills/ and symlink
#               it into detected vendor skill directories
#   -h, --help  print this help
#
# Environment (tests and air-gapped use):
#   ACE_ADOPT_KIT_TARBALL    path to a local kit tarball, which skips the download
#   ACE_ADOPT_SKILL_TARBALL  path to a local skill tarball
#   ACE_ADOPT_REPO_SLUG      override the GitHub repository (owner/name)
#
# POSIX sh. Needs curl and tar. git and python3 widen the checks when present.
# The kit manifest (tools/kit-manifest.txt) drives every write:
#
#   kit  paths are the files of the standard, and an upgrade overwrites them
#   seed paths belong to the adopter, and a copy runs one time alone
#
# Two manifests reach this script. One arrives in the tarball, and one sits in
# the target already. Each path is validated before use. It must live under
# docs/ or tools/, with no absolute form and no ".." component. So no manifest
# line can ever read or delete outside those two trees.

set -u

SLUG=${ACE_ADOPT_REPO_SLUG:-AgentConsumableEnglish/ACE-100}

say() { printf '%s\n' "$*"; }
die() { printf 'adopt: %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
usage: adopt.sh [issue-N] [--owners "OWNERS"] [--migrate]

Adopts the ACE-100 kit into the current repository, or upgrades an
earlier adoption. Run it from the repository root.

  issue-N     pin one issue (default: the newest release)
  --owners X  write the docs/dictionary/ CODEOWNERS entry with these owners
  --migrate   install the ace-migrate skill into .agents/skills/
EOF
}

# A manifest path names a file under docs/ or tools/, and nothing else. This
# rejects absolute paths, ".." and "." components, and anything outside those
# two trees. The .git/ tree is outside them. The rule holds for the new
# manifest and for the old one alike. The check is lexical, and it reads the
# string, not the filesystem.
valid_path() {
  case "$1" in
    docs/?*|tools/?*) : ;;
    *) return 1 ;;
  esac
  case "/$1/" in
    */../*|*/./*|*//*) return 1 ;;
  esac
  return 0
}

# valid_path clears the string, but cp and rm act on the filesystem. A path
# component can be a symlink that points outside the repository. A lexically
# clean path under it then escapes. This rejects a path whose leaf, or whose
# existing ancestor directory, is a symlink. No write and no delete can follow
# a link out of the two trees.
physical_safe() {
  _pp=$1
  [ -L "$_pp" ] && return 1
  _pp=$(dirname "$_pp")
  while [ "$_pp" != "." ]; do
    [ -L "$_pp" ] && return 1
    _pp=$(dirname "$_pp")
  done
  return 0
}

# Appends one line to a file. A missing final newline is repaired first. The
# new line can then never fuse with the last line of the file.
append_line() {
  if [ -s "$1" ] && [ -n "$(tail -c 1 "$1")" ]; then
    printf '\n' >> "$1" || die "cannot write $1"
  fi
  printf '%s\n' "$2" >> "$1" || die "cannot write $1"
}

# --- arguments -----------------------------------------------------------
TAG='' OWNERS='' MIGRATE=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    issue-[0-9]*) TAG=$1 ;;
    issue-*)   usage >&2; die "not an issue tag: $1" ;;
    --owners)  [ "$#" -ge 2 ] || die '--owners takes a value'; OWNERS=$2; shift ;;
    --migrate) MIGRATE=1 ;;
    -h|--help) usage; exit 0 ;;
    *)         usage >&2; die "unknown argument: $1" ;;
  esac
  shift
done

# A relative override path is the caller's, so resolve it before any cd.
case "${ACE_ADOPT_KIT_TARBALL:-}" in
  ''|/*) : ;;
  *) ACE_ADOPT_KIT_TARBALL="$PWD/$ACE_ADOPT_KIT_TARBALL" ;;
esac
case "${ACE_ADOPT_SKILL_TARBALL:-}" in
  ''|/*) : ;;
  *) ACE_ADOPT_SKILL_TARBALL="$PWD/$ACE_ADOPT_SKILL_TARBALL" ;;
esac

# --- the repository root -------------------------------------------------
if root=$(git rev-parse --show-toplevel 2>/dev/null); then
  cd "$root" || die "cannot enter $root"
else
  say 'note: not a git repository — the current directory is treated as the root'
fi

command -v curl >/dev/null 2>&1 || [ -n "${ACE_ADOPT_KIT_TARBALL:-}" ] || die 'curl is not installed'
command -v tar  >/dev/null 2>&1 || die 'tar is not installed'

work=$(mktemp -d) || die 'mktemp failed'
trap 'rm -rf "$work"' EXIT INT TERM

# --- resolve the issue ---------------------------------------------------
if [ -z "$TAG" ] && [ -z "${ACE_ADOPT_KIT_TARBALL:-}" ]; then
  loc=$(curl -fsSLI -o /dev/null -w '%{url_effective}' "https://github.com/$SLUG/releases/latest") \
    || die 'cannot reach github.com to resolve the newest issue'
  TAG=${loc##*/}
  case "$TAG" in
    issue-[0-9]*) : ;;
    *) die "cannot resolve the newest issue from $loc (no release yet?)" ;;
  esac
fi

# --- fetch and extract the kit -------------------------------------------
kit_tgz=${ACE_ADOPT_KIT_TARBALL:-}
if [ -z "$kit_tgz" ]; then
  kit_tgz="$work/kit.tgz"
  url="https://github.com/$SLUG/releases/download/$TAG/ace-100-kit-$TAG.tar.gz"
  curl -fsSL -o "$kit_tgz" "$url" || die "download failed: $url"
fi
mkdir -p "$work/kit"
tar -xzf "$kit_tgz" -C "$work/kit" || die 'cannot extract the kit tarball'

manifest="$work/kit/tools/kit-manifest.txt"
[ -f "$manifest" ] || die 'the kit tarball has no tools/kit-manifest.txt'
new_issue=$(sed -n '1s/.*— //p' "$manifest")
if [ -n "$TAG" ] && [ "$TAG" != "$new_issue" ]; then
  die "the tarball is $new_issue, not the requested $TAG"
fi
TAG=$new_issue
case "$TAG" in issue-[0-9]*) : ;; *) die "the kit manifest names no issue" ;; esac

grep '^kit '  "$manifest" | cut -d' ' -f2- | sort > "$work/new_kit"
grep '^seed ' "$manifest" | cut -d' ' -f2- | sort > "$work/new_seed"
sort "$work/new_kit" "$work/new_seed" > "$work/new_all"
[ -s "$work/new_kit" ] || die 'the kit manifest lists no files'

while IFS= read -r p; do
  valid_path "$p" || die "the kit manifest names an invalid path: $p"
  [ -f "$work/kit/$p" ] || die "the manifest names a file the tarball lacks: $p"
done < "$work/new_all"

# --- detect the mode -----------------------------------------------------
mode=fresh old_issue='' old_invalid=0
if [ -f tools/kit-manifest.txt ]; then
  mode=upgrade
  old_issue=$(sed -n '1s/.*— //p' tools/kit-manifest.txt)
  # The old manifest sits in the target repository. It gets the same
  # validation as the new one. An invalid line drops, and rm never reads it.
  grep '^kit ' tools/kit-manifest.txt | cut -d' ' -f2- | {
    while IFS= read -r p; do
      if valid_path "$p"; then printf '%s\n' "$p"; else echo x >> "$work/old_invalid"; fi
    done
  } | sort > "$work/old_kit"
  [ -f "$work/old_invalid" ] && old_invalid=$(wc -l < "$work/old_invalid" | tr -d ' ')
elif [ -f docs/standard/about.md ] && grep -q 'ACE-100' docs/standard/about.md 2>/dev/null; then
  mode=legacy
fi

if [ "$mode" = "fresh" ]; then
  conflicts=$(while IFS= read -r p; do
    if [ -e "$p" ] || [ -L "$p" ]; then printf '  %s\n' "$p"; fi
  done < "$work/new_all")
  if [ -n "$conflicts" ]; then
    printf 'adopt: these paths exist, and the kit would overwrite them:\n%s\n' "$conflicts" >&2
    printf 'For a rewrite of an existing repository, read:\n' >&2
    printf '  https://github.com/%s/blob/%s/docs/standard/migration.md\n' "$SLUG" "$TAG" >&2
    printf 'Move the paths away or remove them, then run adopt again.\n' >&2
    exit 1
  fi
fi

# Nothing is written yet. The whole run stops when a target sits under a
# symlinked component. A planted link can then never redirect a copy outside
# the repository. This guards every mode, the official tarball included.
unsafe=$(while IFS= read -r p; do
  physical_safe "$p" || printf '  %s\n' "$p"
done < "$work/new_all")
if [ -n "$unsafe" ]; then
  printf 'adopt: a repository path runs through a symlink, so the kit would write outside the repository:\n%s\n' "$unsafe" >&2
  printf 'Remove the symlink(s) and run adopt again.\n' >&2
  exit 1
fi

# --- copy ----------------------------------------------------------------
copy_one() {
  d=$(dirname "$1")
  [ "$d" = "." ] || mkdir -p "$d" || die "cannot make $d"
  rm -f "$1" 2>/dev/null
  cp "$work/kit/$1" "$1" || die "cannot write $1"
}

copied=0 kept=0
while IFS= read -r p; do
  copy_one "$p"; copied=$((copied + 1))
done < "$work/new_kit"
while IFS= read -r p; do
  if [ ! -e "$p" ]; then
    copy_one "$p"; copied=$((copied + 1))
  else
    kept=$((kept + 1))
  fi
done < "$work/new_seed"

# On an upgrade, a kit file the new issue dropped is removed, with its empty
# parent directories. Seed files and adopter documents are never touched.
# Paths here passed valid_path (lexical) and physical_safe (no symlinked
# component), so the walk stays inside docs/ and tools/.
deleted=0
if [ -f "$work/old_kit" ]; then
  comm -23 "$work/old_kit" "$work/new_all" > "$work/gone"
  while IFS= read -r p; do
    [ -f "$p" ] || continue
    physical_safe "$p" || { old_invalid=$((old_invalid + 1)); continue; }
    rm -f "$p" && deleted=$((deleted + 1))
    d=$(dirname "$p")
    while [ "$d" != "." ] && [ -d "$d" ] && [ ! -L "$d" ] && [ -z "$(ls -A "$d")" ]; do
      rmdir "$d"; d=$(dirname "$d")
    done
  done < "$work/gone"
fi

# --- root README links to the documentation map --------------------------
readme=linked
if [ -f README.md ]; then
  if ! grep -q 'docs/README\.md' README.md; then
    printf '\n## Documentation\n\n- [The documentation map](docs/README.md). The top index of the governed documents.\n' >> README.md \
      || die 'cannot write README.md'
    readme=patched
  fi
else
  name=$(basename "$(pwd)")
  cat > README.md <<EOF || die 'cannot write README.md'
---
"@type": CollectionPage
name: $name
description: This index routes readers to the documentation of this repository.
---

# $name

## Documentation

- [The documentation map](docs/README.md). The top index of the governed documents.
EOF
  readme=created
fi

# --- CODEOWNERS ----------------------------------------------------------
co_target=CODEOWNERS
[ -f .github/CODEOWNERS ] && co_target=.github/CODEOWNERS
co=todo
if grep -q '^/docs/dictionary/' "$co_target" 2>/dev/null; then
  co=present
elif [ -n "$OWNERS" ]; then
  append_line "$co_target" "/docs/dictionary/ $OWNERS"
  co=written
fi

# --- the ace-migrate skill (--migrate) -----------------------------------
skill='' links=''
if [ "$MIGRATE" -eq 1 ]; then
  skill_tgz=${ACE_ADOPT_SKILL_TARBALL:-}
  if [ -z "$skill_tgz" ]; then
    skill_tgz="$work/skill.tgz"
    url="https://github.com/$SLUG/releases/download/$TAG/ace-100-skill-$TAG.tar.gz"
    curl -fsSL -o "$skill_tgz" "$url" || die "download failed: $url"
  fi
  mkdir -p .agents/skills || die 'cannot make .agents/skills'
  tar -xzf "$skill_tgz" -C .agents/skills || die 'cannot extract the skill tarball'
  skill=.agents/skills/ace-migrate

  # Cursor, Codex, Copilot, OpenCode, Cline, Amp, and Zed read .agents/skills/
  # directly. These vendors read their own project directory, so a relative
  # symlink points them at the canonical copy.
  for v in .claude .windsurf .continue; do
    [ -d "$v" ] || continue
    if [ -e "$v/skills/ace-migrate" ] && [ ! -L "$v/skills/ace-migrate" ]; then
      say "note: $v/skills/ace-migrate exists and is not a symlink — left alone"
      continue
    fi
    mkdir -p "$v/skills" || continue
    rm -f "$v/skills/ace-migrate" 2>/dev/null
    ln -s ../../.agents/skills/ace-migrate "$v/skills/ace-migrate" && links="$links $v"
  done

  # Skill directories hold agent configuration, not governed documents, so
  # the checker sweep must not read them.
  if [ ! -f .ace-ignore ]; then
    printf '# Paths the ACE-100 checkers do not sweep. One pattern per line.\n' > .ace-ignore \
      || die 'cannot write .ace-ignore'
  fi
  for pat in '^\.agents/' '^\.claude/' '^\.windsurf/' '^\.continue/'; do
    grep -qxF "$pat" .ace-ignore || append_line .ace-ignore "$pat"
  done
fi

# --- check the result ----------------------------------------------------
# The kit self-check covers kit files alone. A seed file belongs to the
# adopter after the first copy, and its findings are never a kit defect.
kit_ok=unknown sweep=skipped surface=0
if [ -x tools/check.sh ] && command -v bash >/dev/null 2>&1; then
  kit_md=$(grep '\.md$' "$work/new_kit")
  old_ifs=$IFS
  IFS='
'
  set -f
  # shellcheck disable=SC2086
  if tools/check.sh $kit_md >/dev/null 2>&1; then kit_ok=yes; else kit_ok=no; fi
  set +f
  IFS=$old_ifs
  if out=$(tools/check.sh 2>&1); then
    sweep=clean
  else
    sweep=findings
    surface=$(printf '%s\n' "$out" | grep -c ' — ACE ')
  fi
  if command -v python3 >/dev/null 2>&1 && [ -f tools/lint.py ]; then
    if ! lout=$(python3 tools/lint.py 2>&1); then
      sweep=findings
      surface=$((surface + $(printf '%s\n' "$lout" | grep -c ' — ACE ')))
    fi
  fi
fi

# --- report --------------------------------------------------------------
say ''
case "$mode" in
  fresh)   say "adopted the ACE-100 kit at $TAG" ;;
  upgrade) say "upgraded the ACE-100 kit: ${old_issue:-unknown} -> $TAG" ;;
  legacy)  say "upgraded a pre-manifest adoption to $TAG (no stale-file cleanup was possible)" ;;
esac
say "  files written: $copied   seed files kept: $kept   stale kit files removed: $deleted"
[ "$old_invalid" -gt 0 ] && say "  note: $old_invalid invalid path(s) in the old manifest were ignored"
case "$readme" in
  linked)  say '  README.md already links to docs/README.md' ;;
  patched) say '  README.md: added a Documentation section that links to docs/README.md' ;;
  created) say '  README.md: created with a link to docs/README.md' ;;
esac
case "$co" in
  present) say "  $co_target already covers /docs/dictionary/" ;;
  written) say "  $co_target: added '/docs/dictionary/ $OWNERS'" ;;
  todo)    say "  todo: add '/docs/dictionary/ <owners>' to $co_target (or rerun with --owners)" ;;
esac
if [ -n "$skill" ]; then
  say "  skill installed: $skill"
  [ -n "$links" ] && say "  symlinked into:$links"
  say '  agents such as Cursor, Codex, Copilot, and OpenCode read .agents/skills/ directly'
fi
case "$kit_ok" in
  yes) say '  the kit files pass tools/check.sh' ;;
  no)  say "  WARNING: the kit files fail tools/check.sh — report this: https://github.com/$SLUG/issues" ;;
  *)   say '  note: tools/check.sh was not run (bash missing?)' ;;
esac
if [ "$sweep" = "findings" ]; then
  say "  the checkers report $surface finding(s) in pre-existing documents — this is the migration surface, not a failed adoption"
  say '  read docs/standard/migration.md before a rewrite'
  [ -n "$skill" ] && say '  the ace-migrate skill runs that rewrite with an agent'
fi
say ''
say 'next steps:'
say '  1. Write the technical terms of your repository in docs/dictionary/technical-terms.md.'
say '  2. Give each writer docs/standard/agent-brief.md.'
say '  3. Review and commit the new files.'
