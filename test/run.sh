#!/bin/bash
# cmfctl test runner. Needs python3 and bash; no headphones, no BlueZ.
#
#   ./test/run.sh              run everything
#   ./test/run.sh proto        run only tests whose file name matches a substring
#
# Python files report through unittest, shell files through test/lib/assert.sh.
# Both are summarised the same way here so a failure looks identical whichever
# language found it.
#
# Lint is optional on purpose. ruff is not installed on the development machine
# and is a CI-only gate, so a missing linter reports a skip and never fails the
# suite -- a runner you cannot run locally stops being run at all.

set -uo pipefail

TEST_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(dirname "$TEST_DIR")
FILTER="${1:-}"

c() { if [[ -t 1 ]]; then printf '\033[%sm' "$1"; fi; }

command -v python3 >/dev/null || {
  echo "test/run.sh: python3 is required" >&2
  exit 1
}

files_run=0
failed=()
skipped=()

shopt -s nullglob

for test_file in "$TEST_DIR"/*_test.py; do
  name=$(basename "$test_file" _test.py)
  [[ -n $FILTER && $name != *"$FILTER"* ]] && continue

  printf '%s%s%s\n' "$(c '1')" "$name" "$(c 0)"
  files_run=$((files_run + 1))

  # The indenting pipe would otherwise mask the test's exit code, since a
  # pipeline reports its last command.
  python3 "$test_file" 2>&1 | sed 's/^/  /'
  (( PIPESTATUS[0] == 0 )) || failed+=("$name")
done

for test_file in "$TEST_DIR"/*_test.sh; do
  name=$(basename "$test_file" _test.sh)
  [[ -n $FILTER && $name != *"$FILTER"* ]] && continue

  printf '%s%s%s\n' "$(c '1')" "$name" "$(c 0)"
  files_run=$((files_run + 1))

  output=$(bash "$test_file" 2>&1)
  status=$?

  # Hide the machine-readable tally from the human output.
  printf '%s\n' "$output" | grep -v '^ASSERT_TALLY ' || true

  # A file that dies before report() emits no tally. That is a crash, not a
  # pass, so treat a missing tally as a failure rather than trusting the exit
  # code of whatever ran last.
  tally=$(printf '%s\n' "$output" | grep '^ASSERT_TALLY ' | tail -1)
  if [[ -z $tally ]]; then
    printf '  %sFAIL%s no tally -- the file exited before report()\n' \
      "$(c '31')" "$(c 0)"
    failed+=("$name")
  else
    read -r _ _ t_fail t_skip <<<"$tally"
    (( t_fail == 0 && status == 0 )) || failed+=("$name")
    (( t_skip == 0 )) || skipped+=("$name has $t_skip skipped assertion(s)")
  fi
done

if [[ -z $FILTER ]]; then
  if command -v ruff >/dev/null 2>&1; then
    printf '%sruff%s\n' "$(c '1')" "$(c 0)"
    ruff check "$ROOT" 2>&1 | sed 's/^/  /'
    (( PIPESTATUS[0] == 0 )) || failed+=("ruff")
  else
    skipped+=("ruff is not installed; lint runs in CI only")
  fi

  if command -v shellcheck >/dev/null 2>&1; then
    printf '%sshellcheck%s\n' "$(c '1')" "$(c 0)"
    shellcheck -x "$ROOT"/install.sh "$TEST_DIR"/*.sh "$TEST_DIR"/lib/*.sh 2>&1 |
      sed 's/^/  /'
    (( PIPESTATUS[0] == 0 )) || failed+=("shellcheck")
  else
    skipped+=("shellcheck is not installed; lint runs in CI only")
  fi
fi

printf '\n'
for note in "${skipped[@]:-}"; do
  [[ -n $note ]] && printf '  %sskip%s  %s\n' "$(c '33')" "$(c 0)" "$note"
done

if (( ${#failed[@]} )); then
  printf '  %sFAIL%s  %s\n' "$(c '31')" "$(c 0)" "${failed[*]}"
  exit 1
fi

printf '  %sok%s    %d file(s)\n' "$(c '32')" "$(c 0)" "$files_run"
