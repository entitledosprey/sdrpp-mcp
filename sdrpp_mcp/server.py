"""MCP server: control SDR++ and find, analyse, decode and log transmissions."""

import os
import re
import shutil
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

import numpy as np
from mcp.server.fastmcp import FastMCP, Image
from scipy.io import wavfile

from . import bandplan, dsp, plots, sdrpp
from .logbook import Logbook

DATA = Path(os.environ.get("SDRPP_MCP_DATA", Path.home() / ".local/share/sdrpp-mcp"))
CAPTURES = DATA / "captures"
CAPTURES.mkdir(parents=True, exist_ok=True)
EDGE_FRACTION = 0.1   # ignore this fraction of the band at each edge (filter roll-off)
DC_MASK_HZ = 12000    # ignore +/- this around the centre (zero-IF DC spike)

mcp = FastMCP(
    "sdrpp",
    instructions=(
        "Controls a running SDR++ instance (via its Rigctl Server and IQ Exporter modules) "
        "to find, identify, decode and log radio transmissions. Frequencies accept Hz or "
        "strings like '146.52M', '433.92 MHz', '1090m', '27.185 MHz'. Bare numbers below "
        "10000 are treated as MHz. Start with sdr_status. Load the sdr-signal-id skill for the "
        "identification workflow and reference material."
    ),
)
log = Logbook(DATA / "logbook.db")


# ---------------------------------------------------------------- helpers


def parse_freq(v) -> float:
    if isinstance(v, (int, float)):
        x = float(v)
        return x * 1e6 if x < 1e4 else x
    s = str(v).strip().lower().replace(",", "").replace(" ", "")
    m = re.fullmatch(r"([0-9]*\.?[0-9]+)(g|ghz|m|mhz|k|khz|hz)?", s)
    if not m:
        raise ValueError(f"cannot parse frequency {v!r}")
    x, unit = float(m.group(1)), m.group(2)
    mult = {"g": 1e9, "ghz": 1e9, "m": 1e6, "mhz": 1e6, "k": 1e3, "khz": 1e3, "hz": 1.0}.get(unit or "")
    if mult is None:
        mult = 1e6 if x < 1e4 else 1.0
    return x * mult


def fmt(hz: float) -> str:
    return f"{hz/1e6:.5f} MHz"


def _stamp(freq_hz, kind, ext):
    return CAPTURES / f"{time.strftime('%Y%m%d-%H%M%S')}_{freq_hz/1e6:.4f}MHz_{kind}.{ext}"


def _state_or_fail(fresh: bool = False):
    if not sdrpp.is_running():
        raise sdrpp.SdrppError("SDR++ is not running. Use sdr_launch or start it yourself.")
    st = sdrpp.radio_state()
    if not st["sample_rate"]:
        raise sdrpp.SdrppError(f"Could not determine sample rate for source {st['source']!r} from SDR++ config.")
    st["center_hz"] = sdrpp.live_center(sdrpp.Rigctl(), use_cache=not fresh)
    return st


def _usable(st):
    half = st["sample_rate"] * (0.5 - EDGE_FRACTION)
    return st["center_hz"] - half, st["center_hz"] + half


def _in_band(st, freq_hz, margin_hz=0.0):
    lo, hi = _usable(st)
    return lo + margin_hz <= freq_hz <= hi - margin_hz and abs(freq_hz - st["center_hz"]) > DC_MASK_HZ + margin_hz


def _ensure_in_band(freq_hz: float, margin_hz: float = 0.0):
    """Make sure freq is inside the usable passband; retune SDR++ if needed."""
    st = _state_or_fail()
    if _in_band(st, freq_hz, margin_hz):
        return st, False
    # sit the signal a fifth of the bandwidth off centre, away from the DC spike
    st = _tune_center(freq_hz + st["sample_rate"] * 0.2)
    if not _in_band(st, freq_hz, margin_hz):
        raise sdrpp.SdrppError(f"Could not bring {fmt(freq_hz)} into the passband (centre {fmt(st['center_hz'])}).")
    return st, True


def _tune_center(target_hz: float):
    """Retune SDR++ so its centre frequency is near target, via the Radio VFO.

    The rigctl server uses SDR++'s normal tuning: a VFO jump outside the view recentres the
    SDR with the VFO near the edge it came in from, a small jump only moves the VFO. So
    approach from below, measure where the VFO landed relative to the centre, then repeat
    the approach with the VFO pre-offset by that amount.
    """
    global _approach_offset
    rig = sdrpp.Rigctl()
    st = sdrpp.radio_state()
    fs = st["sample_rate"] or 2.4e6
    tol = fs * 0.05
    vfo = target_hz + _approach_offset
    for _ in range(4):
        rig.set_freq(vfo - 4 * fs)
        time.sleep(0.15)
        rig.set_freq(vfo)
        time.sleep(0.25)  # tuner settle + buffer flush
        st = _state_or_fail(fresh=True)
        if abs(st["center_hz"] - target_hz) <= tol:
            break
        vfo += target_hz - st["center_hz"]
    _approach_offset = vfo - st["center_hz"]
    return st


_approach_offset = 0.0  # VFO minus centre after SDR++ recentres on an upward jump


@contextmanager
def _keep_vfo():
    """Put the user's Radio VFO back if the body retuned SDR++ to reach another frequency."""
    rig = sdrpp.Rigctl()
    original = rig.get_freq()
    try:
        yield
    finally:
        if rig.get_freq() != original:
            rig.set_freq(original)


def _capture(seconds):
    st = _state_or_fail()
    iq, measured = sdrpp.capture_iq(seconds, st["sample_rate"])
    if len(iq) < 1024:
        raise sdrpp.SdrppError("captured too few samples")
    return st, iq, measured


def _band_exclusions(f, fs):
    edge = fs * (0.5 - EDGE_FRACTION)
    return [(f[0], -edge), (edge, f[-1]), (-DC_MASK_HZ, DC_MASK_HZ)]


def _detections_to_rows(dets, center, top):
    rows = []
    for d in dets[:top]:
        fa = center + d["offset_hz"]
        rows.append({
            "freq_mhz": round(fa / 1e6, 5),
            "width_khz": round(d["width_hz"] / 1e3, 2),
            "peak_snr_db": round(d["peak_snr_db"], 1),
            "avg_snr_db": round(d["avg_snr_db"], 1),
            "duty": d["duty"],
            "band_hint": bandplan.short_label(fa),
        })
    return rows


# ---------------------------------------------------------------- tools: control


@mcp.tool()
def sdr_status() -> dict:
    """Report SDR++ state: running, centre/VFO frequency, mode, source, gain, sample rate,
    whether rigctl and the IQ Exporter are reachable, and which decoders are installed."""
    out = {"sdrpp_running": sdrpp.is_running()}
    st = sdrpp.radio_state()
    out.update({
        "center": fmt(st["center_hz"]),
        "source": st["source"],
        "device": st["device"],
        "sample_rate": st["sample_rate"],
        "gain_settings": st["gain"],
        "audio_sink": (st["streams"].get("Radio") or {}).get("sink"),
    })
    try:
        rig = sdrpp.Rigctl()
        out["vfo"] = fmt(rig.get_freq())
        out["mode"], out["vfo_bandwidth_hz"] = rig.get_mode()
        out["rigctl"] = "ok"
    except sdrpp.SdrppError as e:
        out["rigctl"] = str(e)
    iqc = sdrpp.iq_config()
    out["iq_exporter_config"] = iqc or "missing (run setup_sdrpp.py with SDR++ closed)"
    if out["sdrpp_running"] and iqc and st["sample_rate"]:
        try:
            iq, measured = sdrpp.capture_iq(0.2, st["sample_rate"])
            out["iq_exporter"] = f"ok ({len(iq)} samples, rms {float(np.sqrt(np.mean(np.abs(iq)**2))):.4f})"
            clip = float(np.mean((np.abs(iq.real) > 0.98) | (np.abs(iq.imag) > 0.98)))
            if clip > 0.001:
                out["warning"] = f"ADC clipping in {clip:.1%} of samples: reduce gain"
        except sdrpp.SdrppError as e:
            out["iq_exporter"] = str(e)
    out["decoders"] = {t: bool(shutil.which(t)) for t in ("multimon-ng", "rtl_433", "sox", "direwolf", "acarsdec", "dumpvdl2")}
    out["captures_dir"] = str(CAPTURES)
    return out


@mcp.tool()
def sdr_launch(autostart: bool = True) -> str:
    """Start SDR++ if it isn't running (autostart=True also starts the SDR source)."""
    return sdrpp.launch(autostart)


@mcp.tool()
def sdr_tune(frequency: str, mode: str | None = None, bandwidth_hz: float | None = None) -> dict:
    """Tune SDR++'s Radio VFO so the user hears the frequency. mode: FM (=NFM), WFM, AM, DSB,
    USB, LSB, CW, RAW. bandwidth_hz optional (e.g. 12500 NFM, 200000 WFM, 10000 AM, 2700 SSB)."""
    hz = parse_freq(frequency)
    rig = sdrpp.Rigctl()
    if mode:
        rig.set_mode(mode, bandwidth_hz)
    rig.set_freq(hz)
    time.sleep(0.3)
    m, bw = rig.get_mode()
    return {"vfo": fmt(rig.get_freq()), "mode": m, "bandwidth_hz": bw,
            "band": bandplan.lookup(hz, 25)}


@mcp.tool()
def sdr_power(on: bool) -> str:
    """Start (on=True) or stop the SDR source in SDR++ (the play/stop button)."""
    rig = sdrpp.Rigctl()
    return rig.start() if on else rig.stop()


# ---------------------------------------------------------------- tools: finding


@mcp.tool()
def spectrum_snapshot(seconds: float = 1.0, threshold_db: float = 8.0, fft_size: int = 8192,
                      top: int = 25, frequency: str | None = None) -> list:
    """Capture the full SDR++ passband, detect signals (max-hold, so short bursts count) and
    return a table plus a spectrum/waterfall image. Optionally retune to `frequency` first.
    duty = fraction of time the signal was present (1.0 = continuous)."""
    if frequency:
        _tune_center(parse_freq(frequency))
    st, iq, measured = _capture(seconds)
    fs, c = st["sample_rate"], st["center_hz"]
    f, t, s = dsp.spectrogram(iq, fs, fft_size)
    dets, floor = dsp.detect(f, s, threshold_db, exclude=_band_exclusions(f, fs))
    rows = _detections_to_rows(dets, c, top)
    png = _stamp(c, "snapshot", "png")
    plots.waterfall(png, f + c, t, s, floor,
                    f"SDR++ passband {fmt(c)} ± {fs/2e6:.2f} MHz, {seconds:g}s",
                    marks=[(r["freq_mhz"] * 1e6, f"{r['freq_mhz']:.4f}") for r in rows[:12]])
    summary = {
        "center": fmt(c), "sample_rate": fs, "measured_rate": round(measured),
        "bin_hz": round(f[1] - f[0], 1), "noise_floor_db": round(floor, 1),
        "signals": rows, "image": str(png),
        "note": "Band edges and ±12 kHz around centre are masked. Narrow steady carriers at round "
                "MHz multiples are often RTL-SDR spurs.",
    }
    return [summary, Image(path=str(png))]


@mcp.tool()
def band_sweep(start: str, stop: str, dwell_s: float = 0.5, threshold_db: float = 8.0,
               fft_size: int = 4096, top: int = 60) -> list:
    """Sweep a frequency range wider than the SDR's bandwidth by retuning SDR++ in steps.
    Returns detected signals across the range plus a combined spectrum image.
    Note: this moves the user's SDR++ view; the original VFO frequency is restored afterwards."""
    lo_hz, hi_hz = sorted((parse_freq(start), parse_freq(stop)))
    st = _state_or_fail()
    fs = st["sample_rate"]
    usable = fs * (1 - 2 * EDGE_FRACTION)
    rig = sdrpp.Rigctl()
    original = rig.get_freq()
    steps = int(np.ceil((hi_hz - lo_hz) / usable)) or 1
    if steps > 200:
        raise ValueError(f"{steps} steps needed; narrow the range (usable {usable/1e6:.2f} MHz per step)")
    all_f, all_avg, all_max, found = [], [], [], []
    floors, covered = [], []
    try:
        for i in range(steps):
            target = lo_hz + usable * (i + 0.5)
            st = _tune_center(target)
            iq, _ = sdrpp.capture_iq(dwell_s, fs)
            c = st["center_hz"]
            covered.append((c - usable / 2, c + usable / 2))
            f, t, s = dsp.spectrogram(iq, fs, fft_size)
            dets, floor = dsp.detect(f, s, threshold_db, exclude=_band_exclusions(f, fs))
            floors.append(floor)
            keep = (np.abs(f) <= usable / 2) & (np.abs(f) > DC_MASK_HZ)
            all_f.append(f[keep] + c)
            all_avg.append(dsp.db(s.mean(axis=0))[keep])
            all_max.append(dsp.db(s.max(axis=0))[keep])
            for d in dets:
                fa = c + d["offset_hz"]
                if lo_hz <= fa <= hi_hz:
                    found.append((fa, d))
    finally:
        try:
            rig.set_freq(original)
        except sdrpp.SdrppError:
            pass
    fa = np.concatenate(all_f)
    order = np.argsort(fa)
    floor = float(np.median(floors))
    # merge duplicates from overlapping steps
    found.sort(key=lambda x: x[0])
    merged = []
    for fabs, d in found:
        if merged and abs(fabs - merged[-1][0]) < max(5e3, d["width_hz"] / 2):
            if d["peak_snr_db"] > merged[-1][1]["peak_snr_db"]:
                merged[-1] = (fabs, d)
        else:
            merged.append((fabs, d))
    merged.sort(key=lambda x: -x[1]["peak_snr_db"])
    rows = []
    for fabs, d in merged[:top]:
        rows.append({"freq_mhz": round(fabs / 1e6, 5), "width_khz": round(d["width_hz"] / 1e3, 2),
                     "peak_snr_db": round(d["peak_snr_db"], 1), "duty": d["duty"],
                     "band_hint": bandplan.short_label(fabs)})
    gaps, edge = [], lo_hz
    for a, b in sorted(covered):
        if a > edge + 1e3:
            gaps.append(f"{fmt(edge)} – {fmt(min(a, hi_hz))}")
        edge = max(edge, b)
    if edge < hi_hz - 1e3:
        gaps.append(f"{fmt(edge)} – {fmt(hi_hz)}")
    png = _stamp(lo_hz, "sweep", "png")
    plots.sweep_plot(png, fa[order], np.concatenate(all_avg)[order], np.concatenate(all_max)[order],
                     floor, f"Sweep {fmt(lo_hz)} – {fmt(hi_hz)}, {steps} steps × {dwell_s:g}s",
                     marks=[(r["freq_mhz"] * 1e6, f"{r['freq_mhz']:.3f}") for r in rows[:25]])
    return [{"range": f"{fmt(lo_hz)} – {fmt(hi_hz)}", "steps": steps, "signals": rows,
             "image": str(png), "restored_vfo": fmt(original),
             **({"not_covered": gaps} if gaps else {})}, Image(path=str(png))]


# ---------------------------------------------------------------- tools: identifying


@mcp.tool()
def identify_frequency(frequency: str, window_khz: float = 50.0) -> dict:
    """Band-plan lookup (US/FCC, ITU Region 2): which allocation a frequency falls in and
    which well-known channels/services are nearby. No radio access needed."""
    return bandplan.lookup(parse_freq(frequency), window_khz)


@mcp.tool()
def analyze_signal(frequency: str, bandwidth_hz: float | None = None, seconds: float = 2.0,
                   tune_vfo: bool = False) -> list:
    """Measure a signal's characteristics to help identify it: occupied bandwidth, carrier,
    envelope constancy, FM deviation, FSK levels, symbol rate, burst timing, TDMA periodicity,
    CTCSS / audio tones (for FM/AM), stereo pilot/RDS (WFM). Returns heuristic modulation guesses,
    band-plan context and a zoomed waterfall image. If bandwidth_hz is omitted it is estimated.
    If SDR++ has to retune to reach the signal, the original VFO is restored afterwards, unless
    tune_vfo=True, which leaves the Radio VFO on the signal so the user can listen."""
    if tune_vfo:
        return _analyze(frequency, bandwidth_hz, seconds, tune_vfo)
    with _keep_vfo():
        return _analyze(frequency, bandwidth_hz, seconds, tune_vfo)


def _analyze(frequency, bandwidth_hz, seconds, tune_vfo):
    hz = parse_freq(frequency)
    st, retuned = _ensure_in_band(hz, margin_hz=(bandwidth_hz or 0) / 2)
    for attempt in range(2):
        st, iq, _ = _capture(seconds)
        fs, c = st["sample_rate"], st["center_hz"]
        off = hz - c
        if abs(off) > fs * (0.5 - EDGE_FRACTION):
            raise sdrpp.SdrppError(f"{fmt(hz)} is outside the current passband ({fmt(c)} ± {fs/2e6:.2f} MHz)")

        # wideband view for noise floor + auto bandwidth
        f, t, s = dsp.spectrogram(iq, fs, 8192)
        dets, floor = dsp.detect(f, s, 6.0, exclude=[(-DC_MASK_HZ, DC_MASK_HZ)])
        near = [d for d in dets if abs(d["offset_hz"] - off) < d["width_hz"] / 2 + 5e3]
        est = None
        if near:
            best = max(near, key=lambda d: d["peak_snr_db"])
            est = best["width_hz"]
            if bandwidth_hz is None:
                off = best["offset_hz"]  # recentre on the detected signal
        # weak signals only show their core above the noise; give voice-width room unless
        # it's clearly a narrow carrier
        floor_bw = 10000.0 if (est or 12500.0) > 1500 else 3000.0
        bw = float(bandwidth_hz or max(floor_bw, (est or 12500.0) * 1.25))
        bw = min(bw, fs * 0.5)
        clear_of_dc = abs(off) - bw / 2 > DC_MASK_HZ
        inside = abs(off) + bw / 2 < fs * (0.5 - EDGE_FRACTION)
        if (clear_of_dc and inside) or attempt:
            break
        # the channel overlaps the DC spike or a band edge: put it a quarter-band off centre
        _tune_center(c + off + fs * 0.25)
        hz, retuned = c + off, True
    x, rate = dsp.extract(iq, fs, off, bw)
    binw = f[1] - f[0]
    noise_density = 10 ** (floor / 10)
    noise_power = noise_density * bw  # per-Hz density × channel width
    feat = dsp.features(x, rate, noise_power, est or bw)
    guesses = dsp.classify(feat, bw)

    extra = {}
    obw = feat.get("occupied_bw_99_hz", bw)
    if any("Wideband FM" in g["guess"] for g in guesses):
        extra["wfm"] = dsp.stereo_rds(x, rate)
    if feat.get("envelope_cv") is not None and obw < 30e3:
        mode = "AM" if any(g["guess"].startswith("AM") for g in guesses) else "FM"
        try:
            audio = dsp.demod(x, rate, mode, 22050)
            extra["audio"] = {"demod": mode, **dsp.audio_analysis(audio, 22050)}
        except Exception as e:  # analysis is best-effort
            extra["audio"] = {"error": str(e)}

    # zoomed waterfall around the signal
    zf, zt, zs = dsp.spectrogram(x, rate, int(2 ** np.ceil(np.log2(max(256, rate / max(bw / 200, 1))))))
    keep = np.abs(zf) <= bw * 0.55  # drop the filter skirts
    zf, zs = zf[keep], zs[:, keep]
    zfloor = dsp.noise_floor_db(dsp.db(zs.mean(axis=0)))
    png = _stamp(c + off, "analysis", "png")
    plots.waterfall(png, zf + c + off, zt, zs, zfloor,
                    f"{fmt(c + off)} — channel {bw/1e3:.1f} kHz, {seconds:g}s", dyn=40)
    result = {
        "frequency": fmt(c + off),
        "requested": fmt(hz),
        "retuned_sdrpp": retuned,
        "detected_width_hz": round(est, 1) if est else None,
        "analysis_bandwidth_hz": round(bw, 1),
        "features": feat,
        "modulation_guesses": guesses,
        **extra,
        "band_plan": bandplan.lookup(c + off, 25),
        "image": str(png),
        "bin_hz_wideband": round(binw, 1),
    }
    if tune_vfo:
        # after measuring: with centre tuning on, the VFO lands on the DC spike
        sdrpp.Rigctl().set_freq(c + off)
        result["vfo_tuned"] = fmt(c + off)
    return [result, Image(path=str(png))]


# ---------------------------------------------------------------- tools: recording & decoding


def _channel(hz, bw, seconds, out_rate=None):
    with _keep_vfo():
        st, _ = _ensure_in_band(hz, margin_hz=bw / 2)
        st, iq, _ = _capture(seconds)
    x, rate = dsp.extract(iq, st["sample_rate"], hz - st["center_hz"], bw, out_rate)
    return x, rate


DEFAULT_BW = {"FM": 12500, "NFM": 12500, "WFM": 200000, "AM": 10000, "DSB": 10000,
              "USB": 3000, "LSB": 3000, "CW": 500}


@mcp.tool()
def record_audio(frequency: str, mode: str = "FM", seconds: float = 10.0,
                 bandwidth_hz: float | None = None, audio_rate: int = 22050) -> dict:
    """Demodulate a frequency from the live IQ stream and save a WAV (independent of SDR++'s own
    audio, so the user can keep listening elsewhere). mode: FM/NFM, WFM, AM, USB, LSB, CW."""
    hz = parse_freq(frequency)
    mode = mode.upper()
    bw = bandwidth_hz or DEFAULT_BW.get(mode, 12500)
    x, rate = _channel(hz, max(bw * 1.2, bw + 2000), seconds)
    audio = dsp.demod(x, rate, mode, audio_rate)
    path = _stamp(hz, f"audio-{mode}", "wav")
    wavfile.write(path, audio_rate, (audio * 32767).astype(np.int16))
    return {"file": str(path), "seconds": round(len(audio) / audio_rate, 2), "rate": audio_rate,
            "analysis": dsp.audio_analysis(audio, audio_rate),
            "play": f"aplay {path}  (or ffplay -nodisp -autoexit {path})"}


@mcp.tool()
def record_iq(frequency: str, bandwidth_hz: float = 250000, seconds: float = 5.0,
              fmt_: str = "cu8") -> dict:
    """Save channelised IQ around a frequency. fmt_: 'cu8' (rtl_433 / most tools, 8-bit unsigned)
    or 'cf32' (float32 complex). The output sample rate is chosen as exactly bandwidth_hz
    (250 kS/s default suits rtl_433). The filename carries freq and rate."""
    hz = parse_freq(frequency)
    rate_target = float(bandwidth_hz)
    x, rate = _channel(hz, bandwidth_hz * 0.9, seconds, out_rate=rate_target)
    tag = f"{int(rate/1000)}k"
    path = CAPTURES / f"{time.strftime('%Y%m%d-%H%M%S')}_{hz/1e6:.3f}M_{tag}.{fmt_}"
    if fmt_ == "cu8":
        peak = np.percentile(np.abs(np.concatenate([x.real, x.imag])), 99.9) or 1
        y = np.empty(2 * len(x), np.float32)
        y[0::2], y[1::2] = x.real / peak, x.imag / peak
        np.clip(y * 120 + 127.5, 0, 255).astype(np.uint8).tofile(path)
    elif fmt_ == "cf32":
        x.astype(np.complex64).tofile(path)
    else:
        raise ValueError("fmt_ must be cu8 or cf32")
    return {"file": str(path), "sample_rate": rate, "center_hz": hz, "format": fmt_,
            "samples": len(x)}


MULTIMON_DEMODS = {
    "pager": ["POCSAG512", "POCSAG1200", "POCSAG2400", "FLEX"],
    "pocsag": ["POCSAG512", "POCSAG1200", "POCSAG2400"],
    "flex": ["FLEX"],
    "aprs": ["AFSK1200"],
    "afsk1200": ["AFSK1200"],
    "eas": ["EAS"],
    "same": ["EAS"],
    "dtmf": ["DTMF"],
    "zvei": ["ZVEI1", "ZVEI2", "ZVEI3"],
    "morse": ["MORSE_CW"],
    "x10": ["X10"],
}


@mcp.tool()
def decode(frequency: str, decoder: str, seconds: float = 30.0, bandwidth_hz: float | None = None) -> dict:
    """Capture and decode digital transmissions. decoder:
    - multimon-ng (FM-demodulated audio): pager (POCSAG+FLEX), pocsag, flex, aprs, eas/same, dtmf, zvei, morse
    - rtl_433: ism (433/315/345/915 MHz sensors, remotes, TPMS, meters) -- run on captured IQ
    Long captures block for `seconds`. Privacy: pager and similar traffic can contain personal
    information; summarise rather than repeat sensitive content."""
    hz = parse_freq(frequency)
    decoder = decoder.lower()
    if decoder in ("ism", "rtl_433", "rtl433"):
        exe = shutil.which("rtl_433")
        if not exe:
            return {"error": "rtl_433 not installed. Install with: sudo apt install rtl-433"}
        rec = record_iq(frequency, bandwidth_hz or 250000, seconds, "cu8")
        p = subprocess.run([exe, "-r", f"cu8:{rec['file']}", "-s", str(int(rec["sample_rate"])),
                            "-f", str(int(hz)), "-F", "json", "-M", "level"],
                           capture_output=True, text=True, timeout=120)
        lines = [l for l in p.stdout.splitlines() if l.startswith("{")]
        return {"decoder": "rtl_433", "iq_file": rec["file"], "messages": lines[:200],
                "count": len(lines), "stderr_tail": p.stderr[-800:] if not lines else ""}
    demods = MULTIMON_DEMODS.get(decoder)
    if not demods:
        return {"error": f"unknown decoder {decoder!r}", "available": sorted(MULTIMON_DEMODS) + ["ism"]}
    exe = shutil.which("multimon-ng")
    if not exe:
        return {"error": "multimon-ng not installed. Install with: sudo apt install multimon-ng"}
    bw = bandwidth_hz or (16000 if decoder in ("pager", "pocsag", "flex") else 12500)
    x, rate = _channel(hz, bw, seconds)
    mode = "CW" if decoder == "morse" else "FM"
    audio = dsp.demod(x, rate, mode, 22050)
    raw = (audio * 32767).astype("<i2").tobytes()
    wav = _stamp(hz, f"decode-{decoder}", "wav")
    wavfile.write(wav, 22050, (audio * 32767).astype(np.int16))
    args = [exe, "-t", "raw", "-q"]
    for d in demods:
        args += ["-a", d]
    if decoder in ("pager", "pocsag", "flex"):
        args += ["-e", "-u"]
    args.append("-")
    p = subprocess.run(args, input=raw, capture_output=True, timeout=120)
    out = [l for l in p.stdout.decode(errors="replace").splitlines() if l.strip()]
    return {"decoder": f"multimon-ng {' '.join(demods)}", "audio_file": str(wav),
            "lines": out[:300], "count": len(out),
            "hint": "" if out else "Nothing decoded: check SNR with analyze_signal, try a longer capture, or "
                                   "inverting (pager FSK polarity varies: decoder handles both for POCSAG)."}


# ---------------------------------------------------------------- tools: logbook


@mcp.tool()
def log_signal(frequency: str, label: str, mode: str | None = None, bandwidth_hz: float | None = None,
               identification: str | None = None, confidence: str | None = None,
               notes: str | None = None, files: list[str] | None = None) -> dict:
    """Save an identified (or mystery) signal to the logbook. confidence: confirmed/likely/guess."""
    i = log.add(parse_freq(frequency), label, mode, bandwidth_hz, identification, confidence, notes, files)
    return {"id": i, "saved": label}


@mcp.tool()
def search_log(text: str | None = None, start: str | None = None, stop: str | None = None,
               limit: int = 50) -> list[dict]:
    """Search the logbook by text and/or frequency range."""
    return log.search(text, parse_freq(start) if start else None, parse_freq(stop) if stop else None, limit)


@mcp.tool()
def delete_log_entry(entry_id: int) -> bool:
    """Delete a logbook entry by id."""
    return log.delete(entry_id)


@mcp.tool()
def export_bookmarks(list_name: str = "SDR Log") -> str:
    """Write the logbook into SDR++'s Frequency Manager as a bookmark list (shown on the
    waterfall). SDR++ must be closed; a backup of the old bookmarks file is kept."""
    n = log.export_bookmarks(list_name)
    return f"Wrote {n} bookmarks to list {list_name!r}. Start SDR++ and select it in Frequency Manager."


def main():
    mcp.run()


if __name__ == "__main__":
    main()
