from yamltrip.document import Document
from yamltrip.editor import Editor


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


class TestSyncPreservesComments:
    def test_mapping_comment_preserved_on_unchanged_key(self):
        source = "# top comment\na: 1\n# b comment\nb: 2\n"
        doc = Document(source)
        doc2 = doc.sync(value={"a": 99, "b": 2})
        assert "# b comment" in doc2.source
        assert "# top comment" in doc2.source

    def test_mapping_comment_preserved_on_changed_key(self):
        source = "# a comment\na: 1\n# b comment\nb: 2\n"
        doc = Document(source)
        doc2 = doc.sync(value={"a": 1, "b": 99})
        assert "# b comment" in doc2.source

    def test_list_comment_preserved_on_unchanged_item(self):
        source = "items:\n  # first\n  - a\n  # second\n  - b\n  # third\n  - c\n"
        doc = Document(source)
        doc2 = doc.sync("items", value=["a", "x", "c"])
        assert "# first" in doc2.source
        assert "# third" in doc2.source


class TestSyncPathNotExists:
    def test_creates_path_via_upsert(self):
        doc = Document("a: 1\n")
        doc2 = doc.sync("b", value=2)
        assert doc2["b"] == 2
        assert doc2["a"] == 1

    def test_creates_nested_path(self):
        doc = Document("a: 1\n")
        doc2 = doc.sync("b", "c", value=3)
        assert doc2["b", "c"] == 3


class TestSyncTypeMismatch:
    def test_mapping_to_scalar(self):
        doc = Document("a:\n  x: 1\n  y: 2\n")
        doc2 = doc.sync("a", value="hello")
        assert doc2["a"] == "hello"

    def test_scalar_to_mapping(self):
        doc = Document("a: hello\n")
        doc2 = doc.sync("a", value={"x": 1})
        assert doc2["a"] == {"x": 1}

    def test_list_to_scalar(self):
        doc = Document("a:\n  - 1\n  - 2\n")
        doc2 = doc.sync("a", value="flat")
        assert doc2["a"] == "flat"


class TestSyncRootLevel:
    def test_sync_entire_root(self):
        doc = Document("a: 1\nb: 2\n")
        doc2 = doc.sync(value={"a": 1, "b": 2, "c": 3})
        assert doc2["c"] == 3

    def test_sync_root_remove_key(self):
        doc = Document("a: 1\nb: 2\n")
        doc2 = doc.sync(value={"a": 1})
        assert ("b",) not in doc2


class TestSyncEmptyValues:
    def test_sync_empty_dict_removes_all_keys(self):
        doc = Document("a: 1\nb: 2\n")
        doc2 = doc.sync(value={})
        # After removing all keys, neither key should exist
        assert ("a",) not in doc2
        assert ("b",) not in doc2

    def test_sync_empty_list_removes_all_items(self):
        doc = Document("items:\n  - a\n  - b\n")
        doc2 = doc.sync("items", value=[])
        assert doc2["items"] == []


class TestSyncFlowSequence:
    def test_sync_empty_flow_sequence_to_nonempty(self):
        doc = Document("repos: []\n")
        doc2 = doc.sync("repos", value=["a", "b"])
        assert doc2["repos"] == ["a", "b"]

    def test_sync_nonempty_flow_sequence_append(self):
        doc = Document("items: [a, b]\n")
        doc2 = doc.sync("items", value=["a", "b", "c"])
        assert doc2["items"] == ["a", "b", "c"]

    def test_sync_nonempty_flow_sequence_insert(self):
        doc = Document("items: [a, c]\n")
        doc2 = doc.sync("items", value=["a", "b", "c"])
        assert doc2["items"] == ["a", "b", "c"]

    def test_sync_flow_sequence_replace_only_no_fallback_needed(self):
        doc = Document("items: [a, b]\n")
        doc2 = doc.sync("items", value=["x", "y"])
        assert doc2["items"] == ["x", "y"]

    def test_sync_flow_sequence_to_empty(self):
        doc = Document("items: [a, b]\n")
        doc2 = doc.sync("items", value=[])
        assert doc2["items"] == []

    def test_sync_flow_sequence_nested_in_mapping(self):
        doc = Document("config:\n  items: []\n")
        doc2 = doc.sync("config", "items", value=["x"])
        assert doc2["config", "items"] == ["x"]


class TestSyncNullValue:
    def test_sync_to_none(self):
        doc = Document("a: 1\n")
        doc2 = doc.sync("a", value=None)
        assert doc2["a"] is None


class TestEditorSync:
    def test_sync_mapping(self, tmp_path):
        p = tmp_path / "test.yml"
        p.write_text("a: 1\nb: 2\n", encoding="utf-8")
        with Editor(p) as ed:
            ed.sync(value={"a": 1, "b": 99, "c": 3})
        content = p.read_text(encoding="utf-8")
        assert "b: 99" in content
        assert "c: 3" in content

    def test_sync_noop_preserves_content(self, tmp_path):
        p = tmp_path / "test.yml"
        p.write_text("a: 1\nb: 2\n", encoding="utf-8")
        with Editor(p) as ed:
            ed.sync(value={"a": 1, "b": 2})
        content = p.read_text(encoding="utf-8")
        assert content == "a: 1\nb: 2\n"

    def test_sync_with_path(self, tmp_path):
        p = tmp_path / "test.yml"
        p.write_text("top:\n  a: 1\n", encoding="utf-8")
        with Editor(p) as ed:
            ed.sync("top", value={"a": 2})
        content = p.read_text(encoding="utf-8")
        assert "a: 2" in content


class TestSyncIntegration:
    def test_precommit_style_config(self):
        source = (
            "repos:\n"
            "  # Formatting\n"
            "  - repo: https://github.com/pre-commit/mirrors-prettier\n"
            "    rev: v3.0.0\n"
            "    hooks:\n"
            "      - id: prettier\n"
            "  # Linting\n"
            "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
            "    rev: v0.4.0\n"
            "    hooks:\n"
            "      - id: ruff\n"
            "        args: [--fix]\n"
        )
        doc = Document(source)

        new_repos = [
            {
                "repo": "https://github.com/pre-commit/mirrors-prettier",
                "rev": "v3.0.0",
                "hooks": [{"id": "prettier"}],
            },
            {
                "repo": "https://github.com/astral-sh/ruff-pre-commit",
                "rev": "v0.5.0",  # version bump
                "hooks": [{"id": "ruff", "args": ["--fix"]}],
            },
        ]

        doc2 = doc.sync("repos", value=new_repos)

        # Version was bumped
        assert doc2["repos", 1, "rev"] == "v0.5.0"
        # First repo unchanged
        assert doc2["repos", 0, "rev"] == "v3.0.0"
        # Comments preserved
        assert "# Formatting" in doc2.source
        assert "# Linting" in doc2.source

    def test_multi_level_sync(self):
        source = "ci:\n  autofix_prs: true\n  skip:\n    - codespell\n    - ruff\n"
        doc = Document(source)
        doc2 = doc.sync("ci", value={"autofix_prs": False, "skip": ["codespell"]})
        assert doc2["ci", "autofix_prs"] is False
        assert doc2["ci", "skip"] == ["codespell"]
