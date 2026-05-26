"""Structural API contract tests.

These tests assert invariants about the library's surface — method coverage,
class relationships, etc. — rather than testing runtime behaviour.
"""

from __future__ import annotations

import inspect

from yamltrip.document import Document
from yamltrip.editor import Editor

# Document methods that Editor intentionally does not expose:
#   dump / dumps   — Editor owns the write path; callers don't call these directly.
#   has_anchors    — read-only introspection, not a mutation.
#   query_pretty   — read-only introspection, not a mutation.
_DOCUMENT_ONLY = frozenset({"dump", "dumps", "has_anchors", "query_pretty"})


def _public_methods(cls: type) -> set[str]:
    return {
        name
        for name, _ in inspect.getmembers(cls, predicate=callable)
        if not name.startswith("_")
    }


class TestEditorDocumentMethodCoverage:
    """Every public Document method must have a corresponding Editor wrapper,
    except for those explicitly listed in _DOCUMENT_ONLY."""

    def test_editor_exposes_all_document_mutation_methods(self):
        doc_methods = _public_methods(Document)
        ed_methods = _public_methods(Editor)
        missing = (doc_methods - _DOCUMENT_ONLY) - ed_methods
        assert not missing, (
            f"Editor is missing wrappers for Document methods: {sorted(missing)}\n"
            "Add the wrapper or add the method name to _DOCUMENT_ONLY if intentional."
        )

    def test_document_only_set_is_accurate(self):
        """Fail if _DOCUMENT_ONLY names a method that Editor actually does expose,
        so the exclusion list doesn't silently become stale."""
        ed_methods = _public_methods(Editor)
        stale = _DOCUMENT_ONLY & ed_methods
        assert not stale, (
            f"_DOCUMENT_ONLY lists methods that Editor already exposes: {sorted(stale)}\n"
            "Remove them from _DOCUMENT_ONLY."
        )
