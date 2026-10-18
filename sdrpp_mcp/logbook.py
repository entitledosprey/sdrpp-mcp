"""SQLite logbook of identified signals, with export to SDR++ bookmarks."""

import json
import sqlite3
import time
from pathlib import Path

from . import sdrpp

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY,
    ts REAL NOT NULL,
    freq_hz REAL NOT NULL,
    mode TEXT,
    bandwidth_hz REAL,
    label TEXT NOT NULL,
    identification TEXT,
    confidence TEXT,
    notes TEXT,
    files TEXT
);
CREATE INDEX IF NOT EXISTS signals_freq ON signals(freq_hz);
"""


class Logbook:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def add(self, freq_hz, label, mode=None, bandwidth_hz=None, identification=None,
            confidence=None, notes=None, files=None) -> int:
        cur = self.db.execute(
            "INSERT INTO signals (ts, freq_hz, mode, bandwidth_hz, label, identification, confidence, notes, files)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (time.time(), freq_hz, mode, bandwidth_hz, label, identification, confidence, notes,
             json.dumps(files or [])),
        )
        self.db.commit()
        return cur.lastrowid

    def search(self, text=None, lo_hz=None, hi_hz=None, limit=50) -> list[dict]:
        q, args = "SELECT * FROM signals WHERE 1=1", []
        if text:
            q += " AND (label LIKE ? OR identification LIKE ? OR notes LIKE ?)"
            args += [f"%{text}%"] * 3
        if lo_hz is not None:
            q += " AND freq_hz >= ?"
            args.append(lo_hz)
        if hi_hz is not None:
            q += " AND freq_hz <= ?"
            args.append(hi_hz)
        q += " ORDER BY freq_hz LIMIT ?"
        args.append(limit)
        rows = []
        for r in self.db.execute(q, args):
            d = dict(r)
            d["time"] = time.strftime("%Y-%m-%d %H:%M", time.localtime(d.pop("ts")))
            d["files"] = json.loads(d["files"] or "[]")
            rows.append(d)
        return rows

    def delete(self, entry_id: int) -> bool:
        cur = self.db.execute("DELETE FROM signals WHERE id = ?", (entry_id,))
        self.db.commit()
        return cur.rowcount > 0

    def export_bookmarks(self, list_name="SDR Log") -> int:
        """Write all entries into SDR++'s Frequency Manager as a bookmark list.

        Must be done with SDR++ closed, or SDR++ will overwrite the file.
        """
        if sdrpp.is_running():
            raise sdrpp.SdrppError("Close SDR++ first; it overwrites frequency_manager_config.json while running.")
        path = sdrpp.CONFIG_DIR / "frequency_manager_config.json"
        cfg = json.loads(path.read_text()) if path.exists() else {"lists": {}, "selectedList": list_name}
        path.with_suffix(f".json.bak-{int(time.time())}").write_text(json.dumps(cfg, indent=4))
        marks = {}
        mode_ids = {"NFM": 0, "FM": 0, "WFM": 1, "AM": 2, "DSB": 3, "USB": 4, "CW": 5, "LSB": 6, "RAW": 7}
        for r in self.search(limit=10000):
            name = r["label"]
            base, i = name, 2
            while name in marks:
                name, i = f"{base} ({i})", i + 1
            marks[name] = {
                "frequency": r["freq_hz"],
                "bandwidth": r["bandwidth_hz"] or 12500.0,
                "mode": mode_ids.get((r["mode"] or "FM").upper(), 0),
            }
        cfg.setdefault("lists", {})[list_name] = {"bookmarks": marks, "showOnWaterfall": True}
        path.write_text(json.dumps(cfg, indent=4))
        return len(marks)
