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

    def test_eq(self):
        assert Location(0, 5) == Location(0, 5)
        assert Location(0, 5) != Location(0, 6)

    def test_hash(self):
        s = {Location(0, 5), Location(0, 5), Location(0, 6)}
        assert len(s) == 2


class TestFeatureKind:
    def test_variants_exist(self):
        # FeatureKind uses PascalCase in PyO3 enums
        assert FeatureKind.Scalar is not None
        assert FeatureKind.BlockMapping is not None
        assert FeatureKind.FlowMapping is not None
        assert FeatureKind.BlockSequence is not None
        assert FeatureKind.FlowSequence is not None

    def test_hash(self):
        s = {FeatureKind.Scalar, FeatureKind.BlockMapping, FeatureKind.Scalar}
        assert len(s) == 2


class TestComponent:
    def test_key(self):
        c = Component.key("name")
        assert repr(c) == "Component.key('name')"

    def test_index(self):
        c = Component.index(0)
        assert repr(c) == "Component.index(0)"

    def test_eq(self):
        assert Component.key("a") == Component.key("a")
        assert Component.key("a") != Component.key("b")
        assert Component.index(0) == Component.index(0)
        assert Component.key("0") != Component.index(0)

    def test_hash(self):
        s = {Component.key("a"), Component.key("a"), Component.key("b")}
        assert len(s) == 2


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

    def test_eq(self):
        assert Route(["a", "b"]) == Route(["a", "b"])
        assert Route(["a"]) != Route(["a", "b"])

    def test_hash(self):
        s = {Route(["a", "b"]), Route(["a", "b"]), Route(["a"])}
        assert len(s) == 2
