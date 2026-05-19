from yamltrip.document import Document


class TestSyncMappingAddKey:
    def test_adds_missing_key(self):
        doc = Document("a: 1\n")
        doc2 = doc.sync(value={"a": 1, "b": 2})
        assert doc2["b"] == 2
        assert doc2["a"] == 1


class TestSyncMappingRemoveKey:
    def test_removes_extra_key(self):
        doc = Document("a: 1\nb: 2\n")
        doc2 = doc.sync(value={"a": 1})
        assert doc2["a"] == 1
        assert ("b",) not in doc2


class TestSyncMappingChangeScalar:
    def test_changes_scalar_value(self):
        doc = Document("a: 1\nb: 2\n")
        doc2 = doc.sync(value={"a": 1, "b": 99})
        assert doc2["b"] == 99
        assert doc2["a"] == 1


class TestSyncMappingNested:
    def test_changes_nested_value(self):
        doc = Document("top:\n  a: 1\n  b: 2\n")
        doc2 = doc.sync("top", value={"a": 1, "b": 99})
        assert doc2["top", "b"] == 99

    def test_adds_nested_key(self):
        doc = Document("top:\n  a: 1\n")
        doc2 = doc.sync("top", value={"a": 1, "b": 2})
        assert doc2["top", "b"] == 2


class TestSyncNoop:
    def test_returns_self_when_no_change(self):
        doc = Document("a: 1\nb: 2\n")
        doc2 = doc.sync(value={"a": 1, "b": 2})
        assert doc2 is doc


class TestSyncListAppend:
    def test_appends_new_items(self):
        doc = Document("items:\n  - a\n  - b\n")
        doc2 = doc.sync("items", value=["a", "b", "c"])
        assert doc2["items"] == ["a", "b", "c"]


class TestSyncListRemove:
    def test_removes_items(self):
        doc = Document("items:\n  - a\n  - b\n  - c\n")
        doc2 = doc.sync("items", value=["a", "c"])
        assert doc2["items"] == ["a", "c"]


class TestSyncListReplace:
    def test_replaces_scalar_item(self):
        doc = Document("items:\n  - a\n  - b\n  - c\n")
        doc2 = doc.sync("items", value=["a", "x", "c"])
        assert doc2["items"] == ["a", "x", "c"]


class TestSyncListInsert:
    def test_inserts_in_middle(self):
        doc = Document("items:\n  - a\n  - c\n")
        doc2 = doc.sync("items", value=["a", "b", "c"])
        assert doc2["items"] == ["a", "b", "c"]


class TestSyncListNoop:
    def test_no_change_returns_self(self):
        doc = Document("items:\n  - a\n  - b\n")
        doc2 = doc.sync("items", value=["a", "b"])
        assert doc2 is doc


class TestSyncListOfDicts:
    def test_recurses_into_matching_dicts(self):
        doc = Document(
            "repos:\n  - repo: foo\n    rev: v1\n  - repo: bar\n    rev: v2\n"
        )
        doc2 = doc.sync(
            "repos", value=[{"repo": "foo", "rev": "v1"}, {"repo": "bar", "rev": "v3"}]
        )
        assert doc2["repos", 1, "rev"] == "v3"
        assert doc2["repos", 0, "rev"] == "v1"
