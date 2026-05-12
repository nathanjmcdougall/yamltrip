import pytest

from yamltrip.editor import Editor


@pytest.fixture
def yaml_file(tmp_path):
    p = tmp_path / "test.yml"
    p.write_text("name: foo\nage: 30\nitems:\n  - a\n  - b\n", encoding="utf-8")
    return p


class TestEditorContextManager:
    def test_read_on_enter(self, yaml_file):
        with Editor(yaml_file) as editor:
            assert editor["name"] == "foo"

    def test_write_on_exit(self, yaml_file):
        with Editor(yaml_file) as editor:
            editor.replace("name", value="bar")
        content = yaml_file.read_text(encoding="utf-8")
        assert "bar" in content

    def test_no_write_on_exception(self, yaml_file):
        with pytest.raises(RuntimeError, match="boom"), Editor(yaml_file) as editor:  # noqa: PT012
            editor.replace("name", value="bar")
            msg = "boom"
            raise RuntimeError(msg)
        content = yaml_file.read_text(encoding="utf-8")
        assert "foo" in content
        assert "bar" not in content

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError), Editor(tmp_path / "missing.yml"):
            pass


class TestEditorOriginal:
    def test_original_unchanged(self, yaml_file):
        with Editor(yaml_file) as editor:
            editor.replace("name", value="bar")
            assert editor.original["name"] == "foo"
            assert editor["name"] == "bar"


class TestEditorOperations:
    def test_replace(self, yaml_file):
        with Editor(yaml_file) as editor:
            editor.replace("name", value="bar")
            assert editor["name"] == "bar"

    def test_upsert(self, yaml_file):
        with Editor(yaml_file) as editor:
            editor.upsert("new_key", value="new_val")
            assert editor["new_key"] == "new_val"

    def test_remove(self, yaml_file):
        with Editor(yaml_file) as editor:
            editor.remove("age")
            assert "age" not in editor

    def test_prune_remove(self, yaml_file):
        p = yaml_file.parent / "nested.yml"
        p.write_text("a:\n  b:\n    c: 1\n", encoding="utf-8")
        with Editor(p) as editor:
            editor.prune_remove("a", "b", "c")
            assert "a" not in editor

    def test_append(self, yaml_file):
        with Editor(yaml_file) as editor:
            editor.append("items", value="c")
            result = editor["items"]
            assert "c" in result

    def test_setitem(self, yaml_file):
        with Editor(yaml_file) as editor:
            editor["name"] = "baz"
            assert editor["name"] == "baz"

    def test_setitem_nested(self, yaml_file):
        with Editor(yaml_file) as editor:
            editor["new", "nested"] = "val"
            assert editor["new", "nested"] == "val"

    def test_contains(self, yaml_file):
        with Editor(yaml_file) as editor:
            assert "name" in editor
            assert "missing" not in editor

    def test_document_attribute(self, yaml_file):
        with Editor(yaml_file) as editor:
            doc = editor.document
            assert doc["name"] == "foo"
