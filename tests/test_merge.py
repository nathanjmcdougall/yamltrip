from yamltrip.document import Document


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
