"""Write machine steps without rewriting unrelated BeerXML recipe data."""

import hashlib
import os
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

from pybeerxml import Serializer

from picobrew_server.beerxml.picobrew_parser import PicoBrewRecipeParser
from picobrew_server.beerxml.picobrew_program_step import PicoBrewProgramStep, PicoBrewZymaticProgram


class ProgramConflictError(Exception):
    """The file has changed or another editor is currently saving it."""


def revision(document: bytes) -> str:
    return hashlib.sha256(document).hexdigest()


def save_program(path: Path, index: int, steps: list[PicoBrewProgramStep], expected_revision: str) -> None:
    # A per-file exclusive lock protects editors in different Flask workers.
    # The replacement stays on the same filesystem for an atomic write.
    lock = path.with_name(f".{path.name}.program-lock")
    try:
        lock_fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise ProgramConflictError("Another editor is saving this file. Please try again.") from error
    temporary: Path | None = None
    try:
        document = path.read_bytes()
        if revision(document) != expected_revision:
            raise ProgramConflictError("This file changed since you opened it. Reload the editor before saving.")
        recipes = PicoBrewRecipeParser().parse(path)
        recipe = recipes[index]
        recipe.zymatic = (
            recipe.zymatic.model_copy(update={"steps": steps})
            if recipe.zymatic
            else PicoBrewZymaticProgram(steps=steps)
        )
        written = Serializer().recipe_to_xml_element(recipe).find("ZYMATIC")
        if written is None:
            raise ValueError("The writer did not produce a machine program.")

        # pybeerxml only writes declared model fields. Merge its STEP elements
        # into the original document to retain unknown extensions, comments,
        # program metadata, and every other recipe in a multi-recipe file.
        root = ET.fromstring(document, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True)))
        node = root.findall("RECIPE")[index]
        program = node.find("ZYMATIC")
        if program is None:
            program = ET.SubElement(node, "ZYMATIC")
        previous = list(program)
        position = next((i for i, child in enumerate(previous) if child.tag == "STEP"), 0)
        for child in previous:
            if child.tag == "STEP":
                program.remove(child)
        for offset, step in enumerate(written.findall("STEP")):
            program.insert(position + offset, step)
        ET.indent(root, space="  ")
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".program-", suffix=".xml", delete=False) as output:
            temporary = Path(output.name)
            temporary.chmod(path.stat().st_mode & 0o777)
            output.write(ET.tostring(root, encoding="utf-8", xml_declaration=True))
            output.flush()
            os.fsync(output.fileno())
        restored = PicoBrewRecipeParser().parse(temporary)
        if len(restored) != len(recipes) or restored[index].steps != steps:
            raise ValueError("The saved machine program could not be verified.")
        # Detect external changes made while the replacement was being prepared.
        if revision(path.read_bytes()) != expected_revision:
            raise ProgramConflictError("This file changed while saving. Reload the editor before saving.")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        os.close(lock_fd)
        lock.unlink(missing_ok=True)
