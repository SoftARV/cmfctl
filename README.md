# cmfctl

Control a **CMF Headphone Pro** from Linux — battery, ANC mode, and a live
notification stream — without the Nothing X phone app.

No existing Nothing/CMF tool supports this device: they all hardcode RFCOMM
channel 15, and the Headphone Pro listens on **channel 28**. The protocol was
reverse-engineered here from live capture; see
[docs/FINDINGS.md](docs/FINDINGS.md).

## Install

```console
$ git clone https://github.com/SoftARV/cmfctl.git
$ cd cmfctl
$ ./install.sh
```

That symlinks `bin/cmfctl` into `~/.local/bin`. It is safe to re-run, and it
never overwrites a file it did not create.

Python 3.9 and BlueZ are the only requirements — RFCOMM is reached through the
standard library's `AF_BLUETOOTH` socket, so there is nothing to install.

## Use

Pair and connect the headphones normally, then:

```console
$ cmfctl battery
20%

$ cmfctl anc
transparency

$ cmfctl anc mid
mid

$ cmfctl anc transparency   # talk to someone
transparency

$ cmfctl anc anc            # back to mid, not high
mid

$ cmfctl anc off
off

$ cmfctl status --json
{"battery": 20, "anc": "transparency", "ldac": true, "codec": "ldac", "codecs": ["AAC", "LDAC"]}
```

`status` gathers everything over a single RFCOMM link, which is what makes
polling from a bar widget cheap.

The **LDAC flag** and the **negotiated codec** are different facts: `ldac` says
the headphones will offer it, `codec` is what host and device actually settled
on. `status` reports both.

`cmfctl listen` streams decoded notifications until Ctrl-C.
`cmfctl probe` scans RFCOMM channels, useful on a different model.

The device address is auto-detected from the connected Bluetooth devices;
override with `--mac`.

```console
$ cmfctl features
supported features (0x0002AB43):
  + wear-detect
  + game-mode
  + google-fast-pair
  ...

$ cmfctl dump               # query every command, see what answers
```

Any of the 128 known commands can be reached directly:

```console
$ cmfctl get GET_DEVICE_MODEL
75 b1
$ cmfctl set SET_EQ_MODE 03
```

## Omarchy bar plugin

[**omarchy-cmf-headphones**](https://github.com/SoftARV/omarchy-cmf-headphones)
puts battery, the active noise mode and LDAC status in the Omarchy bar, with
ANC switching in the popup. It shells out to `cmfctl`, so this has to be
installed and on `PATH` first.

## Status

Working: battery, ANC read/set across all six modes (high, mid, low,
adaptive, off, transparency), LDAC status, feature discovery, codec
reporting, plus generic `get`/`set` for every known command.

**Shelved pending more work:** the `ldac`, `spatial` and `eq` subcommands were
removed. Their command ids and payload formats are documented in
[docs/FINDINGS.md](docs/FINDINGS.md) and still reachable through `get`/`set`:

```console
$ cmfctl set SET_LHDC_COMMANDS 01     # enable LDAC (headphones restart themselves)
$ cmfctl set SET_SPATIAL_AUDIO 0100   # spatial on, head tracking off
$ cmfctl set SET_EQ_MODE 03           # more-bass
```

Not implemented by this model: bass boost (acked but ignored — it has the
physical Energy Slider instead).

Not yet decoded: key/gesture configuration, custom EQ curve.

`src/cmfctl/constants.py` holds all 128 command ids (EQ, spatial audio, button
configuration, and the rest) extracted from Nothing X, so adding a command is
now a matter of wiring, not discovery.

Not available over this channel: the Energy Slider and volume — see
[docs/FINDINGS.md](docs/FINDINGS.md).

## Layout

| | |
|--|--|
| `bin/cmfctl` | entry point; this is what lands on `PATH` |
| `src/cmfctl/proto.py` | framing, CRC, RFCOMM |
| `src/cmfctl/constants.py` | the 128 command ids |
| `src/cmfctl/cli.py` | the command line |
| `tools/listen.py` | passive frame logger, for porting to another model |
| `docs/FINDINGS.md` | the protocol write-up, and what is still unknown |
| `test/run.sh` | the test suite; needs no headphones |

## Contributing

`./test/run.sh` runs everything and needs neither hardware nor a network. The
protocol tests use real frames captured from a device, so they pin the wire
format rather than agreeing with whoever wrote them.

See [CHANGELOG.md](CHANGELOG.md) for what changed, and
[docs/SPEC.md](docs/SPEC.md) for how the project is organised.

## Licence

MIT — see [LICENSE](LICENSE).
