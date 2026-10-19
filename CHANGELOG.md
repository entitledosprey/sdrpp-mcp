# Changelog

## 2026-10-19

### Added
- `p25_status` and `p25_calls` tools for the companion sdrpp-p25 trunking module (decoder API +
  event log), and a guard that stops retuning tools while that module owns the tuning.

## 2026-10-18

### Added
- `watch_channel`: continuous listening on one channel (up to 15 min) with per-burst time,
  duration and SNR; LoRa detection by dechirping (reports SF); LoRa demodulation via
  gr-lora_sdr (`lora_gr.py`, run under the system python3); MeshCore packet parsing
  (`meshcore.py`): route, hop path, payload type, and adverts with node name, type and
  position. Message bodies stay encrypted. First live run: 27 of 27 packets CRC-valid.
- `sdrpp.IQStream`: background-thread reader on one IQ Exporter connection, so watching
  reaches ~99% coverage (was ~66% with reconnect-per-chunk).
- `tools/sdrtrunk_to_sdrpp.py`: SDRTrunk playlist → SDR++ Frequency Manager import files.
- Configurable folders: `SDRPP_MCP_DATA` (data root, also used by `setup_sdrpp.py` for the
  probe recorder) and `SDRPP_MCP_IMAGES`; images now default to `images/`.

### Fixed
- Watch image now shows the first 40 ms of the burst, so LoRa chirps are visible instead of
  being averaged into a block; colour scale follows the burst peak for strong signals.
- Packets that cross a capture-chunk boundary are carried over instead of being split, and
  the channel mixer keeps a continuous phase across chunks.

## 2026-10-17

### Added
- MCP server for SDR++ (rigctl + IQ Exporter + "Center Probe" recorder for the true centre
  frequency): status, launch, tune, power, spectrum snapshot, band sweep, frequency
  identification, signal analysis and classification, audio/IQ recording, multimon-ng and
  rtl_433 decoding, SQLite logbook with Frequency Manager export.
- `sdr-signal-id` skill with signal catalog, decoder and hardware references.
- MIT license.

### Fixed
- Tools that retune SDR++ to reach a frequency (analysis, recording, decoding) now restore the
  Radio VFO afterwards.
- Retuning lands exactly on the requested centre: SDR++ recentres ~885 kHz off target after an
  out-of-view jump; `_tune_center` approaches from below and learns that offset. Before this,
  a 2 m sweep silently skipped 145.0–145.9 MHz.
- `band_sweep` reports `not_covered` ranges instead of silently leaving gaps.

### Learned
- Frequency calibration against ATSC pilots works well (13 strong pilots agreed within
  ±0.15 ppm); broadcast FM carriers are too noisy for it.
- On the E4000 dongle, steady carriers at multiples of 2.4 MHz and families spaced 4.8/9.6 MHz
  are receiver spurs; they disappear when the centre frequency changes.
