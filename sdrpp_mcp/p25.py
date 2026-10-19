"""Read-only access to the SDR++ P25 Trunking module (sdrpp-p25) and its dsd-neo decoder.

The module runs dsd-neo with a JSON-Lines API on loopback; this talks to that API as an extra
client, and reads the decoder's event log for call history.
"""

import json
import re
import socket
from pathlib import Path

from .sdrpp import CONFIG_DIR, read_json

P25_DIR = CONFIG_DIR / "p25_trunking"
EVENT_RE = re.compile(
    r"^(?P<time>\S+ \S+) (?P<proto>P25p\d) TGT: (?P<tg>\d+); SRC: (?P<src>\d+);.*?"
    r"(?:TName: (?P<tname>[^;]+);)?.*?(?:SName: (?P<sname>[^;]+);)?.*?Slot (?P<slot>\d)")


def _settings() -> dict:
    cfg = read_json("p25_trunking_config") or {}
    return next((v for v in cfg.values() if isinstance(v, dict)), {})


def api_get(whats=("status", "system", "call", "quality", "metrics"), timeout=1.5) -> dict | None:
    """Latest telemetry records from the decoder, or None if it isn't running."""
    port = int(_settings().get("apiPort", 9911))
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout) as s:
            f = s.makefile("rwb")
            if json.loads(f.readline()).get("type") != "welcome":
                return None
            out = {}
            for i, what in enumerate(whats):
                f.write((json.dumps({"id": i, "cmd": "get", "what": what}) + "\n").encode())
                f.flush()
                out[what] = json.loads(f.readline()).get("data")
            return out
    except (OSError, ValueError):
        return None


def owns_tuning() -> bool:
    """True while the P25 module's decoder is running on a radio input (it retunes SDR++)."""
    data = api_get(("status",), timeout=0.5)
    return bool(data and (data.get("status") or {}).get("radio_input"))


def recent_calls(limit=30, talkgroup=None) -> list[dict]:
    logs = sorted((P25_DIR / "run").glob("*_events.log"), key=lambda p: p.stat().st_mtime)
    if not logs:
        return []
    rows, last = [], None
    for line in logs[-1].read_text(errors="replace").splitlines():
        m = EVENT_RE.match(line)
        if not m or line == last:
            continue
        last = line
        if talkgroup and talkgroup not in (m["tg"].lstrip("0"), (m["tname"] or "")):
            continue
        rows.append({"time": m["time"], "protocol": m["proto"], "talkgroup": int(m["tg"]),
                     "talkgroup_name": (m["tname"] or "").strip(), "source": int(m["src"]),
                     "source_alias": (m["sname"] or "").strip(), "slot": int(m["slot"]),
                     "encrypted": " ENC" in line or "ALG:" in line})
    return rows[-limit:][::-1]


def profile_name() -> str:
    pid = _settings().get("profile", "")
    p = P25_DIR / "profiles" / f"{pid}.json"
    return json.loads(p.read_text()).get("name", pid) if p.exists() else pid
