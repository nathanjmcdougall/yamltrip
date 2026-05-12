"""Tests for critical edge cases."""

import os

import pytest

from yamltrip.document import Document
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
        # Simulate external modification with a different mtime
        p.write_text("name: baz\n", encoding="utf-8")
        stat = p.stat()
        os.utime(p, (stat.st_atime, stat.st_mtime + 1))
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
