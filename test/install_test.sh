#!/bin/bash
# install.sh, exercised against a throwaway HOME.
#
# Every case here is a way a real machine differs from a clean one: the link is
# already there, something else owns the name, an old checkout is still linked,
# the bin directory does not exist yet. Installing is the one thing every user
# does exactly once, on a machine nobody tested, so it gets the coverage.
#
# Scratch lives under $TMPDIR, never inside the repo -- a stray symlink in the
# tree is the sort of thing that trips plugin validation next door, and a test
# that pollutes the checkout is a test people stop running.
set -uo pipefail

TEST_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(dirname "$TEST_DIR")
# shellcheck source-path=SCRIPTDIR source=lib/assert.sh
source "$TEST_DIR/lib/assert.sh"

INSTALL="$ROOT/install.sh"
TARGET_REL=".local/bin/cmfctl"

assert_file "$INSTALL" "install.sh exists"
if [[ ! -f $INSTALL ]]; then
  report
  exit $?
fi

# Each case gets its own HOME so no case can see another's leftovers.
new_home() {
  mktemp -d "${TMPDIR:-/tmp}/cmfctl-install-test.XXXXXX"
}

# Runs install.sh with a fake HOME and a PATH that already contains its bin
# dir, so the PATH warning does not fire in cases that are not testing it.
run_install() {
  local home="$1"
  shift
  HOME="$home" PATH="$home/.local/bin:$PATH" bash "$INSTALL" "$@" 2>&1
}

# --- a clean machine -------------------------------------------------------
home=$(new_home)
out=$(run_install "$home")
status=$?
assert_eq 0 "$status" "fresh install exits 0"
assert_symlink_to "$home/$TARGET_REL" "$ROOT/bin/cmfctl" \
  "fresh install links bin/cmfctl onto PATH"
assert_contains "$out" "cmfctl status" "prints a verification command"
rm -rf "$home"

# --- the bin directory does not exist yet ----------------------------------
home=$(new_home)
rm -rf "$home/.local"
run_install "$home" >/dev/null
if [[ -d $home/.local/bin ]]; then
  pass "creates ~/.local/bin when absent"
else
  fail "creates ~/.local/bin when absent"
fi
rm -rf "$home"

# --- running it twice ------------------------------------------------------
# The common case: a user re-runs it after pulling. It must not error, and it
# must not churn the link.
home=$(new_home)
run_install "$home" >/dev/null
before=$(readlink "$home/$TARGET_REL")
out=$(run_install "$home")
status=$?
after=$(readlink "$home/$TARGET_REL")
assert_eq 0 "$status" "re-running exits 0"
assert_eq "$before" "$after" "re-running leaves the link untouched"
assert_contains "$out" "already" "re-running says the link is already in place"
rm -rf "$home"

# --- something else already owns the name ----------------------------------
# A real file here is almost certainly not ours -- a hand-written wrapper, a
# copy someone made. Clobbering it silently would destroy work, so the file
# must survive byte for byte, and the run must not claim success.
home=$(new_home)
mkdir -p "$home/.local/bin"
printf '#!/bin/sh\necho not ours\n' > "$home/$TARGET_REL"
sum_before=$(sha256sum "$home/$TARGET_REL" | cut -d' ' -f1)
out=$(run_install "$home")
status=$?
sum_after=$(sha256sum "$home/$TARGET_REL" | cut -d' ' -f1)
assert_eq "$sum_before" "$sum_after" "an existing real file is left byte-identical"
assert_contains "$out" "not a symlink" "explains why it refused"
if [[ $status -ne 0 ]]; then
  pass "refusing to install exits non-zero"
else
  fail "refusing to install exits non-zero" "got exit 0 while cmfctl is not on PATH"
fi
rm -rf "$home"

# --- an old checkout is still linked ---------------------------------------
# Moving the repo is exactly what this project just did, so a stale link is a
# realistic starting state, not a hypothetical one.
home=$(new_home)
mkdir -p "$home/.local/bin" "$home/old-checkout/bin"
printf '#!/bin/sh\n' > "$home/old-checkout/bin/cmfctl"
ln -s "$home/old-checkout/bin/cmfctl" "$home/$TARGET_REL"
out=$(run_install "$home")
status=$?
assert_eq 0 "$status" "a stale symlink is not an error"
assert_symlink_to "$home/$TARGET_REL" "$ROOT/bin/cmfctl" \
  "a stale symlink is re-pointed at this checkout"
rm -rf "$home"

# --- the bin directory is not on PATH --------------------------------------
# Installing succeeds; the shell just cannot find it yet. Worth saying so,
# because the symptom otherwise is "command not found" after a clean install.
home=$(new_home)
out=$(HOME="$home" PATH="/usr/bin:/bin" bash "$INSTALL" 2>&1)
status=$?
assert_contains "$out" "PATH" "warns when ~/.local/bin is not on PATH"
assert_eq 0 "$status" "a PATH warning is not a failure -- the link was made"
rm -rf "$home"

# --- runs from anywhere ----------------------------------------------------
# BASH_SOURCE, not $PWD: a user who cloned somewhere else and typed the full
# path must get the same result.
home=$(new_home)
out=$(cd / && HOME="$home" PATH="$home/.local/bin:$PATH" bash "$INSTALL" 2>&1)
status=$?
# Carry the installer's own output into the failure. An assertion that reports
# only "expected 0, actual 1" sends whoever reads it back to reproduce the run
# by hand, which on a CI-only failure means a push per guess.
if [[ $status -eq 0 ]]; then
  pass "runs from a different working directory"
else
  fail "runs from a different working directory" "exit $status" "${out//$'\n'/ | }"
fi
assert_symlink_to "$home/$TARGET_REL" "$ROOT/bin/cmfctl" \
  "links correctly when invoked by absolute path from elsewhere"
rm -rf "$home"

# --- a machine without the prerequisites -----------------------------------
# Reported in one pass, and nothing on disk is touched: a user who is missing
# python3 should not also have to wonder what the installer changed first.
# A PATH holding the coreutils the script needs to start, but no python3.
# Emptying PATH outright would remove bash and dirname too, killing the script
# before it could report anything -- which tests the harness, not the installer.
home=$(new_home)
stub_bin="$home/stub-bin"
mkdir -p "$stub_bin"
for tool in bash env dirname mkdir readlink ln cut; do
  ln -sf "$(command -v "$tool")" "$stub_bin/$tool"
done
out=$(HOME="$home" PATH="$stub_bin" bash "$INSTALL" 2>&1)
status=$?
assert_contains "$out" "missing prerequisites" "names what is missing"
assert_contains "$out" "python3" "names python3 specifically"
if [[ $status -ne 0 ]]; then
  pass "a missing prerequisite exits non-zero"
else
  fail "a missing prerequisite exits non-zero"
fi
if [[ ! -e $home/$TARGET_REL ]]; then
  pass "nothing is linked when a prerequisite is missing"
else
  fail "nothing is linked when a prerequisite is missing"
fi
rm -rf "$home"

# --- the script itself -----------------------------------------------------
src=$(cat "$INSTALL")
assert_contains "$src" "set -euo pipefail" "uses a strict shell"
if [[ $src == *sudo* ]]; then
  fail "never calls sudo" "found a sudo reference"
else
  pass "never calls sudo"
fi

report
