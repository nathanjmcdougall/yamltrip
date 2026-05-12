"""yamltrip — round-tripping YAML library for Python."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from yamltrip._core import Component, Feature, FeatureKind, Location, Route
from yamltrip.document import Document
from yamltrip.editor import Editor
from yamltrip.errors import (
    KeyExistsError,
    KeyMissingError,
    ParseError,
    PatchError,
    QueryError,
    YAMLTripError,
)

if TYPE_CHECKING:
    pass


def loads(source: str) -> Document:
    """Parse a YAML string into a Document."""
    return Document(source)


def load(path: str | Path) -> Document:
    """Read a YAML file into a Document."""
    return Document(Path(path).read_text(encoding="utf-8"))


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
    "ParseError",
    "PatchError",
    "QueryError",
    "Route",
    "YAMLTripError",
    "edit",
    "load",
    "loads",
]
