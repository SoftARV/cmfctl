#!/bin/bash
# Assertions for the cmfctl shell tests. Sourced by every *_test.sh.
#
# A test file reports through these functions only; the runner reads the
# tallies off a stdout marker so it never has to parse prose. Deliberately a
# trimmed version of the same contract pip-plugin uses, carrying only the
# assertions cmfctl actually needs.

ASSERT_PASS=0
ASSERT_FAIL=0
ASSERT_SKIP=0

_c() { if [[ -t 1 ]]; then printf '\033[%sm' "$1"; fi; }

pass() {
  ASSERT_PASS=$((ASSERT_PASS + 1))
  printf '  %sPASS%s %s\n' "$(_c 32)" "$(_c 0)" "$1"
}

fail() {
  ASSERT_FAIL=$((ASSERT_FAIL + 1))
  printf '  %sFAIL%s %s\n' "$(_c 31)" "$(_c 0)" "$1"
  [[ $# -gt 1 ]] && printf '       %s\n' "${@:2}"
  return 0
}

# A skip must name the task that will remove it. An unexplained skip is how a
# test quietly stops testing anything; requiring the task id makes the debt
# visible in the summary and greppable in the tree.
skip() {
  local task="$1" reason="$2"
  ASSERT_SKIP=$((ASSERT_SKIP + 1))
  printf '  %sSKIP%s [%s] %s\n' "$(_c 33)" "$(_c 0)" "$task" "$reason"
}

assert_eq() {
  local expected="$1" actual="$2" msg="$3"
  if [[ $expected == "$actual" ]]; then
    pass "$msg"
  else
    fail "$msg" "expected: $expected" "actual:   $actual"
  fi
}

# Long haystacks are truncated: a failure that prints an entire README buries
# the other failures above it and nobody scrolls back up.
assert_contains() {
  local haystack="$1" needle="$2" msg="$3"
  if [[ $haystack == *"$needle"* ]]; then
    pass "$msg"
  else
    local shown=$haystack
    if (( ${#shown} > 200 )); then
      shown="${shown:0:200}... (${#haystack} chars)"
    fi
    fail "$msg" "expected to contain: $needle" "actual: ${shown//$'\n'/ }"
  fi
}

assert_file() {
  if [[ -f $1 ]]; then pass "$2"; else fail "$2" "missing file: $1"; fi
}

# Resolves both sides, so a link expressed relatively still matches.
assert_symlink_to() {
  local link="$1" target="$2" msg="$3"
  if [[ ! -L $link ]]; then
    fail "$msg" "not a symlink: $link"
  elif [[ $(readlink -f "$link") == "$(readlink -f "$target")" ]]; then
    pass "$msg"
  else
    fail "$msg" "expected -> $(readlink -f "$target")" \
                "actual   -> $(readlink -f "$link")"
  fi
}

# Emitted last by every test file; the runner sums these.
report() {
  printf 'ASSERT_TALLY %d %d %d\n' "$ASSERT_PASS" "$ASSERT_FAIL" "$ASSERT_SKIP"
  [[ $ASSERT_FAIL -eq 0 ]]
}
