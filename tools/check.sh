#!/usr/bin/env bash
# ACE-100 canonical checker (Issue 2). Settles the mechanical rules a shell can:
# front matter and its mandatory properties (ACE 13.2), the H1 (ACE 13.6), the
# 120-line size limit (ACE 15.1), American spelling in prose (ACE 1.12), link
# resolution (ACE 14.5), and one README.md index per directory (ACE 11.3).
#
# It does NOT check: vocabulary layers, voice, tense, modality, sentence limits,
# meaning, or topic division. A clean run is necessary and not sufficient.
# `tools/lint.py` covers the pattern rules; a reader covers the rest.
#
# Adapted from the checker of the first field migration, with thanks.
#
#   tools/check.sh <path>...   # check the given files
#   tools/check.sh             # check every governed file (git-tracked + untracked)
#
# Optional: a .ace-ignore file at the repository root excludes paths from the
# full sweep. One grep pattern per line. Lines that start with '#' and blank
# lines are comments.
#
# Exits non-zero when any check fails. Failures name the file and the ACE rule.

set -uo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null || dirname "$0")" || exit 2

files=()
sweep=0
if [ "$#" -gt 0 ]; then
  files=("$@")
else
  sweep=1
  list=$(git ls-files --cached --others --exclude-standard '*.md' 2>/dev/null || find . -name '*.md')
  if [ -f .ace-ignore ]; then
    # Comments and blank lines must not reach grep: a blank pattern matches
    # every path, and -v then empties the sweep silently.
    list=$(printf '%s\n' "$list" | grep -v -f <(sed '/^#/d;/^[[:space:]]*$/d' .ace-ignore))
  fi
  while IFS= read -r line; do
    [ -n "$line" ] && files+=("$line")
  done <<EOF
$list
EOF
fi

if [ "${#files[@]}" -eq 0 ]; then
  echo 'no files to check'
  exit 0
fi

fail=0
note() { printf '%s\n' "$1"; fail=1; }

for f in "${files[@]}"; do
  [ -f "$f" ] || { note "$f — missing"; continue; }

  # --- front matter (ACE 13.2) -------------------------------------------------
  if [ "$(head -1 "$f")" != "---" ]; then
    note "$f:1 — ACE 13.2: no front matter; the document must open with '---'"
    continue
  fi
  close=$(awk 'NR>1 && $0=="---" {print NR; exit}' "$f")
  if [ -z "$close" ]; then
    note "$f:1 — ACE 13.2: front matter never closes"
    continue
  fi

  # Exemptions (ACE 13.7): rule identifiers named in `exempt:` are skipped.
  exempt=$(awk -v c="$close" 'NR>1 && NR<c && index($0,"exempt:")==1 {print; exit}' "$f")

  props='"@type" name description isPartOf'
  # ACE 13.3: the root index of the repository is the one document with no parent.
  [ "$f" = "README.md" ] && props='"@type" name description'
  for prop in $props; do
    awk -v c="$close" -v p="$prop" 'NR>1 && NR<c && index($0, p": ")==1 {found=1} END {exit !found}' "$f" \
      || note "$f — ACE 13.2: front matter has no '$prop' property"
  done

  # --- the H1 is the first line of the body, and equals `name` (ACE 13.6) ------
  h1=$(awk -v c="$close" 'NR>c && NF {print; exit}' "$f")
  case "$h1" in
    '# '*)
      name=$(awk -v c="$close" 'NR>1 && NR<c && index($0,"name: ")==1 {sub(/^name: */,""); print; exit}' "$f")
      name=${name%\"}; name=${name#\"}; name=${name%\'}; name=${name#\'}
      [ "${h1#\# }" = "$name" ] \
        || note "$f — ACE 13.6: the H1 and the 'name' property differ
    H1:   ${h1#\# }
    name: $name" ;;
    *) note "$f — ACE 13.6: the first line of the body must be the H1, found: ${h1:0:40}" ;;
  esac

  # --- size (ACE 15.1: 120 body lines, everything counts) ----------------------
  case "$exempt" in *"15.1"*) : ;; *)
    body=$(awk -v c="$close" 'NR>c' "$f" | wc -l | tr -d ' ')
    [ "$body" -le 120 ] || note "$f — ACE 15.1: $body body lines, the limit is 120"
  ;; esac

  # --- American English in prose (ACE 1.12) ------------------------------------
  # Backticked text, code blocks, link targets, and path-shaped tokens are
  # identifiers or quoted text; the rule does not reach inside them.
  # A dictionary table names words in order to ban them; a mention is not a use.
  indict=0
  case "$f" in docs/dictionary/*) indict=1 ;; esac
  case "$exempt" in *"1.12"*) : ;; *)
    british=$(awk -v c="$close" -v indict="$indict" '
      NR<=c {next}
      /^```/ {code = !code; next}
      code {next}
      indict && /^[[:space:]]*\|/ {next}
      {
        gsub(/`[^`]*`/, "")
        gsub(/\]\([^)]*\)/, "]")
        gsub(/[^ \t]*\.(md|ts|tsx|js|json|sh|py|css|sql)\b/, "")
        gsub(/[^ \t]*\/[^ \t]*/, "")
        print
      }' "$f" \
      | grep -oiE '\b(colour|behaviour|centre|licence|catalogue|organis(e|ed|ing|ation)|normalis(e|ed|ing|ation)|initialis(e|ed|ing|ation)|analys(e|ed|ing)|recognis(e|ed|ing))[a-z]*' \
      | sort -u | paste -sd' ' - | tr -d '\n')
    [ -z "$british" ] || note "$f — ACE 1.12: British spelling in prose: $british"
  ;; esac

  # --- links resolve, and point at files (ACE 14.5) -----------------------------
  dir=$(dirname "$f")
  while IFS= read -r target; do
    [ -n "$target" ] || continue
    case "$target" in http*|'#'*|mailto:*|'<'*) continue ;; esac
    path="${target%%#*}"
    [ -n "$path" ] || continue
    if [ ! -e "$dir/$path" ]; then
      note "$f — ACE 14.5: link does not resolve: $target"
    elif [ -d "$dir/$path" ]; then
      note "$f — ACE 14.5: link points at a directory: $target"
    fi
  done < <(grep -o '](\([^)]*\))' "$f" 2>/dev/null | sed 's/^](//; s/)$//')
done

# --- every governed directory has an index (ACE 11.3) --------------------------
if [ "$sweep" -eq 1 ]; then
  for dir in $(printf '%s\n' "${files[@]}" | sed -e '/\//!s:.*:.:' -e 's:/[^/]*$::' | sort -u); do
    [ "$dir" = "." ] && continue
    [ -f "$dir/README.md" ] || note "$dir — ACE 11.3: the directory has no README.md index"
  done
fi

if [ "$fail" -eq 0 ]; then
  printf 'ok — %d file(s) pass the mechanical checks\n' "${#files[@]}"
fi
exit "$fail"
