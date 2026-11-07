"""SQLite storage for brew sessions, step events, temperature readings and error reports.

One database file replaces the per-session JSON files. Each reading is a single
appended row instead of a rewrite of the whole session, writes are atomic, and
WAL mode lets the web UI read while the machine logs from another worker.
"""

import json
import logging
import re
import sqlite3
from collections.abc import Generator
from contextlib import closing, contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from flask import current_app

from picobrew_server.utils.constants import CLEANING_RECIPE_IDS, SYSTEM_USER

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
# The machine logs temperatures at most once every 60 s; a long-quiet session is no longer running.
ACTIVE_TIMEOUT = timedelta(minutes=15)
SENSOR_INDEXES = (1, 2, 3, 4)
# Legacy JSON logs kept only the temperatures, in the order the firmware sends them (wort, heat1, board, heat2).
LEGACY_SENSOR_ORDER = (2, 1, 3, 4)
READING_PATTERN = re.compile(r"\s*([1-4])\s*/\s*(-?\d+(?:\.\d+)?)\s*")
# Reset point: step/sessionTime/stepStart/heatStart/holdStart/drainStart/recipeIndex/transport.
# The firmware copies each field into a 32-byte buffer, so bound every field to a 32-bit integer's digits.
RECOVERY_SNAPSHOT = re.compile(r"-?\d{1,10}(/-?\d{1,10}){7}")

SCHEMA = """
CREATE TABLE IF NOT EXISTS brew_session (
    id TEXT PRIMARY KEY,
    recipe_id TEXT,
    recipe_name TEXT,
    kind TEXT NOT NULL DEFAULT 'brew',
    user_id TEXT,
    machine_id TEXT,
    firmware TEXT,
    -- The exact program record sent to the machine, so recovery is unaffected by later recipe edits.
    program TEXT,
    started_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    ended_at TEXT,
    recovery_snapshot TEXT,
    state INTEGER,
    source TEXT NOT NULL DEFAULT 'machine'
);
CREATE INDEX IF NOT EXISTS brew_session_started ON brew_session (started_at);

CREATE TABLE IF NOT EXISTS session_step (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES brew_session (id) ON DELETE CASCADE,
    name TEXT,
    state INTEGER,
    started_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS session_step_session ON session_step (session_id, id);

CREATE TABLE IF NOT EXISTS session_reading (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES brew_session (id) ON DELETE CASCADE,
    step_id INTEGER REFERENCES session_step (id) ON DELETE SET NULL,
    recorded_at TEXT NOT NULL,
    state INTEGER,
    sensor_1 REAL,
    sensor_2 REAL,
    sensor_3 REAL,
    sensor_4 REAL,
    raw_data TEXT
);
CREATE INDEX IF NOT EXISTS session_reading_session ON session_reading (session_id, id);
CREATE INDEX IF NOT EXISTS session_reading_step ON session_reading (step_id);

-- Error reports may name sessions this server never saw, so there is no foreign key.
CREATE TABLE IF NOT EXISTS session_error (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    machine_id TEXT NOT NULL,
    errorcode INTEGER NOT NULL,
    reported_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS session_error_session ON session_error (session_id);

CREATE TABLE IF NOT EXISTS legacy_import (
    name TEXT PRIMARY KEY,
    imported_at TEXT NOT NULL
);
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(moment: datetime) -> str:
    """Serialize as fixed-width UTC so stored timestamps sort as text."""
    return moment.astimezone(timezone.utc).isoformat(timespec="milliseconds")


def from_iso(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def parse_readings(data: str | None) -> dict[int, float]:
    """Parse firmware readings such as ``2/67|1/75|3/74|4/76`` into sensor index -> temperature."""
    readings: dict[int, float] = {}
    for part in (data or "").split("|"):
        match = READING_PATTERN.fullmatch(part)
        if match:
            readings[int(match[1])] = float(match[2])
    return readings


def session_kind(user_id: str | None, recipe_id: str | None) -> str:
    """Cleaning and rinse runs come from the system user or use one of the built-in cleaning programs."""
    return "cleaning" if user_id == SYSTEM_USER or recipe_id in CLEANING_RECIPE_IDS else "brew"


def session_status(ended_at: datetime | None, last_seen_at: datetime, now: datetime | None = None) -> str:
    if ended_at is not None:
        return "completed"
    if (now or utcnow()) - last_seen_at <= ACTIVE_TIMEOUT:
        return "in_progress"
    return "interrupted"


class BrewSessionStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    # -------- Connection & schema --------
    def _open(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 15000")
        # Checked on every connection (a single header read), so a database file that was
        # deleted or replaced while the server runs gets its tables back on the next request.
        if connection.execute("PRAGMA user_version").fetchone()[0] < SCHEMA_VERSION:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(SCHEMA)
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        return connection

    @contextmanager
    def _transaction(self) -> Generator[sqlite3.Connection]:
        """Commit on success and roll back on error; BEGIN IMMEDIATE serializes writers up front."""
        with closing(self._open()) as connection:
            connection.isolation_level = None
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except BaseException:
                connection.execute("ROLLBACK")
                raise
            connection.execute("COMMIT")

    # -------- Writes from the machine API --------
    def create_session(
        self,
        session_id: str,
        recipe_id: str,
        recipe_name: str | None,
        kind: str,
        user_id: str | None,
        machine_id: str | None,
        firmware: str | None,
        program: str | None = None,
        at: datetime | None = None,
    ) -> None:
        now = to_iso(at or utcnow())
        with self._transaction() as db:
            db.execute(
                "INSERT INTO brew_session (id, recipe_id, recipe_name, kind, user_id, machine_id, firmware, "
                "program, started_at, last_seen_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, recipe_id, recipe_name, kind, user_id, machine_id, firmware, program, now, now),
            )

    def record_step(self, session_id: str, name: str | None, state: int | None, at: datetime | None = None) -> bool:
        now = to_iso(at or utcnow())
        with self._transaction() as db:
            if not self._touch(db, session_id, now, state):
                return False
            db.execute(
                "INSERT INTO session_step (session_id, name, state, started_at) VALUES (?, ?, ?, ?)",
                (session_id, name, state, now),
            )
        return True

    def record_reading(
        self,
        session_id: str,
        data: str | None,
        snapshot: str | None,
        state: int | None,
        at: datetime | None = None,
    ) -> bool:
        now = to_iso(at or utcnow())
        temps = parse_readings(data)
        with self._transaction() as db:
            if not self._touch(db, session_id, now, state):
                return False
            if snapshot is not None:
                db.execute("UPDATE brew_session SET recovery_snapshot = ? WHERE id = ?", (snapshot, session_id))
            db.execute(
                "INSERT INTO session_reading (session_id, step_id, recorded_at, state, "
                "sensor_1, sensor_2, sensor_3, sensor_4, raw_data) "
                "VALUES (?, (SELECT MAX(id) FROM session_step WHERE session_id = ?), ?, ?, ?, ?, ?, ?, ?)",
                (session_id, session_id, now, state, *(temps.get(i) for i in SENSOR_INDEXES), data),
            )
        return True

    def end_session(self, session_id: str, at: datetime | None = None) -> bool:
        now = to_iso(at or utcnow())
        with self._transaction() as db:
            if not self._touch(db, session_id, now):
                return False
            db.execute("UPDATE brew_session SET ended_at = COALESCE(ended_at, ?) WHERE id = ?", (now, session_id))
        return True

    def resume_session(self, session_id: str, at: datetime | None = None) -> sqlite3.Row | None:
        """Return the recovery data and mark the session as seen, since the machine is resuming it."""
        now = to_iso(at or utcnow())
        with self._transaction() as db:
            if not self._touch(db, session_id, now):
                return None
            return db.execute(
                "SELECT recipe_id, program, recovery_snapshot FROM brew_session WHERE id = ?", (session_id,)
            ).fetchone()

    def touch_session(self, session_id: str, at: datetime | None = None) -> bool:
        """Mark the session as seen; False when it does not exist."""
        with self._transaction() as db:
            return self._touch(db, session_id, to_iso(at or utcnow()))

    def record_error(self, machine_id: str, session_id: str, errorcode: int, at: datetime | None = None) -> None:
        with self._transaction() as db:
            db.execute(
                "INSERT INTO session_error (session_id, machine_id, errorcode, reported_at) VALUES (?, ?, ?, ?)",
                (session_id, machine_id, errorcode, to_iso(at or utcnow())),
            )

    @staticmethod
    def _touch(db: sqlite3.Connection, session_id: str, now: str, state: int | None = None) -> bool:
        cursor = db.execute(
            "UPDATE brew_session SET last_seen_at = MAX(last_seen_at, ?), state = COALESCE(?, state) WHERE id = ?",
            (now, state, session_id),
        )
        return cursor.rowcount == 1

    # -------- Reads for the web UI --------
    _SUMMARY_COLUMNS = """
        s.*,
        (SELECT COUNT(*) FROM session_step st WHERE st.session_id = s.id) AS step_count,
        (SELECT name FROM session_step st WHERE st.session_id = s.id ORDER BY st.id DESC LIMIT 1) AS current_step,
        (SELECT COUNT(*) FROM session_reading r WHERE r.session_id = s.id) AS reading_count,
        (SELECT MAX(sensor_2) FROM session_reading r WHERE r.session_id = s.id) AS max_wort,
        (SELECT COUNT(*) FROM session_error e WHERE e.session_id = s.id) AS error_count
    """
    # The history page aggregates each table once instead of running correlated subqueries per
    # session, and leaves out the large program and recovery columns it never shows.
    _LIST_QUERY = """
        WITH readings AS (
            SELECT session_id, COUNT(*) AS reading_count, MAX(sensor_2) AS max_wort, MAX(id) AS last_id
            FROM session_reading GROUP BY session_id
        ),
        steps AS (SELECT session_id, COUNT(*) AS step_count, MAX(id) AS last_id FROM session_step GROUP BY session_id),
        errors AS (SELECT session_id, COUNT(*) AS error_count FROM session_error GROUP BY session_id)
        SELECT s.id, s.recipe_id, s.recipe_name, s.kind, s.user_id, s.machine_id, s.firmware,
               s.started_at, s.last_seen_at, s.ended_at, s.state, s.source,
               COALESCE(steps.step_count, 0) AS step_count,
               last_step.name AS current_step,
               COALESCE(readings.reading_count, 0) AS reading_count,
               readings.max_wort,
               last_reading.sensor_2 AS latest_wort,
               COALESCE(errors.error_count, 0) AS error_count
        FROM brew_session s
        LEFT JOIN readings ON readings.session_id = s.id
        LEFT JOIN session_reading last_reading ON last_reading.id = readings.last_id
        LEFT JOIN steps ON steps.session_id = s.id
        LEFT JOIN session_step last_step ON last_step.id = steps.last_id
        LEFT JOIN errors ON errors.session_id = s.id
        ORDER BY s.started_at DESC, s.rowid DESC
    """

    def list_sessions(self) -> list[dict[str, Any]]:
        with closing(self._open()) as db:
            rows = db.execute(self._LIST_QUERY).fetchall()
        now = utcnow()
        return [self._summary(row, now) for row in rows]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with closing(self._open()) as db:
            row = db.execute(f"SELECT {self._SUMMARY_COLUMNS} FROM brew_session s WHERE s.id = ?", (session_id,))
            row = row.fetchone()
            if row is None:
                return None
            latest = db.execute(
                "SELECT recorded_at, sensor_1, sensor_2, sensor_3, sensor_4 FROM session_reading "
                "WHERE session_id = ? ORDER BY id DESC LIMIT 1",
                (session_id,),
            ).fetchone()
        summary = self._summary(row, utcnow())
        summary["latest_wort"] = latest["sensor_2"] if latest else None
        summary["latest_reading"] = (
            {
                "recorded_at": from_iso(latest["recorded_at"]),
                **{f"sensor_{i}": latest[f"sensor_{i}"] for i in SENSOR_INDEXES},
            }
            if latest
            else None
        )
        return summary

    @staticmethod
    def _summary(row: sqlite3.Row, now: datetime) -> dict[str, Any]:
        summary = dict(row)
        started = from_iso(row["started_at"])
        last_seen = from_iso(row["last_seen_at"])
        ended = from_iso(row["ended_at"])
        assert started is not None and last_seen is not None
        summary.update(
            started_at=started,
            last_seen_at=last_seen,
            ended_at=ended,
            status=session_status(ended, last_seen, now),
            duration=max((ended or last_seen) - started, timedelta(0)),
        )
        return summary

    def get_steps(self, session_id: str) -> list[dict[str, Any]]:
        """Return steps with their duration and wort-temperature range, in machine order."""
        with closing(self._open()) as db:
            session = db.execute(
                "SELECT last_seen_at, ended_at FROM brew_session WHERE id = ?", (session_id,)
            ).fetchone()
            if session is None:
                return []
            rows = db.execute(
                """
                SELECT st.id, st.name, st.state, st.started_at,
                       COUNT(r.id) AS reading_count,
                       MIN(r.sensor_2) AS wort_min,
                       MAX(r.sensor_2) AS wort_max,
                       (SELECT sensor_2 FROM session_reading WHERE step_id = st.id ORDER BY id LIMIT 1) AS wort_start,
                       (SELECT sensor_2 FROM session_reading WHERE step_id = st.id ORDER BY id DESC LIMIT 1) AS wort_end
                FROM session_step st LEFT JOIN session_reading r ON r.step_id = st.id
                WHERE st.session_id = ?
                GROUP BY st.id ORDER BY st.id
                """,
                (session_id,),
            ).fetchall()
        session_end = from_iso(session["ended_at"]) or from_iso(session["last_seen_at"])
        steps = [dict(row) for row in rows]
        for index, step in enumerate(steps):
            start = from_iso(step["started_at"])
            end = from_iso(steps[index + 1]["started_at"]) if index + 1 < len(steps) else session_end
            assert start is not None and end is not None
            step["started_at"] = start
            step["duration"] = max(end - start, timedelta(0))
        return steps

    def get_readings(self, session_id: str, after_id: int = 0) -> list[sqlite3.Row]:
        with closing(self._open()) as db:
            return db.execute(
                "SELECT id, step_id, recorded_at, state, sensor_1, sensor_2, sensor_3, sensor_4 "
                "FROM session_reading WHERE session_id = ? AND id > ? ORDER BY id",
                (session_id, after_id),
            ).fetchall()

    def get_errors(self, session_id: str) -> list[dict[str, Any]]:
        with closing(self._open()) as db:
            rows = db.execute(
                "SELECT errorcode, machine_id, reported_at FROM session_error WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
        return [{**dict(row), "reported_at": from_iso(row["reported_at"])} for row in rows]

    # -------- Legacy JSON import --------
    def import_legacy_json(self, directory: Path) -> int:
        """Import JSON session logs and error reports written by earlier versions, once per file.

        The files are left in place so a downgrade or manual inspection still works.
        """
        candidates = [(f"session/{p.name}", p) for p in sorted(directory.glob("*.json"))]
        candidates += [(f"error/{p.name}", p) for p in sorted((directory / "errors").glob("*.json"))]
        if not candidates:
            return 0
        with closing(self._open()) as db:
            done = {row[0] for row in db.execute("SELECT name FROM legacy_import")}
        imported = 0
        for name, path in candidates:
            if name in done:
                continue
            # One short transaction per file: a bad file is skipped on its own and never
            # holds the write lock long enough to block the machine's logging.
            try:
                with self._transaction() as db:
                    # Another worker may have imported it since the check above.
                    if db.execute("SELECT 1 FROM legacy_import WHERE name = ?", (name,)).fetchone():
                        continue
                    record = json.loads(path.read_text())
                    if name.startswith("session/"):
                        self._import_legacy_session(db, record, path)
                    else:
                        self._import_legacy_error(db, record)
                    db.execute("INSERT INTO legacy_import (name, imported_at) VALUES (?, ?)", (name, to_iso(utcnow())))
            except sqlite3.OperationalError as error:
                # A locked or unwritable database is not the file's fault; try again on the next start.
                logger.warning("Could not import legacy session file %s: %s", path, error)
                continue
            except Exception as error:
                logger.warning("Skipping unreadable legacy session file %s: %s", path, error)
                continue
            imported += 1
        if imported:
            logger.info("Imported %d legacy session files from %s", imported, directory)
        return imported

    @staticmethod
    def _import_legacy_error(db: sqlite3.Connection, record: Any) -> None:
        db.execute(
            "INSERT INTO session_error (session_id, machine_id, errorcode, reported_at) VALUES (?, ?, ?, ?)",
            (
                str(record["session_id"]),
                str(record["machine_id"]),
                int(record["errorcode"]),
                to_iso(datetime.fromisoformat(record["reported_at"])),
            ),
        )

    def _import_legacy_session(self, db: sqlite3.Connection, record: Any, path: Path) -> None:
        if not isinstance(record, dict) or not isinstance(record.get("steps"), list):
            # Older versions wrote session files in place, so a power loss could truncate them.
            raise ValueError("not a session log")
        session_id = str(record.get("session_id") or path.stem)
        if db.execute("SELECT 1 FROM brew_session WHERE id = ?", (session_id,)).fetchone():
            return
        day = _parse_legacy_date(record.get("date")) or date.fromtimestamp(path.stat().st_mtime)
        clock = _LegacyClock(day)

        steps: list[tuple[str | None, datetime | None, list[tuple[datetime, list[float | None]]]]] = []
        ended = False
        for step in record.get("steps", []):
            if step.get("name") == "Session Ended" and "temperatures" not in step:
                ended = True
                continue
            readings = []
            for time_text, temps in (step.get("temperatures") or {}).items():
                moment = clock.advance(time_text)
                if moment is not None:
                    readings.append((moment, [_to_float(t) for t in temps]))
            steps.append((step.get("name"), readings[0][0] if readings else None, readings))

        moments = [moment for _, _, readings in steps for moment, _ in readings]
        started = moments[0] if moments else datetime.combine(day, datetime.min.time()).astimezone()
        last_seen = moments[-1] if moments else started

        snapshot = record.get("machine_state")
        db.execute(
            "INSERT INTO brew_session (id, recipe_id, recipe_name, kind, user_id, machine_id, firmware, program, "
            "started_at, last_seen_at, ended_at, recovery_snapshot, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'legacy-json')",
            (
                session_id,
                _text(record.get("recipe_id")),
                _text(record.get("recipe_name")),
                session_kind(_text(record.get("user_id")), _text(record.get("recipe_id"))),
                _text(record.get("user_id")),
                _text(record.get("machine_id")),
                _text(record.get("firmware")),
                _text(record.get("program")),
                to_iso(started),
                to_iso(last_seen),
                to_iso(last_seen) if ended else None,
                snapshot if isinstance(snapshot, str) and RECOVERY_SNAPSHOT.fullmatch(snapshot) else None,
            ),
        )
        previous = started
        for name, step_start, readings in steps:
            step_start = step_start or previous
            cursor = db.execute(
                "INSERT INTO session_step (session_id, name, started_at) VALUES (?, ?, ?)",
                (session_id, name, to_iso(step_start)),
            )
            for moment, temps in readings:
                by_sensor = dict(zip(LEGACY_SENSOR_ORDER, temps))
                db.execute(
                    "INSERT INTO session_reading (session_id, step_id, recorded_at, "
                    "sensor_1, sensor_2, sensor_3, sensor_4) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (session_id, cursor.lastrowid, to_iso(moment), *(by_sensor.get(i) for i in SENSOR_INDEXES)),
                )
                previous = moment


class _LegacyClock:
    """Turn the time-of-day keys of legacy logs into datetimes, rolling over at midnight."""

    def __init__(self, day: date) -> None:
        self.day = day
        self.last: datetime | None = None

    def advance(self, text: str) -> datetime | None:
        for fmt in ("%X", "%H:%M:%S", "%I:%M:%S %p"):
            try:
                clock = datetime.strptime(text.strip(), fmt).time()
                break
            except ValueError:
                continue
        else:
            return None
        moment = datetime.combine(self.day, clock)
        if self.last is not None and moment < self.last:
            self.day += timedelta(days=1)
            moment = datetime.combine(self.day, clock)
        self.last = moment
        return moment.astimezone()  # legacy times were written in server-local time


def _parse_legacy_date(text: Any) -> date | None:
    if not isinstance(text, str):
        return None
    for fmt in ("%x", "%m/%d/%y", "%m/%d/%Y", "%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_store() -> BrewSessionStore:
    """Return the store configured for the current Flask app."""
    return BrewSessionStore(current_app.config["BREW_DATABASE"])
