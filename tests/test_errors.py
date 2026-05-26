import pytest

from yamltrip.errors import (
    KeyExistsError,
    KeyMissingError,
    NodeTypeError,
    ParseError,
    PatchError,
    QueryError,
    RoutingError,
    YAMLTripError,
)


class TestErrorHierarchy:
    def test_base_error(self):
        assert issubclass(YAMLTripError, Exception)

    def test_parse_error(self):
        assert issubclass(ParseError, YAMLTripError)

    def test_query_error(self):
        assert issubclass(QueryError, YAMLTripError)

    def test_patch_error(self):
        assert issubclass(PatchError, YAMLTripError)

    def test_key_exists_error(self):
        assert issubclass(KeyExistsError, PatchError)

    def test_key_missing_error(self):
        assert issubclass(KeyMissingError, PatchError)

    def test_node_type_error_inherits_patch_error_and_type_error(self):
        assert issubclass(NodeTypeError, PatchError)
        assert issubclass(NodeTypeError, TypeError)

    def test_raise_and_catch_base(self):
        msg = "key already exists"
        with pytest.raises(YAMLTripError, match=msg):
            raise KeyExistsError(msg)


class TestRoutingErrorHierarchy:
    def test_routing_error_is_patch_error(self):
        assert issubclass(RoutingError, PatchError)

    def test_routing_error_is_not_type_error(self):
        assert not issubclass(RoutingError, TypeError)

    def test_routing_error_is_not_node_type_error(self):
        assert not issubclass(RoutingError, NodeTypeError)

    def test_raise_and_catch_as_patch_error(self):
        msg = "route through scalar"
        with pytest.raises(PatchError):
            raise RoutingError(msg)

    def test_message(self):
        err = RoutingError("Route passes through a non-mapping node at a")
        assert "a" in str(err)
