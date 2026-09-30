import json
import re
from io import BytesIO
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

import pytest

from picobrew_server import create_app
from picobrew_server.beerxml.picobrew_parser import PicoBrewRecipeParser
from picobrew_server.beerxml.program_editor import revision


@pytest.fixture
def library(tmp_path):
    directory = tmp_path / "recipes"
    directory.mkdir()
    return directory


@pytest.fixture
def client(library):
    return create_app({"TESTING": True, "SECRET_KEY": "test", "UPLOAD_FOLDER": str(library)}).test_client()


def xml():
    return b"""<RECIPES>
      <RECIPE><NAME>First Ale</NAME><BREWER>A brewer</BREWER><NOTES>Keep these notes &amp; details</NOTES>
        <BATCH_SIZE>9.5</BATCH_SIZE><ABV>5.4</ABV><IBU>32</IBU>
        <FERMENTABLES><FERMENTABLE><NAME>Pale malt</NAME><AMOUNT>2</AMOUNT></FERMENTABLE></FERMENTABLES>
        <CUSTOM attribute="keep">Unknown recipe extension</CUSTOM><!-- keep this comment -->
        <KEGSMART><STEPS><STEP><NAME>Ferment</NAME><TEMP>18</TEMP><TIME>7</TIME></STEP></STEPS></KEGSMART>
      </RECIPE>
      <RECIPE><NAME>Second Ale</NAME><ZYMATIC><MASH_TEMP>67</MASH_TEMP><CUSTOM>Machine metadata</CUSTOM>
        <STEP><NAME>Original</NAME><TEMP>67</TEMP><TIME>60</TIME><LOCATION>Mash</LOCATION><DRAIN>5</DRAIN></STEP>
      </ZYMATIC></RECIPE>
    </RECIPES>"""


def url(scope="library", file="ale.xml", index=0, batch=None):
    values = {"scope": scope, "file": file, "recipe": index}
    if batch is not None:
        values["batch"] = batch
    return "/program?" + urlencode(values)


def form(client, target):
    response = client.get(target)
    assert response.status_code == 200
    csrf = re.search(r'name="csrf" value="([^"]+)"', response.text)
    digest = re.search(r'name="revision" value="([^"]+)"', response.text)
    assert csrf is not None and digest is not None
    return {
        "csrf": csrf[1],
        "revision": digest[1],
        "step_name": ["Heat", "Mash", "Hop addition"],
        "step_temp": ["67", "67", "97"],
        "step_time": ["0", "60", "10"],
        "step_location": ["PassThrough", "Mash", "Adjunct2"],
        "step_drain": ["0", "5", "2"],
    }


def stage(client):
    client.post("/upload", data={"recipes": (BytesIO(xml()), "ale.xml")})
    with client.session_transaction() as session:
        return session["pending_import"]


def test_add_program_persists_all_fields_and_machine_feed(client, library):
    path = library / "ale.xml"
    path.write_bytes(xml())
    target = url()
    response = client.post(target, data=form(client, target))
    assert response.location.endswith("/")
    recipe = PicoBrewRecipeParser().parse(path)[0]
    assert [step.serialize() for step in recipe.steps] == [
        "Heat,67,0,0,0",
        "Mash,67,60,1,5",
        "Hop addition,97,10,3,2",
    ]
    assert (
        "Heat,67,0,0,0/Mash,67,60,1,5/Hop addition,97,10,3,2"
        in client.get("/API/SyncUser?user=test&machine=Zymatic").text
    )
    assert recipe.filename == "ale.xml"
    assert (recipe.abv, recipe.ibu, recipe.batch_size) == (5.4, 32, 9.5)
    assert recipe.fermentables[0].name == "Pale malt"
    assert "source_file" not in path.read_text()
    assert not list(library.glob(".*"))


def test_only_selected_program_changes_in_multi_recipe_file(client, library):
    path = library / "ale.xml"
    path.write_bytes(xml())
    before = ET.fromstring(xml())
    ET.indent(before, space="  ")
    target = url(index=1)
    data = form(client, target)
    # Reordering and removal are represented by the submitted row order.
    for key in ["name", "temp", "time", "location", "drain"]:
        values = data[f"step_{key}"]
        data[f"step_{key}"] = [values[2], values[0]]
    assert client.post(target, data=data).status_code == 302
    after = ET.fromstring(path.read_bytes())
    assert ET.tostring(before[0]).split() == ET.tostring(after[0]).split()
    recipes = PicoBrewRecipeParser().parse(path)
    assert not recipes[0].steps
    assert [step.name for step in recipes[1].steps] == ["Hop addition", "Heat"]
    assert after[1].findtext("ZYMATIC/MASH_TEMP") == "67"
    assert after[1].findtext("ZYMATIC/CUSTOM") == "Machine metadata"


def test_write_preserves_unknown_tags_comments_and_kegsmart(client, library):
    path = library / "ale.xml"
    path.write_bytes(xml())
    target = url()
    client.post(target, data=form(client, target))
    root = ET.fromstring(path.read_bytes())
    custom = root[0].find("CUSTOM")
    assert custom is not None
    assert custom.attrib == {"attribute": "keep"}
    assert root[0].findtext("CUSTOM") == "Unknown recipe extension"
    assert root[0].findtext("NOTES") == "Keep these notes & details"
    assert root[0].findtext("KEGSMART/STEPS/STEP/NAME") == "Ferment"
    assert "<!-- keep this comment -->" in path.read_text()
    assert root[1].find("ZYMATIC") is not None


def test_import_editor_saves_staged_file_until_confirmation(client, library):
    batch = stage(client)
    path = library / ".pending" / batch / "ale.xml"
    target = url("import", batch=batch)
    response = client.post(target, data=form(client, target))
    assert response.location.endswith("/validate")
    assert len(PicoBrewRecipeParser().parse(path)[0].steps) == 3
    assert "Hop addition" in client.get("/validate").text
    assert client.get("/API/SyncUser?user=test&machine=Zymatic").text == "#|#"
    client.post("/submit_eula", data={"action": "continue", "accept_eula": "on"})
    assert len(PicoBrewRecipeParser().parse(library / "ale.xml")[0].steps) == 3


def test_cancel_import_discards_edited_program(client, library):
    batch = stage(client)
    target = url("import", batch=batch)
    client.post(target, data=form(client, target))
    client.post("/submit_eula", data={"action": "cancel"})
    assert not list(library.glob("*.xml"))
    assert client.get(target).status_code == 404


def test_stale_import_editor_cannot_edit_replacement_batch(client):
    batch = stage(client)
    target = url("import", batch=batch)
    data = form(client, target)
    stage(client)
    assert client.post(target, data=data).status_code == 404


def test_conflicting_edit_retains_user_input_and_does_not_overwrite(client, library):
    path = library / "ale.xml"
    path.write_bytes(xml())
    target = url()
    data = form(client, target)
    external = xml().replace(b"First Ale", b"Updated elsewhere")
    path.write_bytes(external)
    response = client.post(target, data=data)
    assert response.status_code == 409
    assert "changed since you opened" in response.text
    assert 'value="Hop addition"' in response.text
    assert path.read_bytes() == external


def test_failed_atomic_replace_preserves_file_and_cleans_temporary_files(client, library, monkeypatch):
    path = library / "ale.xml"
    path.write_bytes(xml())
    target = url()
    data = form(client, target)

    def fail(*args):
        raise OSError("disk failure")

    monkeypatch.setattr("picobrew_server.beerxml.program_editor.os.replace", fail)
    response = client.post(target, data=data)
    assert response.status_code == 500
    assert path.read_bytes() == xml()
    assert [file.name for file in library.iterdir()] == ["ale.xml"]


def test_busy_file_lock_is_not_removed_by_another_editor(client, library):
    path = library / "ale.xml"
    path.write_bytes(xml())
    target = url()
    data = form(client, target)
    lock = library / ".ale.xml.program-lock"
    lock.write_text("another writer")
    response = client.post(target, data=data)
    assert response.status_code == 409
    assert "Another editor is saving" in response.text
    assert lock.read_text() == "another writer"
    assert path.read_bytes() == xml()


def test_empty_program_cannot_accidentally_remove_existing_steps(client, library):
    path = library / "ale.xml"
    path.write_bytes(xml())
    target = url(index=1)
    data = form(client, target)
    data = {key: value for key, value in data.items() if not key.startswith("step_")}
    response = client.post(target, data=data)
    assert response.status_code == 422
    assert "Add at least one step" in response.text
    assert path.read_bytes() == xml()


@pytest.mark.parametrize(
    "field,value",
    [
        ("step_name", ""),
        ("step_name", "Bad/name"),
        ("step_name", "Bad,name"),
        ("step_location", "Unknown"),
        ("step_temp", "nan"),
        ("step_temp", "111"),
        ("step_time", "-1"),
        ("step_time", "1.5"),
        ("step_drain", "inf"),
        ("step_drain", ""),
    ],
)
def test_invalid_steps_are_not_saved(client, library, field, value):
    path = library / "ale.xml"
    path.write_bytes(xml())
    target = url()
    data = form(client, target)
    data[field][0] = value
    response = client.post(target, data=data)
    assert response.status_code == 422
    assert "The program was not saved" in response.text
    assert path.read_bytes() == xml()


def test_csrf_and_incomplete_columns_are_rejected(client, library):
    path = library / "ale.xml"
    path.write_bytes(xml())
    target = url()
    data = form(client, target)
    csrf = data.pop("csrf")
    assert client.post(target, data=data).status_code == 400
    data["csrf"] = csrf
    data["step_drain"] = []
    assert client.post(target, data=data).status_code == 400
    assert path.read_bytes() == xml()


@pytest.mark.parametrize(
    "file,index", [("../outside.xml", 0), (".pending/ale.xml", 0), ("ale.xml", -1), ("ale.xml", 2), ("ale.xml", "bad")]
)
def test_editor_rejects_invalid_paths_and_indexes(client, library, file, index):
    (library / "ale.xml").write_bytes(xml())
    (library.parent / "outside.xml").write_bytes(xml())
    assert client.get(url(file=file, index=index)).status_code == 404


def test_nested_library_files_have_distinct_edit_links_and_symlinks_are_rejected(client, library):
    nested = library / "nested"
    nested.mkdir()
    (nested / "ale.xml").write_bytes(xml())
    target = url(file="nested/ale.xml", index=1)
    assert client.get(target).status_code == 200
    assert "file=nested/ale.xml" in client.get("/").text
    (library / "link.xml").symlink_to(nested / "ale.xml")
    assert client.get(url(file="link.xml")).status_code == 404


def test_latin1_file_stays_readable_after_saving(client, library):
    path = library / "ale.xml"
    source = '<?xml version="1.0" encoding="iso-8859-1"?>' + xml().decode().replace("First Ale", "Helles Märzen")
    path.write_bytes(source.encode("iso-8859-1"))
    target = url()
    data = form(client, target)
    assert client.post(target, data=data).status_code == 302
    assert PicoBrewRecipeParser().parse(path)[0].name == "Helles Märzen"
    assert revision(path.read_bytes()) != data["revision"]


def test_live_checks_are_advisory_and_do_not_change_the_file(client, library):
    path = library / "ale.xml"
    path.write_bytes(xml())
    target = url()
    data = form(client, target)
    rows = [
        {field: data[f"step_{field}"][i] for field in ["name", "temp", "time", "location", "drain"]} for i in [2, 1, 0]
    ]
    check = target.replace("/program?", "/program/check?")
    response = client.post(check, json={"rows": rows})
    assert response.status_code == 200
    assert any("before mashing" in item["message"] for item in response.json["warnings"])
    assert path.read_bytes() == xml()
    for field in ["name", "temp", "time", "location", "drain"]:
        data[f"step_{field}"] = [r[field] for r in rows]
    assert client.post(target, data=data).status_code == 302
    assert "advisory warning" in client.get("/").text
    assert PicoBrewRecipeParser().parse(path)[0].steps[0].name == "Hop addition"


def test_template_draft_can_be_saved_from_import_editor(client, library):
    batch = stage(client)
    target = url("import", batch=batch)
    response = client.get(target)
    payload = re.search(r'id="program-templates-data">(.*?)</script>', response.text, re.S)
    assert payload is not None
    templates = json.loads(payload[1])
    assert {"recipe", "single", "multi"}.issubset({template["id"] for template in templates})
    starter = next(template for template in templates if template["id"] == "single")
    data = form(client, target)
    for field in ["name", "temp", "time", "location", "drain"]:
        data[f"step_{field}"] = [r[field] for r in starter["rows"]]
    path = library / ".pending" / batch / "ale.xml"
    assert not PicoBrewRecipeParser().parse(path)[0].steps
    assert client.post(target, data=data).status_code == 302
    restored = PicoBrewRecipeParser().parse(path)[0]
    assert len(restored.steps) == len(starter["rows"])
    assert restored.steps[1].temp == 67
    assert restored.steps[1].time == 90
    assert not (library / "ale.xml").exists()


def test_check_endpoint_rejects_malformed_rows_and_stale_import_scope(client, library):
    (library / "existing.xml").write_bytes(xml())
    target = url(file="existing.xml").replace("/program?", "/program/check?")
    assert client.post(target, json={"rows": [{}]}).status_code == 400
    assert client.post(target, json={"rows": "wrong"}).status_code == 400
    batch = stage(client)
    target = url("import", batch=batch).replace("/program?", "/program/check?")
    client.post("/submit_eula", data={"action": "cancel"})
    assert client.post(target, json={"rows": []}).status_code == 404
