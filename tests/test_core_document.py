import pytest

from yamltrip._core import Document, FeatureKind, Route


class TestDocumentParsing:
    def test_parse_simple(self):
        doc = Document("name: foo")
        assert doc.source() == "name: foo"

    def test_parse_invalid_raises(self):
        with pytest.raises(ValueError, match="Failed to parse YAML"):
            Document("{")


class TestDocumentQuery:
    def test_query_exists_true(self):
        doc = Document("name: foo")
        route = Route(["name"])
        assert doc.query_exists(route) is True

    def test_query_exists_false(self):
        doc = Document("name: foo")
        route = Route(["missing"])
        assert doc.query_exists(route) is False

    def test_query_exact(self):
        doc = Document("name: foo")
        route = Route(["name"])
        feature = doc.query_exact(route)
        assert feature is not None
        assert feature.location.start >= 0
        assert feature.location.end > feature.location.start

    def test_query_exact_missing(self):
        doc = Document("name: foo")
        route = Route(["missing"])
        with pytest.raises(KeyError):
            doc.query_exact(route)

    def test_extract(self):
        doc = Document("name: foo")
        route = Route(["name"])
        feature = doc.query_exact(route)
        assert feature is not None
        assert doc.extract(feature) == "foo"

    def test_nested_query(self):
        doc = Document("a:\n  b: 42")
        route = Route(["a", "b"])
        feature = doc.query_exact(route)
        assert feature is not None
        assert doc.extract(feature) == "42"

    def test_sequence_query(self):
        doc = Document("items:\n  - a\n  - b")
        route = Route(["items", 0])
        feature = doc.query_exact(route)
        assert feature is not None
        assert doc.extract(feature) == "a"


class TestExtractCrossDocumentUTF8:
    """Using a Feature from one document on another can produce byte offsets
    that land mid-UTF-8 codepoint.  This must raise ValueError, not crash."""

    def test_extract_mid_utf8_raises_not_panics(self):
        # "x: y" — scalar "y" is at byte offset 3..4
        doc_a = Document("x: y")
        feature = doc_a.query_exact(Route(["x"]))
        assert feature is not None
        assert feature.location.start == 3
        assert feature.location.end == 4

        # "🎉: z" — 🎉 is 4 UTF-8 bytes (F0 9F 8E 89), so byte 3 is a
        # continuation byte, not a char boundary.
        doc_b = Document("\U0001f389: z")

        # Should raise a clean ValueError, not a Rust panic / PanicException.
        with pytest.raises(ValueError, match="UTF-8"):
            doc_b.extract(feature)


class TestDocumentFeatureKind:
    def test_scalar_kind(self):
        doc = Document("name: foo")
        route = Route(["name"])
        feature = doc.query_exact(route)
        assert feature is not None
        assert feature.kind == FeatureKind.Scalar

    def test_mapping_kind(self):
        doc = Document("a:\n  b: 1")
        route = Route(["a"])
        feature = doc.query_exact(route)
        assert feature is not None
        assert feature.kind == FeatureKind.BlockMapping
