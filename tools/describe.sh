#!/usr/bin/env bash
# ACE-100 corpus reader (Issue 4). Prints the path and the `description`
# property of each governed document, one row for each (ACE 19.1).
#
# ACE 13.2 puts a description on every document, and ACE 11.3 puts an index in
# every directory. A reader that opens whole documents to find one fact pays
# for those two rules and takes nothing back. This tool is the read side of
# them, and Section 19 gives the protocol.
#
#   tools/describe.sh                 # every governed document
#   tools/describe.sh docs            # the documents under a path
#   tools/describe.sh docs migrate    # the rows that match a pattern
#
# The pattern is a basic regular expression, and it matches the whole row.
#
# The file list matches `tools/check.sh`: git-tracked and untracked files,
# with a find fallback, filtered by `.ace-ignore`. The two must agree. Without
# that, the map of a reader differs from the corpus that the checker governs.
# Nothing reports the gap.
#
# This tool is a reader, not a checker. It never fails on content. It exits
# non-zero only when the sweep matches no file at all.

set -uo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" || exit 2

scope=${1:-}
pattern=${2:-}

list=$(git ls-files --cached --others --exclude-standard '*.md' 2>/dev/null || find . -name '*.md' | sed 's|^\./||')
if [ -f .ace-ignore ]; then
  patterns=$(grep -v -e '^[[:space:]]*$' -e '^[[:space:]]*#' .ace-ignore)
  if [ -n "$patterns" ]; then
    list=$(printf '%s\n' "$list" | grep -v -f <(printf '%s\n' "$patterns"))
  fi
fi

if [ -n "$scope" ]; then
  # A trailing slash on the argument is permitted, and it drops.
  scope=${scope%/}
  list=$(printf '%s\n' "$list" | grep -e "^$scope/" -e "^$scope\$")
fi

# The rows are sorted. `check.sh` reports findings in file order, and a reader
# wants one stable order across runs. The set of files is the same either way.
list=$(printf '%s\n' "$list" | sort)

rows=0
while IFS= read -r f; do
  [ -n "$f" ] || continue
  [ -f "$f" ] || continue
  [ "$(head -1 "$f")" = "---" ] || continue
  close=$(awk 'NR>1 && $0=="---" {print NR; exit}' "$f")
  [ -n "$close" ] || continue
  d=$(awk -v c="$close" 'NR>1 && NR<c && index($0,"description: ")==1 {sub(/^description: */,""); print; exit}' "$f")
  d=${d%\"}; d=${d#\"}; d=${d%\'}; d=${d#\'}
  # A document with no description breaks ACE 13.2. The checker reports that.
  # This tool shows the gap, rather than a silent omission of the row.
  [ -n "$d" ] || d='(no description — ACE 13.2)'
  row="$f — $d"
  case "$pattern" in
    '') printf '%s\n' "$row"; rows=$((rows + 1)) ;;
    *) if printf '%s\n' "$row" | grep -q "$pattern"; then
         printf '%s\n' "$row"; rows=$((rows + 1))
       fi ;;
  esac
done <<EOF
$list
EOF

if [ "$rows" -eq 0 ]; then
  echo 'no rows — check the path, the pattern, and .ace-ignore' >&2
  exit 1
fi
