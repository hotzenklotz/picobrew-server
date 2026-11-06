import json
import re
import sqlite3
from pathlib import Path

import pytest

from picobrew_server import create_app
from picobrew_server.beerxml.picobrew_parser import PicoBrewRecipeParser
from picobrew_server.beerxml.picobrew_program_step import PicoBrewProgramStep, PicoBrewZymaticProgram
from picobrew_server.beerxml.picobrew_recipe import PicoBrewRecipe
from picobrew_server.blueprints import picobrew_api as api
from picobrew_server.session_store import BrewSessionStore


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "MACHINE_PATH", str(tmp_path / "machines"))
    return create_app(
        {
            "TESTING": True,
            "BREW_DATABASE": str(tmp_path / "sessions" / "brew_sessions.sqlite3"),
            "LEGACY_SESSION_PATH": str(tmp_path / "sessions"),
        }
    ).test_client()


def store(tmp_path):
    return BrewSessionStore(tmp_path / "sessions" / "brew_sessions.sqlite3")


def test_firmware_check_reports_no_update(client):
    response = client.get(
        "/API/zymaticFirmwareCheck", query_string={"machine": "500000000000", "ver": 1, "maj": 1, "min": 14}
    )
    assert response.status_code == 200
    assert response.data == b"#F#"


@pytest.mark.parametrize("route", ["/API/SyncUser", "/API/SyncUSer"])
def test_sync_converts_celsius_and_preserves_fahrenheit_exports(client, monkeypatch, route):
    parser = PicoBrewRecipeParser()
    recipes = [parser.parse(Path(__file__).parents[1] / "picobrew_server" / "recipes" / "Party_Porter.xml")[0]]
    recipes.append(
        PicoBrewRecipe(
            name="Fahrenheit Ale",
            filename="fahrenheit.xml",
            zymatic=PicoBrewZymaticProgram(
                steps=[
                    PicoBrewProgramStep(name="Mash", temp=152, time=60, location="Mash", drain=5),
                    PicoBrewProgramStep(name="Chill", temp=65, time=10, location="PassThrough", drain=10),
                ]
            ),
        )
    )
    before = [recipe.model_dump() for recipe in recipes]
    monkeypatch.setattr(api, "get_recipes", lambda: recipes)
    response = client.get(route, query_string={"user": "test", "machine": "Zymatic"})
    assert response.status_code == 200
    porter, fahrenheit = response.text.strip("#").split("|")[:2]
    assert "Heat to Single S...,153,0,0,0" in porter
    assert "Boil Adjunct 1,207,60,2,5" in porter
    assert "Chill,64,10,0,10" in porter
    assert fahrenheit == f"Fahrenheit Ale/{recipes[1].id}/Mash,152,60,1,5/Chill,65,10,0,10/"
    assert client.get(route, query_string={"user": "test", "machine": "Zymatic"}).data == response.data
    assert [recipe.model_dump() for recipe in recipes] == before


@pytest.mark.parametrize(
    "marker,metadata,temperatures,expected",
    [
        ("", "", [39, 67, 97, 18, 0], [102, 153, 207, 64, 0]),
        ("", "", [102, 152, 207, 65, 0], [102, 152, 207, 65, 0]),
        ("", "<BOIL_TEMP>207</BOIL_TEMP>", [65, 0], [65, 0]),
        ("", "<BOIL_TEMP>unknown</BOIL_TEMP>", [67, 0], [153, 0]),
        ("<TEMPERATURE_UNIT>F</TEMPERATURE_UNIT>", "", [65, 0], [65, 0]),
        ("<TEMPERATURE_UNIT>C</TEMPERATURE_UNIT>", "<BOIL_TEMP>207</BOIL_TEMP>", [67, 0], [153, 0]),
    ],
)
def test_sync_resolves_units_for_entire_program(
    client, monkeypatch, tmp_path, marker, metadata, temperatures, expected
):
    steps = "".join(
        f"<STEP><NAME>Step {i}</NAME><TEMP>{temp}</TEMP><TIME>10</TIME>"
        "<LOCATION>PassThrough</LOCATION><DRAIN>5</DRAIN></STEP>"
        for i, temp in enumerate(temperatures)
    )
    document = f"<RECIPES><RECIPE><NAME>Ale</NAME><ZYMATIC>{marker}{steps}{metadata}</ZYMATIC></RECIPE></RECIPES>"
    path = tmp_path / "ale.xml"
    path.write_text(document)
    recipes = PicoBrewRecipeParser().parse(path)
    monkeypatch.setattr(api, "get_recipes", lambda: recipes)
    response = client.get("/API/SyncUser?user=test&machine=Zymatic")
    expected_steps = "/".join(f"Step {i},{temp},10,0,5" for i, temp in enumerate(expected))
    assert response.text == f"#Ale/{recipes[0].id}/{expected_steps}/|#"
    assert path.read_text() == document


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
    saved_session = store(tmp_path).get_session(session_id)
    assert saved_session is not None and saved_session["recovery_snapshot"] == snapshot

    for code in (303, 305):
        response = client.get(
            "/API/sessionerror", query_string={"machine": "500000000000", "session": session_id, "errorcode": code}
        )
        assert response.status_code == 200
        assert response.data == b""
    events = store(tmp_path).get_errors(session_id)
    assert sorted(event["errorcode"] for event in events) == [303, 305]
    assert all(event["machine_id"] == "500000000000" for event in events)
    assert all(event["reported_at"] for event in events)
    session = store(tmp_path).get_session(session_id)
    assert session is not None
    assert (session["recovery_snapshot"], session["ended_at"]) == (snapshot, None)
    response = client.get("/API/recoversession", query_string={"session": session_id, "code": 1})
    assert response.status_code == 200
    assert response.text == f"#{snapshot}#"


@pytest.mark.parametrize("session", ["unknown-session", "", "../escaped"])
def test_error_report_does_not_require_an_existing_session(client, tmp_path, session):
    response = client.get(
        "/API/sessionerror", query_string={"machine": "500000000000", "session": session, "errorcode": 300}
    )
    assert response.status_code == 200
    assert [event["errorcode"] for event in store(tmp_path).get_errors(session)] == [300]
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


def make_program_recipe(name, filename="ale.xml", index=0, temp=152):
    return PicoBrewRecipe(
        name=name,
        filename=filename,
        source_file=f"/library/{filename}",
        source_index=index,
        zymatic=PicoBrewZymaticProgram(
            steps=[PicoBrewProgramStep(name=f"{name} Mash", temp=temp, time=60, location="Mash", drain=5)]
        ),
    )


def start_session(client, recipe_id, user=api.LOCAL_USER):
    response = client.get(
        "/API/logSession",
        query_string={"user": user, "recipe": recipe_id, "code": 0, "machine": "500000000000", "firm": "1.1.14"},
    )
    assert response.status_code == 200
    assert re.fullmatch(r"#[0-9a-f]{32}#", response.text)
    return response.text.strip("#")


def sync(client, user=api.LOCAL_USER):
    return client.get("/API/SyncUser", query_string={"user": user, "machine": "500000000000"}).text


@pytest.mark.parametrize(
    "route",
    [
        "/API/logsession?session=0123456789abcdef0123456789abcdef&code=abc",
        "/API/recoversession?session=0123456789abcdef0123456789abcdef&code=2",
        "/API/logsession?code=1",
        "/API/doesNotExist",
        "/API/SyncUser?user=x&machine=m",
    ],
)
def test_machine_api_errors_never_contain_a_payload_delimiter(client, monkeypatch, route):
    def broken():
        raise RuntimeError("library unavailable")

    monkeypatch.setattr(api, "get_recipes", broken)
    response = client.get(route)
    assert response.status_code >= 400
    assert b"#" not in response.data
    assert response.mimetype == "text/plain"


def test_html_error_pages_are_kept_for_the_browser(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert response.mimetype == "text/html"


@pytest.mark.parametrize("session", ["0123456789abcdef0123456789abcdef", "not-a-session", "../escaped", ""])
def test_recovery_without_a_snapshot_reports_none(client, tmp_path, session):
    (tmp_path / "escaped.json").write_text(json.dumps({"machine_state": "1/2/3/4/5/6/0/1"}))
    response = client.get("/API/recoversession", query_string={"session": session, "code": 1})
    assert response.status_code == 200
    assert response.text == "#!#"


def test_recovery_before_the_first_temperature_log_reports_none(client, monkeypatch):
    monkeypatch.setattr(api, "get_recipes", lambda: [])
    session_id = start_session(client, "recipe-id")
    assert client.get("/API/recoversession", query_string={"session": session_id, "code": 1}).text == "#!#"


def test_temperatures_before_any_step_event_keep_the_reset_point(client, tmp_path, monkeypatch):
    monkeypatch.setattr(api, "get_recipes", lambda: [])
    session_id = start_session(client, "recipe-id")
    snapshot = "2/600000/500000/500000/550000/0/0/1"
    response = client.get(
        "/API/LogSession",
        query_string={"session": session_id, "data": "2/150|1/160|3/90|4/158", "code": 2, "step": snapshot, "state": 0},
    )
    assert response.status_code == 200
    session = store(tmp_path).get_session(session_id)
    assert session is not None and session["recovery_snapshot"] == snapshot
    [reading] = store(tmp_path).get_readings(session_id)
    assert reading["step_id"] is None
    assert [reading[f"sensor_{i}"] for i in (2, 1, 3, 4)] == [150, 160, 90, 158]
    assert client.get("/API/recoversession", query_string={"session": session_id, "code": 1}).text == f"#{snapshot}#"


def test_malformed_snapshot_is_not_handed_back_to_the_machine(client, monkeypatch):
    monkeypatch.setattr(api, "get_recipes", lambda: [])
    session_id = start_session(client, "recipe-id")
    client.get("/API/LogSession", query_string={"session": session_id, "data": "2/150", "code": 2, "step": "None"})
    assert client.get("/API/recoversession", query_string={"session": session_id, "code": 1}).text == "#!#"


def test_recovery_returns_the_program_the_session_started_with(client, monkeypatch):
    first = make_program_recipe("First", filename="pair.xml", index=0, temp=150)
    second = make_program_recipe("Second", filename="pair.xml", index=1, temp=160)
    recipes = [first, second]
    monkeypatch.setattr(api, "get_recipes", lambda: recipes)

    records = sync(client).strip("#").split("|")[:2]
    second_id = records[1].split("/")[1]
    assert records[0].split("/")[1] != second_id
    session_id = start_session(client, second_id)

    recipes.clear()  # later edits or deletions must not change recovery
    response = client.get("/API/recoversession", query_string={"session": session_id, "code": 0})
    assert response.text == f"#{records[1]}|!#"


def test_cleaning_sessions_can_be_recovered(client, monkeypatch):
    monkeypatch.setattr(api, "get_recipes", lambda: [])
    cleaning = sync(client, user=api.SYSTEM_USER).strip("#").split("|")[0]
    session_id = start_session(client, cleaning.split("/")[1], user=api.SYSTEM_USER)
    response = client.get("/API/recoversession", query_string={"session": session_id, "code": 0})
    assert response.text == f"#{cleaning}|!#"


def test_sessions_from_older_versions_recover_by_recipe_id(client, tmp_path, monkeypatch):
    recipe = make_program_recipe("Ale")
    monkeypatch.setattr(api, "get_recipes", lambda: [recipe])
    session_id = "0123456789abcdef0123456789abcdef"
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / f"{session_id}.json").write_text(json.dumps({"recipe_id": recipe.id, "steps": []}))
    response = client.get("/API/recoversession", query_string={"session": session_id, "code": 0})
    assert response.text == f"#{recipe.serialize()}|!#"


def test_unknown_recovery_recipe_is_an_error_without_payload(client, monkeypatch):
    monkeypatch.setattr(api, "get_recipes", lambda: [])
    session_id = start_session(client, "recipe-id")
    response = client.get("/API/recoversession", query_string={"session": session_id, "code": 0})
    assert response.status_code == 404
    assert b"#" not in response.data


@pytest.mark.parametrize("session", ["../escaped", "0123456789ABCDEF0123456789ABCDEF", "abc"])
def test_logging_rejects_session_ids_that_are_not_ours(client, tmp_path, session):
    escaped = tmp_path / "escaped.json"
    escaped.write_text(json.dumps({"steps": []}))
    response = client.get("/API/logsession", query_string={"session": session, "code": 3})
    assert response.status_code == 422
    assert json.loads(escaped.read_text()) == {"steps": []}


def test_session_logs_are_stored_with_the_machine_details(client, tmp_path, monkeypatch):
    monkeypatch.setattr(api, "get_recipes", lambda: [])
    session_id = start_session(client, "recipe-id")
    client.get("/API/logsession", query_string={"session": session_id, "code": 1, "data": "Mash", "state": 0})
    client.get("/API/logsession", query_string={"session": session_id, "code": 3})
    assert [step["name"] for step in store(tmp_path).get_steps(session_id)] == ["Mash"]
    session = store(tmp_path).get_session(session_id)
    assert session is not None
    assert (session["machine_id"], session["firmware"], session["status"]) == ("500000000000", "1.1.14", "completed")


def test_session_database_failure_is_not_acknowledged(client, tmp_path, monkeypatch):
    monkeypatch.setattr(api, "get_recipes", lambda: [])
    session_id = start_session(client, "recipe-id")

    def broken(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(BrewSessionStore, "record_reading", broken)
    response = client.get("/API/LogSession", query_string={"session": session_id, "code": 2, "data": "2/150"})
    assert response.status_code == 500
    assert b"#" not in response.data


def test_empty_library_is_an_empty_list(client, monkeypatch):
    monkeypatch.setattr(api, "get_recipes", lambda: [])
    assert sync(client) == "##"


def test_checksync_always_requests_a_reload(client):
    response = client.get("/API/checksync", query_string={"user": api.LOCAL_USER})
    assert response.text == "#T#"
    assert not response.text.strip("#").startswith("!")


def test_first_setup_tolerates_the_stray_byte_after_the_last_index(client, tmp_path):
    machine = "500000000000|aa,1/bb,2/cc,3/dd,4\x01"
    response = client.get("/API/firstSetup", query_string={"machine": machine, "admin": 0})
    assert response.status_code == 200
    [record] = (tmp_path / "machines").glob("*.json")
    assert json.loads(record.read_text())["sensors"] == {"1": "aa", "2": "bb", "3": "cc", "4": "dd"}


@pytest.mark.parametrize("content", ['{"recipe_id": "x", "steps": [', "[]", '{"recipe_id": "x"}', "\udcff"])
def test_corrupt_session_files_are_treated_as_unknown(client, tmp_path, content):
    session_id = "0123456789abcdef0123456789abcdef"
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / f"{session_id}.json").write_bytes(content.encode("utf-8", "surrogateescape"))
    assert client.get("/API/recoversession", query_string={"session": session_id, "code": 1}).text == "#!#"
    assert client.get("/API/recoversession", query_string={"session": session_id, "code": 0}).status_code == 404
    response = client.get("/API/logsession", query_string={"session": session_id, "code": 2, "data": "2/150"})
    assert response.status_code == 404


def test_oversized_snapshot_fields_are_not_handed_back_to_the_machine(client, monkeypatch):
    monkeypatch.setattr(api, "get_recipes", lambda: [])
    session_id = start_session(client, "recipe-id")
    step = "1/2/3/4/5/6/7/" + "9" * 40
    client.get("/API/LogSession", query_string={"session": session_id, "data": "2/150", "code": 2, "step": step})
    assert client.get("/API/recoversession", query_string={"session": session_id, "code": 1}).text == "#!#"
