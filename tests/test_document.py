import pytest

from yamltrip._core import FeatureKind
from yamltrip.document import Document
from yamltrip.errors import (
    KeyExistsError,
    KeyMissingError,
    NodeTypeError,
    PatchError,
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


class TestDocumentGet:
    def test_empty_document_returns_default(self):
        doc = Document("")
        assert doc.get() is None

    def test_comment_only_returns_default(self):
        doc = Document("# just a comment\n")
        assert doc.get() is None

    def test_directive_only_returns_default(self):
        doc = Document("---\n")
        assert doc.get() is None

    def test_root_value_returned(self):
        doc = Document("name: foo\n")
        assert doc.get() == {"name": "foo"}

    def test_existing_key(self):
        doc = Document("name: foo\nversion: 1\n")
        assert doc.get("name") == "foo"

    def test_missing_key_returns_none(self):
        doc = Document("name: foo\n")
        assert doc.get("missing") is None

    def test_missing_key_returns_custom_default(self):
        doc = Document("name: foo\n")
        assert doc.get("missing", default={}) == {}

    def test_nested_existing_path(self):
        doc = Document("a:\n  b: 1\n")
        assert doc.get("a", "b") == 1

    def test_nested_missing_path(self):
        doc = Document("a:\n  b: 1\n")
        assert doc.get("a", "c") is None

    def test_null_value_returns_none(self):
        doc = Document("key: null\n")
        assert doc.get("key") is None

    def test_malformed_value_raises_query_error(self):
        """get() should raise QueryError (not ValueError) for unparsable values."""
        doc = Document("a:\n  b: 1\n  b: 2")
        with pytest.raises(QueryError):
            doc.get("a")

    def test_root_still_raises_on_empty(self):
        doc = Document("")
        with pytest.raises(QueryError):
            doc.root


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


class TestDocumentReplaceComplex:
    def test_replace_with_dict(self):
        doc = Document("config:\n  key: value\n")
        doc2 = doc.replace("config", value={"key": "new", "extra": "field"})
        assert doc2["config"] == {"key": "new", "extra": "field"}

    def test_replace_with_list(self):
        doc = Document("repos: []\n")
        doc2 = doc.replace(
            "repos", value=[{"repo": "local", "hooks": [{"id": "my-hook"}]}]
        )
        result = doc2["repos"]
        assert len(result) == 1
        assert result[0]["repo"] == "local"
        assert result[0]["hooks"] == [{"id": "my-hook"}]

    def test_replace_with_nested_dict_in_list(self):
        doc = Document("data:\n  - old\n")
        doc2 = doc.replace("data", value=[{"a": {"b": [1, 2, 3]}}])
        assert doc2["data"] == [{"a": {"b": [1, 2, 3]}}]

    def test_replace_complex_preserves_other_keys(self):
        doc = Document("name: foo\nconfig:\n  key: value\nversion: 1\n")
        doc2 = doc.replace("config", value={"new_key": "new_val"})
        assert doc2["name"] == "foo"
        assert doc2["version"] == 1
        assert doc2["config"] == {"new_key": "new_val"}

    def test_replace_complex_preserves_comments_on_other_keys(self):
        doc = Document("name: foo  # keep this\nconfig: old\n")
        doc2 = doc.replace("config", value={"a": 1})
        assert "# keep this" in doc2.source

    def test_replace_nested_key_with_dict(self):
        doc = Document("outer:\n  inner: old\n")
        doc2 = doc.replace("outer", "inner", value={"a": 1, "b": 2})
        assert doc2["outer", "inner"] == {"a": 1, "b": 2}

    def test_replace_complex_with_complex(self):
        doc = Document("config:\n  a: 1\n  b: 2\n")
        doc2 = doc.replace("config", value={"x": 10, "y": 20})
        assert doc2["config"] == {"x": 10, "y": 20}

    def test_replace_scalar_with_list(self):
        doc = Document("items: none\n")
        doc2 = doc.replace("items", value=["a", "b", "c"])
        assert doc2["items"] == ["a", "b", "c"]

    def test_replace_deeply_nested_with_dict(self):
        doc = Document("a:\n  b:\n    c: old\n")
        doc2 = doc.replace("a", "b", "c", value={"deep": "value"})
        assert doc2["a", "b", "c"] == {"deep": "value"}

    def test_replace_comment_relocation(self):
        doc = Document("repos: []  # managed by tool\n")
        doc2 = doc.replace("repos", value=[{"repo": "local"}])
        assert "# managed by tool" in doc2.source
        result = doc2["repos"]
        assert result == [{"repo": "local"}]

    def test_replace_root_level_with_dict(self):
        doc = Document("key: value\n")
        doc2 = doc.replace(value={"new_key": "new_val", "another": 42})
        assert doc2["new_key"] == "new_val"
        assert doc2["another"] == 42

    def test_replace_top_level_key_with_dict(self):
        """Indentation depth 0: top-level key gets value indented at 2 spaces."""
        doc = Document("config: old\n")
        doc2 = doc.replace("config", value={"a": 1})
        assert doc2["config"] == {"a": 1}
        # Value should be indented at 2 spaces (base_indent=0 + 2)
        assert "  a: 1" in doc2.source

    def test_replace_depth2_key_with_dict(self):
        """Indentation depth 2: nested key gets value indented at 4 spaces."""
        doc = Document("outer:\n  config: old\n")
        doc2 = doc.replace("outer", "config", value={"a": 1})
        assert doc2["outer", "config"] == {"a": 1}
        assert "    a: 1" in doc2.source

    def test_replace_with_empty_dict(self):
        doc = Document("config:\n  key: value\n")
        doc2 = doc.replace("config", value={})
        assert doc2["config"] == {}

    def test_replace_with_empty_list(self):
        doc = Document("items:\n  - a\n  - b\n")
        doc2 = doc.replace("items", value=[])
        assert doc2["items"] == []

    def test_replace_block_scalar_with_dict(self):
        doc = Document("description: |\n  This is a\n  multi-line string\n")
        doc2 = doc.replace("description", value={"summary": "short"})
        assert doc2["description"] == {"summary": "short"}

    def test_replace_folded_scalar_with_list(self):
        doc = Document("notes: >\n  folded\n  text\n")
        doc2 = doc.replace("notes", value=["a", "b"])
        assert doc2["notes"] == ["a", "b"]

    def test_replace_flow_mapping_with_dict(self):
        doc = Document("config: {a: 1, b: 2}\n")
        doc2 = doc.replace("config", value={"x": 10})
        assert doc2["config"] == {"x": 10}

    def test_replace_key_with_hash_in_value(self):
        doc = Document("color: '#ff0000'\n")
        doc2 = doc.replace("color", value={"r": 255, "g": 0, "b": 0})
        assert doc2["color"] == {"r": 255, "g": 0, "b": 0}


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


class TestDocumentUpsertComplex:
    def test_upsert_existing_with_dict(self):
        doc = Document("config:\n  key: value\n")
        doc2 = doc.upsert("config", value={"key": "new", "extra": "field"})
        assert doc2["config"] == {"key": "new", "extra": "field"}

    def test_upsert_existing_with_list(self):
        doc = Document("repos: []\n")
        doc2 = doc.upsert("repos", value=[{"repo": "local"}])
        assert doc2["repos"] == [{"repo": "local"}]

    def test_upsert_missing_with_dict(self):
        """This already works via Op.add — verify it stays working."""
        doc = Document("name: foo\n")
        doc2 = doc.upsert("config", value={"a": 1})
        assert doc2["config"] == {"a": 1}
        assert doc2["name"] == "foo"

    def test_upsert_missing_with_list(self):
        """This already works via Op.add — verify it stays working."""
        doc = Document("name: foo\n")
        doc2 = doc.upsert("items", value=["a", "b"])
        assert doc2["items"] == ["a", "b"]


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

    def test_append_flow_sequence(self):
        doc = Document("items: [a, b]\n")
        doc2 = doc.append("items", value="c")
        assert doc2["items"] == ["a", "b", "c"]

    def test_append_empty_flow_sequence(self):
        doc = Document("items: []\n")
        doc2 = doc.append("items", value="x")
        assert doc2["items"] == ["x"]

    def test_extend_list_flow_sequence(self):
        doc = Document("items: [a]\n")
        doc2 = doc.extend_list("items", values=["b", "c"])
        assert doc2["items"] == ["a", "b", "c"]

    def test_extend_list_empty_flow_sequence(self):
        doc = Document("items: []\n")
        doc2 = doc.extend_list("items", values=["a", "b"])
        assert doc2["items"] == ["a", "b"]

    def test_remove_from_list(self):
        doc = Document("items:\n  - a\n  - b\n  - c")
        doc2 = doc.remove_from_list("items", values=["b"])
        result = doc2["items"]
        assert "b" not in result
        assert "a" in result
        assert "c" in result


class TestDocumentInsert:
    def test_insert_middle(self):
        doc = Document("items:\n  - a\n  - b\n  - c\n")
        doc2 = doc.insert("items", index=1, value="x")
        assert doc2["items"] == ["a", "x", "b", "c"]

    def test_insert_beginning(self):
        doc = Document("items:\n  - a\n  - b\n")
        doc2 = doc.insert("items", index=0, value="x")
        assert doc2["items"] == ["x", "a", "b"]

    def test_insert_end(self):
        doc = Document("items:\n  - a\n  - b\n")
        doc2 = doc.insert("items", index=2, value="x")
        assert doc2["items"] == ["a", "b", "x"]

    def test_insert_negative_index(self):
        doc = Document("items:\n  - a\n  - b\n  - c\n")
        doc2 = doc.insert("items", index=-1, value="x")
        assert doc2["items"] == ["a", "b", "x", "c"]

    def test_insert_clamps_large_positive(self):
        doc = Document("items:\n  - a\n  - b\n")
        doc2 = doc.insert("items", index=100, value="x")
        assert doc2["items"] == ["a", "b", "x"]

    def test_insert_clamps_large_negative(self):
        doc = Document("items:\n  - a\n  - b\n")
        doc2 = doc.insert("items", index=-100, value="x")
        assert doc2["items"] == ["x", "a", "b"]

    def test_insert_complex_value(self):
        doc = Document("repos:\n  - repo: a\n  - repo: c\n")
        doc2 = doc.insert("repos", index=1, value={"repo": "b"})
        repos = doc2["repos"]
        assert repos[0] == {"repo": "a"}
        assert repos[1] == {"repo": "b"}
        assert repos[2] == {"repo": "c"}

    def test_insert_preserves_comments(self):
        source = "items:\n  # first\n  - a\n  # third\n  - c\n"
        doc = Document(source)
        doc2 = doc.insert("items", index=1, value="b")
        assert "# first" in doc2.source
        assert "# third" in doc2.source

    def test_insert_immutable(self):
        doc = Document("items:\n  - a\n  - b\n")
        doc2 = doc.insert("items", index=0, value="x")
        assert doc["items"] == ["a", "b"]
        assert doc2["items"] == ["x", "a", "b"]

    def test_insert_not_a_sequence(self):
        doc = Document("name: foo\n")
        with pytest.raises(PatchError):
            doc.insert("name", index=0, value="x")

    def test_insert_path_not_found(self):
        doc = Document("name: foo\n")
        with pytest.raises(PatchError):
            doc.insert("missing", index=0, value="x")

    def test_insert_flow_sequence_converts_to_block(self):
        doc = Document("items: [a, b, c]\n")
        doc2 = doc.insert("items", index=1, value="x")
        assert doc2["items"] == ["a", "x", "b", "c"]

    def test_insert_empty_flow_sequence(self):
        doc = Document("items: []\n")
        doc2 = doc.insert("items", index=0, value="x")
        assert doc2["items"] == ["x"]

    def test_insert_flow_sequence_append_semantics(self):
        doc = Document("items: [a, b]\n")
        doc2 = doc.insert("items", index=99, value="c")
        assert doc2["items"] == ["a", "b", "c"]

    def test_insert_flow_sequence_negative_index(self):
        doc = Document("items: [a, b, c]\n")
        doc2 = doc.insert("items", index=-1, value="x")
        assert doc2["items"] == ["a", "b", "x", "c"]

    def test_insert_nested_path(self):
        doc = Document("config:\n  items:\n    - a\n    - b\n")
        doc2 = doc.insert("config", "items", index=1, value="x")
        assert doc2["config", "items"] == ["a", "x", "b"]


class TestNodeTypeError:
    def test_remove_from_list_on_scalar_raises_node_type_error(self):
        doc = Document("name: foo\n")
        with pytest.raises(NodeTypeError, match="not a list"):
            doc.remove_from_list("name", values=["foo"])

    def test_remove_from_list_node_type_error_is_patch_error(self):
        doc = Document("name: foo\n")
        with pytest.raises(PatchError):
            doc.remove_from_list("name", values=["foo"])
