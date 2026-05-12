"""Tests for the public API surface."""

import yamltrip


class TestTopLevelFunctions:
    def test_loads(self):
        doc = yamltrip.loads("name: foo")
        assert doc["name"] == "foo"

    def test_load(self, tmp_path):
        p = tmp_path / "test.yml"
        p.write_text("name: bar\n", encoding="utf-8")
        doc = yamltrip.load(p)
        assert doc["name"] == "bar"

    def test_edit(self, tmp_path):
        p = tmp_path / "test.yml"
        p.write_text("name: foo\n", encoding="utf-8")
        with yamltrip.edit(p) as editor:
            editor["name"] = "bar"
        assert "bar" in p.read_text(encoding="utf-8")


class TestExports:
    def test_all_exports_accessible(self):
        for name in yamltrip.__all__:
            assert hasattr(yamltrip, name), f"{name} missing from yamltrip"

    def test_document_class(self):
        assert yamltrip.Document is not None

    def test_editor_class(self):
        assert yamltrip.Editor is not None

    def test_error_classes(self):
        assert issubclass(yamltrip.ParseError, yamltrip.YAMLTripError)
        assert issubclass(yamltrip.QueryError, yamltrip.YAMLTripError)
        assert issubclass(yamltrip.PatchError, yamltrip.YAMLTripError)
        assert issubclass(yamltrip.KeyExistsError, yamltrip.PatchError)
        assert issubclass(yamltrip.KeyMissingError, yamltrip.PatchError)

    def test_core_types(self):
        assert yamltrip.Location is not None
        assert yamltrip.Route is not None
        assert yamltrip.Component is not None
        assert yamltrip.Feature is not None
        assert yamltrip.FeatureKind is not None
