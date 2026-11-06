import csv
import io
import json
from datetime import timedelta

import pytest

from picobrew_server import create_app
from picobrew_server.session_store import BrewSessionStore, parse_readings, utcnow
from picobrew_server.utils.constants import LOCAL_USER, SYSTEM_USER


@pytest.fixture
def paths(tmp_path):
    sessions = tmp_path / "sessions"
    return {"db": sessions / "brew_sessions.sqlite3", "legacy": sessions, "recipes": tmp_path / "recipes"}


@pytest.fixture
def client(paths):
    paths["recipes"].mkdir()
    app = create_app(
        {
            "TESTING": True,
            "UPLOAD_FOLDER": str(paths["recipes"]),
            "BREW_DATABASE": str(paths["db"]),
            "LEGACY_SESSION_PATH": str(paths["legacy"]),
        }
    )
    return app.test_client()


def start_session(client, recipe="recipe-id", user=LOCAL_USER):
    response = client.get(
        "/API/logSession",
        query_string={"user": user, "recipe": recipe, "code": 0, "machine": "500000000000", "firm": "1.1.14"},
    )
    session_id = response.text.strip("#")
    assert len(session_id) == 32
    return session_id


def log_step(client, session_id, name):
    assert client.get("/API/logsession", query_string={"session": session_id, "code": 1, "data": name, "state": 3})


def log_reading(client, session_id, data, snapshot="0/1/2/3/4/5/6/0"):
    response = client.get(
        "/API/LogSession",
        query_string={"session": session_id, "code": 2, "data": data, "step": snapshot, "state": 3},
    )
    assert response.status_code == 200


def test_parse_readings_maps_sensor_indexes():
    assert parse_readings("2/67|1/75.5|3/74|4/-1") == {2: 67.0, 1: 75.5, 3: 74.0, 4: -1.0}
    assert parse_readings("garbage|9/10|") == {}
    assert parse_readings(None) == {}


def test_logged_session_appears_in_history_and_detail(client):
    session_id = start_session(client)
    log_step(client, session_id, "Heat Water")
    log_reading(client, session_id, "2/20|1/30|3/40|4/31")
    log_step(client, session_id, "Mash")
    log_reading(client, session_id, "2/66|1/70|3/41|4/69")
    log_reading(client, session_id, "2/67|1/71|3/41|4/70")

    history = client.get("/sessions")
    assert history.status_code == 200
    assert "Brewing now" in history.text
    assert f"/sessions/{session_id}" in history.text

    detail = client.get(f"/sessions/{session_id}")
    assert detail.status_code == 200
    assert "Heat Water" in detail.text and "Mash" in detail.text
    assert "66.0°F" in detail.text  # wort temperature when the mash step started

    data = client.get(f"/sessions/{session_id}/data.json").get_json()
    assert data["session"]["status"] == "in_progress"
    assert data["poll_seconds"]
    assert data["readings"]["sensor_2"] == [20, 66, 67]
    assert data["readings"]["sensor_1"] == [30, 70, 71]
    assert [step["name"] for step in data["steps"]] == ["Heat Water", "Mash"]
    assert data["readings"]["step_id"] == [data["steps"][0]["id"]] + [data["steps"][1]["id"]] * 2
    assert {"summary", "steps", "errors", "status"} <= data["html"].keys()

    # Live polling only receives readings newer than the last one it has.
    newer = client.get(f"/sessions/{session_id}/data.json", query_string={"after": data["last_id"]}).get_json()
    assert newer["readings"]["t"] == []
    assert newer["last_id"] == data["last_id"]

    client.get("/API/logsession", query_string={"session": session_id, "code": 3})
    finished = client.get(f"/sessions/{session_id}/data.json").get_json()
    assert finished["session"]["status"] == "completed"
    assert finished["poll_seconds"] is None
    assert "Completed" in client.get("/sessions").text


def test_csv_export_labels_steps_and_sensors(client):
    session_id = start_session(client)
    log_step(client, session_id, "Mash")
    log_reading(client, session_id, "2/66|1/70|3/41|4/69")
    response = client.get(f"/sessions/{session_id}/readings.csv")
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0][:3] == ["recorded_at_utc", "elapsed_seconds", "step"]
    assert "Wort (°F, sensor 2)" in rows[0]
    assert rows[1][2] == "Mash"
    assert rows[1][rows[0].index("Wort (°F, sensor 2)")] == "66.0"


def test_reset_reports_are_shown_on_the_session(client):
    session_id = start_session(client)
    client.get("/API/sessionerror", query_string={"machine": "500000000000", "session": session_id, "errorcode": 303})
    detail = client.get(f"/sessions/{session_id}")
    assert "Brownout reset" in detail.text
    assert client.get(f"/sessions/{session_id}/data.json").get_json()["errors"][0]["code"] == 303
    assert "1 reset" in client.get("/sessions").text


def test_logs_for_unknown_sessions_are_not_stored(client, paths):
    for code, data in ((1, "Mash"), (2, "2/66"), (3, None)):
        response = client.get("/API/logsession", query_string={"session": "f" * 32, "code": code, "data": data})
        assert response.status_code == 404
    assert BrewSessionStore(paths["db"]).list_sessions() == []


def test_readings_before_the_first_step_are_kept(client):
    session_id = start_session(client)
    log_reading(client, session_id, "2/20")
    data = client.get(f"/sessions/{session_id}/data.json").get_json()
    assert data["readings"]["sensor_2"] == [20]
    assert data["readings"]["step_id"] == [None]


def test_cleaning_sessions_are_labelled_and_filterable(client):
    brew_id = start_session(client)
    cleaning_id = start_session(client, recipe="7f489e3740f848519558c41a036fe2cb", user=SYSTEM_USER)
    # Running sessions are always highlighted, so end them to check the filtered table alone.
    for session_id in (brew_id, cleaning_id):
        client.get("/API/logsession", query_string={"session": session_id, "code": 3})
    everything = client.get("/sessions").text
    assert brew_id in everything and cleaning_id in everything
    assert "Cleaning v1" in everything
    cleaning = client.get("/sessions?kind=cleaning").text
    assert cleaning_id in cleaning and brew_id not in cleaning
    brews = client.get("/sessions?kind=brew").text
    assert brew_id in brews and cleaning_id not in brews


def test_sessions_without_recent_logs_are_interrupted(paths):
    store = BrewSessionStore(paths["db"])
    long_ago = utcnow() - timedelta(hours=3)
    store.create_session("a" * 32, "r", "Ale", "brew", None, None, None, at=long_ago)
    store.record_reading("a" * 32, "2/66", None, None, at=long_ago + timedelta(minutes=5))
    (session,) = store.list_sessions()
    assert session["status"] == "interrupted"
    assert session["duration"] == timedelta(minutes=5)
    # Recovery means the machine is brewing again.
    store.resume_session("a" * 32)
    assert store.get_session("a" * 32)["status"] == "in_progress"


def test_empty_history_and_unknown_session(client):
    assert "No brew sessions yet" in client.get("/sessions").text
    assert client.get(f"/sessions/{'0' * 32}").status_code == 404
    assert client.get(f"/sessions/{'0' * 32}/data.json").status_code == 404
    assert client.get(f"/sessions/{'0' * 32}/readings.csv").status_code == 404


def test_legacy_json_sessions_and_errors_are_imported_once(paths):
    legacy = paths["legacy"]
    (legacy / "errors").mkdir(parents=True)
    (legacy / ("b" * 32 + ".json")).write_text(
        json.dumps(
            {
                "date": "03/14/24",
                "recipe_id": "r1",
                "recipe_name": "Old Ale",
                "session_id": "b" * 32,
                "machine_state": "0/1/2/3/4/5/6/0",
                "steps": [
                    {"name": "Heat Water", "temperatures": {"23:58:00": ["20", "30", "40", "31"]}},
                    {"name": "Mash", "temperatures": {"23:59:30": ["66", "70", "41", "69"], "00:00:30": ["67"]}},
                    {"name": "Session Ended"},
                ],
            }
        )
    )
    (legacy / "broken.json").write_text("{not json")
    (legacy / "errors" / "e1.json").write_text(
        json.dumps(
            {"machine_id": "m", "session_id": "b" * 32, "errorcode": 302, "reported_at": "2024-03-14T23:59:00+00:00"}
        )
    )

    store = BrewSessionStore(paths["db"], legacy)
    (session,) = store.list_sessions()
    assert session["recipe_name"] == "Old Ale"
    assert session["status"] == "completed"
    assert session["recovery_snapshot"] == "0/1/2/3/4/5/6/0"
    # Readings past midnight continue on the next day instead of jumping backwards.
    assert session["duration"] == timedelta(minutes=2, seconds=30)
    steps = store.get_steps("b" * 32)
    assert [step["name"] for step in steps] == ["Heat Water", "Mash"]
    readings = store.get_readings("b" * 32)
    # Legacy files kept temperatures in firmware order: sensors 2, 1, 3, 4.
    assert [(r["sensor_2"], r["sensor_1"], r["sensor_3"], r["sensor_4"]) for r in readings] == [
        (20, 30, 40, 31),
        (66, 70, 41, 69),
        (67, None, None, None),
    ]
    assert [error["errorcode"] for error in store.get_errors("b" * 32)] == [302]

    # Files from the JSON version that stored the program keep it, so they can still be recovered.
    (legacy / ("c" * 32 + ".json")).write_text(
        json.dumps(
            {
                "recipe_id": "r2",
                "program": "Ale/r2/Mash,152,60,1,5/",
                "user_id": SYSTEM_USER,
                "machine_state": "None",
                "steps": [],
            }
        )
    )
    (legacy / ("d" * 32 + ".json")).write_text(json.dumps({"recipe_id": "r3"}))
    assert store.import_legacy_json(legacy) == 1
    resumed = store.resume_session("c" * 32)
    assert resumed is not None
    assert (resumed["program"], resumed["recovery_snapshot"]) == ("Ale/r2/Mash,152,60,1,5/", None)
    assert store.get_session("c" * 32)["kind"] == "cleaning"
    assert store.get_session("d" * 32) is None

    assert store.import_legacy_json(legacy) == 0
    assert len(store.get_readings("b" * 32)) == 3
    assert len(store.get_errors("b" * 32)) == 1
