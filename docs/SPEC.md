# SPEC — cmfctl & the CMF Headphones widget: two publishable repos

Status: **draft, awaiting approval**
Date: 2026-08-28
Scope: cross-repo. Lives here because `cmfctl` is the dependency the other side
rests on. The widget gets its own `docs/SPEC.md` when it grows features.

---

## 1. Objective

The work lives in two places that do not know about each other:

| | where | git | published |
|--|--|--|--|
| `cmfctl` — the CLI that owns the Bluetooth protocol | `~/Projects/cmfctl` | 6 commits, clean | yes — `SoftARV/cmfctl`, public |
| `nec.cmf-headphones` — the Omarchy bar widget | `~/.config/omarchy/plugins/nec.cmf-headphones` | 8 commits, clean, **no remote** | no |

The widget is finished and working but unshareable: no remote, a README that
still says `git clone <this repo>`, and a dependency on a `cmfctl` binary that a
stranger has no supported way to install. `cmfctl` itself is public with **no
description, no licence and no topics**.

**Goal:** make both installable by someone who is not you, from a URL, with the
dependency between them handled explicitly — and organised the way you already
organise `pip-plugin`, not a second invented convention.

**Target users:** Omarchy users with a CMF Headphone Pro (widget); Linux users
who want the headphones scriptable (CLI alone); you, six months from now,
adding EQ and spatial audio.

**Non-goal:** no new headphone features. The shelved `ldac`, `spatial` and `eq`
subcommands stay shelved. This is packaging and organisation.

---

## 2. Constraints, verified

### 2.1 The plugin must be its own repo

`omarchy plugin add <git-url>` — the only supported install path —
(`/usr/share/omarchy/bin/omarchy-plugin-add`, lines 118–145):

```bash
git clone -- "$url" "$stage"          # clones the whole repo
omarchy-plugin-validate "$stage"      # expects $stage/manifest.json
id=$(jq -r '.id' "$stage/manifest.json")
mv "$stage" "$PLUGINS_DIR/$id"
```

`manifest.json` must be at the **repo root**; there is no subdirectory support.
A monorepo with `plugin/` would leave every user cloning and copying by hand.
**→ Two repos.**

### 2.2 Install by copy, not by symlink

I initially proposed symlinking the checkout into `~/.config/omarchy/plugins/`.
**Your `pip-plugin/install.sh` already rejects that, and it is right:**

```
# Copied rather than symlinked: omarchy-plugin-validate rejects a plugin folder
# containing any symlink, so a linked install would validate as broken and the
# shell would quietly never load it.
```

Confirmed by test — `omarchy plugin validate` on a real directory exits 0, on a
symlinked one exits 1, because its last check is
`find "$PLUGIN_DIR" -name .git -prune -o -type l -print -quit` and a symlink
passed as the argument matches itself.

A symlinked plugin *would* in fact load — `omarchy-plugin-catalog` discovers
with `find -L`, which follows symlinks, and `PluginRegistry.entryPointUrl`
(line 100) builds paths by string concatenation with no `realpath`. But it
would fail every validation you or a user ever ran against it, which is a trap.
**We follow the `pip-plugin` convention: `install.sh` copies the runtime files
in.** This also keeps `~/.config/omarchy/plugins/softarv.cmf-headphones` holding
only what the shell loads, exactly as `nec.pip` does today.

### 2.3 Consequences for `.gitignore`

Your `pip-plugin/.gitignore` records the same hazard from the other side — test
scratch had to move to `$TMPDIR` because *any* symlink under the plugin folder
fails validation. The CMF plugin inherits that rule: **no test may create a
symlink inside the repo.**

### 2.4 What the official docs say

From `/usr/share/omarchy/shell/README.md` — the plugin authoring contract:

**Confirms §2.1, in their words:** *"A plugin is a **git repo** with a
`manifest.json` at its root. Adding one clones it straight into
`~/.config/omarchy/plugins/<id>/`."*

**The install path has a consequence I had not accounted for.**
`omarchy plugin update <id>` is *"a fast-forward pull of that checkout"* —
the installed directory is expected to **be** a git checkout. A copy-install
produces a plugins directory with no `.git`, so `omarchy plugin update
softarv.cmf-headphones` silently has nothing to update. That is fine for you and
wrong for a user.

Your `pip-plugin` README already resolves this, and the CMF plugin copies it:

```bash
omarchy plugin add https://github.com/SoftARV/omarchy-pip-handler.git --enable
~/.config/omarchy/plugins/nec.pip/install.sh
```

`omarchy plugin add` clones the **whole repo** — `install.sh` included — into
the plugins dir, and the user then runs `install.sh` *from there*. Which is
exactly what the branch at the top of `pip-plugin/install.sh` is for:

```bash
if [[ $(readlink -f "$REPO") == "$(readlink -f "$PLUGIN_DIR" 2>/dev/null || echo "")" ]]; then
  say "plugin: this checkout is already the installed plugin"
```

So one `install.sh` serves both paths, and the user's plugin dir stays a git
checkout that `omarchy plugin update` can fast-forward:

| who | runs | `install.sh` does |
|--|--|--|
| user | `omarchy plugin add <url> --enable`, then `<plugins-dir>/install.sh` | detects it *is* the installed checkout, skips the copy, resolves `cmfctl` |
| you | `./install.sh` from `~/Projects/cmf-headphones-plugin` | copies the runtime files into the plugins dir |

**Other applicable guidance:**

- *"plugins land disabled so you can review the code before enabling"* — the
  README's install line needs `--enable` (or the user gets a plugin that appears
  to do nothing). `--yes` is documented as *"the path for scripts and AI
  agents"*; `install-deps` and CI use it.
- *"Plugins run as unsandboxed code inside `omarchy-shell`… Only add repos whose
  code you are willing to run."* Since the docs tell users to review before
  enabling, the README should make review cheap — see M3.
- The installer *"never runs plugin code, install hooks, or sudo"*. `install.sh`
  is therefore never automatic; it is always a second, explicit step.
- `omarchy bar put <id> --before omarchy.audio`, the shape the current README
  already uses, is **correct** — `put` exists (`omarchy bar --help`). For a
  bar-widget-only plugin `bar put` is also the *right* enable path: `pip-plugin`
  learned the hard way that a plugin listed in `shell.json`'s `plugins[]` is
  never placed on the bar, and `omarchy bar put` then *"reports success without
  doing anything"*.

**Manifest check.** Our `barWidget.schema` is idiomatic — `integer` with
`min`/`max`/`step`/`defaultValue` matches first-party `SystemUpdate`'s
`refreshIntervalSec` exactly, and `boolean` is in the supported set
(`boolean`, `enum`, `integer`, `multiselect`, `path`, `string`). Two gaps:

- first-party schema entries carry a per-key `description`; ours has none
- **`showBattery` is dead.** It is declared in the schema, and
  `grep showBattery *.qml` matches nothing. The README admits it —
  *"reserved; the bar currently shows the mark only"*. The docs are explicit
  that *"the fields on each entry are the values the plugin sees"*, so this
  ships a switch in the user's settings UI that does nothing. Fix before
  publishing (M3).

---

## 3. Workspace and folder organisation

### 3.1 Where the repos live

Both are flat siblings in `~/Projects`, matching every other project you have.
No parent grouping folder — nothing else in `~/Projects` nests, and a wrapper
would break the muscle memory of `cd ~/Projects/<tab>`.

| local directory | GitHub repo | why this name |
|--|--|--|
| `~/Projects/cmfctl` | `SoftARV/cmfctl` | unchanged — already published under this name |
| `~/Projects/cmf-headphones-plugin` | `SoftARV/omarchy-cmf-headphones` | mirrors `pip-plugin` → `SoftARV/omarchy-pip-handler`: descriptive `-plugin` suffix locally, `omarchy-*` product name on GitHub. Sorts adjacent to `cmfctl`. |

The installed copy stays at `~/.config/omarchy/plugins/softarv.cmf-headphones`.
**The plugin id does not change** — your `shell.json` references it, and
renaming it silently drops the widget out of your bar.

```
~/Projects/
├── cmfctl/                      ← the CLI (protocol lives here)
├── cmf-headphones-plugin/       ← the widget (moved out of ~/.config)
└── pip-plugin/                  ← the convention both follow

~/.config/omarchy/plugins/
└── softarv.cmf-headphones/          ← install target: manifest + QML only, no .git
```

### 3.2 Convention, taken from `pip-plugin`

| folder | holds | precedent |
|--|--|--|
| `bin/` | executables that land on `PATH` | `pip-plugin/bin/omarchy-pip` |
| `docs/` | `SPEC.md`, `SPEC-<version>.md` for shipped versions, `SPIKE-*.md` for investigations | `pip-plugin/docs/` |
| `tasks/` | `plan.md`, `todo.md`, `archive/` | `pip-plugin/tasks/` |
| `test/` | `*_test.*`, a `run.sh` runner, `lib/`, `fixtures/` | `pip-plugin/test/` |
| `config/` | shipped defaults, never user state | `pip-plugin/config/` |
| root | `install.sh`, `README.md`, `CHANGELOG.md`, `LICENSE`, `.gitignore` — plus `manifest.json` and the QML for a plugin, which *must* be at root | both |

Two deviations, each with a reason:

- **cmfctl adds `src/cmfctl/`.** `pip-plugin` has no equivalent because its CLI
  is one self-contained bash file. cmfctl is three Python modules that import
  each other, so they need a package directory; `bin/cmfctl` stays a thin entry
  point, consistent with `bin/`.
- **cmfctl adds `tools/`.** `listen.py` is a reverse-engineering instrument, not
  a test and not shipped on `PATH`. It fits none of the folders above.

### 3.3 `cmfctl` target tree

```
~/Projects/cmfctl/
├── bin/
│   └── cmfctl                    # entry point (was ./cmfctl.py) — this is what gets linked
├── src/cmfctl/
│   ├── __init__.py               # __version__ = "0.1.0" — canonical (§4.1)
│   ├── cli.py                    # the body of cmfctl.py; imports __version__
│   ├── constants.py              # the 128 command ids
│   └── proto.py                  # framing, CRC, RFCOMM
├── tools/
│   └── listen.py                 # passive frame logger, for porting to another model
├── docs/
│   ├── SPEC.md                   # this file
│   ├── FINDINGS.md               # the protocol write-up
│   └── capture.log               # the evidence FINDINGS.md rests on
├── test/
│   ├── run.sh                    # runner, mirroring pip-plugin/test/run.sh
│   ├── proto_test.py             # framing + CRC, no hardware needed
│   ├── install_test.sh           # install.sh behaviour, in a temp HOME
│   └── version_test.sh           # §4.2
├── tasks/
│   ├── plan.md                   # §1 carries the versioning policy, as pip-plugin does
│   └── todo.md
├── install.sh
├── CHANGELOG.md
├── LICENSE                       # MIT — the repo has none today
├── README.md
├── .gitignore                    # unchanged; decompiled/ stays ignored
└── .github/workflows/ci.yml
```

`bin/cmfctl` keeps the `sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))`
trick from `cmfctl.py:27`, retargeted at `../src`. The `realpath` is what makes
the `~/.local/bin` symlink work; **it must survive the move or every install
breaks.**

### 3.4 `cmf-headphones-plugin` target tree

```
~/Projects/cmf-headphones-plugin/
├── manifest.json                 # root — required by omarchy plugin add
├── Panel.qml                     # root — bar button and popup
├── CmfService.qml                # root — polling, state, cmfctl calls
├── NothingHeadphoneIcon.qml      # root — the dot-matrix mark
├── scripts/
│   └── install-deps.sh           # clone + install cmfctl; called by install.sh, also standalone
├── docs/
│   └── SPEC.md                   # later, when the widget grows features
├── test/
│   ├── run.sh
│   ├── manifest_test.sh          # the jq subset of omarchy-plugin-validate
│   ├── validate_test.sh          # shells out to the real omarchy plugin validate
│   └── version_test.sh           # §4.2
├── tasks/
│   ├── plan.md
│   └── todo.md
├── install.sh                    # dual-mode (§2.4): dev copy, or dependency setup in place
├── preview.png
├── CHANGELOG.md                  # manifest.json .version is canonical (§4.1)
├── LICENSE                       # already present, MIT
├── README.md
└── .gitignore                    # must forbid symlink-producing test scratch
```

The four root files are the entire install payload — the same shape as
`nec.pip`, which holds only `manifest.json`, `Panel.qml`, `Service.qml`.

---

## 4. Versioning

**Both projects start at `0.1.0`.** The plugin's `manifest.json` already
declares it; `cmfctl` has no version string anywhere today and gets one.

The convention is `pip-plugin`'s, unchanged — SemVer 2.0.0, tags prefixed `v`
(`v0.1.0`, `v0.1.1`, `v0.2.0` are already on `pip-plugin`), a
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) `CHANGELOG.md` with
`## [Unreleased]` at the top, and the policy itself written into
`tasks/plan.md §1` so a release decision has somewhere to be argued.

`0.1.0` is honest for both: `cmfctl` has never been versioned despite being
public, and neither surface is promised stable. Carry `pip-plugin`'s wording
into both changelogs:

> While on `0.x`, the CLI surface and settings schema may change between minor
> versions; see `tasks/plan.md` for the versioning policy.

### 4.1 Where the version lives

One canonical source per project, and a test whose job is to stop copies
drifting from it:

| project | canonical | copies to keep honest |
|--|--|--|
| plugin | `manifest.json` `.version` | none — no CLI. `CHANGELOG.md` only. |
| `cmfctl` | `src/cmfctl/__init__.py` `__version__` | `CHANGELOG.md`. `cli.py` imports it, so `--version` cannot drift by construction. |

`cmfctl` has no manifest, so its canonical version is the package's
`__version__` — and **`cmfctl --version` is a new flag**, since the CLI has none
today. `cli.py` must *import* `__version__` rather than repeat it: `pip-plugin`
needs `version_test.sh` precisely because its bash CLI cannot import anything,
and a Python package can simply not have the second copy.

### 4.2 What the version test checks

`test/version_test.sh` in both repos, deriving the expected value from the
canonical source rather than hardcoding it — so a release bump touches the
files the procedure names and never a test:

- the canonical version is semver (`^[0-9]+\.[0-9]+\.[0-9]+$`)
- `cmfctl --version` prints exactly it (cmfctl only)
- **the newest released `CHANGELOG.md` heading matches it** — the top `##`
  heading that is not `[Unreleased]`
- if `HEAD` is tagged, the tag is `v<canonical>`

The changelog cross-check is an **addition** to `pip-plugin`'s convention, not
something it does today. It earns its place here because the changelog is the
only copy on the plugin side, so without it the plugin's version test would be
a lone "is it semver" assertion. Worth backporting to `pip-plugin` later.

### 4.3 Release procedure

Tag last, after CI is green (M6) — a tag names a commit you have already
verified. Per release, in order: update `CHANGELOG.md` (move `[Unreleased]`
entries under a dated heading), bump the canonical version, run `test/run.sh`,
commit, `git tag -a v<x.y.z>`, push with `--follow-tags`, then
`gh release create`.

---

## 5. Capability map

Seven modules, built in dependency order. Each is independently verifiable — you
can stop after any one and be in a working state.

```
M0 repos ──┬───────────────────────────────────────────┐
           │                                           │
M1 cmfctl restructure ──► M2 cmfctl hygiene ──┐        │
                                              ├──► M5 CI ──► M6 tag 0.1.0
M3 plugin relocate + publish ──► M4 install UX ┘
```

| id | module | depends on | separable because |
|--|--|--|--|
| **M0** | create/curate the GitHub repos with `gh` | — | Pure remote-side setup; nothing local changes. |
| **M1** | cmfctl: `bin/` + `src/` layout, `install.sh`, `__version__` | M0 | The `cmfctl` on `PATH` is what everything else assumes. Verified alone by `cmfctl status --json`. |
| **M2** | cmfctl: LICENSE, stray files, README, CHANGELOG | M1 | Pure hygiene, no behaviour change. |
| **M3** | plugin: relocate to `~/Projects`, `install.sh`, publish, preview | M0 (parallel with M1) | Verified alone: the shell still loads the widget after a copy-install. |
| **M4** | plugin: detect missing `cmfctl`, `scripts/install-deps.sh` | M1, M3 | Needs `install.sh` to call and the real repo URL to clone. |
| **M5** | CI on both repos | M1–M4 | Guards what the others established. |
| **M6** | tag and release `0.1.0` on both | M5 | A tag should name a commit CI has already verified. |

Order: **M0 → M1 → M2 → M3 → M4 → M5 → M6.** M3 may precede M1 to publish
sooner; M4 is the only module genuinely blocked on both sides.

---

## 6. Module specs

### M0 — GitHub repos (authorised: `gh` + your `personal` SSH key)

You have authorised repo creation on your account. `gh` is authenticated as
`SoftARV` with `repo` scope; `git@personal` resolves to `github.com` with
`~/.ssh/id_ed25519_personal`. Exact commands, to be run verbatim:

```bash
# new — the widget
gh repo create SoftARV/omarchy-cmf-headphones --public \
  --description "Battery, ANC and LDAC for a CMF Headphone Pro in the Omarchy bar"
git -C ~/Projects/cmf-headphones-plugin remote add origin \
  git@personal:SoftARV/omarchy-cmf-headphones.git
git -C ~/Projects/cmf-headphones-plugin push -u origin main

# existing — cmfctl is public but bare: no description, licence or topics
gh repo edit SoftARV/cmfctl \
  --description "Control a CMF Headphone Pro from Linux — battery, ANC, LDAC, over Bluetooth RFCOMM" \
  --add-topic bluetooth --add-topic rfcomm --add-topic nothing \
  --add-topic cmf-headphone-pro --add-topic linux --add-topic reverse-engineering
gh repo edit SoftARV/omarchy-cmf-headphones \
  --add-topic omarchy --add-topic quickshell --add-topic qml \
  --add-topic bluetooth --add-topic cmf-headphone-pro
```

Note `omarchy-pip-handler` uses `git@github.com:` while everything else uses
`git@personal:`. Both work; the new remote uses `personal` for consistency with
the majority and with `cmfctl` itself.

**Acceptance criteria**

- [ ] `gh repo view SoftARV/omarchy-cmf-headphones` succeeds and reports `PUBLIC`
- [ ] `gh repo view SoftARV/cmfctl --json description,repositoryTopics` shows both populated
- [ ] `git -C ~/Projects/cmf-headphones-plugin status -sb` shows `main...origin/main`, nothing ahead
- [ ] `git ls-remote` succeeds over SSH without a password prompt
- [ ] no other repo on the account was touched

### M1 — cmfctl: `bin/` + `src/` layout and `install.sh`

Move to the §3.3 tree. `install.sh`, modelled on `pip-plugin/install.sh` — same
`say`/`warn` helpers, same "safe to re-run" contract, same batched dependency
report:

- resolves its own directory via `BASH_SOURCE`, so it works from anywhere
- reports **all** missing dependencies at once, not one per run
- checks `python3` ≥ 3.9 and that `import socket; socket.AF_BLUETOOTH` resolves —
  a missing bluetooth stack should fail here, loudly, not later inside the widget
- symlinks `bin/cmfctl` → `~/.local/bin/cmfctl`; if the link already points here,
  says so and does nothing
- if a **non-symlink** exists at that path, leaves it alone and warns — same
  wording as `pip-plugin`, which refuses rather than clobbers
- warns if `~/.local/bin` is not on `$PATH`
- ends by printing the verification command

**Acceptance criteria**

- [ ] `./install.sh` on a clean machine ends with `cmfctl status --json` printing
      `{"battery": …, "anc": …, "ldac": …}`
- [ ] `cmfctl` works through the `~/.local/bin` symlink from a directory that is
      **not** the repo — proves the `realpath` import path survived
- [ ] every README-documented subcommand still runs: `battery`, `anc`,
      `anc <mode>` ×6, `status`, `status --json`, `features`, `dump`, `listen`,
      `probe`, `codec`, `get`, `set`
- [ ] `./install.sh` twice is a no-op, not an error
- [ ] a real file at `~/.local/bin/cmfctl` is left alone, with a warning
- [ ] `python3 -m compileall -q bin src tools` is clean
- [ ] the running widget keeps working across the move — it calls bare `cmfctl`

### M2 — cmfctl: licence, stray files, README

Decisions made on your behalf (you delegated the cleanup) — override any:

| file | fate | why |
|--|--|--|
| `try_anc.py` | **delete** | A one-off experiment that succeeded. Its result shipped as `cmfctl anc`, its method is in FINDINGS.md, and it hardcodes `sys.path.insert(0, '.')` so it only runs from the repo root. Nothing reads it. |
| `listen.py` | **keep** → `tools/` | Genuinely reusable: it is how you would map a *different* Nothing model. Distinct from `cmfctl listen`, which decodes rather than logs raw. |
| `capture.log` | **keep** → `docs/` | The evidence behind FINDINGS.md; MAC already `XX:XX:…`. Note `.gitignore` has `*.log` in `pip-plugin` — cmfctl's does not, so this stays tracked. Confirm nothing else in it identifies you. |
| `FINDINGS.md` | **keep** → `docs/` | Referenced from the README; update the links. |
| `decompiled/` | **unchanged** | Correctly gitignored with the reason written in `.gitignore`. Do not touch. |

- Add `LICENSE` (MIT, "Miguel Rincon"). The repo is public **today** with no
  licence, which makes it legally unshareable despite being visible. The plugin
  already declares MIT, so this matches.
- Add `CHANGELOG.md`, seeded from the existing six commits.
- README: paths `./cmfctl.py` → `cmfctl`; new **Install** section leading with
  `install.sh`; the "Omarchy bar plugin" section links the widget's GitHub URL
  instead of a local `~/.config` path.

**Acceptance criteria**

- [ ] `LICENSE` exists; `git ls-files` shows no `try_anc.py`
- [ ] no link in `README.md` or `docs/FINDINGS.md` 404s
- [ ] `grep -rn 'cmfctl\.py' README.md docs/` returns only deliberate historical mentions
- [ ] `git grep -iE '([0-9A-F]{2}:){5}[0-9A-F]{2}'` finds no real MAC anywhere

### M3 — plugin: relocate, install by copy, publish

**Relocate.** `mv ~/.config/omarchy/plugins/nec.cmf-headphones ~/Projects/cmf-headphones-plugin`
— a plain `mv`, so `.git` travels and all 8 commits survive. Never re-init.
Then `./install.sh` writes the runtime files back to
`~/.config/omarchy/plugins/softarv.cmf-headphones`, so the bar is never broken for
more than the moment between the two steps.

**`install.sh`**, ported from `pip-plugin/install.sh`. It is **dual-mode** per
§2.4: it first compares `readlink -f` of its own directory against the plugins
directory, and when they match it says so and skips the copy entirely — that is
the user's post-`omarchy plugin add` path, and skipping the copy is what keeps
their plugin dir a git checkout that `omarchy plugin update` can fast-forward.
In dev mode it copies. In both modes it resolves the `cmfctl` dependency by
delegating to `scripts/install-deps.sh` (M4).

The file list is derived from `manifest.json` rather than hardcoded, because a
hardcoded list there silently forgot `Panel.qml` and the only symptom was a line
on the shell's console:

```bash
files=(manifest.json)
while IFS= read -r entry; do [[ -n $entry ]] && files+=("$entry"); done \
  < <(jq -r '.entryPoints[]?' "$REPO/manifest.json")
for extra in "$REPO"/*.qml; do [[ -e $extra ]] && files+=("$(basename "$extra")"); done
```

`NothingHeadphoneIcon.qml` is not an entry point, so the `*.qml` sweep is what
carries it — the same reason it exists in `pip-plugin`. Copy only when `cmp`
differs, then `omarchy-shell shell rescanPlugins`, then print the reminder that
`omarchy restart shell` is needed for geometry changes (already in the README).

**Rename the plugin id** to `softarv.cmf-headphones` — your GitHub alias rather
than your laptop login. Lowercase, matching every other id on the system and the
bare-username form of `jankeesvw.notification-center` and `yeleticc.vpn`.

Do it **now, in this module**: an id is a public identifier from first
publication, and with no users yet the change costs one string. After M6 tags
`0.1.0` it would break every install. Also set the manifest's `author` from
`"nec"` to `"Miguel Rincon"`, matching `nec.pip`.

Four things move together, and the order matters — the bar entry must be
rewritten before the old directory disappears, or the widget vanishes from the
bar with nothing to put back:

1. `manifest.json`: `"id": "softarv.cmf-headphones"`, `"author": "Miguel Rincon"`
2. `~/.config/omarchy/shell.json`: the `bar.layout.right` entry
   `{"id": "nec.cmf-headphones"}` → `{"id": "softarv.cmf-headphones"}`.
   **Back the file up first.** This is the one authorised exception to the
   "ask first" rule on `shell.json` (§10) — you asked for the rename, and it
   cannot happen without this edit. The entry carries **no settings**, verified,
   so it is a single string replacement with nothing to migrate.
3. `./install.sh` to populate `~/.config/omarchy/plugins/softarv.cmf-headphones`
4. `rm -rf ~/.config/omarchy/plugins/nec.cmf-headphones` — only once step 3 has
   produced a working widget under the new id

`nec.pip` and `nec.notifications` keep their ids. `nec.pip` is already published
as `SoftARV/omarchy-pip-handler`, so renaming it would break real installs for
no gain — that is a decision for its own spec, not this one.

**Fix `showBattery`** (§2.4). It is in the manifest schema and in no QML file —
a switch in the user's settings UI that does nothing. Either wire it to the
battery text next to the bar icon, which is what its label promises, or drop the
key and its `defaults` entry. **Recommendation: wire it.** The label already
describes the behaviour, the bar has room, and removing a key that the README
has advertised is the worse of the two. Also add a per-key `description` to each
schema entry, as first-party manifests do.

**Publish** per M0, then rewrite the README's install section to the two-path
shape `pip-plugin` uses (§2.4):

```bash
omarchy plugin add https://github.com/SoftARV/omarchy-cmf-headphones.git --enable
~/.config/omarchy/plugins/softarv.cmf-headphones/install.sh
omarchy bar put softarv.cmf-headphones --before omarchy.audio
```

`--enable` is not optional in that first line — the docs are explicit that
plugins land disabled so the code can be reviewed first.

Three more README sections, each earning its place from the docs:

- **What this plugin runs.** The docs warn that plugins are *"unsandboxed code
  inside `omarchy-shell`"* and tell users to review before enabling. Make that
  review cheap: state plainly that the widget spawns exactly two kinds of
  subprocess — `cmfctl status|anc|set …` and
  `gdbus monitor --system --dest org.bluez` — and nothing else, ever.
- **Uninstalling** — `omarchy plugin remove softarv.cmf-headphones`, mirroring
  `pip-plugin`.
- The §2.2 validate-rejects-symlinks rule, so nobody re-invents the link install.

**preview.png** — every other third-party plugin you have installed ships one.
Screenshot the bar button and the open popup, connected, ANC active with the
level row visible. Cropped, PNG, ≲500 KB. **You take this; I cannot screenshot
your bar.**

**Acceptance criteria**

- [ ] `omarchy plugin validate ~/Projects/cmf-headphones-plugin` exits 0
- [ ] `omarchy plugin validate ~/.config/omarchy/plugins/softarv.cmf-headphones` **also** exits 0 — the copy install's whole point
- [ ] after `./install.sh` and `omarchy restart shell`, the widget renders and switches ANC
- [ ] `omarchy plugin list --json | jq '.[] | select(.id=="softarv.cmf-headphones")'` finds it
- [ ] `grep -c nec.cmf-headphones ~/.config/omarchy/shell.json` returns 0, and the
      widget is still in `bar.layout.right` in its original position
- [ ] `~/.config/omarchy/plugins/nec.cmf-headphones` no longer exists
- [ ] `jq -r '.id, .author' manifest.json` prints the new id and `Miguel Rincon`
- [ ] a `shell.json` backup exists from before the edit
- [ ] the installed dir contains exactly `manifest.json` + the three `.qml` files — no `.git`, `docs/`, `test/`
- [ ] `git -C ~/Projects/cmf-headphones-plugin log --oneline | wc -l` ≥ 8 — history survived
- [ ] a scratch `git clone` of the published URL into a temp dir passes `omarchy plugin validate`
- [ ] `install.sh` run twice reports "already up to date" and copies nothing
- [ ] `install.sh` run **from inside the plugins dir** reports "this checkout is
      already the installed plugin" and copies nothing — the user path, §2.4
- [ ] after a real `omarchy plugin add` of the published URL,
      `omarchy plugin update softarv.cmf-headphones` fast-forwards cleanly
- [ ] `grep -r showBattery *.qml` matches, or the key is gone from the manifest
- [ ] every `barWidget.schema` entry has a `description`
- [ ] `preview.png` committed and rendering in the GitHub README

### M4 — plugin: handle a missing `cmfctl`

**The bug this fixes.** `CmfService.qml:onExited` treats *every* non-zero exit as
"headphones are off" and sets `connected = false`. A user who installs the widget
without `cmfctl` therefore sees **"Not connected"** — a confident, wrong
diagnosis pointing them at their Bluetooth instead of the missing dependency.
It is the worst thing about the current install experience.

**Design.** Do not infer this from `statusProc`'s exit code — Quickshell's
`Process` gives no reliable code for a binary that fails to *start*. Probe
explicitly, at startup and after each failed status:

```qml
property bool cmfctlMissing: false

Process {
  id: probeProc
  command: ["sh", "-c", "command -v cmfctl >/dev/null 2>&1"]
  onExited: function (code) { root.cmfctlMissing = (code !== 0) }
}
```

`sh` is always present, so the probe cannot itself fail to start. The widget
inherits `omarchy-shell`'s `PATH`; if `~/.local/bin` is absent from it the probe
reports missing, which is the honest answer.

**Panel changes** (`Panel.qml`, the status `Text` at ~133–150 that today returns
`"Not connected"`):

- when `cmfctlMissing`: `cmfctl not found on PATH`
- a second wrapping line gives the fix, selectable so it can be copied
- the ANC row, level row and LDAC toggle are **hidden, not disabled** — none of
  them can do anything
- the bar icon uses the existing dimmed `barTint`; no new bar state

**`scripts/install-deps.sh`** — invoked by `install.sh` (§M3) and standalone,
because the panel needs a single command it can show a stuck user:

- clones `https://github.com/SoftARV/cmfctl` to `~/.local/share/cmfctl`
  (`git pull` if already present), runs its `install.sh`
- verifies with `cmfctl status --json`, prints the result
- prints `omarchy restart shell` last — the probe only re-runs on widget reload
- refuses to run as root; no `sudo` anywhere — the docs are explicit that the
  Omarchy installer *"never runs plugin code, install hooks, or sudo"*, and a
  script it points users at should hold the same line

The panel's fix line names `install.sh`, not this script directly — one command
for the user to remember, matching `pip-plugin`'s README:
`~/.config/omarchy/plugins/softarv.cmf-headphones/install.sh`

**Acceptance criteria**

- [ ] with `cmfctl` off `PATH`, the popup says `cmfctl not found on PATH` and shows the fix — **not** "Not connected"
- [ ] with `cmfctl` present and the headphones off, it still says "Not connected" — the important negative test
- [ ] with `cmfctl` missing, no ANC or LDAC control is visible or clickable
- [ ] after `install-deps.sh` + `omarchy restart shell`, the widget reaches its normal connected state with no manual step
- [ ] `install-deps.sh` is idempotent and exits non-zero with a readable message when git or the network is unavailable
- [ ] the LDAC restart flow (`restarting`, `restartGuard`) is untouched

### M5 — CI

**cmfctl** (`.github/workflows/ci.yml`, `ubuntu-latest`, push + PR):
`python3 -m compileall -q bin src tools`; `test/run.sh`; `ruff check` (installed
in CI — it is **not** available locally, so it must never become a local
pre-commit requirement).

**plugin** — GitHub runners have no `omarchy`, so CI runs the jq subset of
`omarchy-plugin-validate` that we can check honestly: `schemaVersion == 1`;
`id`/`name`/`version`/`kinds`/`entryPoints` present; `id` matches
`^[A-Za-z0-9][A-Za-z0-9._-]*$` and is not `omarchy.*`; every entry-point path
relative, `..`-free and existing; `kinds: ["bar-widget"]` implies
`entryPoints.barWidget`; no symlinks outside `.git`. The workflow must state in
a comment that it is a subset and that `omarchy plugin validate` on the real
path is authoritative — the same split `pip-plugin/test/plugin_validate_test.sh`
already makes.

**Acceptance criteria**

- [ ] both workflows green on a push to `main`
- [ ] breaking `manifest.json` (`schemaVersion: "1"`) fails plugin CI
- [ ] breaking a frame test fails cmfctl CI
- [ ] each run under two minutes, no secrets

### M6 — tag and release `0.1.0`

The §4.3 procedure, once per repo, after CI is green.

`cmfctl`'s `CHANGELOG.md` is written backwards from its six existing commits —
there is real history to describe (ANC across six modes, the codec reporting,
the LDAC correction), and `0.1.0` should say what the thing does rather than
"initial release". The plugin's is written from its eight, and must call out
that `showBattery` now works (or is gone), because a settings key changing
behaviour is exactly what a changelog exists to record.

Both `0.1.0` entries carry the `0.x` note from §4.

```bash
git tag -a v0.1.0 -m "cmfctl 0.1.0"
git push --follow-tags
gh release create v0.1.0 --title "cmfctl 0.1.0" --notes-from-tag
```

**Acceptance criteria**

- [ ] `test/version_test.sh` passes in both repos
- [ ] `cmfctl --version` prints `0.1.0`; `jq -r .version manifest.json` prints `0.1.0`
- [ ] the newest non-`[Unreleased]` heading in each `CHANGELOG.md` is `[0.1.0]`, dated
- [ ] `git tag` shows `v0.1.0` in both; `git ls-remote --tags origin` shows it pushed
- [ ] `gh release view v0.1.0` succeeds on both repos
- [ ] each `CHANGELOG.md` has an empty `## [Unreleased]` section ready for the next change
- [ ] no version string exists anywhere outside the canonical source and the changelog

---

## 7. Commands

| | |
|--|--|
| `./install.sh` | cmfctl: link onto `PATH`. plugin: copy into the plugins dir |
| `cmfctl status --json` | verify the CLI end to end |
| `test/run.sh` | the test suite, either repo |
| `cmfctl --version` | new in 0.1.0; must match `src/cmfctl/__init__.py` |
| `git tag -a v0.1.0 && git push --follow-tags` | release, after CI is green (§4.3) |
| `python3 -m compileall -q bin src tools` | cmfctl syntax gate |
| `omarchy plugin validate <dir>` | authoritative plugin check — **real dir, never a symlink** |
| `omarchy restart shell` | reload the widget; `rescanPlugins` alone keeps the old instance |
| `scripts/install-deps.sh` | install cmfctl for a widget user |
| `omarchy plugin add https://github.com/SoftARV/omarchy-cmf-headphones` | what a stranger runs |

---

## 8. Code style

- **cmfctl:** stdlib only. The README's "no dependency to install" is a feature —
  it is why `install.sh` can be a symlink. Match the existing voice: comments
  explain *why* (`constants.py` is resolved from the app's own table "rather
  than transcribed by hand"), never what the line does.
- **QML:** two-space indent, `readonly property` for derived state, `Style.*`
  tokens for spacing and fonts, never literals. `CmfService.qml`'s comments
  record hard-won runtime facts — StdioCollector ordering, `EBUSY` on fan-out,
  the LDAC power-cycle. They are load-bearing: **do not reword or drop them
  during the move.**
- **Shell:** `set -euo pipefail`; `say`/`warn` helpers as in `pip-plugin`;
  batch dependency reports; never `sudo`; never write to `~/.config/hypr`.
- **Commits:** the existing imperative, lowercase-scoped style — `anc: resume at
  the remembered level`. One module per commit series; a `git mv` never shares a
  commit with an edit, so review can follow the move.
- **Docs:** `docs/SPEC.md` is current; freeze a copy as `docs/SPEC-<version>.md`
  when a version ships, as `pip-plugin` does.

---

## 9. Testing strategy

**Automatable, no headphones** — `proto.py` is pure: `crc16_modbus`, `build`
and `frames` take bytes and return bytes. `test/proto_test.py` covers:

- `crc16_modbus` against a known frame from `docs/capture.log`
- `build` → `frames` round-trips, empty and multi-byte payloads
- a truncated buffer yields nothing rather than raising
- a bad CRC yields `crc_ok = False`, not a silent pass
- two concatenated frames yield both — the streaming case

**Automatable, no hardware** — `test/install_test.sh` runs `install.sh` against
a temp `HOME`: fresh install, re-run is a no-op, a real file at the target is
refused, a stale symlink is re-pointed. `test/manifest_test.sh` and
`validate_test.sh` do the plugin side, mirroring
`pip-plugin/test/plugin_validate_test.sh` and `install_test.sh`.

**Manual, hardware required** — a checklist in the plugin README: each of the
six ANC modes round-trips; battery matches the phone app; the LDAC toggle shows
"Restarting…" and recovers within ~9 s; the widget recovers across a power cycle.

**Regression watch.** The two things most likely to break here are (a) the
`realpath` import path once modules move under `src/`, and (b) the "headphones
off" vs "cmfctl missing" distinction in M4. Both have explicit criteria above;
do not mark a module done on the happy path alone.

---

## 10. Boundaries

**Always**

- After M3 renames it, keep the plugin id `softarv.cmf-headphones` fixed — from
  first publication it is a public identifier, and `shell.json` references it.
- Preserve git history: `mv` directories, never re-init.
- Install the plugin by **copying**, never symlinking (§2.2).
- Keep `install.sh` dual-mode: when run from inside the plugins dir it must not
  copy, or it breaks `omarchy plugin update` for every user (§2.4).
- Derive the install file list from `manifest.json`, never hardcode it.
- Ship no setting that the QML does not read (§2.4, `showBattery`).
- Verify the live widget still works after any structural change.
- Keep `cmfctl` dependency-free.
- Keep one canonical version per project (§4.1); a new copy needs a test that
  derives from the canonical source, never a hardcoded string.

**Ask first**

- Renaming a repo, a local directory, or any user-visible id.
- Anything touching `~/.config/omarchy/shell.json` or `~/.config/hypr` — with
  one carve-out: the single id string the M3 rename requires, backed up first.
- Force-pushing, changing a repo's visibility, or moving/deleting a pushed tag.
- Any version bump past `0.1.0`.
- Adding a runtime dependency to either project.
- Changing `proto.py` — reverse-engineered and expensive to re-derive.

**Never**

- Commit `decompiled/` — derivative of Nothing's proprietary app. The reason is
  already in `.gitignore`; keep it there.
- Publish a real MAC address or an unredacted capture.
- Create a symlink anywhere inside a plugin repo, including from tests.
- Vendor `cmfctl` into the plugin — you ruled this out; it would fork the
  protocol across two repos.
- Move `manifest.json` off the plugin repo root — it breaks `omarchy plugin add`.
- Touch any repo on the account other than the two named in M0.
- `sudo` in any install script.
- Add headphone features here. EQ and spatial audio are a later spec.

---

## 11. Assumptions

Correct any of these before I start:

1. Local directory `~/Projects/cmf-headphones-plugin`, repo
   `SoftARV/omarchy-cmf-headphones`, public, remote over the `personal` alias.
2. Plugin id becomes `softarv.cmf-headphones` (§M3), from `nec.cmf-headphones`;
   `cmfctl`'s repo name is unchanged.
3. MIT both sides, author "Miguel Rincon" (the plugin already declares MIT).
4. `try_anc.py` deleted, `listen.py` survives in `tools/` (§M2).
5. cmfctl stays stdlib-only with no `pyproject.toml` — you chose `install.sh`;
   pipx and AUR remain open as a later, additive step.
6. M0 runs when you approve this spec, not before — the repo name in §3.1 is
   assumption 1, and creating it is the one step that is public and awkward to
   undo.
7. You take `preview.png`.
8. `showBattery` gets **wired up** rather than removed (§M3). It is the only
   assumption here that adds behaviour rather than moving files; say so if you
   would rather drop the key.
9. Both projects release `0.1.0` — not `1.0.0`. Neither surface is promised
   stable yet, and `pip-plugin` set the same precedent by shipping `0.1.0`
   first. `cmfctl` being already public does not make it `1.0`.

---

## 12. Sources

Read directly, not recalled:

| claim | source |
|--|--|
| plugin = git repo, manifest at root; `plugin update` is a fast-forward pull; plugins land disabled; unsandboxed-code warning; `--yes` is the agent path | `/usr/share/omarchy/shell/README.md` |
| manifest schema, `kinds` table, `barWidget.schema` example | same |
| clone-then-validate-then-move install flow | `/usr/share/omarchy/bin/omarchy-plugin-add` |
| symlink rejection; entry-point and id rules | `/usr/share/omarchy/bin/omarchy-plugin-validate`, plus a live test |
| `find -L` discovery (symlinks *are* followed at runtime) | `/usr/share/omarchy/bin/omarchy-plugin-catalog` |
| entry-point path resolution without `realpath` | `/usr/share/omarchy/shell/services/PluginRegistry.qml:100` |
| `omarchy bar put` exists and takes `--before` | `omarchy bar --help` |
| supported schema types; `refreshIntervalSec` precedent | first-party manifests under `/usr/share/omarchy/shell/plugins/` |
| copy-not-symlink; manifest-derived file list; dual-mode install; two-path README | `~/Projects/pip-plugin/{install.sh,README.md,.gitignore}` |
