"""Tests for normalize_keys."""

import pytest

from yamltrip.document import normalize_keys


class TestNormalizeKeys:
    def test_str_key(self) -> None:
        assert normalize_keys("foo") == ("foo",)

    def test_int_key(self) -> None:
        assert normalize_keys(0) == (0,)

    def test_tuple_of_str(self) -> None:
        assert normalize_keys(("a", "b")) == ("a", "b")

    def test_tuple_of_int(self) -> None:
        assert normalize_keys((0, 1)) == (0, 1)

    def test_tuple_mixed(self) -> None:
        assert normalize_keys(("a", 0, "b")) == ("a", 0, "b")

    def test_empty_tuple(self) -> None:
        assert normalize_keys(()) == ()

    def test_invalid_type_raises(self) -> None:
        with pytest.raises(TypeError, match="Keys must be str, int, or tuple"):
            normalize_keys([1, 2])

    def test_invalid_tuple_element_raises(self) -> None:
        with pytest.raises(TypeError, match="Key elements must be str or int"):
            normalize_keys(("a", 3.14))
