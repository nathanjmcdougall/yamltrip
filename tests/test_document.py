import pytest

from yamltrip.document import Document
from yamltrip.errors import ParseError, QueryError


class TestDocumentConstruction:
    def test_from_string(self):
        doc = Document("name: foo")
        assert doc.source == "name: foo"

    def test_empty_string(self):
        doc = Document("")
        assert doc.source == ""


class TestDocumentGetitem:
    def test_single_key(self):
        doc = Document("name: foo")
        assert doc["name"] == "foo"

    def test_nested_keys(self):
        doc = Document("a:\n  b: 42")
        assert doc["a", "b"] == 42

    def test_sequence_index(self):
        doc = Document("items:\n  - a\n  - b")
        assert doc["items", 0] == "a"
        assert doc["items", 1] == "b"

    def test_missing_key_raises(self):
        doc = Document("name: foo")
        with pytest.raises(QueryError):
            doc["missing"]

    def test_integer_value(self):
        doc = Document("count: 42")
        assert doc["count"] == 42

    def test_boolean_value(self):
        doc = Document("flag: true")
        assert doc["flag"] is True

    def test_null_value(self):
        doc = Document("nothing: null")
        assert doc["nothing"] is None

    def test_list_value(self):
        doc = Document("items:\n  - a\n  - b")
        result = doc["items"]
        assert result == ["a", "b"]

    def test_dict_value(self):
        doc = Document("a:\n  b: 1\n  c: 2")
        result = doc["a"]
        assert result == {"b": 1, "c": 2}


class TestDocumentContains:
    def test_key_exists(self):
        doc = Document("name: foo")
        assert ("name",) in doc

    def test_key_missing(self):
        doc = Document("name: foo")
        assert ("missing",) not in doc

    def test_nested_key_exists(self):
        doc = Document("a:\n  b: 1")
        assert ("a", "b") in doc

    def test_nested_key_missing(self):
        doc = Document("a:\n  b: 1")
        assert ("a", "c") not in doc


class TestDocumentInspection:
    def test_query_returns_feature(self):
        from yamltrip._core import FeatureKind

        doc = Document("name: foo")
        feature = doc.query("name")
        assert feature.kind == FeatureKind.Scalar

    def test_extract(self):
        doc = Document("name: foo")
        feature = doc.query("name")
        assert doc.extract(feature) == "foo"


class TestDocumentOutput:
    def test_dumps(self):
        source = "name: foo\n"
        doc = Document(source)
        assert doc.dumps() == source

    def test_dump(self, tmp_path):
        source = "name: foo\n"
        doc = Document(source)
        p = tmp_path / "out.yml"
        doc.dump(p)
        assert p.read_text(encoding="utf-8") == source
