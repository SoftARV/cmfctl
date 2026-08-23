# cmfctl

Control a **CMF Headphone Pro** from Linux — battery, ANC mode, and a live
notification stream — without the Nothing X phone app.

No existing Nothing/CMF tool supports this device: they all hardcode RFCOMM
channel 15, and the Headphone Pro listens on **channel 28**. The protocol was
reverse-engineered here from live capture; see [FINDINGS.md](FINDINGS.md).

## Use

Pair and connect the headphones normally, then:

```console
$ ./cmfctl.py battery
55%

$ ./cmfctl.py anc
anc

$ ./cmfctl.py anc transparency
transparency

$ ./cmfctl.py anc off
off

$ ./cmfctl.py status --json
{"battery": 55, "anc": "anc", "ldac": true}
```

`status` gathers everything over a single RFCOMM link, which is what makes
polling from a bar widget cheap.

`./cmfctl.py listen` streams decoded notifications until Ctrl-C.
`./cmfctl.py probe` scans RFCOMM channels, useful on a different model.

The device address is auto-detected from the connected Bluetooth devices;
override with `--mac`.

```console
$ ./cmfctl.py features
supported features (0x0002AB43):
  + wear-detect
  + game-mode
  ...

$ ./cmfctl.py dump               # query every command, see what answers
```

Any of the 128 known commands can be reached directly:

```console
$ ./cmfctl.py get GET_DEVICE_MODEL
75 b1
$ ./cmfctl.py set SET_EQ_MODE 03
```

## Requirements

Python 3 and BlueZ. Nothing else — RFCOMM is reached through the standard
library's `AF_BLUETOOTH` socket, so there is no dependency to install.

## Omarchy bar plugin

`~/.config/omarchy/plugins/nec.cmf-headphones/` puts battery, the active noise
mode and LDAC status in the bar, with ANC switching in the popup. It shells out
to `cmfctl`, so `~/.local/bin/cmfctl` must stay on PATH.

## Status

Working: battery, ANC read/set, LDAC status, feature discovery, codec
reporting, plus generic `get`/`set` for every known command.

**Shelved pending more work:** the `ldac`, `spatial` and `eq` subcommands were
removed. Their command ids and payload formats are documented in
[FINDINGS.md](FINDINGS.md) and still reachable through `get`/`set`, e.g.

```console
$ ./cmfctl.py set SET_LHDC_COMMANDS 01     # enable LDAC, then `reconnect`
$ ./cmfctl.py set SET_SPATIAL_AUDIO 0100   # spatial on, head tracking off
$ ./cmfctl.py set SET_EQ_MODE 03           # more-bass
```

Not implemented by this model: bass boost (acked but ignored — it has the
physical Energy Slider instead).

Not yet decoded: key/gesture configuration, custom EQ curve.

`constants.py` holds all 128 command ids (EQ, spatial audio, button
configuration, and the rest) extracted from Nothing X, so adding a command is
now a matter of wiring, not discovery.

Not available over this channel: the Energy Slider and volume — see
[FINDINGS.md](FINDINGS.md).
