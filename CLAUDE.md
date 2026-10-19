# Development notes

## Layout

- `sdrpp_mcp/server.py`: FastMCP server and tool definitions; frequency parsing, tuning
  and passband helpers (`_in_band`, `_ensure_in_band`, `_tune_center`).
- `sdrpp_mcp/sdrpp.py`: SDR++ integration: config reading, `Rigctl` client, `live_center`
  (centre-probe trick), `capture_iq` (one-shot IQ Exporter read), `IQStream` (background
  thread, continuous chunks), `launch`.
- `sdrpp_mcp/dsp.py`: numpy/scipy DSP: spectrogram, noise floor, detection, channel
  extraction, demodulators, feature measurement, `classify`, audio/tone and stereo/RDS checks.
- `sdrpp_mcp/plots.py`: matplotlib (Agg) waterfall and sweep images.
- `sdrpp_mcp/bandplan.py`: US allocations (`ALLOCATIONS`) and named channels (`NOTABLE`).
- `sdrpp_mcp/meshcore.py`: MeshCore packet parser (cleartext fields only).
- `sdrpp_mcp/lora_gr.py`: standalone gr-lora_sdr flowgraph; runs under the **system**
  `/usr/bin/python3` (GNU Radio isn't in the venv), reads a cf32 file, prints JSON per frame.
- `sdrpp_mcp/p25.py`: read-only client for the sdrpp-p25 module's decoder API (port from
  `p25_trunking_config.json`, default 9911) and event log; `owns_tuning()` backs the retune guard.
- `sdrpp_mcp/logbook.py`: SQLite logbook and SDR++ Frequency Manager export.
- `setup_sdrpp.py`: one-off SDR++ configuration (run with SDR++ closed; honours `SDRPP_MCP_DATA`).
- `tools/sdrtrunk_to_sdrpp.py`: SDRTrunk playlist → SDR++ Frequency Manager import files.
- `CHANGELOG.md`: what changed and why, by date.
- `skill/sdr-signal-id/`: the companion skill (`SKILL.md` + `references/`).

## Commands

```sh
python3 -m venv .venv && .venv/bin/pip install -e .   # install (editable)
.venv/bin/sdrpp-mcp                                   # run the stdio server
.venv/bin/python -c "import sdrpp_mcp.server"         # quick import check
```

There is no test suite. Test DSP changes against synthetic signals (NFM tone, WFM, AM, USB,
OOK, 2-FSK at known SNR) and, when hardware is available, against live references such as
broadcast FM, NOAA Weather Radio, or ATSC pilots for frequency accuracy. For the LoRa path,
generate packets with gr-lora_sdr's own TX blocks (whitening → header → add_crc →
hamming_enc → interleaver → gray_demap → modulate, sync word 0x12) into a cf32 file, add CFO
and noise, and run `lora_gr.py` on it; a CRC-valid frame proves the chain.

The server is a long-lived process: reconnect the MCP client after code changes. Short
offline checks can call module functions directly; real runs should go through the tools.

## Configuration

Environment variables (set in the MCP client's server entry):

- `SDRPP_MCP_DATA`: data root (default `~/.local/share/sdrpp-mcp`): `images/`, `captures/`,
  `center-probe/`, `logbook.db`. If changed, rerun `setup_sdrpp.py` with the same value (SDR++
  closed) so the Center Probe recorder writes to the new `center-probe/`; otherwise tuning breaks.
- `SDRPP_MCP_IMAGES`: PNG folder override (default `$SDRPP_MCP_DATA/images`).
- `SDRPP_IQ_INSTANCE`: IQ Exporter instance name (default "IQ Exporter").

## Constraints and gotchas

- **`mcp<2`**: the code uses `mcp.server.fastmcp.FastMCP`, which 2.x renamed.
- **SDR++ config value types**: IQ Exporter and recorder options are stored by *display name*
  (`"Baseband"`, `"TCP (Server)"`, `"Float32"`). The recorder `mode` must be an **int**
  (`0` = baseband); a string makes SDR++ crash at startup.
- **True centre frequency**: rigctl reports only the VFO, and SDR++ doesn't save `config.json`
  on rigctl retunes. `live_center()` triggers the "Center Probe" recorder and parses
  `_<hz>Hz_` from the filename. The result is cached for 30 s while the VFO is unchanged.
- **Tuning**: rigctl always uses SDR++'s normal tuning mode. A VFO jump outside the view
  recentres with the VFO near the edge it came in from (≈ −885 kHz from centre when jumping up
  at 2.4 MS/s); a small jump only moves the VFO. `_tune_center` always approaches from below
  (jump to target − 4·fs, then up), learns that offset in `_approach_offset`, and corrects until
  the live centre is within 5% of fs. Never assume where the centre landed: read it.
- **DC spike**: mask ±`DC_MASK_HZ` (12 kHz) around centre, and ignore the outer
  `EDGE_FRACTION` (10%) of the band. `analyze_signal` retunes if a channel overlaps either.
- **Memory**: keep captures short. Multi-second complex64 captures at 2.4 MS/s plus
  spectrograms add up quickly.
- **Frequency Manager export** refuses while SDR++ is running, because SDR++ overwrites its config on exit.
  Mode ids: NFM 0, WFM 1, AM 2, DSB 3, USB 4, CW 5, LSB 6, RAW 7.
- **Decoders**: multimon-ng takes raw s16le audio at 22050 Hz. rtl_433 takes `cu8` IQ at 250 kS/s
  (`-r cu8:<file> -s <rate> -f <hz> -F json -M level`).
- **P25 guard**: `_tune_center` and `sdr_tune` call `_p25_guard()`, which refuses while the
  sdrpp-p25 decoder reports a radio input. The module defends its tuning and would undo ours.
- **VFO restore**: tools that retune to reach a frequency wrap the work in `_keep_vfo()`
  (`analyze_signal` skips it when `tune_vfo=True`). `band_sweep` restores explicitly.
- **Sweep coverage**: `band_sweep` records each step's actual span and returns `not_covered`
  if any part of the range was missed.
- **Spurs seen on the reference hardware** (E4000, 2.4 MS/s): steady narrow carriers at exact
  multiples of 2.4 MHz, and families spaced exactly 4.8 or 9.6 MHz. They vanish or move when the
  centre changes, which is the quickest test.
- **IQStream**: one TCP connection, background thread, bounded queue (oldest chunk dropped
  and counted if the consumer falls behind). `capture_iq` reconnects per call and loses ~0.1 s.
- **watch_channel**: chunks are mixed with a continuous phase (`extract(..., n0=)`), and a burst
  still on air at a chunk end is carried into the next chunk, so packets aren't split. Output
  rate is 4x the channel bandwidth because gr-lora_sdr needs an integer oversampling factor.
  LoRa detection is `dsp.lora_check` (dechirp peak-to-mean; noise/FSK ≈ 8, LoRa ≫ 30).
  MeshCore: sync word 0x12, preamble 32 symbols at SF ≤ 8 (gr frame_sync is given 8 and
  still locks). Decoding runs after listening, one `lora_gr.py` subprocess per burst
  (~1 s each). The watch image shows only the first 40 ms so chirps aren't averaged away by
  the plot's row decimation (max 400 rows).

## Ideas not done yet

- `calibrate_ppm` tool: scan ATSC pilots (lower edge + 309.441 kHz) and report the PPM error
  (the manual method is in the README; a dongle here measured +0.72 ppm).
- Overnight / multi-hour MeshCore watch building a node and path map.
- `rtlamr` decoder for ERT utility meters (910–920 MHz).
- Tighten `classify` so a symbol-rate line is only reported well above the noise (it once
  called four 2 ms noise spikes "linear digital at 600 sym/s").
- Identify 900 MHz FHSS devices (6 ms 2-FSK beacons, ~528 kHz channel spacing).

## Conventions

- Tools return plain dicts and strings. Errors raise `sdrpp.SdrppError` with a short fix hint.
- Frequencies are Hz internally. `parse_freq` accepts suffixes, and bare numbers below 1e4 are MHz.
- Tools that move the user's SDR++ view should restore the VFO, or report that they retuned.
- Keep the skill's legal guardrails: receive only, no decryption, no cellular or cordless-phone content.
  Summarise private traffic rather than repeating it.
