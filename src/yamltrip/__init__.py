"""yamltrip — round-tripping YAML library for Python."""

from __future__ import annotations

from pathlib import Path

from yamltrip._core import Component, Feature, FeatureKind, Location, Route
from yamltrip.document import Document
from yamltrip.editor import Editor
from yamltrip.errors import (
    KeyExistsError,
    KeyMissingError,
    NodeTypeError,
    ParseError,
    PatchError,
    QueryError,
    RoutingError,
    YAMLTripError,
)


def loads(source: str) -> Document:
    """Parse a YAML string into a Document."""
    return Document(source)


def load(path: str | Path) -> Document:
    """Read a YAML file into a Document."""
    try:
        source = Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        msg = f"File is not valid UTF-8: {path}"
        raise ParseError(msg) from None
    return Document(source)


def edit(path: str | Path) -> Editor:
    """Open a YAML file for editing (context manager)."""
    return Editor(path)


__all__ = [
    "Component",
    "Document",
    "Editor",
    "Feature",
    "FeatureKind",
    "KeyExistsError",
    "KeyMissingError",
    "Location",
    "NodeTypeError",
    "ParseError",
    "PatchError",
    "QueryError",
    "Route",
    "RoutingError",
    "YAMLTripError",
    "edit",
    "load",
    "loads",
]
