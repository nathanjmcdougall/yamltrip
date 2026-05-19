"""End-to-end integration tests exercising file I/O round-trips."""

import yamltrip


class TestLoadMutateDumpLoad:
    def test_load_replace_dump_reload(self, tmp_path):
        p = tmp_path / "config.yml"
        p.write_text("name: Alice\nage: 30\n", encoding="utf-8")

        doc = yamltrip.load(p)
        doc2 = doc.replace("age", value=31)
        doc2.dump(p)

        reloaded = yamltrip.load(p)
        assert reloaded["name"] == "Alice"
        assert reloaded["age"] == 31

    def test_load_add_dump_reload(self, tmp_path):
        p = tmp_path / "config.yml"
        p.write_text("name: Alice\n", encoding="utf-8")

        doc = yamltrip.load(p)
        doc2 = doc.add(key="city", value="Portland")
        doc2.dump(p)

        reloaded = yamltrip.load(p)
        assert reloaded["name"] == "Alice"
        assert reloaded["city"] == "Portland"

    def test_multi_mutation_round_trip(self, tmp_path):
        p = tmp_path / "config.yml"
        p.write_text("version: 1\nitems:\n  - a\n  - b\n", encoding="utf-8")

        doc = yamltrip.load(p)
        doc = doc.replace("version", value=2)
        doc = doc.append("items", value="c")
        doc.dump(p)

        reloaded = yamltrip.load(p)
        assert reloaded["version"] == 2
        assert reloaded["items"] == ["a", "b", "c"]


class TestEditorEndToEnd:
    def test_editor_writes_on_success(self, tmp_path):
        p = tmp_path / "config.yml"
        p.write_text("version: 1\n", encoding="utf-8")

        with yamltrip.edit(p) as editor:
            editor.replace("version", value=2)

        reloaded = yamltrip.load(p)
        assert reloaded["version"] == 2

    def test_editor_discards_on_exception(self, tmp_path):
        p = tmp_path / "config.yml"
        p.write_text("version: 1\n", encoding="utf-8")

        try:
            with yamltrip.edit(p) as editor:
                editor.replace("version", value=2)
                msg = "abort"
                raise RuntimeError(msg)
        except RuntimeError:
            pass

        reloaded = yamltrip.load(p)
        assert reloaded["version"] == 1

    def test_editor_multi_operation(self, tmp_path):
        p = tmp_path / "config.yml"
        p.write_text("name: Alice\nage: 30\nitems:\n  - x\n", encoding="utf-8")

        with yamltrip.edit(p) as editor:
            editor.replace("name", value="Bob")
            editor.replace("age", value=25)
            editor.append("items", value="y")

        reloaded = yamltrip.load(p)
        assert reloaded["name"] == "Bob"
        assert reloaded["age"] == 25
        assert reloaded["items"] == ["x", "y"]


class TestInsertPreCommitRepo:
    """The primary use case: inserting a pre-commit repo at a specific position."""

    def test_insert_repo_between_existing(self):
        source = """\
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
  # ruff for linting
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
"""
        doc = yamltrip.Document(source)
        new_repo = {
            "repo": "https://github.com/psf/black",
            "rev": "23.10.0",
            "hooks": [{"id": "black"}],
        }
        doc2 = doc.insert("repos", index=1, value=new_repo)

        # Verify ordering
        repos = doc2["repos"]
        assert repos[0]["repo"] == "https://github.com/pre-commit/pre-commit-hooks"
        assert repos[1]["repo"] == "https://github.com/psf/black"
        assert repos[2]["repo"] == "https://github.com/astral-sh/ruff-pre-commit"

        # Verify comments preserved
        assert "# ruff for linting" in doc2.source

        # Verify the new repo content
        assert "id: black" in doc2.source
        assert "rev: 23.10.0" in doc2.source
