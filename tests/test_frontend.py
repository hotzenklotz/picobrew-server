import os
import re
import time
from io import BytesIO
from pathlib import Path

import pytest

from picobrew_server import create_app
from picobrew_server.beerxml.picobrew_program_step import PicoBrewProgramStep, PicoBrewZymaticProgram
from picobrew_server.beerxml.picobrew_recipe import PicoBrewRecipe


def recipe_xml(*names, program=True):
    """Build a BeerXML batch with optional machine programs for frontend tests."""
    steps = [PicoBrewProgramStep(name="Mash", temp=67, time=60, location="Mash", drain=5)]
    recipes = [
        PicoBrewRecipe(name=name, zymatic=PicoBrewZymaticProgram(steps=steps) if program else None) for name in names
    ]
    documents = [recipe.to_xml(skip_empty=True) for recipe in recipes]
    return b"<RECIPES>" + b"".join(xml.encode() if isinstance(xml, str) else xml for xml in documents) + b"</RECIPES>"


@pytest.fixture
def library(tmp_path):
    """Create an isolated recipe directory for each test."""
    directory = tmp_path / "recipes"
    directory.mkdir()
    return directory


@pytest.fixture
def client(library):
    """Create a Flask test client with a stable signing key and isolated library."""
    return create_app({"TESTING": True, "SECRET_KEY": "test", "UPLOAD_FOLDER": str(library)}).test_client()


def upload(client, *files):
    """Send named byte streams through the multipart recipe upload endpoint."""
    return client.post("/upload", data={"recipes": [(BytesIO(data), name) for name, data in files]})


def test_homepage_reports_availability_without_claiming_sync(client, library):
    """The library reports program availability without claiming device synchronization."""
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
    """Empty libraries and missing pending batches lead to the import flow."""
    assert "Import your first recipe" in client.get("/").text
    response = client.get("/validate")
    assert response.status_code == 302
    assert response.location.endswith("/import")
    assert client.post("/submit_eula").location.endswith("/import")


def test_batch_review_includes_every_recipe_and_stays_out_of_machine_feed(client, library):
    """A batch stays hidden until acceptance and then publishes every reviewed recipe."""
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
    """The server keeps recipes staged when the acceptance checkbox is missing."""
    upload(client, ("ale.xml", recipe_xml("Ale")))
    response = client.post("/submit_eula", data={"action": "continue"})
    assert response.location.endswith("/validate")
    assert not (library / "ale.xml").exists()
    assert "confirm the checkbox" in client.get("/validate").text


def test_cancel_only_discards_staged_files(client, library):
    """Cancelling an import preserves existing published recipes."""
    original = recipe_xml("Original")
    (library / "original.xml").write_bytes(original)
    upload(client, ("new.xml", recipe_xml("New")))
    response = client.post("/submit_eula", data={"action": "cancel"})
    assert response.location.endswith("/import")
    assert (library / "original.xml").read_bytes() == original
    assert not (library / "new.xml").exists()
    assert not list((library / ".pending").iterdir())


def test_bad_files_and_duplicate_names_do_not_overwrite_library(client, library):
    """Rejected uploads leave existing recipes intact and explain each rejection."""
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
    """One invalid upload does not prevent review of other valid files."""
    upload(client, ("good.xml", recipe_xml("Good")), ("bad.xml", b"broken"))
    review = client.get("/validate")
    assert "Good" in review.text
    assert "bad.xml: no readable recipes" in review.text
    assert "1 recipe ready for review" in review.text


def test_library_only_import_is_explicit(client, library):
    """Recipes without machine programs can be imported with clear availability feedback."""
    upload(client, ("plain.xml", recipe_xml("Plain", program=False)))
    assert "Missing machine program" in client.get("/validate").text
    client.post("/submit_eula", data={"accept_eula": "on", "action": "continue"})
    assert (library / "plain.xml").exists()
    assert "0 available to your machine" in client.get("/").text
    assert client.get("/API/SyncUser?user=test&machine=Zymatic").text == "#|#"


def test_new_filename_collision_rolls_back_batch_without_overwriting(client, library):
    """A collision arising during review rolls back earlier additions and preserves the existing file."""
    upload(client, ("a.xml", recipe_xml("A")), ("b.xml", recipe_xml("B")))
    original = recipe_xml("Created during review")
    (library / "b.xml").write_bytes(original)
    response = client.post("/submit_eula", data={"accept_eula": "on", "action": "continue"})
    assert response.location.endswith("/validate")
    assert not (library / "a.xml").exists()
    assert (library / "b.xml").read_bytes() == original
    assert len(list((library / ".pending").glob("*/*.xml"))) == 2


def test_partial_storage_failure_does_not_publish_a_partial_batch(client, library, monkeypatch):
    """A publication failure removes previously added files from the library."""
    upload(client, ("a.xml", recipe_xml("A")), ("b.xml", recipe_xml("B")))
    original_link = Path.hardlink_to

    def fail_second(destination, source):
        """Simulate a storage failure while publishing the second recipe."""
        if destination.name == "b.xml":
            raise OSError("disk error")
        original_link(destination, source)

    monkeypatch.setattr(Path, "hardlink_to", fail_second)
    response = client.post("/submit_eula", data={"accept_eula": "on", "action": "continue"})
    assert response.location.endswith("/validate")
    assert not list(library.glob("*.xml"))


def test_recipe_content_is_escaped(client, library):
    """Recipe names are escaped before appearing in rendered HTML."""
    (library / "escaped.xml").write_bytes(recipe_xml('<script>alert("x")</script>'))
    page = client.get("/")
    assert page.status_code == 200
    assert '<script>alert("x")</script>' not in page.text
    assert "&lt;script&gt;" in page.text


@pytest.mark.parametrize("route", ["/", "/recipes"])
def test_library_sorts_unnamed_recipes_and_matches_dialogs(client, library, route):
    """Missing names must not break sorting or change card-to-dialog associations."""
    (library / "mixed.xml").write_bytes(recipe_xml("Zebra", None, "alpha"))
    page = client.get(route)
    assert page.status_code == 200
    cards = re.findall(r'<h2 class="recipe-name">(.*?)</h2>.*?data-open-recipe="(.*?)"', page.text, re.S)
    dialogs = re.findall(r'<sl-dialog id="(.*?)" class="recipe-dialog" label="(.*?)">', page.text)
    assert cards == [("Untitled recipe", "recipe-1"), ("alpha", "recipe-2"), ("Zebra", "recipe-3")]
    assert dialogs == [(dialog_id, name) for name, dialog_id in cards]


def test_upload_removes_stale_batches_and_preserves_recent_and_unrelated_paths(client, library):
    """An upload expires old import batches without deleting recent batches or unrelated paths."""
    pending = library / ".pending"
    stale = pending / ("a" * 32)
    recent = pending / ("b" * 32)
    unrelated = pending / "unrelated"
    for directory in [stale, recent, unrelated]:
        directory.mkdir(parents=True)
        (directory / "ale.xml").write_bytes(recipe_xml("Ale"))
    old = time.time() - 2 * 24 * 60 * 60
    for directory in [stale, unrelated]:
        os.utime(directory, (old, old))
    outside = library / "originals"
    outside.mkdir()
    (outside / "original.xml").write_bytes(recipe_xml("Original"))
    symlink = pending / ("c" * 32)
    symlink.symlink_to(outside, target_is_directory=True)
    os.utime(outside, (old, old))

    response = upload(client, ("new.xml", recipe_xml("New")))
    assert response.location.endswith("/validate")
    assert not stale.exists()
    assert (recent / "ale.xml").exists()
    assert (unrelated / "ale.xml").exists()
    assert symlink.is_symlink()
    assert (outside / "original.xml").exists()
    assert "New" in client.get("/validate").text


def test_stale_cleanup_failure_does_not_block_other_cleanup_or_upload(client, library, monkeypatch, caplog):
    """Failure to remove one expired batch must not stop cleanup of others or new uploads."""
    from picobrew_server.blueprints import frontend

    stale = library / ".pending" / ("a" * 32)
    other = library / ".pending" / ("b" * 32)
    old = time.time() - 2 * 24 * 60 * 60
    for directory in [stale, other]:
        directory.mkdir(parents=True)
        (directory / "ale.xml").write_bytes(recipe_xml("Ale"))
        os.utime(directory, (old, old))
    original_remove = frontend.shutil.rmtree

    def fail_one(directory):
        """Simulate a storage error for just one expired import."""
        if directory == stale:
            raise OSError("cleanup denied")
        original_remove(directory)

    monkeypatch.setattr(frontend.shutil, "rmtree", fail_one)
    response = upload(client, ("new.xml", recipe_xml("New")))
    assert response.location.endswith("/validate")
    assert stale.exists()
    assert not other.exists()
    assert "Could not remove expired import" in caplog.text
    assert "New" in client.get("/validate").text


def test_second_upload_replaces_the_current_sessions_batch(client, library):
    """Uploading again replaces this session's batch while preserving another session's batch."""
    upload(client, ("first.xml", recipe_xml("First")))
    with client.session_transaction() as state:
        first = library / ".pending" / state["pending_import"]
    other_client = client.application.test_client()
    upload(other_client, ("other.xml", recipe_xml("Other")))
    with other_client.session_transaction() as state:
        other = library / ".pending" / state["pending_import"]
    upload(client, ("second.xml", recipe_xml("Second")))
    assert not first.exists()
    assert (other / "other.xml").exists()
    review = client.get("/validate")
    assert "Second" in review.text
    assert "First" not in review.text
    assert "Other" in other_client.get("/validate").text


@pytest.mark.parametrize("cleanup_error", [False, True], ids=["already-removed", "unlink-failed"])
def test_rollback_continues_after_missing_or_unremovable_destination(
    client, library, monkeypatch, caplog, cleanup_error
):
    """Rollback still removes later files when the first destination is missing or cannot be removed."""
    upload(client, *[(name + ".xml", recipe_xml(name)) for name in ["a", "b", "c"]])
    original_link = Path.hardlink_to
    original_unlink = Path.unlink

    def fail_third(destination, source):
        """Fail the final publication, optionally removing an earlier destination first."""
        if destination.name == "c.xml":
            if not cleanup_error:
                original_unlink(library / "a.xml")
            raise OSError("disk error")
        original_link(destination, source)

    def fail_first(destination, missing_ok=False):
        """Make only the first published destination impossible to remove."""
        if cleanup_error and destination == library / "a.xml":
            raise OSError("unlink denied")
        original_unlink(destination, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "hardlink_to", fail_third)
    monkeypatch.setattr(Path, "unlink", fail_first)
    response = client.post("/submit_eula", data={"accept_eula": "on", "action": "continue"})
    assert response.status_code == 302
    assert response.location.endswith("/validate")
    assert not (library / "b.xml").exists()
    assert not (library / "c.xml").exists()
    assert (library / "a.xml").exists() == cleanup_error
    assert len(list((library / ".pending").glob("*/*.xml"))) == 3
    if cleanup_error:
        assert "Could not roll back" in caplog.text
        assert "Some files may remain in your library" in client.get("/validate").text
    else:
        assert "Could not roll back" not in caplog.text
        assert "Could not add these files" in client.get("/validate").text
