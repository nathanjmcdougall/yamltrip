"""Tests for critical edge cases."""

import pytest

from yamltrip._core import Op, Patch
from yamltrip.document import (
    Document,
    _classify_patch_error,
    _make_route,
    _PatchErrorKind,
)
from yamltrip.editor import Editor
from yamltrip.errors import PatchError, QueryError


class TestExtendListEmpty:
    def test_extend_list_empty_returns_same(self):
        doc = Document("items:\n  - a")
        doc2 = doc.extend_list("items", values=[])
        assert doc2 is doc

    def test_extend_list_empty_source_unchanged(self):
        doc = Document("items:\n  - a")
        doc2 = doc.extend_list("items", values=[])
        assert doc2.source == doc.source


class TestUpsertIntKeyCreation:
    def test_upsert_int_key_at_root_raises(self):
        doc = Document("name: foo")
        with pytest.raises(PatchError, match="integer key"):
            doc.upsert(0, value="bar")

    def test_upsert_int_key_intermediate_raises(self):
        doc = Document("name: foo")
        with pytest.raises(PatchError, match="integer key"):
            doc.upsert("items", 0, "sub", value=True)

    def test_upsert_int_key_existing_path_works(self):
        doc = Document("items:\n  - a\n  - b")
        doc2 = doc.upsert("items", 0, value="x")
        assert doc2["items", 0] == "x"


class TestUpsertRootReplace:
    def test_upsert_empty_keys_replaces_root(self):
        doc = Document("name: foo")
        doc2 = doc.upsert(value="replaced")
        assert "replaced" in doc2.source


class TestRemoveFromListDuplicates:
    def test_removes_all_occurrences(self):
        doc = Document("items:\n  - a\n  - b\n  - a\n  - c")
        doc2 = doc.remove_from_list("items", values=["a"])
        result = doc2["items"]
        assert "a" not in result
        assert "b" in result
        assert "c" in result


class TestContainsTypeError:
    def test_float_key_raises_type_error(self):
        doc = Document("name: foo")
        with pytest.raises(TypeError):
            3.14 in doc  # noqa: B015

    def test_object_key_raises_type_error(self):
        doc = Document("name: foo")
        with pytest.raises(TypeError):
            object() in doc  # noqa: B015


class TestHasAnchors:
    def test_document_without_anchors(self):
        doc = Document("name: foo")
        assert doc.has_anchors() is False

    def test_document_with_anchors(self):
        doc = Document("defaults: &defaults\n  a: 1\noverrides:\n  <<: *defaults")
        assert doc.has_anchors() is True


class TestEditorExternalModification:
    def test_external_modification_raises(self, tmp_path):
        p = tmp_path / "test.yml"
        p.write_text("name: foo\n", encoding="utf-8")

        editor = Editor(p)
        editor.__enter__()
        editor.replace("name", value="bar")
        # Simulate external modification by changing the file content
        p.write_text("name: baz\n", encoding="utf-8")
        with pytest.raises(RuntimeError, match="modified externally"):
            editor.__exit__(None, None, None)


class TestDocumentRepr:
    def test_repr_shows_byte_count(self):
        doc = Document("name: foo")
        assert repr(doc) == "Document(<9 bytes>)"

    def test_repr_empty(self):
        doc = Document("")
        assert repr(doc) == "Document(<0 bytes>)"


class TestQueryMissingPath:
    def test_query_missing_raises(self):
        doc = Document("name: foo")
        with pytest.raises(QueryError):
            doc.query("missing")

    def test_getitem_missing_raises(self):
        doc = Document("name: foo")
        with pytest.raises(QueryError):
            doc["missing"]


class TestPatchErrorStringPins:
    """Pin the yamlpatch error substrings that _classify_patch_error depends on.

    If yamlpatch changes its error wording these tests fail loudly rather than
    causing silent mis-classification at runtime.
    """

    def _raw_error(self, doc: Document, *keys: str, op: Op) -> str:
        """Trigger a PatchError through _apply_patches and return its message."""
        route = _make_route(keys)
        with pytest.raises(PatchError) as exc_info:
            doc._apply_patches([Patch(route=route, operation=op)])
        return str(exc_info.value)

    def test_flow_sequence_substring(self):
        """Op.append on a flow-sequence node raises an error containing 'flow sequence'."""
        doc = Document("items: [a, b]\n")
        msg = self._raw_error(doc, "items", op=Op.append("c"))
        assert _PatchErrorKind.FLOW_SEQUENCE.value in msg

    def test_not_a_sequence_substring(self):
        """Op.append on a scalar node raises an error containing 'only permitted against sequence'."""
        doc = Document("name: hello\n")
        msg = self._raw_error(doc, "name", op=Op.append("x"))
        assert _PatchErrorKind.NOT_A_SEQUENCE.value in msg

    def test_block_sequence_expected_substring(self):
        """Op.insert_at on a flow-sequence node raises an error containing 'expected BlockSequence'."""
        doc = Document("items: [a, b]\n")
        msg = self._raw_error(doc, "items", op=Op.insert_at(index=0, value="c"))
        assert _PatchErrorKind.BLOCK_SEQUENCE_EXPECTED.value in msg

    def test_classify_flow_sequence(self):
        doc = Document("items: [a, b]\n")
        msg = self._raw_error(doc, "items", op=Op.append("c"))
        assert _classify_patch_error(PatchError(msg)) == _PatchErrorKind.FLOW_SEQUENCE

    def test_classify_not_a_sequence(self):
        doc = Document("name: hello\n")
        msg = self._raw_error(doc, "name", op=Op.append("x"))
        assert _classify_patch_error(PatchError(msg)) == _PatchErrorKind.NOT_A_SEQUENCE

    def test_classify_block_sequence_expected(self):
        doc = Document("items: [a, b]\n")
        msg = self._raw_error(doc, "items", op=Op.insert_at(index=0, value="c"))
        assert (
            _classify_patch_error(PatchError(msg))
            == _PatchErrorKind.BLOCK_SEQUENCE_EXPECTED
        )

    def test_classify_unknown(self):
        assert (
            _classify_patch_error(PatchError("some unrelated error"))
            == _PatchErrorKind.UNKNOWN
        )
