"""Diff logic for the sync operation."""

from __future__ import annotations

from typing import Any, TypeAlias

from yamltrip import _core

KeyPart: TypeAlias = "str | int"


def _compute_patches(
    old_value: Any,
    new_value: Any,
    path: tuple[KeyPart, ...],
) -> list[_core.Patch]:
    """Compute minimal patches to transform old_value into new_value at path."""
    if old_value == new_value:
        return []

    old_is_dict = isinstance(old_value, dict)
    new_is_dict = isinstance(new_value, dict)

    if old_is_dict and new_is_dict:
        return _diff_mappings(old_value, new_value, path)

    old_is_list = isinstance(old_value, list)
    new_is_list = isinstance(new_value, list)

    if old_is_list and new_is_list:
        return _diff_lists(old_value, new_value, path)

    # Type mismatch or scalar change — replace
    route = _core.Route(list(path))
    op = _core.Op.replace(new_value)
    return [_core.Patch(route=route, operation=op)]


def _diff_mappings(
    old: dict[str, Any],
    new: dict[str, Any],
    path: tuple[KeyPart, ...],
) -> list[_core.Patch]:
    """Diff two mappings and return patches."""
    patches: list[_core.Patch] = []

    # Keys in new that exist in old — recurse
    for key in new:
        if key in old:
            child_patches = _compute_patches(old[key], new[key], (*path, key))
            patches.extend(child_patches)
        else:
            # New key — add
            route = _core.Route(list(path))
            op = _core.Op.add(key, new[key])
            patches.append(_core.Patch(route=route, operation=op))

    # Keys in old not in new — remove
    for key in old:
        if key not in new:
            route = _core.Route([*path, key])
            op = _core.Op.remove()
            patches.append(_core.Patch(route=route, operation=op))

    return patches


def _diff_lists(
    _old: list[Any],
    new: list[Any],
    path: tuple[KeyPart, ...],
) -> list[_core.Patch]:
    """Diff two lists using SequenceMatcher and return patches.

    Placeholder — will be fully implemented in Task 2.
    """
    route = _core.Route(list(path))
    op = _core.Op.replace(new)
    return [_core.Patch(route=route, operation=op)]
