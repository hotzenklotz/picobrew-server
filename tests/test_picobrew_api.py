import json
import re

import pytest

from picobrew_server import create_app
from picobrew_server.beerxml.picobrew_program_step import PicoBrewProgramStep, PicoBrewZymaticProgram
from picobrew_server.beerxml.picobrew_recipe import PicoBrewRecipe
from picobrew_server.blueprints import picobrew_api as api


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "MACHINE_PATH", str(tmp_path / "machines"))
    monkeypatch.setattr(api, "SESSION_PATH", str(tmp_path / "sessions"))
    monkeypatch.setattr(api, "SESSION_ERROR_PATH", str(tmp_path / "sessions" / "errors"))
    return create_app({"TESTING": True}).test_client()


def test_firmware_check_reports_no_update(client):
    response = client.get(
        "/API/zymaticFirmwareCheck", query_string={"machine": "500000000000", "ver": 1, "maj": 1, "min": 14}
    )
    assert response.status_code == 200
    assert response.data == b"#F#"


def test_machine_account_is_stable_and_can_sync_recipes(client, monkeypatch):
    recipe = PicoBrewRecipe(
        filename="ale.xml",
        name="Ale",
        zymatic=PicoBrewZymaticProgram(
            steps=[PicoBrewProgramStep(name="Mash", temp=152, time=60, location="Mash", drain=5)]
        ),
    )
    monkeypatch.setattr(api, "get_recipes", lambda: [recipe])

    response = client.get("/API/usersetup", query_string={"machine": "500000000000", "admin": 0})
    assert response.status_code == 200
    match = re.fullmatch(r"#([0-9a-f]{32})/([^/,|#]{1,20})\|#", response.text)
    assert match is not None
    user_id = match[1]
    assert user_id != api.SYSTEM_USER
    # Account identity is independent of machine registration and app lifetime.
    other_client = create_app({"TESTING": True}).test_client()
    other_response = other_client.get("/API/usersetup", query_string={"machine": "500000000001", "admin": 0})
    assert other_response.data == response.data

    for route in ("/API/SyncUser", "/API/SyncUSer"):
        response = client.get(route, query_string={"user": user_id, "machine": "500000000000"})
        assert response.status_code == 200
        assert response.text == f"#{recipe.serialize()}|#"


def test_first_setup_persists_sensor_indexes_and_updates_one_machine(client, tmp_path):
    for sensor_id in ("0123456789abcdef", "fedcba9876543210"):
        response = client.get(
            "/API/firstSetup",
            query_string={"machine": f"500000000000|{sensor_id},1/second,2/third,3/fourth,4", "admin": 0},
        )
        assert response.status_code == 200
        assert response.data == b""
        records = list((tmp_path / "machines").glob("*.json"))
        assert len(records) == 1
        record = json.loads(records[0].read_text())
        assert record["machine_id"] == "500000000000"
        assert record["user_id"] == api.LOCAL_USER
        assert record["sensors"] == {"1": sensor_id, "2": "second", "3": "third", "4": "fourth"}
        assert record["updated_at"]
    assert not list((tmp_path / "machines").glob("*.tmp"))


@pytest.mark.parametrize(
    "machine",
    ["500000000000", "|a,1/b,2/c,3/d,4", "500000000000|a,1/b,2/c,3", "500000000000|a,1/b,2/c,3/d,3"],
)
def test_first_setup_rejects_incomplete_or_duplicate_sensor_indexes(client, tmp_path, machine):
    response = client.get("/API/firstSetup", query_string={"machine": machine, "admin": 0})
    assert response.status_code == 422
    assert not (tmp_path / "machines").exists()


def test_setup_does_not_use_machine_identifier_as_a_filename(client, tmp_path):
    response = client.get("/API/firstSetup", query_string={"machine": "../escaped|a,1/b,2/c,3/d,4", "admin": 0})
    assert response.status_code == 200
    assert not (tmp_path / "escaped.json").exists()
    records = list((tmp_path / "machines").glob("*.json"))
    assert len(records) == 1
    assert re.fullmatch(r"[0-9a-f]{32}\.json", records[0].name)
    assert json.loads(records[0].read_text())["machine_id"] == "../escaped"


def test_error_reports_preserve_recovery_state_and_each_event(client, tmp_path, monkeypatch):
    monkeypatch.setattr(api, "get_recipes", lambda: [])
    response = client.get(
        "/API/logSession",
        query_string={
            "user": api.LOCAL_USER,
            "recipe": "recipe-id",
            "code": 0,
            "machine": "500000000000",
            "firm": "1.1.14",
        },
    )
    assert response.status_code == 200
    session_id = response.text.strip("#")
    assert len(session_id) == 32
    client.get("/API/logsession", query_string={"session": session_id, "code": 1, "data": "Mash", "state": 0})
    snapshot = "0/520264/520081/520081/0/0/0/0"
    response = client.get(
        "/API/LogSession",
        query_string={"session": session_id, "data": "2/67|1/75|3/74|4/76", "code": 2, "step": snapshot, "state": 0},
    )
    assert response.status_code == 200
    session_file = tmp_path / "sessions" / f"{session_id}.json"
    saved_session = session_file.read_bytes()

    for code in (303, 305):
        response = client.get(
            "/API/sessionerror", query_string={"machine": "500000000000", "session": session_id, "errorcode": code}
        )
        assert response.status_code == 200
        assert response.data == b""
    events = [json.loads(path.read_text()) for path in (tmp_path / "sessions" / "errors").glob("*.json")]
    assert sorted(event["errorcode"] for event in events) == [303, 305]
    assert all(event["machine_id"] == "500000000000" and event["session_id"] == session_id for event in events)
    assert all(event["reported_at"] for event in events)
    assert session_file.read_bytes() == saved_session
    response = client.get("/API/recoversession", query_string={"session": session_id, "code": 1})
    assert response.status_code == 200
    assert response.text == f"#{snapshot}#"


@pytest.mark.parametrize("session", ["unknown-session", "", "../escaped"])
def test_error_report_does_not_require_an_existing_session(client, tmp_path, session):
    response = client.get(
        "/API/sessionerror", query_string={"machine": "500000000000", "session": session, "errorcode": 300}
    )
    assert response.status_code == 200
    records = list((tmp_path / "sessions" / "errors").glob("*.json"))
    assert len(records) == 1
    assert json.loads(records[0].read_text())["session_id"] == session
    assert not (tmp_path / "escaped.json").exists()


@pytest.mark.parametrize(
    ("route", "query"),
    [
        ("/API/zymaticFirmwareCheck", {"machine": "m", "ver": 1, "maj": 1}),
        ("/API/zymaticFirmwareCheck", {"machine": "m", "ver": 1, "maj": 1, "min": "bad"}),
        ("/API/usersetup", {"machine": "m"}),
        ("/API/usersetup", {"machine": "", "admin": 0}),
        ("/API/usersetup", {"machine": "m", "admin": 1}),
        ("/API/firstSetup", {"machine": "m|a,1/b,2/c,3/d,4"}),
        ("/API/sessionerror", {"machine": "m", "errorcode": 300}),
        ("/API/sessionerror", {"machine": "m", "session": "s", "errorcode": "bad"}),
        ("/API/sessionerror", {"machine": "m", "session": "s", "errorcode": -1}),
    ],
)
def test_new_routes_validate_firmware_arguments(client, route, query):
    assert client.get(route, query_string=query).status_code == 422


@pytest.mark.parametrize(
    ("route", "query", "storage"),
    [
        ("/API/firstSetup", {"machine": "m|a,1/b,2/c,3/d,4", "admin": 0}, "machines"),
        ("/API/sessionerror", {"machine": "m", "session": "s", "errorcode": 300}, "sessions"),
    ],
)
def test_storage_failure_does_not_acknowledge_a_lost_report(client, tmp_path, route, query, storage):
    (tmp_path / storage).write_text("not a directory")
    assert client.get(route, query_string=query).status_code == 500
