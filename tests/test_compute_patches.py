"""Tests for compute_patches."""

import yamltrip
from yamltrip.sync import DiffMode, compute_patches


class TestComputePatchesSync:
    def test_no_change_returns_empty(self) -> None:
        assert compute_patches({"a": 1}, {"a": 1}, ()) == []

    def test_scalar_change(self) -> None:
        patches = compute_patches({"a": 1}, {"a": 2}, ())
        assert len(patches) == 1
        doc = yamltrip.loads("a: 1\n")
        result = doc.sync("a", value=2)
        assert result["a"] == 2

    def test_add_key(self) -> None:
        patches = compute_patches({"a": 1}, {"a": 1, "b": 2}, ())
        assert len(patches) == 1

    def test_remove_key(self) -> None:
        patches = compute_patches({"a": 1, "b": 2}, {"a": 1}, ())
        assert len(patches) == 1

    def test_nested_change(self) -> None:
        patches = compute_patches({"a": {"b": 1}}, {"a": {"b": 2}}, ())
        assert len(patches) == 1

    def test_list_element_change(self) -> None:
        patches = compute_patches([1, 2, 3], [1, 4, 3], ("items",))
        assert len(patches) == 1

    def test_type_mismatch_replaces(self) -> None:
        patches = compute_patches({"a": 1}, {"a": [1, 2]}, ())
        assert len(patches) == 1


class TestComputePatchesMerge:
    def test_no_change_returns_empty(self) -> None:
        assert compute_patches({"a": 1}, {"a": 1}, (), mode=DiffMode.MERGE) == []

    def test_keeps_extra_keys(self) -> None:
        patches = compute_patches({"a": 1, "b": 2}, {"a": 3}, (), mode=DiffMode.MERGE)
        # Only patch for changing "a", "b" is kept
        assert len(patches) == 1

    def test_list_replaced_entirely(self) -> None:
        patches = compute_patches([1, 2, 3], [4, 5], ("items",), mode=DiffMode.MERGE)
        assert len(patches) == 1
