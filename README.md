# sdrpp-mcp

An [MCP](https://modelcontextprotocol.io) server that drives a running
[SDR++](https://github.com/AlexandreRouma/SDRPlusPlus) instance to **find, identify, decode,
record and log radio transmissions**. A companion skill (`skill/sdr-signal-id`) packages the
identification workflow and reference material: signal signatures, decoder notes, hardware
quirks and US legal guardrails.

It works with any SDR++ source. It was developed and tested on an RTL-SDR (Nooelec SMArTee XTR, E4000
tuner, 2.4 MS/s).

## Features

- **Live spectrum**: snapshot the current passband with max-hold detection against an
  estimated noise floor, or step-sweep an arbitrary range (up to 200 retunes). Both return
  waterfall PNGs.
- **Signal analysis**: extract a channel and measure:
  - SNR, 99% occupied bandwidth, duty cycle and bursts
  - envelope statistics, spectral skew and flatness
  - FM deviation and FSK levels, symbol rate (snapped to standard bauds), TDMA framing
  - CTCSS and audio tones, WFM stereo pilot and RDS

  A heuristic classifier then makes a modulation guess: NFM, WFM, AM, SSB, CW/OOK, 2/4-FSK, wideband digital or carrier.
- **Band plan lookup**: US allocations plus named channels (NOAA WX1–7, FRS/GMRS, MURS, APRS,
  ACARS, AIS, ISM, etc.).
- **Demodulation and recording**: FM, WFM (75 µs de-emphasis), AM, USB, LSB and CW to WAV, or raw IQ
  (`cu8` / `cf32`) for offline tools.
- **Decoding**:
  - [multimon-ng](https://github.com/EliasOenal/multimon-ng): POCSAG/FLEX pagers, APRS/AFSK1200, EAS/SAME, DTMF, ZVEI, Morse, X10.
  - [rtl_433](https://github.com/merbanan/rtl_433): ISM-band sensors.
- **Logbook**: SQLite log of identified signals, searchable, exportable as an SDR++
  Frequency Manager bookmark list.

## How it talks to SDR++

| SDR++ module | Port | Used for |
|---|---|---|
| Rigctl Server | localhost:4532 | tuning the Radio VFO, mode/bandwidth, start/stop, triggering the centre probe |
| IQ Exporter (Baseband, TCP server, Float32) | localhost:4533 | live wideband IQ for spectrum, analysis and demodulation |
| Recorder "Center Probe" (baseband) | – | rigctl only reports the VFO, so a ~0.1 s baseband recording's filename reveals the true centre frequency; the file is then deleted |

`setup_sdrpp.py` configures all three. Run it with SDR++ **closed**. It backs up each changed
file next to the original as `*.json.bak-<time>`.

## Install

Requires Python ≥ 3.10 and SDR++ 1.2+ (nightly builds include the IQ Exporter).

```sh
git clone https://github.com/entitledosprey/sdrpp-mcp.git
cd sdrpp-mcp
python3 -m venv .venv && .venv/bin/pip install -e .
python3 setup_sdrpp.py            # with SDR++ closed
sudo apt install multimon-ng rtl-433   # optional decoders
```

Register the server with your MCP client as a stdio server, for example:

```json
{
  "mcpServers": {
    "sdrpp": { "command": "/path/to/sdrpp-mcp/.venv/bin/sdrpp-mcp" }
  }
}
```

### Skill

`skill/sdr-signal-id/` is an Agent Skill (`SKILL.md` plus `references/`). To install it, copy or symlink the
directory into your client's skills folder:

```sh
ln -s "$PWD/skill/sdr-signal-id" ~/.config/<client>/skills/sdr-signal-id
```

## Tools

| Tool | Purpose |
|---|---|
| `sdr_status` | SDR++ running? rigctl/IQ reachable, centre, rate, gain, clipping, installed decoders |
| `sdr_launch` | start SDR++ (optionally with `--autostart`) |
| `sdr_tune` | set VFO frequency, mode, bandwidth |
| `sdr_power` | start/stop the source |
| `spectrum_snapshot` | detect signals in the current passband, returns a waterfall image |
| `band_sweep` | sweep `start`–`stop`, merge detections, restore the VFO |
| `identify_frequency` | band plan allocation and known channels near a frequency |
| `analyze_signal` | measure and classify one signal, with a zoomed waterfall |
| `record_audio` | demodulate to WAV |
| `record_iq` | save raw IQ (`cu8`/`cf32`) |
| `decode` | run multimon-ng or rtl_433 on a capture |
| `log_signal` / `search_log` / `delete_log_entry` | logbook |
| `export_bookmarks` | write the logbook to SDR++'s Frequency Manager (SDR++ must be closed) |

Frequencies accept Hz or strings such as `146.52M`, `433.92 MHz` or `1090m`. Bare numbers below 10000
are treated as MHz.

## Data locations

Everything lives under `~/.local/share/sdrpp-mcp/`:

- `captures/`: WAV, IQ and PNG files
- `center-probe/`: temporary probe files
- `logbook.db`: the logbook

## Frequency calibration

RTL-SDR crystals are typically off by somewhere between 0 and 50 ppm, and TCXO models by about 1 ppm. A good local reference
is the ATSC digital TV pilot: an unmodulated carrier at the channel's lower edge plus 309.441 kHz.
Measure the apparent offset of a few strong pilots. The correction is
`ppm = (true − measured) / true × 10⁶`. Enter it, rounded, under **Source → PPM Correction** in
SDR++.

## Legal

The software is for receiving only. In the US, 47 USC 605 and ECPA restrict divulging or using the contents of
private communications. Decoding cellular or cordless-phone content and decrypting anything are both off limits. Know
your local rules.

## License

MIT. See [LICENSE](LICENSE).
