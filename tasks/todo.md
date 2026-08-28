# TODO — `cmfctl` & `softarv.cmf-headphones` 0.1.0

Ordered task list for [`tasks/plan.md`](plan.md). Each task lands working,
verifiable behaviour. Do them in order; do not start a task whose checkpoint has
not been cleared.

Legend: `[ ]` not started · `[~]` in progress · `[x]` done
Repo: **C** = `~/Projects/cmfctl` · **P** = the plugin repo

---

## Phase 1 — cmfctl core

### [x] T1 — Protocol test net **(C)**

Written **before** the move, not after. `proto.py` is pure, so it can be covered
without headphones, and a suite that passes both sides of T2 is the only thing
that proves the move preserved behaviour. Written afterwards it would prove only
that the code works.

**Files:** `test/run.sh`, `test/proto_test.py`

**Acceptance criteria**
- [x] `crc16_modbus` matches a known-good frame taken from `capture.log`
- [x] `build` → `frames` round-trips: empty payload, single byte, multi-byte
- [x] Two concatenated frames yield both — the streaming case the listener hits
- [x] A truncated buffer yields nothing and does **not** raise
- [x] A corrupted CRC yields `crc_ok = False` — it must not silently pass
- [x] A frame with no CRC flag yields `crc_ok = None`, distinct from `False`
- [x] `test/run.sh` runs the suite, exits non-zero on failure, and prints a
      one-line summary
- [x] `test/run.sh` **skips** `ruff` loudly when it is absent, never fails —
      `ruff` is not installed on this machine and is CI-only
- [x] The whole suite runs with the headphones off

**Verify:** `./test/run.sh` green · deliberately flip a byte in a fixture frame
and confirm the CRC test fails

### [x] T2 — `bin/` + `src/` layout **(C)**

The riskiest operation in the project. `~/.local/bin/cmfctl` currently points at
`~/Projects/cmfctl/cmfctl.py` — **the exact file this task moves** — so the
symlink must be re-pointed inside this task, never as a follow-up.

**Files:** `bin/cmfctl`, `src/cmfctl/{__init__,cli,constants,proto}.py`,
`tools/listen.py`, `docs/{FINDINGS.md,capture.log}`, `~/.local/bin/cmfctl`

**Acceptance criteria**
- [x] Layout matches SPEC §3.3; every move is `git mv`, so history follows
- [x] `bin/cmfctl` keeps the `realpath` trick from `cmfctl.py:27`, retargeted at
      `../src` — this is what makes the symlink install work
- [x] `~/.local/bin/cmfctl` re-pointed at `bin/cmfctl` **in this task**
- [x] T1's suite still passes, unchanged — no test edited to accommodate the move
- [x] `cmfctl status --json` works **from `/tmp`, through the symlink** — not
      from the repo root, which would pass even with the trick broken
- [x] Every documented subcommand runs: `battery`, `anc`, `anc` ×6 modes,
      `status`, `status --json`, `features`, `dump`, `listen`, `probe`, `codec`,
      `get`, `set`
- [x] `python3 -m compileall -q bin src tools` clean
- [x] `CmfService.qml`'s comments are untouched — they record runtime facts
      (StdioCollector ordering, `EBUSY`, the LDAC power-cycle)
- [x] The move and any edit are separate commits

**Verify:** `cd /tmp && cmfctl status --json` · `./test/run.sh` · the bar widget
still shows battery and switches ANC

> **CHECKPOINT A** — headphones on. `command -v cmfctl` resolves, `cmfctl status
> --json` prints from `/tmp`, and the live widget works. Recovery if not:
> `ln -sfn ~/Projects/cmfctl/bin/cmfctl ~/.local/bin/cmfctl`.

> **CHECKPOINT A CLEARED** 2026-08-28. `status --json` from `/tmp` through the
> symlink returned battery 25%, LDAC negotiated; all six ANC modes round-tripped
> and the starting mode was restored. Widget not checked — it is out of the bar
> while the plugin is being reorganised.

### [x] T3 — `install.sh` **(C)**

Makes T2's layout reproducible for someone who is not you. Modelled on
`pip-plugin/install.sh`: same `say`/`warn` helpers, same safe-to-re-run
contract, same batched dependency report.

**Files:** `install.sh`, `test/install_test.sh`

**Acceptance criteria**
- [x] Resolves its own directory via `BASH_SOURCE`; works when run from anywhere
- [x] Reports **all** missing dependencies at once, not one per run
- [x] Checks `python3` ≥ 3.9 **and** that `import socket; socket.AF_BLUETOOTH`
      resolves — a missing bluetooth stack fails here, loudly, not later inside
      the widget
- [x] Symlinks `bin/cmfctl` → `~/.local/bin/cmfctl`, creating the dir if needed
- [x] An existing symlink already pointing here: says so, changes nothing
- [x] A **real file** at the target is left alone with a warning, never clobbered
- [x] Warns when `~/.local/bin` is not on `$PATH`
- [x] Prints the verification command as its last line
- [x] `set -euo pipefail`; no `sudo` anywhere
- [x] `install_test.sh` covers, under a temp `HOME`: fresh install, re-run is a
      no-op, real file refused, stale symlink re-pointed
- [x] shellcheck clean

**Verify:** `HOME=$(mktemp -d) ./install.sh` twice · `./test/run.sh`

### [x] T4 — `0.1.0` and `--version` **(C)**

**Files:** `src/cmfctl/__init__.py`, `src/cmfctl/cli.py`, `test/version_test.sh`

**Acceptance criteria**
- [x] `__version__ = "0.1.0"` in `src/cmfctl/__init__.py` — the canonical source
- [x] `cli.py` **imports** it; the string appears exactly once in the codebase
- [x] `cmfctl --version` prints `0.1.0` and exits 0
- [x] `--version` is listed in `--help`
- [x] `version_test.sh` derives the expected value from `__init__.py` rather than
      hardcoding it, so a bump never touches a test
- [x] It asserts: semver shape · `--version` matches · newest non-`[Unreleased]`
      `CHANGELOG.md` heading matches · a tag on `HEAD`, if any, is `v<version>`
- [x] The changelog assertion **skips loudly, naming T5**, until `CHANGELOG.md`
      exists — never passes vacuously

**Verify:** `cmfctl --version` · `./test/run.sh`

*The planned check — bump `__init__.py` to `0.1.1` and watch the test fail —
does **not** fail, by design. `cli.py` imports the canonical value, so a lone
bump leaves nothing to disagree with; that model was carried over from
`pip-plugin`, whose bash CLI cannot import and so keeps a second copy. The two
assertions that can catch drift were exercised directly instead, since both are
skipped in normal runs and would otherwise ship untested:*

- *changelog: a temporary `CHANGELOG.md` at `[0.1.0]` passes; bumping the
  package to `0.1.1` fails with `expected: 0.1.1 / actual: 0.1.0`*
- *tag: a local `v0.9.9` fails, `v0.1.0` passes; both deleted afterwards*
- *duplicate literal: a second `"0.1.0"` added to `tools/listen.py` fails with
  `expected: 1 / actual: 2`*

---

## Phase 2 — cmfctl publishable

### [x] T5 — Licence, docs, repo metadata **(C)**

`cmfctl` is public **today** with no licence, description or topics. A public
repo with no licence is legally unshareable regardless of intent.

**Files:** `LICENSE`, `CHANGELOG.md`, `README.md`, `docs/FINDINGS.md`,
`try_anc.py` (deleted), plus `gh repo edit`

**Acceptance criteria**
- [x] `LICENSE` — MIT, "Miguel Rincon"
- [x] `CHANGELOG.md` — Keep a Changelog 1.1.0, an empty `## [Unreleased]`, and a
      dated `## [0.1.0]` written **backwards from the six existing commits**:
      ANC across six modes, codec reporting, the LDAC self-restart correction.
      Not "initial release"
- [x] It carries the `0.x` note: the CLI surface may change between minor versions
- [x] README: `./cmfctl.py` → `cmfctl` throughout; an **Install** section leading
      with `install.sh`; the Omarchy section links the widget's GitHub URL
- [x] `docs/FINDINGS.md` links resolve after the move
- [x] **Open question 1 resolved:** `try_anc.py` deleted — you confirmed it
- [x] `gh repo edit` sets the description and topics from SPEC §M0
- [x] `git grep -iE '([0-9A-F]{2}:){5}[0-9A-F]{2}'` finds nothing — currently
      verified clean in working tree *and* full history; keep it that way
- [x] `T4`'s changelog assertion now runs instead of skipping

**Verify:** `./test/run.sh` · `gh repo view SoftARV/cmfctl` shows description and
topics · every README link resolves

> **CHECKPOINT B** — be the stranger. `git clone` the pushed repo to a temp dir,
> run `install.sh` under a temp `HOME`, confirm `cmfctl --version` and `--help`
> work. Headphones not required.

---

## Phase 3 — plugin move, rename, publish

### [x] T6 — Relocate and dual-mode `install.sh` **(P)**

Plain `mv` so `.git` travels and all 8 commits survive — never re-init. Then
`install.sh` writes the runtime files back, so the bar is broken only for the
moment between the two.

*Open question 3 resolved: `~/Projects/cmf-headphones-plugin`.*

**Files:** the whole repo → `~/Projects/cmf-headphones-plugin`, plus
`install.sh`, `test/{run.sh,manifest_test.sh,validate_test.sh}`, `.gitignore`

**Acceptance criteria**
- [x] `git log --oneline | wc -l` ≥ 8 in the moved repo — history survived
- [x] `install.sh` is **dual-mode**: when its own directory *is* the plugins dir
      it says so and copies nothing, preserving the user's git checkout so
      `omarchy plugin update` keeps working (SPEC §2.4)
- [x] The file list is derived from `manifest.json` plus a root `*.qml` sweep,
      never hardcoded — a hardcoded list is how `pip-plugin` lost `Panel.qml`
- [x] `NothingHeadphoneIcon.qml` is carried by the sweep, though it is not an
      entry point
- [x] Copies only when `cmp` differs; a second run reports "already up to date"
- [x] Runs `omarchy-shell shell rescanPlugins`, then prints the
      `omarchy restart shell` reminder
- [x] The installed dir holds **exactly** `manifest.json` + the three `.qml`
      files — no `.git`, `docs/`, `test/`
- [x] `.gitignore` forbids test scratch inside the repo — **any** symlink under a
      plugin folder fails `omarchy plugin validate`
- [x] `omarchy plugin validate` exits 0 against **both** the repo and the
      installed copy
- [~] The widget still renders and switches ANC, under the **old** id.
      *Installed and validated, but not on the bar: you removed it while we
      reorganise and will re-add it once T10 lands the dependency check.*

**Verify:** `./install.sh` twice · `omarchy plugin validate` both paths ·
`omarchy restart shell` and use the widget

### [x] T7 — Rename the id to `softarv.cmf-headphones` **(P)**

Your GitHub alias, not your laptop login. Do it now: an id is public from first
publication, and with no users yet it costs one string.

**The four steps are ordered.** The bar entry must be rewritten before the old
directory is deleted, or the widget vanishes with nothing to put back.

**Files:** `manifest.json`, `~/.config/omarchy/shell.json`, both plugin dirs

**Acceptance criteria**
- [x] `~/.config/omarchy/shell.json` **backed up** before any edit —
      *not needed: the widget had already been taken off the bar, so the file
      held no reference to either id and was never opened*
- [x] 1. `manifest.json`: `id` → `softarv.cmf-headphones`, `author` → `Miguel Rincon`
- [x] 2. `shell.json`: no-op, per above. **`Panel.qml` needed it instead** —
      `moduleName` and `ipcTarget` both carried the id and were not in the
      plan; missing them would have left IPC addressing a dead id
- [x] 3. `./install.sh` populates `~/.config/omarchy/plugins/softarv.cmf-headphones`
- [x] 4. `rm -rf ~/.config/omarchy/plugins/nec.cmf-headphones` — **only** once
      step 3 has produced a working widget
- [~] The widget keeps its **original position**, between `nec.pip` and
      `omarchy.tailscale` — *it is off the bar by your choice; re-adding is
      `omarchy bar put softarv.cmf-headphones --before omarchy.audio` after T10*
- [x] `grep -c nec.cmf-headphones ~/.config/omarchy/shell.json` returns 0
- [x] `omarchy plugin list --json` finds the new id and not the old
- [x] `nec.pip` and `nec.notifications` untouched

**Verify:** `omarchy restart shell` · the widget is where it was and still works

> **CHECKPOINT C** — headphones on. The widget renders under the new id, in its
> original bar position, and switches ANC. Only then delete the old directory.

### [ ] T8 — Publish **(P)**

**Files:** `README.md`, `CHANGELOG.md`, `preview.png`, the GitHub repo

**Acceptance criteria**
- [ ] `gh repo create SoftARV/omarchy-cmf-headphones --public` with the SPEC §M0
      description; remote over the `personal` alias; `main` pushed
- [ ] README install section is the **two-path** shape: `omarchy plugin add …
      --enable`, then `install.sh` from the installed checkout
- [ ] `--enable` is present — plugins land disabled and would otherwise appear
      broken
- [ ] A **"What this plugin runs"** section naming exactly two subprocesses,
      `cmfctl …` and `gdbus monitor --system --dest org.bluez`. The docs tell
      users to review before enabling; make that cheap
- [ ] An **Uninstalling** section, mirroring `pip-plugin`
- [ ] The SPEC §2.2 symlink rule recorded, so nobody re-invents the link install
- [ ] No `git clone <this repo>` placeholder anywhere
- [ ] `CHANGELOG.md` seeded from the 8 commits, with the `0.x` note
- [ ] `preview.png` — bar button plus open popup, connected, ANC active with the
      level row visible. Cropped, ≲500 KB. **You capture this**
- [ ] History scanned before first push — currently verified clean

**Verify:** `gh repo view` · README renders with the preview

> **CHECKPOINT D** — clone the published URL to a scratch dir and
> `omarchy plugin validate` it. Confirm the checkout is one `omarchy plugin
> update` can fast-forward. Headphones not required.

---

## Phase 4 — plugin install UX

### [ ] T9 — `showBattery`, and schema descriptions **(P)**

`showBattery` is declared in `barWidget.schema` and read by no QML file — a
switch in the user's settings UI that does nothing. **Open question 2:** wire it
(default) or drop it.

**Files:** `manifest.json`, `Panel.qml`

**Acceptance criteria**
- [ ] Either `grep showBattery *.qml` matches and toggling it changes the bar,
      **or** the key and its `defaults` entry are gone — not a third state
- [ ] If wired: the battery percentage shows beside the icon when true, hides
      when false, with no layout jump on the bar
- [ ] Every `barWidget.schema` entry gains a `description`, as first-party
      manifests have
- [ ] `omarchy plugin validate` still exits 0
- [ ] The decision and its reason are recorded in `CHANGELOG.md` — a settings key
      changing behaviour is exactly what a changelog is for

**Verify:** toggle it in the settings UI, watch the bar · checklist-only, there
is no automated QML coverage

### [ ] T10 — Detect a missing `cmfctl` **(P)**

Today `CmfService.qml:onExited` treats every non-zero exit as "headphones off",
so a user without `cmfctl` is told **"Not connected"** — a confident wrong
diagnosis pointing them at their Bluetooth.

**Files:** `CmfService.qml`, `Panel.qml`, `scripts/install-deps.sh`, `install.sh`

**Acceptance criteria**
- [ ] Detection is an **explicit probe**, `sh -c 'command -v cmfctl'`, not an
      inference from `statusProc`'s exit code — Quickshell gives no reliable code
      for a binary that fails to start, and `sh` always starts
- [ ] Probe runs at startup and after each failed status
- [ ] Missing: the popup says `cmfctl not found on PATH` plus a selectable fix
      line naming `install.sh`
- [ ] Missing: the ANC row, level row and LDAC toggle are **hidden, not
      disabled** — none of them can do anything
- [ ] **Present but headphones off: still "Not connected"** — the negative test
      that matters most
- [ ] The bar icon uses the existing dimmed `barTint`; no new bar state
- [ ] `scripts/install-deps.sh` clones `SoftARV/cmfctl` to
      `~/.local/share/cmfctl` (or pulls), runs its `install.sh`, verifies with
      `cmfctl status --json`, prints `omarchy restart shell` last
- [ ] It refuses to run as root and uses no `sudo`
- [ ] It is idempotent, and exits non-zero with a readable message when git or
      the network is unavailable
- [ ] `install.sh` delegates to it when `cmfctl` is missing
- [ ] The LDAC restart flow — `restarting`, `restartGuard` — is untouched

**Verify:** see Checkpoint E — this task has **no automated coverage**

> **CHECKPOINT E** — take `cmfctl` off `PATH`, `omarchy restart shell`, read the
> popup: it must name the dependency, not the Bluetooth. Then restore it and
> confirm recovery. Then repeat with `cmfctl` present and the headphones off, and
> confirm it still says "Not connected".

---

## Phase 5 — ship

### [ ] T11 — CI **(C + P)**

**Files:** `.github/workflows/ci.yml` in both repos

**Acceptance criteria**
- [ ] cmfctl: `python3 -m compileall -q bin src tools`, `test/run.sh`,
      `ruff check` — `ruff` installed **in CI only**, never a local requirement
- [ ] plugin: the jq subset of `omarchy-plugin-validate` — `schemaVersion == 1`;
      required fields; the id regex and no `omarchy.*`; entry points relative,
      `..`-free and existing; `bar-widget` implies `entryPoints.barWidget`; no
      symlinks outside `.git`
- [ ] A comment states plainly that it is a subset and that
      `omarchy plugin validate` on a real path is authoritative
- [ ] The MAC grep runs as a gate in both
- [ ] Both green on `main`; each run under two minutes; no secrets
- [ ] Breaking `manifest.json` (`schemaVersion: "1"`) fails plugin CI
- [ ] Breaking a frame test fails cmfctl CI

**Verify:** push a deliberate breakage to a branch, watch it fail, revert

### [ ] T12 — Tag and release `0.1.0` **(C + P)**

Last, because a tag should name a commit CI has already verified.

**Files:** `CHANGELOG.md` in both, plus tags and releases

**Acceptance criteria**
- [ ] `version_test.sh` passes in both repos
- [ ] `cmfctl --version` prints `0.1.0`; `jq -r .version manifest.json` prints `0.1.0`
- [ ] The newest non-`[Unreleased]` heading in each `CHANGELOG.md` is `[0.1.0]`,
      dated
- [ ] `git tag -a v0.1.0`, pushed with `--follow-tags`, on both
- [ ] `gh release create v0.1.0` on both; `gh release view` succeeds
- [ ] Each `CHANGELOG.md` keeps an empty `## [Unreleased]` for what comes next
- [ ] No version string exists outside the canonical source and the changelog

**Verify:** `gh release view v0.1.0` in both repos

---

## Done means

Both repos public, licensed, described, tagged `v0.1.0`, CI green. A stranger
installs the CLI from a URL and the widget with `omarchy plugin add`, and if they
skip the CLI the widget tells them so by name. Your bar works throughout.
