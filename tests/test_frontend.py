from io import BytesIO
from pathlib import Path

import pytest

from picobrew_server import create_app
from picobrew_server.beerxml.picobrew_program_step import PicoBrewProgramStep, PicoBrewZymaticProgram
from picobrew_server.beerxml.picobrew_recipe import PicoBrewRecipe


def recipe_xml(*names, program=True):
    steps = [PicoBrewProgramStep(name="Mash", temp=67, time=60, location="Mash", drain=5)]
    recipes = [
        PicoBrewRecipe(name=name, zymatic=PicoBrewZymaticProgram(steps=steps) if program else None) for name in names
    ]
    documents = [recipe.to_xml(skip_empty=True) for recipe in recipes]
    return b"<RECIPES>" + b"".join(xml.encode() if isinstance(xml, str) else xml for xml in documents) + b"</RECIPES>"


@pytest.fixture
def library(tmp_path):
    directory = tmp_path / "recipes"
    directory.mkdir()
    return directory


@pytest.fixture
def client(library):
    return create_app({"TESTING": True, "SECRET_KEY": "test", "UPLOAD_FOLDER": str(library)}).test_client()


def upload(client, *files):
    return client.post("/upload", data={"recipes": [(BytesIO(data), name) for name, data in files]})


def test_homepage_reports_availability_without_claiming_sync(client, library):
    (library / "available.xml").write_bytes(recipe_xml("Available Ale"))
    (library / "missing.xml").write_bytes(recipe_xml("Plain BeerXML", program=False))
    response = client.get("/")
    assert response.status_code == 200
    assert "Recipe library" in response.text
    assert "<strong>2</strong> recipes" in response.text
    assert "<strong>1</strong> available to machine" in response.text
    assert "synced" not in response.text.lower()
    assert client.get("/recipes").status_code == 200
    assert client.get("/import").status_code == 200


def test_empty_library_and_missing_review_are_useful(client):
    assert "Import your first recipe" in client.get("/").text
    response = client.get("/validate")
    assert response.status_code == 302
    assert response.location.endswith("/import")
    assert client.post("/submit_eula").location.endswith("/import")


def test_batch_review_includes_every_recipe_and_stays_out_of_machine_feed(client, library):
    response = upload(
        client,
        ("one.xml", recipe_xml("First Ale", "Second Ale")),
        ("two.BEERXML", recipe_xml("Third Ale")),
    )
    assert response.location.endswith("/validate")
    review = client.get("/validate")
    assert review.status_code == 200
    assert all(name in review.text for name in ["First Ale", "Second Ale", "Third Ale"])
    assert "3 recipes ready for review" in review.text
    assert not list(library.glob("*.xml"))
    assert client.get("/API/SyncUser?user=test&machine=Zymatic").text == "#|#"
    assert "Import your first recipe" in client.get("/").text
    response = client.post("/submit_eula", data={"action": "continue", "accept_eula": "on"})
    assert response.location.endswith("/")
    assert sorted(file.name for file in library.iterdir() if file.is_file()) == ["one.xml", "two.BEERXML"]
    assert "Added 3 recipes" in client.get("/").text
    assert "Third Ale" in client.get("/API/SyncUser?user=test&machine=Zymatic").text
    assert not list((library / ".pending").iterdir())


def test_confirmation_is_required_on_server(client, library):
    upload(client, ("ale.xml", recipe_xml("Ale")))
    response = client.post("/submit_eula", data={"action": "continue"})
    assert response.location.endswith("/validate")
    assert not (library / "ale.xml").exists()
    assert "confirm the checkbox" in client.get("/validate").text


def test_cancel_only_discards_staged_files(client, library):
    original = recipe_xml("Original")
    (library / "original.xml").write_bytes(original)
    upload(client, ("new.xml", recipe_xml("New")))
    response = client.post("/submit_eula", data={"action": "cancel"})
    assert response.location.endswith("/import")
    assert (library / "original.xml").read_bytes() == original
    assert not (library / "new.xml").exists()
    assert not list((library / ".pending").iterdir())


def test_bad_files_and_duplicate_names_do_not_overwrite_library(client, library):
    original = recipe_xml("Original")
    (library / "ale.xml").write_bytes(original)
    response = upload(
        client,
        ("ale.xml", recipe_xml("Replacement")),
        ("broken.xml", b"not XML"),
        ("empty.xml", b"<RECIPES/>"),
        ("notes.txt", b"not a recipe"),
    )
    assert response.location.endswith("/import")
    page = client.get("/import")
    assert page.status_code == 200
    assert "already exists" in page.text
    assert "no readable recipes" in page.text
    assert "choose a BeerXML file" in page.text
    assert (library / "ale.xml").read_bytes() == original
    assert not list((library / ".pending").iterdir())


def test_valid_files_can_be_reviewed_alongside_rejected_files(client):
    upload(client, ("good.xml", recipe_xml("Good")), ("bad.xml", b"broken"))
    review = client.get("/validate")
    assert "Good" in review.text
    assert "bad.xml: no readable recipes" in review.text
    assert "1 recipe ready for review" in review.text


def test_library_only_import_is_explicit(client, library):
    upload(client, ("plain.xml", recipe_xml("Plain", program=False)))
    assert "Missing machine program" in client.get("/validate").text
    client.post("/submit_eula", data={"accept_eula": "on", "action": "continue"})
    assert (library / "plain.xml").exists()
    assert "0 available to your machine" in client.get("/").text
    assert client.get("/API/SyncUser?user=test&machine=Zymatic").text == "#|#"


def test_new_filename_collision_rolls_back_batch_without_overwriting(client, library):
    upload(client, ("a.xml", recipe_xml("A")), ("b.xml", recipe_xml("B")))
    original = recipe_xml("Created during review")
    (library / "b.xml").write_bytes(original)
    response = client.post("/submit_eula", data={"accept_eula": "on", "action": "continue"})
    assert response.location.endswith("/validate")
    assert not (library / "a.xml").exists()
    assert (library / "b.xml").read_bytes() == original
    assert len(list((library / ".pending").glob("*/*.xml"))) == 2


def test_partial_storage_failure_does_not_publish_a_partial_batch(client, library, monkeypatch):
    upload(client, ("a.xml", recipe_xml("A")), ("b.xml", recipe_xml("B")))
    original_link = Path.hardlink_to

    def fail_second(destination, source):
        if destination.name == "b.xml":
            raise OSError("disk error")
        original_link(destination, source)

    monkeypatch.setattr(Path, "hardlink_to", fail_second)
    response = client.post("/submit_eula", data={"accept_eula": "on", "action": "continue"})
    assert response.location.endswith("/validate")
    assert not list(library.glob("*.xml"))


def test_recipe_content_is_escaped(client, library):
    (library / "escaped.xml").write_bytes(recipe_xml('<script>alert("x")</script>'))
    page = client.get("/")
    assert page.status_code == 200
    assert '<script>alert("x")</script>' not in page.text
    assert "&lt;script&gt;" in page.text
