"""Waterfall / spectrum images for inspecting captures."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .dsp import db  # noqa: E402


def _fmt_freq(hz):
    return f"{hz/1e6:.4f} MHz" if hz >= 1e6 else f"{hz/1e3:.1f} kHz"


def waterfall(path, f_abs, t, frames, floor_db, title, marks=(), max_rows=400, dyn=45):
    """Two-panel image: avg + max-hold spectrum on top, waterfall below.

    marks: iterable of (abs_hz, label) to annotate.
    """
    p = db(frames)
    if len(p) > max_rows:
        step = int(np.ceil(len(p) / max_rows))
        n = (len(p) // step) * step
        p = 10 * np.log10(np.mean(10 ** (p[:n] / 10).reshape(-1, step, p.shape[1]), axis=1))
        t = t[:n:step]
    # Collapse bins so the image stays readable
    cols = p.shape[1]
    if cols > 2048:
        k = cols // 2048
        c = (cols // k) * k
        p = p[:, :c].reshape(len(p), -1, k).max(axis=2)
        f_abs = f_abs[:c].reshape(-1, k).mean(axis=1)
    scale, unit = (1e6, "MHz") if (f_abs[-1] - f_abs[0]) > 2e5 or f_abs[0] > 1e7 else (1e3, "kHz")
    fx = f_abs / scale
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True,
                                   gridspec_kw={"height_ratios": [1, 2.2]})
    ax1.plot(fx, db(np.mean(10 ** (p / 10), axis=0)) - floor_db, lw=0.7, label="average")
    ax1.plot(fx, p.max(axis=0) - floor_db, lw=0.5, alpha=0.6, label="max hold")
    ax1.set_ylabel("dB over noise floor")
    ax1.set_ylim(-5, max(20, float(np.nanmax(p) - floor_db) + 5))
    ax1.grid(alpha=0.3)
    ax1.legend(loc="upper right", fontsize=8)
    for hz, label in marks:
        ax1.axvline(hz / scale, color="red", lw=0.6, alpha=0.6)
        ax1.annotate(label, (hz / scale, ax1.get_ylim()[1]), rotation=90, fontsize=7,
                     va="top", ha="right", color="darkred")
    ax2.imshow(p, aspect="auto", origin="upper", cmap="viridis",
               extent=[fx[0], fx[-1], t[-1] if len(t) else 1, 0],
               vmin=floor_db - 3, vmax=floor_db + dyn, interpolation="nearest")
    ax2.set_ylabel("time (s)")
    ax2.set_xlabel(f"frequency ({unit})")
    ax2.ticklabel_format(axis="x", useOffset=False, style="plain")
    fig.suptitle(title, fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=90)
    plt.close(fig)
    return path


def sweep_plot(path, f_abs, avg_db, max_db, floor_db, title, marks=()):
    fig, ax = plt.subplots(figsize=(15, 5))
    fx = f_abs / 1e6
    ax.plot(fx, avg_db - floor_db, lw=0.6, label="average")
    ax.plot(fx, max_db - floor_db, lw=0.4, alpha=0.6, label="max hold")
    for hz, label in marks:
        ax.axvline(hz / 1e6, color="red", lw=0.5, alpha=0.5)
        ax.annotate(label, (hz / 1e6, ax.get_ylim()[1]), rotation=90, fontsize=6,
                    va="top", ha="right", color="darkred")
    ax.set_xlabel("frequency (MHz)")
    ax.ticklabel_format(axis="x", useOffset=False, style="plain")
    ax.set_ylabel("dB over noise floor")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=90)
    plt.close(fig)
    return path
