"""Round-trip preservation tests."""

import pytest

from yamltrip import Document


class TestCommentPreservation:
    def test_inline_comment(self):
        source = "name: foo  # important\nage: 30\n"
        doc = Document(source).replace("name", value="bar")
        assert "# important" in doc.source

    def test_header_comment(self):
        source = "# File header\nname: foo\n"
        doc = Document(source).replace("name", value="bar")
        assert "# File header" in doc.source

    def test_comment_between_keys(self):
        source = "a: 1\n# middle\nb: 2\n"
        doc = Document(source).replace("a", value=10)
        assert "# middle" in doc.source


class TestQuotePreservation:
    def test_single_quotes_replaced(self):
        source = "name: 'foo'\n"
        doc = Document(source).replace("name", value="bar")
        # The value is replaced; we mainly check it round-trips without errors
        assert "bar" in doc.source

    def test_double_quotes(self):
        source = 'name: "foo"\n'
        doc = Document(source).replace("name", value="bar")
        assert "bar" in doc.source


class TestBlankLinePreservation:
    def test_blank_lines_between_sections(self):
        source = "a: 1\n\nb: 2\n"
        doc = Document(source).replace("a", value=10)
        assert "\n\n" in doc.source

    def test_trailing_newline(self):
        source = "name: foo\n"
        doc = Document(source).replace("name", value="bar")
        assert doc.source.endswith("\n")


class TestIndentationPreservation:
    def test_nested_indent_preserved(self):
        source = "parent:\n    child: foo\n    other: bar\n"
        doc = Document(source).replace("parent", "child", value="baz")
        # Check indentation is preserved (4-space indent)
        lines = doc.source.split("\n")
        child_line = [l for l in lines if "child" in l][0]
        assert child_line.startswith("    ")

    def test_two_space_indent(self):
        source = "parent:\n  child: foo\n"
        doc = Document(source).replace("parent", "child", value="baz")
        lines = doc.source.split("\n")
        child_line = [l for l in lines if "child" in l][0]
        assert child_line.startswith("  ")


class TestSequencePreservation:
    def test_append_preserves_sequence_style(self):
        source = "items:\n  - a\n  - b\n"
        doc = Document(source).append("items", value="c")
        assert "- a" in doc.source
        assert "- b" in doc.source
        assert "- c" in doc.source

    def test_remove_preserves_others(self):
        source = "items:\n  - a\n  - b\n  - c\n"
        doc = Document(source).remove_from_list("items", values=["b"])
        assert "- a" in doc.source
        assert "- c" in doc.source
        assert "- b" not in doc.source


class TestIdempotent:
    def test_no_op_roundtrip(self):
        source = "# header\nname: foo  # inline\nitems:\n  - a\n  - b\n"
        doc = Document(source)
        assert doc.source == source

    def test_replace_same_value(self):
        source = "name: foo\n"
        doc = Document(source).replace("name", value="foo")
        # Value should still be there
        assert doc["name"] == "foo"


class TestComplexDocument:
    def test_multi_operation_preserves_structure(self):
        source = (
            "# Config file\n"
            "server:\n"
            "  host: localhost  # default\n"
            "  port: 8080\n"
            "\n"
            "database:\n"
            "  url: postgres://localhost\n"
            "  pool: 5\n"
        )
        doc = Document(source)
        doc = doc.replace("server", "port", value=9090)
        doc = doc.replace("database", "pool", value=10)

        assert "# Config file" in doc.source
        assert "# default" in doc.source
        assert doc["server", "host"] == "localhost"
        assert doc["server", "port"] == 9090
        assert doc["database", "pool"] == 10
