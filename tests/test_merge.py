import pytest

from yamltrip import edit
from yamltrip.document import Document
from yamltrip.errors import PatchError


class TestMergeMapping:
    def test_keeps_extra_keys(self):
        doc = Document("a: 1\nb: 2\nc: 3\n")
        doc2 = doc.merge(value={"a": 10, "d": 4})
        assert doc2["a"] == 10
        assert doc2["b"] == 2
        assert doc2["c"] == 3
        assert doc2["d"] == 4

    def test_nested_merge(self):
        doc = Document("db:\n  host: localhost\n  port: 5432\n  user: admin\n")
        doc2 = doc.merge("db", value={"port": 3306, "ssl": True})
        assert doc2["db", "host"] == "localhost"
        assert doc2["db", "port"] == 3306
        assert doc2["db", "user"] == "admin"
        assert doc2["db", "ssl"] is True

    def test_deeply_nested_merge(self):
        doc = Document("a:\n  b:\n    c: 1\n    d: 2\n  e: 3\n")
        doc2 = doc.merge("a", value={"b": {"c": 99}})
        assert doc2["a", "b", "c"] == 99
        assert doc2["a", "b", "d"] == 2
        assert doc2["a", "e"] == 3


class TestMergeListReplacement:
    def test_list_replaced_entirely(self):
        doc = Document("items:\n  - a\n  - b\n  - c\n")
        doc2 = doc.merge("items", value=["x"])
        assert doc2["items"] == ["x"]

    def test_nested_list_replaced(self):
        doc = Document("cfg:\n  tags:\n    - alpha\n    - beta\n  name: foo\n")
        doc2 = doc.merge("cfg", value={"tags": ["gamma"]})
        assert doc2["cfg", "tags"] == ["gamma"]
        assert doc2["cfg", "name"] == "foo"


class TestMergeFlowSequence:
    def test_flow_sequence_replaced(self):
        doc = Document("cfg:\n  tags: [alpha, beta]\n  name: foo\n")
        doc2 = doc.merge("cfg", value={"tags": ["gamma"], "extra": 1})
        assert doc2["cfg", "tags"] == ["gamma"]
        assert doc2["cfg", "name"] == "foo"
        assert doc2["cfg", "extra"] == 1

    def test_flow_sequence_at_path(self):
        doc = Document("items: [a, b, c]\n")
        doc2 = doc.merge("items", value=["x", "y"])
        assert doc2["items"] == ["x", "y"]


class TestMergeTypePromotion:
    def test_scalar_to_mapping(self):
        doc = Document("settings: defaults\n")
        doc2 = doc.merge("settings", value={"debug": True})
        assert doc2["settings", "debug"] is True

    def test_mapping_to_scalar(self):
        doc = Document("settings:\n  debug: true\n")
        doc2 = doc.merge("settings", value="off")
        assert doc2["settings"] == "off"


class TestMergePathCreation:
    def test_creates_missing_path(self):
        doc = Document("a: 1\n")
        doc2 = doc.merge("new_section", value={"x": 1})
        assert doc2["new_section", "x"] == 1
        assert doc2["a"] == 1

    def test_creates_nested_missing_path(self):
        doc = Document("a: 1\n")
        doc2 = doc.merge("b", "c", value={"d": 2})
        assert doc2["b", "c", "d"] == 2


class TestMergeNoop:
    def test_returns_self_when_equal(self):
        doc = Document("a: 1\nb: 2\n")
        doc2 = doc.merge(value={"a": 1, "b": 2})
        assert doc2 is doc

    def test_returns_self_when_subset(self):
        doc = Document("a: 1\nb: 2\nc: 3\n")
        doc2 = doc.merge(value={"a": 1, "b": 2})
        assert doc2 is doc


class TestEditorMerge:
    def test_editor_merge(self, tmp_path):
        p = tmp_path / "test.yaml"
        p.write_text("a: 1\nb: 2\n", encoding="utf-8")
        with edit(p) as ed:
            ed.merge(value={"a": 99, "c": 3})
        result = p.read_text(encoding="utf-8")
        assert "a: 99" in result
        assert "b: 2" in result
        assert "c: 3" in result


class TestMergeErrors:
    def test_merge_through_scalar_raises(self):
        """Merging through a scalar path raises PatchError."""
        doc = Document("a:\n  b: 1\n")
        with pytest.raises(PatchError):
            doc.merge("a", "b", "c", value={"x": 1})
