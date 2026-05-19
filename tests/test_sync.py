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
