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


class TestExtractCrossDocument:
    """Using a Feature from one document on another must raise ValueError."""

    def test_extract_cross_document_rejected(self):
        doc_a = Document("x: y")
        feature = doc_a.query_exact(Route(["x"]))
        assert feature is not None

        doc_b = Document("a: b")
        with pytest.raises(ValueError, match="does not belong"):
            doc_b.extract(feature)

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

        # Should raise ValueError — now caught by source_hash check first.
        with pytest.raises(ValueError, match="does not belong"):
            doc_b.extract(feature)


class TestParseValueUTF8:
    """parse_value must not panic on documents with multi-byte UTF-8 chars."""

    def test_parse_value_multibyte_key(self):
        doc = Document("🔑: hello")
        assert doc.parse_value(Route(["🔑"])) == "hello"

    def test_parse_value_multibyte_value(self):
        doc = Document("key: 🎉")
        assert doc.parse_value(Route(["key"])) == "🎉"

    def test_parse_value_multibyte_nested(self):
        doc = Document("日本:\n  名前: こんにちは")
        assert doc.parse_value(Route(["日本", "名前"])) == "こんにちは"

    def test_parse_value_multibyte_multiline_dedent(self):
        """Exercises the dedenting path with multi-byte characters."""
        doc = Document("parent:\n  子: |\n    日本語テキスト\n    二行目")
        result = doc.parse_value(Route(["parent", "子"]))
        assert "日本語テキスト" in result


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
