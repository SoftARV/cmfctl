# PLAN — `cmfctl` & `softarv.cmf-headphones` 0.1.0

Implementation plan for [`docs/SPEC.md`](../docs/SPEC.md) (approved 2026-08-28).

- **Release target:** `0.1.0` on both repos — two organised, publishable projects
  with the dependency between them handled explicitly
- **Task list:** [`tasks/todo.md`](todo.md)
- **Scope:** cross-repo. `~/Projects/cmfctl` and the widget, which becomes
  `~/Projects/cmf-headphones-plugin`. The plugin repo gets its own `tasks/`
  in T6; until then both task lists live here.

---

## 1. Versioning

`0.1.0` for both, per SPEC §4. The plugin's `manifest.json` already declares it;
`cmfctl` has no version string anywhere and gets one in T4.

Canonical sources, one per project: `manifest.json .version` for the plugin,
`src/cmfctl/__init__.py __version__` for `cmfctl`. `cli.py` **imports**
`__version__` rather than repeating it, so `--version` cannot drift by
construction — the reason `pip-plugin` needs a two-file cross-check is that bash
cannot import, and Python can.

That leaves `CHANGELOG.md` as the only copy able to drift, so `version_test.sh`
checks the newest non-`[Unreleased]` heading against the canonical value. That
check is an addition to the `pip-plugin` convention, not something it does yet.

Tags are `v0.1.0`, pushed in T12 **after** CI is green — a tag should name a
commit that has already been verified. Still `0.x`: neither the CLI surface nor
the settings schema is promised stable.

---

## 2. Slicing strategy

The spec's module order (`M0 → M6`) is close to right but not vertical: `M0`
bundles repo setup for both projects, and `M5` bundles CI for both. Split along
the repo boundary instead, so each task lands one complete, observable change to
one project.

| Task | M0 repos | M1 restructure | M2 hygiene | M3 plugin | M4 install UX | M5 CI | M6 release |
|------|:--------:|:--------------:|:----------:|:---------:|:-------------:|:-----:|:----------:|
| T1 proto tests        |   | ○full |   |   |   |   |   |
| T2 bin/ + src/ move   |   | ●full |   |   |   |   |   |
| T3 `install.sh`       |   | ●full |   |   |   |   |   |
| T4 `0.1.0` + `--version` |   | ●   |   |   |   |   | ○ |
| T5 licence, docs, metadata | ●cmfctl |   | ●full |   |   |   |   |
| T6 relocate + install.sh |   |   |   | ●part |   |   |   |
| T7 id rename          |   |   |   | ●part |   |   |   |
| T8 publish + README   | ●plugin |   |   | ●full |   |   |   |
| T9 `showBattery`      |   |   |   | ○ |   |   |   |
| T10 missing-`cmfctl`  |   |   |   |   | ●full |   |   |
| T11 CI                |   |   |   |   |   | ●full |   |
| T12 tag `0.1.0`       |   |   |   |   |   |   | ●full |

● built here ○ consumed here

**`cmfctl` comes first, entirely.** Not for tidiness — the widget shells out to
`cmfctl` on every poll, so the CLI must be correct and on `PATH` before the
plugin is touched at all. Doing the plugin first would mean debugging two moving
parts at once the first time the bar went blank.

**The riskiest single operation is T2**, and it is deliberately fenced. Verified:
`~/.local/bin/cmfctl` is a symlink to `~/Projects/cmfctl/cmfctl.py`, the exact
file T2 moves. The moment it moves, every `cmfctl` invocation on this machine
fails and the widget goes dark. So T1 writes the test net *first*, T2 re-points
the symlink in the same task, and Checkpoint A is a live check rather than a
green suite.

**T1 before T2 is the whole trick.** `proto.py` is pure — `crc16_modbus`,
`build`, `frames` take bytes and return bytes — so it can be fully covered
without headphones. Writing that suite against the *current* flat layout gives a
net that must go on passing after the move. Tests written afterwards would only
prove the code works, never that the move preserved it.

**T7 is split from T6** because the id rename is the only step that edits
`shell.json`. Keeping the relocate (T6) separate means that if the bar breaks, it
is unambiguous which change did it.

---

## 3. Phases and checkpoints

```
Phase 1  cmfctl core       T1  T2   ─┬─ CHECKPOINT A: the widget survived the move
                           T3  T4   ─┤
Phase 2  cmfctl publish    T5       ─┼─ CHECKPOINT B: a stranger can install cmfctl
Phase 3  plugin move       T6  T7   ─┼─ CHECKPOINT C: bar renders under the new id
                           T8       ─┼─ CHECKPOINT D: `omarchy plugin add` works
Phase 4  plugin UX         T9  T10  ─┼─ CHECKPOINT E: the missing-cmfctl path is real
Phase 5  ship              T11 T12  ─┘
```

### Checkpoint A — after T2

**The only checkpoint that can break daily use.** Confirm live, not by test
suite: `command -v cmfctl` resolves, `cmfctl status --json` prints battery from
a directory that is not the repo, and the bar widget still shows battery and
switches ANC. If any of those fail, the symlink is the first thing to check.

Headphones must be on for this one.

### Checkpoint B — after T5

`cmfctl` is now something a stranger installs from a URL. Verify by being that
stranger: clone the pushed repo to a temp directory, run its `install.sh` under
a temp `HOME`, and confirm `cmfctl --version` and `--help` work with nothing
else on the machine. A licence and a description that only exist locally do not
count.

### Checkpoint C — after T7

The bar must show the widget under `softarv.cmf-headphones`, **in its original
position** in `bar.layout.right` between `nec.pip` and `omarchy.tailscale`. Then
delete the old plugin directory — not before. This is the gate that stops a
half-renamed plugin from leaving the bar with neither id working.

### Checkpoint D — after T8

Install the published plugin the way a user would, into a scratch environment:
`git clone` the URL, `omarchy plugin validate` the clone. Confirm
`omarchy plugin update` sees a git checkout it can fast-forward. This is the
checkpoint that catches the copy-vs-clone trap from SPEC §2.4.

### Checkpoint E — after T10

Take `cmfctl` off `PATH` for real, restart the shell, and read what the popup
says. It must name the missing dependency, not claim the headphones are
disconnected. Then restore `cmfctl` and confirm the widget recovers on its own.

This checkpoint exists because **T10 has no automated coverage whatsoever** —
Quickshell's `Process` behaviour for a binary that fails to start is exactly what
we are guessing about, and only a live run settles it.

---

## 4. Risk register

| Risk | Impact | Handling |
|------|--------|----------|
| **T2 breaks `~/.local/bin/cmfctl`** — verified: it points at `~/Projects/cmfctl/cmfctl.py`, the file being moved | Every `cmfctl` call fails; the widget goes dark until noticed | Re-point the symlink inside T2, never as a follow-up. T1's suite brackets the move. Checkpoint A is a live check. Recovery is one `ln -sfn`. |
| The `realpath` import trick does not survive `src/` | `cmfctl` works in the repo, fails through the symlink — the sneakier half of the same failure | An explicit criterion: run it from `/tmp`, through the symlink, not from the repo root |
| T7 deletes the old plugin dir before the new id renders | Widget gone from the bar with no fallback | Fixed 4-step order, delete last, gated at Checkpoint C |
| The `shell.json` edit loses the widget's bar position | Widget reappears in the wrong section, or not at all | Back up first. Verified the entry carries **no settings** — `{"id": "nec.cmf-headphones"}` and nothing else — so it is one string, not a migration |
| Copy-install leaves users unable to `omarchy plugin update` | Every user is stuck on the version they first installed | Dual-mode `install.sh` (SPEC §2.4); a test that runs it from inside the plugins dir; Checkpoint D uses a real clone |
| Quickshell gives no reliable exit code for a missing binary | The missing-`cmfctl` message never fires, or fires when the headphones are merely off | Probe with `sh -c 'command -v cmfctl'` — `sh` always starts. No unit coverage is possible; Checkpoint E settles it, including the negative case |
| **QML has no automated coverage at all** | T9 and T10 regressions land unnoticed | Keep both thin, put the logic in `CmfService.qml` properties rather than `Panel.qml` bindings, and mark checklist-only criteria as such rather than implying tests exist |
| Publishing something private | Irreversible once pushed | **Already verified clean:** no MAC address in either working tree, nor in either repo's full git history. `capture.log` is pre-redacted to `XX:XX:…`. The grep stays as a CI gate anyway |
| `ruff` is not installed on this machine | A local `test/run.sh` that requires it fails for you every time | CI-only, by design. `test/run.sh` must skip it loudly when absent, never fail |
| Hardware is in the loop | Checkpoints stall when the headphones are off or out of battery | Hardware-free work (T1, T3, T4, T11) is ordered so it never waits. Each checkpoint states whether headphones are needed |
| Both repos public before CI exists | A broken `main` is visible while T11 is still pending | Acceptable: `cmfctl` is already public today, and 0.1.0 is not tagged until T12, after CI is green |

### Open questions

Three decisions the spec proposes but you have not confirmed. Each has a default
so no task blocks; each is cheap to reverse at the named point.

1. **`try_anc.py` — delete?** Default: yes (SPEC §M2). Decide at **T5**, before
   the licence and README land. Nothing reads it and its result shipped as
   `cmfctl anc`, but it is your reverse-engineering history.
2. **`showBattery` — wire or drop?** Default: wire it (SPEC §M3). Decide at
   **T9**. Wiring adds behaviour; dropping removes a key the README advertised.
   It is the only task in this plan that changes what the widget does.
3. **Local directory name.** Default `~/Projects/cmf-headphones-plugin`, matching
   `pip-plugin`. Decide **before T6**, when the `mv` happens — trivial now,
   annoying once the remote and CI reference it.

---

## 5. Out of scope for 0.1.0

Carried from the spec so no task quietly absorbs them:

- **No new headphone features.** The shelved `ldac`, `spatial` and `eq`
  subcommands stay shelved and reachable only through `get`/`set`.
- No `pyproject.toml`, no pipx, no AUR `PKGBUILD` — additive later, and `0.1.0`
  should not carry a packaging system nobody has asked for yet.
- No renaming `nec.pip` or `nec.notifications`. You have explicitly deferred
  this; `nec.pip` is published and renaming it would break real installs.
- No vendoring `cmfctl` into the plugin, and no monorepo.
- No changes to `proto.py`'s protocol handling — moved, never edited.
- No backport of the changelog cross-check to `pip-plugin`.
- No `preview.png` capture by me; T8 depends on you for it.
