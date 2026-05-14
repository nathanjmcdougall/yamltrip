import pytest

from yamltrip._core import FeatureKind
from yamltrip.document import Document
from yamltrip.errors import (
    KeyExistsError,
    KeyMissingError,
    QueryError,
)


class TestDocumentConstruction:
    def test_from_string(self):
        doc = Document("name: foo")
        assert doc.source == "name: foo"

    def test_empty_string(self):
        doc = Document("")
        assert doc.source == ""

    def test_equality(self):
        assert Document("name: foo") == Document("name: foo")

    def test_inequality(self):
        assert Document("name: foo") != Document("name: bar")

    def test_equality_not_implemented_for_other_types(self):
        assert Document("name: foo") != "name: foo"

    def test_hashable(self):
        doc1 = Document("name: foo")
        doc2 = Document("name: foo")
        assert hash(doc1) == hash(doc2)
        assert {doc1, doc2} == {doc1}


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


class TestParseValueDedent:
    """Tests for parse_value's dedent logic on multiline/nested YAML values."""

    def test_block_literal_scalar(self):
        source = "desc: |\n  line one\n  line two\n"
        doc = Document(source)
        assert doc["desc"] == "line one\nline two\n"

    def test_block_folded_scalar(self):
        source = "desc: >\n  line one\n  line two\n"
        doc = Document(source)
        assert doc["desc"] == "line one line two\n"

    def test_block_literal_strip(self):
        source = "desc: |-\n  line one\n  line two\n"
        doc = Document(source)
        assert doc["desc"] == "line one\nline two"

    def test_block_literal_keep(self):
        source = "desc: |+\n  line one\n  line two\n\n"
        doc = Document(source)
        assert doc["desc"] == "line one\nline two\n\n"

    def test_block_scalar_with_blank_lines(self):
        source = "desc: |\n  first\n\n  second\n"
        doc = Document(source)
        assert doc["desc"] == "first\n\nsecond\n"

    def test_nested_block_scalar(self):
        source = "outer:\n  inner: |\n    hello\n    world\n"
        doc = Document(source)
        assert doc["outer", "inner"] == "hello\nworld\n"

    def test_deeply_nested_value(self):
        source = "a:\n  b:\n    c:\n      d: deep\n"
        doc = Document(source)
        assert doc["a", "b", "c", "d"] == "deep"

    def test_nested_mapping_value(self):
        source = "root:\n  x: 1\n  y: 2\n"
        doc = Document(source)
        assert doc["root"] == {"x": 1, "y": 2}

    def test_nested_sequence_value(self):
        source = "root:\n  items:\n    - a\n    - b\n    - c\n"
        doc = Document(source)
        assert doc["root", "items"] == ["a", "b", "c"]


class TestDocumentContains:
    def test_key_exists(self):
        doc = Document("name: foo")
        assert "name" in doc

    def test_key_missing(self):
        doc = Document("name: foo")
        assert "missing" not in doc

    def test_nested_key_exists(self):
        doc = Document("a:\n  b: 1")
        assert ("a", "b") in doc

    def test_nested_key_missing(self):
        doc = Document("a:\n  b: 1")
        assert ("a", "c") not in doc


class TestDocumentInspection:
    def test_query_returns_feature(self):
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


class TestDocumentReplace:
    def test_replace_scalar(self):
        doc = Document("name: foo")
        doc2 = doc.replace("name", value="bar")
        assert doc2["name"] == "bar"
        assert doc["name"] == "foo"  # original unchanged

    def test_replace_preserves_comments(self):
        doc = Document("# header\nname: foo  # inline")
        doc2 = doc.replace("name", value="bar")
        assert "# header" in doc2.source
        assert "# inline" in doc2.source

    def test_replace_missing_raises(self):
        doc = Document("name: foo")
        with pytest.raises(KeyMissingError):
            doc.replace("missing", value="bar")


class TestDocumentAdd:
    def test_add_key(self):
        doc = Document("name: foo")
        doc2 = doc.add(key="age", value=30)
        assert doc2["age"] == 30
        assert doc2["name"] == "foo"

    def test_add_existing_raises(self):
        doc = Document("name: foo")
        with pytest.raises(KeyExistsError):
            doc.add(key="name", value="bar")

    def test_add_to_nested(self):
        doc = Document("a:\n  b: 1")
        doc2 = doc.add("a", key="c", value=2)
        assert doc2["a", "c"] == 2


class TestDocumentUpsert:
    def test_upsert_existing(self):
        doc = Document("name: foo")
        doc2 = doc.upsert("name", value="bar")
        assert doc2["name"] == "bar"

    def test_upsert_missing(self):
        doc = Document("name: foo")
        doc2 = doc.upsert("age", value=30)
        assert doc2["age"] == 30


class TestDocumentRemove:
    def test_remove_key(self):
        doc = Document("name: foo\nage: 30")
        doc2 = doc.remove("age")
        assert "age" not in doc2
        assert doc2["name"] == "foo"


class TestDocumentPruneRemove:
    def test_prune_remove(self):
        doc = Document("a:\n  b:\n    c: 1")
        doc2 = doc.prune_remove("a", "b", "c")
        assert "a" not in doc2

    def test_remove_with_prune_flag(self):
        doc = Document("a:\n  b:\n    c: 1")
        doc2 = doc.remove("a", "b", "c", prune=True)
        assert "a" not in doc2


class TestDocumentAppend:
    def test_append(self):
        doc = Document("items:\n  - a\n  - b")
        doc2 = doc.append("items", value="c")
        result = doc2["items"]
        assert "c" in result

    def test_extend_list(self):
        doc = Document("items:\n  - a")
        doc2 = doc.extend_list("items", values=["b", "c"])
        result = doc2["items"]
        assert "b" in result
        assert "c" in result

    def test_remove_from_list(self):
        doc = Document("items:\n  - a\n  - b\n  - c")
        doc2 = doc.remove_from_list("items", values=["b"])
        result = doc2["items"]
        assert "b" not in result
        assert "a" in result
        assert "c" in result
