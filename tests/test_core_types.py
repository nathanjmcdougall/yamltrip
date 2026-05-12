from yamltrip._core import Component, FeatureKind, Location, Route


class TestLocation:
    def test_start_end(self):
        loc = Location(start=0, end=5)
        assert loc.start == 0
        assert loc.end == 5

    def test_repr(self):
        loc = Location(start=0, end=5)
        assert "0" in repr(loc)
        assert "5" in repr(loc)


class TestFeatureKind:
    def test_variants_exist(self):
        # FeatureKind uses PascalCase in PyO3 enums
        assert FeatureKind.Scalar is not None
        assert FeatureKind.BlockMapping is not None
        assert FeatureKind.FlowMapping is not None
        assert FeatureKind.BlockSequence is not None
        assert FeatureKind.FlowSequence is not None


class TestComponent:
    def test_key(self):
        c = Component.key("name")
        assert repr(c) == "Component.key('name')"

    def test_index(self):
        c = Component.index(0)
        assert repr(c) == "Component.index(0)"


class TestRoute:
    def test_from_keys(self):
        route = Route(["a", "b"])
        assert len(route) == 2

    def test_from_mixed(self):
        route = Route(["items", 0])
        assert len(route) == 2

    def test_empty(self):
        route = Route([])
        assert len(route) == 0
