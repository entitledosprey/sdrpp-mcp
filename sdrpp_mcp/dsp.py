"""Signal processing: spectrum, detection, channel extraction, demod, features."""

from fractions import Fraction

import numpy as np
from scipy import signal

COMMON_BAUDS = [
    45.45, 50, 75, 100, 110, 150, 300, 400, 512, 600, 1200, 1600, 2400, 3200, 3600,
    4800, 6250, 6400, 9600, 10500, 12500, 19200, 38400, 50000, 72000,
]

CTCSS = [
    67.0, 69.3, 71.9, 74.4, 77.0, 79.7, 82.5, 85.4, 88.5, 91.5, 94.8, 97.4, 100.0, 103.5,
    107.2, 110.9, 114.8, 118.8, 123.0, 127.3, 131.8, 136.5, 141.3, 146.2, 151.4, 156.7,
    159.8, 162.2, 165.5, 167.9, 171.3, 173.8, 177.3, 179.9, 183.5, 186.2, 189.9, 192.8,
    196.6, 199.5, 203.5, 206.5, 210.7, 218.1, 225.7, 229.1, 233.6, 241.8, 250.3, 254.1,
]


def db(x):
    return 10 * np.log10(np.maximum(x, 1e-20))


# ---------------------------------------------------------------- spectrum


def spectrogram(iq: np.ndarray, fs: float, nfft: int = 4096):
    """Return (freq offsets Hz, frame times s, linear power [frames, bins])."""
    nfft = int(min(nfft, max(64, len(iq) // 4)))
    f, t, s = signal.spectrogram(
        iq, fs=fs, window="hann", nperseg=nfft, noverlap=0,
        return_onesided=False, scaling="density", mode="psd", detrend=False,
    )
    f = np.fft.fftshift(f)
    s = np.fft.fftshift(s, axes=0).T  # frames x bins
    return f, t, s


def noise_floor_db(p_db: np.ndarray) -> float:
    # A low percentile is robust to crowded bands; the median would ride on signals.
    return float(np.percentile(p_db, 30))


def _runs(mask: np.ndarray):
    m = np.concatenate([[False], mask, [False]]).astype(np.int8)
    d = np.diff(m)
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))  # [start, stop)


def detect(f, frames, threshold_db=8.0, min_width_hz=0.0, merge_gap_hz=None,
           exclude=None):
    """Find signals in a spectrogram. Detects on max-hold so bursts are caught,
    then characterises each detection with its average power and duty cycle.

    exclude: list of (lo_hz, hi_hz) offset ranges to ignore (band edges, DC).
    """
    binw = f[1] - f[0]
    avg = frames.mean(axis=0)
    mx = frames.max(axis=0)
    avg_db, mx_db = db(avg), db(mx)
    floor_avg = noise_floor_db(avg_db)
    floor_max = noise_floor_db(mx_db)
    k = 2
    smooth = np.convolve(mx_db, np.ones(2 * k + 1) / (2 * k + 1), mode="same")
    mask = smooth > floor_max + threshold_db
    if exclude:
        for lo, hi in exclude:
            mask[(f >= lo) & (f <= hi)] = False
    runs = _runs(mask)
    gap = int((merge_gap_hz if merge_gap_hz is not None else 3 * binw) / binw)
    merged = []
    for a, b in runs:
        if merged and a - merged[-1][1] <= gap:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    floor_lin = 10 ** (floor_avg / 10)
    out = []
    for a, b in merged:
        width = (b - a) * binw
        if width < min_width_hz:
            continue
        seg = avg[a:b]
        pk = a + int(np.argmax(mx[a:b]))
        excess = np.maximum(seg - floor_lin, 0)
        centroid = float(np.sum(f[a:b] * excess) / np.sum(excess)) if excess.sum() > 0 else float(f[pk])
        band = frames[:, a:b].mean(axis=1)
        duty = float(np.mean(band > floor_lin * 10 ** (min(threshold_db, 6.0) / 10)))
        out.append({
            "offset_hz": centroid,
            "peak_offset_hz": float(f[pk]),
            "width_hz": float(width),
            "peak_snr_db": float(mx_db[pk] - floor_avg),
            "avg_snr_db": float(db(seg.max()) - floor_avg),
            "duty": round(duty, 3),
        })
    out.sort(key=lambda d: -d["peak_snr_db"])
    return out, floor_avg


# ---------------------------------------------------------------- channelising


def extract(iq: np.ndarray, fs: float, offset_hz: float, bandwidth_hz: float,
            out_rate: float | None = None):
    """Shift `offset_hz` to DC, low-pass to bandwidth, resample.

    out_rate: exact output rate, else the smallest integer decimation giving
    at least 2x the bandwidth. Returns (samples, rate).
    """
    n = np.arange(len(iq), dtype=np.float64)
    x = iq * np.exp(-2j * np.pi * offset_hz / fs * n).astype(np.complex64)
    if out_rate:
        fr = Fraction(out_rate / fs).limit_denominator(2000)
        up, down = fr.numerator, fr.denominator
        y = signal.resample_poly(x, up, down)
        rate = fs * up / down
        # resample_poly's anti-alias filter is at the output Nyquist; tighten to the channel.
        if bandwidth_hz < rate * 0.9:
            taps = signal.firwin(129, bandwidth_hz / 2, fs=rate)
            y = signal.lfilter(taps, 1, y)
    else:
        d = max(1, int(fs // (2.0 * bandwidth_hz)))
        taps = signal.firwin(8 * d + 1, bandwidth_hz / 2, fs=fs)
        y = signal.lfilter(taps, 1, x)[::d] if d > 1 else signal.lfilter(taps, 1, x)
        rate = fs / d
    return y.astype(np.complex64), rate


def resample_real(x: np.ndarray, fs: float, out_rate: float) -> np.ndarray:
    fr = Fraction(out_rate / fs).limit_denominator(2000)
    return signal.resample_poly(x, fr.numerator, fr.denominator)


# ---------------------------------------------------------------- demodulators


def demod(x: np.ndarray, fs: float, mode: str, audio_rate: int = 22050,
          deemph_us: float | None = None) -> np.ndarray:
    """Demodulate channelised complex baseband to real audio at audio_rate."""
    mode = mode.upper()
    if mode in ("FM", "NFM", "WFM"):
        a = np.angle(x[1:] * np.conj(x[:-1])) * fs / (2 * np.pi)  # Hz of deviation
        if mode == "WFM" or deemph_us:
            tau = (deemph_us or 75.0) * 1e-6
            alpha = 1 - np.exp(-1 / (fs * tau))
            a = signal.lfilter([alpha], [1, alpha - 1], a)
    elif mode in ("AM", "DSB"):
        a = np.abs(x)
        a = a - np.mean(a)
    elif mode == "CW":
        # 700 Hz beat note
        a = np.real(x * np.exp(2j * np.pi * 700 / fs * np.arange(len(x))))
    elif mode == "USB":
        a = _ssb(x, fs, upper=True)
    elif mode == "LSB":
        a = _ssb(x, fs, upper=False)
    else:
        raise ValueError(f"unsupported mode {mode}")
    y = resample_real(a, fs, audio_rate)
    # remove DC and normalise
    y = signal.lfilter([1, -1], [1, -0.995], y)
    peak = np.percentile(np.abs(y), 99.9) or 1.0
    return np.clip(y / peak * 0.8, -1, 1).astype(np.float32)


def _ssb(x, fs, upper):
    # Keep one sideband: filter the analytic signal's positive (USB) or negative (LSB) half.
    # 1425 Hz low-pass shifted by 1575 Hz -> one-sided 150-3000 Hz passband
    taps = signal.firwin(255, 1425, fs=fs)
    n = np.arange(len(taps)) - (len(taps) - 1) / 2
    shift = np.exp((2j if upper else -2j) * np.pi * 1575 / fs * n)
    ctaps = taps * shift
    y = signal.lfilter(ctaps, 1, x)
    return np.real(y)


# ---------------------------------------------------------------- features


def _snap_baud(r):
    best = min(COMMON_BAUDS, key=lambda b: abs(b - r) / b)
    return best if abs(best - r) / best < 0.03 else None


def _line_spectrum_peak(sig_, fs, fmin, fmax):
    """Strongest spectral line of sig_ in [fmin, fmax]; returns (freq, prominence_db)."""
    sig_ = sig_ - np.mean(sig_)
    n = int(2 ** np.ceil(np.log2(max(len(sig_), 1024))))
    spec = np.abs(np.fft.rfft(sig_ * np.hanning(len(sig_)), n)) ** 2
    fr = np.fft.rfftfreq(n, 1 / fs)
    sel = (fr >= fmin) & (fr <= fmax)
    if sel.sum() < 8:
        return None, 0.0
    s, fsel = spec[sel], fr[sel]
    i = int(np.argmax(s))
    prom = db(s[i]) - db(np.median(s))
    # refine with parabolic interpolation
    if 0 < i < len(s) - 1:
        a, b, c = db(s[i - 1]), db(s[i]), db(s[i + 1])
        p = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) != 0 else 0
        df = fsel[1] - fsel[0]
        return float(fsel[i] + p * df), float(prom)
    return float(fsel[i]), float(prom)


def tdma_period(power: np.ndarray, frame_s: float):
    """Detect periodic on/off structure (e.g. DMR's 60 ms TDMA frame)."""
    p = power - power.mean()
    if len(p) < 32 or np.allclose(p, 0):
        return None
    ac = np.correlate(p, p, mode="full")[len(p) - 1:]
    ac /= ac[0]
    lo = max(2, int(0.01 / frame_s))
    pk, props = signal.find_peaks(ac[lo:], height=0.4)
    if not len(pk):
        return None
    return round(float((pk[0] + lo) * frame_s), 4), round(float(props["peak_heights"][0]), 2)


def features(x: np.ndarray, fs: float, noise_power: float, est_bw: float) -> dict:
    """Measure modulation features of a channelised signal centred at DC."""
    out = {"channel_rate_hz": round(fs, 1)}
    frame = max(16, int(fs * 0.002))  # 2 ms frames
    nfr = len(x) // frame
    if nfr < 4:
        return {"error": "capture too short"}
    p = (np.abs(x[: nfr * frame].reshape(nfr, frame)) ** 2).mean(axis=1)
    on = p > noise_power * 4  # 6 dB over channel noise
    out["duty_cycle"] = round(float(on.mean()), 3)
    runs = _runs(on)
    out["bursts"] = len(runs)
    if runs:
        durs = [(b - a) * frame / fs for a, b in runs]
        out["burst_ms_median"] = round(1000 * float(np.median(durs)), 1)
        out["burst_ms_max"] = round(1000 * float(np.max(durs)), 1)
    period = tdma_period(p, frame / fs) if 0.2 < on.mean() < 0.8 else None
    if period:
        out["power_periodicity_s"] = period[0]
        out["periodicity_strength"] = period[1]
    if on.sum() < 4:
        out["note"] = "signal not present above noise during capture"
        return out
    xo = x[: nfr * frame].reshape(nfr, frame)[on].ravel()
    sig_p = float(np.mean(np.abs(xo) ** 2))
    out["snr_db_in_channel"] = round(float(db(max(sig_p - noise_power, 1e-20)) - db(noise_power)), 1)

    env = np.abs(xo)
    out["envelope_cv"] = round(float(np.std(env) / (np.mean(env) + 1e-12)), 3)
    k = np.mean(env ** 4) / (np.mean(env ** 2) ** 2 + 1e-20)
    out["envelope_kurtosis"] = round(float(k), 2)  # ~1 constant envelope, ~2 Gaussian/OFDM

    # Spectrum of the "on" portion
    nfft = int(2 ** np.ceil(np.log2(max(256, min(len(xo) // 4, fs / max(est_bw / 128, 1))))))
    nfft = min(nfft, 1 << 16)
    f, ps = signal.welch(xo, fs=fs, nperseg=min(nfft, len(xo)), return_onesided=False, detrend=False)
    f, ps = np.fft.fftshift(f), np.fft.fftshift(ps)
    nd = noise_power / fs  # noise density
    ex = np.maximum(ps - nd, 0)
    if ex.sum() > 0:
        c = np.cumsum(ex) / ex.sum()
        lo = f[np.searchsorted(c, 0.005)]
        hi = f[min(np.searchsorted(c, 0.995), len(f) - 1)]
        out["occupied_bw_99_hz"] = round(float(hi - lo), 1)
        pk = int(np.argmax(ex))
        out["spectral_peak_offset_hz"] = round(float(f[pk]), 1)
        # carrier: fraction of power in the strongest ~3 bins
        cf = ex[max(0, pk - 1): pk + 2].sum() / ex.sum()
        out["carrier_fraction"] = round(float(cf), 3)
        cen = np.sum(f * ex) / ex.sum()
        sd = np.sqrt(np.sum((f - cen) ** 2 * ex) / ex.sum())
        out["spectral_skew"] = round(float(np.sum((f - cen) ** 3 * ex) / ex.sum() / (sd ** 3 + 1e-12)), 2)
        # flatness of the in-band spectrum (1 = flat-topped like OFDM/noise)
        band = ex[(f >= lo) & (f <= hi)]
        if len(band) > 4:
            out["inband_flatness"] = round(float(np.exp(np.mean(np.log(band + 1e-30))) / np.mean(band)), 3)

    # Instantaneous frequency
    ifreq = np.angle(xo[1:] * np.conj(xo[:-1])) * fs / (2 * np.pi)
    sm = max(1, int(fs / max(est_bw, 1) / 2))
    if sm > 1:
        ifreq = np.convolve(ifreq, np.ones(sm) / sm, mode="valid")
    out["freq_deviation_rms_hz"] = round(float(np.std(ifreq)), 1)
    out["freq_deviation_peak_hz"] = round(float(np.percentile(np.abs(ifreq - np.mean(ifreq)), 99)), 1)
    lim = np.percentile(np.abs(ifreq), 99.5) or 1
    hist, edges = np.histogram(ifreq, bins=81, range=(-lim, lim))
    hs = np.convolve(hist, [1, 2, 3, 2, 1], mode="same") / 9
    pks, _ = signal.find_peaks(hs, prominence=hs.max() * 0.15, distance=4)
    levels = [round(float((edges[i] + edges[i + 1]) / 2), 1) for i in pks]
    out["fsk_levels_hz"] = levels
    out["fsk_level_count"] = len(levels)

    # Symbol rate candidates
    fmax = min(fs / 2.2, 1.2 * est_bw)
    tr = np.abs(np.diff(ifreq))
    r1, p1 = _line_spectrum_peak(tr, fs, 30, fmax)
    r2, p2 = _line_spectrum_peak(np.abs(xo) ** 2, fs, 30, fmax)
    cands = []
    for r, pr, src in ((r1, p1, "freq-transitions"), (r2, p2, "envelope")):
        if r and pr > 12:
            cands.append({"rate": round(r, 1), "prominence_db": round(pr, 1), "from": src,
                          "matches_standard": _snap_baud(r)})
    out["symbol_rate_candidates"] = cands
    return out


def classify(feat: dict, bw_hz: float) -> list[dict]:
    """Heuristic modulation guesses from features. Returns ranked candidates."""
    g = []
    if "envelope_cv" not in feat:
        return [{"guess": "no signal", "why": feat.get("note", "")}]
    cv = feat["envelope_cv"]
    kurt = feat.get("envelope_kurtosis", 0)
    cf = feat.get("carrier_fraction", 0)
    obw = feat.get("occupied_bw_99_hz", bw_hz)
    skew = feat.get("spectral_skew", 0)
    lv = feat.get("fsk_level_count", 0)
    dev = feat.get("freq_deviation_rms_hz", 0)
    duty = feat.get("duty_cycle", 1)
    flat = feat.get("inband_flatness", 0)
    sr = [c for c in feat.get("symbol_rate_candidates", []) if c.get("matches_standard")]
    snr = feat.get("snr_db_in_channel", 0)
    const_env = cv < 0.25 or (snr < 12 and cv < 0.4)

    fsk = const_env and lv in (2, 4) and bool(sr)
    if obw < 3000 and cf > 0.5 and duty < 0.9 and feat.get("bursts", 0) >= 3:
        g.append({"guess": "CW / OOK keyed carrier", "why": f"narrow carrier switching on/off ({feat['bursts']} bursts)"})
    elif obw < 300 and cf > 0.5:
        g.append({"guess": "unmodulated carrier / beacon / birdie", "why": "narrow steady carrier; check if it moves with tuning (RTL-SDR spur)"})
    if fsk:
        g.append({"guess": f"{lv}-FSK digital at ~{sr[0]['matches_standard']} baud",
                  "why": f"constant envelope, {lv} discrete frequency levels {feat.get('fsk_levels_hz')}, standard symbol rate"})
    if const_env and not fsk and obw > 60e3:
        g.append({"guess": "Wideband FM (broadcast)", "why": f"constant envelope, ~{obw/1e3:.0f} kHz wide"})
    elif const_env and not fsk and obw > 2000:
        extra = f"; {lv} frequency clusters (could be FSK without a clean symbol-rate line, or a steady audio tone)" if lv in (2, 4) else ""
        g.append({"guess": "Analog FM (NFM voice/tones) or GFSK/GMSK data",
                  "why": f"constant envelope, frequency deviation rms {dev:.0f} Hz, {obw/1e3:.1f} kHz{extra}"})
    if not const_env and duty >= 0.5 and cf > 0.25 and abs(skew) < 0.8:
        g.append({"guess": "AM (double sideband with carrier)", "why": f"strong carrier ({cf:.0%} of power), symmetric, varying envelope"})
    if not const_env and abs(skew) >= 0.8 and 1500 < obw < 4500:
        side = "USB" if skew > 0 else "LSB"
        g.append({"guess": f"SSB voice (likely {side})", "why": f"one-sided spectrum (skew {skew}), ~{obw:.0f} Hz, no symmetric carrier"})
    if not const_env and cf < 0.25 and flat > 0.6 and kurt > 1.6 and obw > 100e3:
        g.append({"guess": "OFDM (LTE/ATSC/DAB/HD Radio/Wi-Fi-like)", "why": f"flat-topped spectrum, Gaussian-like envelope (kurtosis {kurt})"})
    elif not const_env and cf < 0.25 and sr:
        g.append({"guess": f"Linear digital (PSK/QAM) at ~{sr[0]['matches_standard']} sym/s",
                  "why": "varying envelope with a symbol-rate line"})
    if duty < 0.3 and feat.get("burst_ms_median", 1e9) < 500:
        g.append({"guess": "bursty / packet transmissions", "why": f"duty {duty:.0%}, median burst {feat.get('burst_ms_median')} ms"})
    per = feat.get("power_periodicity_s")
    if per and 0.055 <= per <= 0.065:
        g.append({"guess": "TDMA with 60 ms frame (DMR single active slot)", "why": f"power repeats every {per*1000:.0f} ms"})
    elif per and 0.025 <= per <= 0.035:
        g.append({"guess": "TDMA with 30 ms slots (DMR/TETRA-like)", "why": f"power repeats every {per*1000:.0f} ms"})
    if not g:
        g.append({"guess": "unclassified", "why": "features ambiguous; inspect the waterfall image and listen"})
    return g


def audio_analysis(audio: np.ndarray, rate: int) -> dict:
    """Tones in demodulated audio: CTCSS, AFSK pairs, dominant tones."""
    out = {}
    if len(audio) < rate // 4:
        return out
    # CTCSS: low-pass below 300 Hz and look for a standard tone
    lp = signal.sosfilt(signal.butter(6, 280, fs=rate, output="sos"), audio)
    n = int(2 ** np.ceil(np.log2(len(lp))))
    sp = np.abs(np.fft.rfft(lp * np.hanning(len(lp)), n)) ** 2
    fr = np.fft.rfftfreq(n, 1 / rate)
    sel = (fr > 60) & (fr < 260)
    if sel.any():
        i = np.argmax(sp[sel])
        f0 = fr[sel][i]
        prom = db(sp[sel][i]) - db(np.median(sp[sel]))
        tone = min(CTCSS, key=lambda c: abs(c - f0))
        if prom > 20 and abs(tone - f0) < 1.0:
            out["ctcss_hz"] = tone
    # Dominant audio tones 300-5000 Hz
    f, p = signal.welch(audio, fs=rate, nperseg=4096)
    sel = (f > 300) & (f < 5000)
    pk, pr = signal.find_peaks(db(p[sel]), prominence=15)
    tones = sorted(zip(pr["prominences"], f[sel][pk]), reverse=True)[:5]
    out["audio_tones_hz"] = [round(float(t), 0) for _, t in tones]
    ts = set(round(t / 50) * 50 for t in out["audio_tones_hz"])
    if {1200, 2200} <= ts:
        out["afsk_hint"] = "Bell 202 AFSK 1200 (APRS/AX.25, NOAA SAME uses 2083/1563)"
    if {1550, 2100} <= ts or {1550, 2050} <= ts:
        out["afsk_hint"] = "Possible EAS/SAME (2083.3/1562.5 Hz)"
    if 1000 in ts and len(ts) == 1:
        out["note"] = "Steady 1 kHz tone (test tone / ID / courtesy tone)"
    return out


def stereo_rds(x: np.ndarray, fs: float) -> dict:
    """For WFM: look for 19 kHz stereo pilot and 57 kHz RDS in the FM composite."""
    comp = np.angle(x[1:] * np.conj(x[:-1]))
    f, p = signal.welch(comp, fs=fs, nperseg=8192)
    def band(lo, hi):
        s = (f >= lo) & (f <= hi)
        return db(p[s].max()) if s.any() else -200
    ref = db(np.median(p[(f > 60e3) & (f < 75e3)])) if fs > 160e3 else None
    out = {}
    if ref is not None:
        out["pilot_19k_db"] = round(float(band(18.95e3, 19.05e3) - ref), 1)
        out["rds_57k_db"] = round(float(band(55.5e3, 58.5e3) - ref), 1)
        out["stereo_pilot_19k"] = out["pilot_19k_db"] > 10
        out["rds_57k"] = out["rds_57k_db"] > 6
        out["note"] = "SDR++'s WFM demodulator decodes RDS (station name/radiotext) in its Radio menu"
    return out
