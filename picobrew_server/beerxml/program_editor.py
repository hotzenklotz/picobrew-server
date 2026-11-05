"""Write machine steps without rewriting unrelated BeerXML recipe data."""

import fcntl
import hashlib
import os
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.parsers import expat

from pybeerxml import Serializer

from picobrew_server.beerxml.picobrew_parser import PicoBrewRecipeParser
from picobrew_server.beerxml.picobrew_program_step import PicoBrewProgramStep, PicoBrewZymaticProgram


class ProgramConflictError(Exception):
    """The file has changed or another editor is currently saving it."""


def revision(document: bytes) -> str:
    return hashlib.sha256(document).hexdigest()


def root_span(document: bytes) -> tuple[int, int, str, dict[str, str]]:
    """Locate the root element's bytes, the declared encoding, and namespace prefixes."""
    parser = expat.ParserCreate()
    state: dict = {"depth": 0, "start": None, "end": None, "encoding": "utf-8", "namespaces": {}}

    def declaration(_version: str, encoding: str | None, _standalone: int) -> None:
        if encoding:
            state["encoding"] = encoding

    def start(_name: str, attributes: dict[str, str]) -> None:
        if state["depth"] == 0:
            state["start"] = parser.CurrentByteIndex
        state["depth"] += 1
        for name, value in attributes.items():
            if name == "xmlns":
                state["namespaces"].setdefault("", value)
            elif name.startswith("xmlns:"):
                state["namespaces"].setdefault(name[6:], value)

    def end(_name: str) -> None:
        state["depth"] -= 1
        if state["depth"] == 0:
            state["end"] = parser.CurrentByteIndex

    parser.XmlDeclHandler = declaration
    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.Parse(document, True)
    if state["start"] is None or state["end"] is None:
        raise ValueError("The document has no root element.")
    # For <ROOT/> the end event points at the start tag; otherwise at </ROOT>.
    close = document.index(b">", state["end"]) + 1
    return state["start"], close, state["encoding"], state["namespaces"]


def serialize(document: bytes, root: ET.Element) -> bytes:
    """Replace only the root element, keeping the prolog, DOCTYPE, comments, and namespace prefixes."""
    try:
        start, end, encoding, namespaces = root_span(document)
        "".encode(encoding)
    except (ValueError, LookupError, expat.ExpatError):
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)
    for prefix, uri in namespaces.items():
        if prefix:
            try:
                # ElementTree only reads prefixes from its global registry.
                ET.register_namespace(prefix, uri)
            except ValueError:
                pass
    try:
        text = ET.tostring(root, encoding="unicode", default_namespace=namespaces.get("") or None)
    except ValueError:
        text = ET.tostring(root, encoding="unicode")
    return document[:start] + text.encode(encoding, "xmlcharrefreplace") + document[end:]


def save_program(path: Path, index: int, steps: list[PicoBrewProgramStep], expected_revision: str) -> None:
    # The kernel releases the per-file lock if a worker exits. Keep the lock
    # file so all workers lock the same inode, even after a recipe is replaced.
    # The replacement stays on the same filesystem for an atomic write.
    lock = path.with_name(f".{path.name}.program-lock")
    lock_fd = os.open(lock, os.O_CREAT | os.O_WRONLY, 0o600)
    temporary: Path | None = None
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ProgramConflictError("Another editor is saving this file. Please try again.") from error
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
            output.write(serialize(document, root))
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
        try:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        finally:
            os.close(lock_fd)
