"""SDR++ integration: config files, rigctl server and IQ Exporter stream."""

import json
import os
import queue
import re
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

import numpy as np

CONFIG_DIR = Path(os.environ.get("SDRPP_CONFIG_DIR", Path.home() / ".config/sdrpp"))
IQ_INSTANCE = os.environ.get("SDRPP_IQ_INSTANCE", "IQ Exporter")
RIGCTL_INSTANCE = os.environ.get("SDRPP_RIGCTL_INSTANCE", "Rigctl Server")

# SDR++ source module name -> its config file stem
SOURCE_CONFIGS = {
    "RTL-SDR": "rtl_sdr_config",
    "RTL-TCP": "rtl_tcp_config",
    "Airspy": "airspy_config",
    "AirspyHF+": "airspyhf_config",
    "HackRF": "hackrf_config",
    "PlutoSDR": "plutosdr_source_config",
    "LimeSDR": "limesdr_config",
    "BladeRF": "bladerf_config",
}

MODES = ["FM", "WFM", "AM", "DSB", "USB", "CW", "LSB", "RAW"]


class SdrppError(RuntimeError):
    pass


def read_json(name: str) -> dict:
    path = CONFIG_DIR / f"{name}.json"
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return {}


def is_running() -> bool:
    return subprocess.run(["pgrep", "-x", "sdrpp"], capture_output=True).returncode == 0


def launch(autostart: bool = True) -> str:
    if is_running():
        return "SDR++ is already running."
    exe = shutil.which("sdrpp")
    if not exe:
        raise SdrppError("sdrpp executable not found on PATH")
    args = [exe] + (["--autostart"] if autostart else [])
    subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(40):
        time.sleep(0.25)
        if is_running():
            return "SDR++ launched" + (" with the source started." if autostart else ".")
    raise SdrppError("sdrpp did not start")


# ---------------------------------------------------------------- config state


def radio_state() -> dict:
    """Source, sample rate and gain from SDR++'s config files.

    center_hz here is only what SDR++ last saved; use live_center() for the real value.
    """
    c = read_json("config")
    source = c.get("source", "")
    state = {
        "center_hz": float(c.get("frequency", 0.0)),
        "vfo_offsets": c.get("vfoOffsets", {}),
        "source": source,
        "decimation": int(c.get("decimation", 1) or 1),
        "sample_rate": None,
        "gain": None,
        "device": None,
        "streams": c.get("streams", {}),
    }
    stem = SOURCE_CONFIGS.get(source)
    if stem:
        sc = read_json(stem)
        devices = sc.get("devices", {})
        dev = sc.get("device") or (next(iter(devices)) if devices else None)
        d = devices.get(dev, {}) if dev else {}
        state["device"] = dev
        sr = d.get("sampleRate") or sc.get("sampleRate")
        if sr:
            state["sample_rate"] = float(sr) / max(state["decimation"], 1)
        state["gain"] = {k: d[k] for k in ("gain", "tunerAgc", "rtlAgc", "biasT", "ppm", "directSampling") if k in d}
    return state


def iq_config() -> dict:
    return read_json("iq_exporter_config").get(IQ_INSTANCE, {})


def rigctl_config() -> dict:
    return read_json("rigctl_server_config").get(RIGCTL_INSTANCE, {})


PROBE_DIR = Path(os.environ.get("SDRPP_MCP_DATA", Path.home() / ".local/share/sdrpp-mcp")) / "center-probe"
_center_cache: dict = {}


def live_center(rig: "Rigctl", use_cache: bool = True) -> float:
    """True centre frequency of SDR++ right now.

    rigctl only reports the VFO, and config.json isn't saved on rigctl retunes, so this
    briefly runs the "Center Probe" baseband recorder (whose filename contains the centre
    frequency) and deletes the file. Cached while the VFO frequency stays put.
    """
    vfo = rig.get_freq()
    if use_cache and _center_cache.get("vfo") == vfo and time.time() - _center_cache["t"] < 30:
        return _center_cache["center"]
    PROBE_DIR.mkdir(parents=True, exist_ok=True)
    before = set(PROBE_DIR.glob("*.wav"))
    if "RPRT 0" not in rig.cmd("\\recorder_start"):
        raise SdrppError("rigctl could not start the Center Probe recorder; run setup_sdrpp.py with SDR++ closed.")
    time.sleep(0.12)
    rig.cmd("\\recorder_stop")
    center = None
    for _ in range(20):
        new = set(PROBE_DIR.glob("*.wav")) - before
        if new:
            for f in new:
                m = re.search(r"_(\d+)Hz_", f.name)
                if m:
                    center = float(m.group(1))
                try:
                    f.unlink()
                except OSError:
                    pass
            break
        time.sleep(0.05)
    if center is None:
        raise SdrppError(f"Center Probe produced no recording in {PROBE_DIR}; check its recorder settings in SDR++.")
    _center_cache.update(vfo=vfo, center=center, t=time.time())
    return center


# ---------------------------------------------------------------- rigctl


class Rigctl:
    def __init__(self, host: str | None = None, port: int | None = None, timeout: float = 3.0):
        cfg = rigctl_config()
        self.host = host or cfg.get("host", "localhost")
        self.port = int(port or cfg.get("port", 4532))
        self.timeout = timeout

    def cmd(self, line: str, multiline: bool = False) -> str:
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
                s.sendall((line + "\n").encode())
                data = b""
                s.settimeout(self.timeout)
                while True:
                    try:
                        chunk = s.recv(4096)
                    except socket.timeout:
                        break
                    if not chunk:
                        break
                    data += chunk
                    if not multiline and data.endswith(b"\n"):
                        # Replies to get_mode span two lines; give them a moment.
                        s.settimeout(0.15)
        except OSError as e:
            raise SdrppError(
                f"rigctl server not reachable on {self.host}:{self.port} ({e}). "
                "In SDR++ open the 'Rigctl Server' menu and press Start (or enable 'Listen on startup')."
            ) from e
        return data.decode(errors="replace").strip()

    def get_freq(self) -> float:
        return float(self.cmd("f").splitlines()[0])

    def set_freq(self, hz: float) -> None:
        r = self.cmd(f"F {int(round(hz))}")
        if "RPRT 0" not in r:
            raise SdrppError(f"set_freq failed: {r!r}")

    def get_mode(self) -> tuple[str, float | None]:
        lines = self.cmd("m").splitlines()
        mode = lines[0] if lines else "?"
        bw = float(lines[1]) if len(lines) > 1 and lines[1].replace(".", "").isdigit() else None
        return mode, bw

    def set_mode(self, mode: str, bandwidth_hz: float | None = None) -> None:
        mode = mode.upper()
        if mode == "NFM":
            mode = "FM"
        if mode not in MODES:
            raise SdrppError(f"mode must be one of {MODES}")
        r = self.cmd(f"M {mode} {int(bandwidth_hz) if bandwidth_hz else 0}")
        if "RPRT 0" not in r:
            raise SdrppError(f"set_mode failed: {r!r}")

    def start(self) -> str:
        return self.cmd("\\start")

    def stop(self) -> str:
        return self.cmd("\\stop")


# ---------------------------------------------------------------- IQ exporter

_SAMPLE_TYPES = {
    # key -> (numpy dtype, full-scale divisor)
    "int8": (np.int8, 128.0),
    "int16": (np.int16, 32768.0),
    "int32": (np.int32, 2147483648.0),
    "float32": (np.float32, 1.0),
}


def _sample_type(cfg: dict) -> tuple:
    st = str(cfg.get("sampleType", "int16")).lower()
    for key, v in _SAMPLE_TYPES.items():
        if key in st:
            return key, v
    return "int16", _SAMPLE_TYPES["int16"]


def capture_iq(seconds: float, sample_rate: float, discard_s: float = 0.05) -> tuple[np.ndarray, float]:
    """Read `seconds` of baseband IQ from SDR++'s IQ Exporter (TCP server mode).

    Returns (complex64 samples, measured sample rate).
    """
    host, port, dtype, scale, bytes_per_sample = _iq_endpoint()
    want = int((seconds + discard_s) * sample_rate) * bytes_per_sample
    buf = bytearray(want)
    view = memoryview(buf)
    got = 0
    try:
        with socket.create_connection((host, port), timeout=3.0) as s:
            s.settimeout(3.0)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 << 20)
            t0 = None
            while got < want:
                n = s.recv_into(view[got:], want - got)
                if n == 0:
                    break
                if t0 is None:
                    t0 = time.perf_counter()
                got += n
            elapsed = time.perf_counter() - (t0 or time.perf_counter())
    except (socket.timeout, OSError) as e:
        raise _iq_error(e, host, port) from e
    got -= got % bytes_per_sample
    iq = _to_complex(buf[:got], dtype, scale)
    measured = len(iq) / elapsed if elapsed > 0 else sample_rate
    skip = int(discard_s * sample_rate)
    return iq[skip:], measured


def _to_complex(raw: bytes | bytearray, dtype, scale) -> np.ndarray:
    x = np.frombuffer(bytes(raw), dtype=dtype).astype(np.float32)
    if scale != 1.0:
        x /= scale
    return x.view(np.complex64)


def _iq_error(e: Exception, host, port) -> "SdrppError":
    if isinstance(e, socket.timeout):
        return SdrppError(
            "IQ Exporter connected but no data arrived. Is the SDR source started (play button) and "
            "the IQ Exporter 'Start' pressed?"
        )
    return SdrppError(
        f"IQ Exporter not reachable on {host}:{port} ({e}). In SDR++ open the 'IQ Exporter' menu, "
        "set Mode=Baseband, Protocol=TCP (Server), and press Start."
    )


class IQStream:
    """Continuous IQ from the IQ Exporter: a background thread keeps one connection open and
    queues fixed-size chunks, so processing between chunks doesn't lose samples. If the
    consumer falls behind, the oldest chunk is dropped and counted in `dropped`."""

    def __init__(self, chunk_s: float, sample_rate: float, max_queue: int = 6):
        self.host, self.port, self.dtype, self.scale, self.bps = _iq_endpoint()
        self.chunk_s = chunk_s
        self.chunk_bytes = int(chunk_s * sample_rate) * self.bps
        self.queue = queue.Queue(max_queue)
        self.dropped = 0
        self.error = None
        self._stop = threading.Event()

    def __enter__(self):
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout=3.0)
        except OSError as e:
            raise _iq_error(e, self.host, self.port) from e
        self.sock.settimeout(3.0)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 << 20)
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        return self

    def _run(self):
        buf = bytearray(self.chunk_bytes)
        view = memoryview(buf)
        try:
            while not self._stop.is_set():
                got = 0
                while got < self.chunk_bytes:
                    n = self.sock.recv_into(view[got:], self.chunk_bytes - got)
                    if n == 0:
                        raise OSError("IQ Exporter closed the connection")
                    got += n
                item = (time.time() - self.chunk_s, bytes(buf))
                if self.queue.full():
                    self.queue.get_nowait()
                    self.dropped += 1
                self.queue.put_nowait(item)
        except (socket.timeout, OSError) as e:
            if not self._stop.is_set():
                self.error = _iq_error(e, self.host, self.port)

    def get(self, timeout: float = 5.0) -> tuple[float, np.ndarray]:
        """Next chunk as (approximate wall-clock start time, complex64 samples)."""
        while True:
            if self.error:
                raise self.error
            try:
                t, raw = self.queue.get(timeout=timeout)
                return t, _to_complex(raw, self.dtype, self.scale)
            except queue.Empty:
                if self.error:
                    raise self.error
                raise SdrppError("IQ stream stalled; is the SDR source still running?")

    def __exit__(self, *exc):
        self._stop.set()
        self.sock.close()
        self.thread.join(timeout=2)


def _iq_endpoint():
    """Validate the IQ Exporter config; return (host, port, dtype, scale, bytes per sample)."""
    cfg = iq_config()
    if not cfg:
        raise SdrppError(
            f"No '{IQ_INSTANCE}' module configured in SDR++. Run setup_sdrpp.py with SDR++ closed, "
            "or add an iq_exporter instance in SDR++'s Module Manager."
        )
    mode = str(cfg.get("mode", "")).lower()
    proto = str(cfg.get("protocol", "")).lower()
    if mode and "base" not in mode:
        raise SdrppError(f"IQ Exporter mode is {cfg.get('mode')!r}; set it to Baseband.")
    if proto and "server" not in proto:
        raise SdrppError(f"IQ Exporter protocol is {cfg.get('protocol')!r}; set it to TCP (Server).")
    host = cfg.get("host", "localhost")
    if host in ("0.0.0.0", ""):
        host = "localhost"
    port = int(cfg.get("port", 1234))
    _, (dtype, scale) = _sample_type(cfg)
    bytes_per_sample = 2 * np.dtype(dtype).itemsize
    return host, port, dtype, scale, bytes_per_sample
