"""Diff logic for the sync operation."""

from __future__ import annotations

from difflib import SequenceMatcher
from enum import Enum
from typing import TYPE_CHECKING, Any

from ._core import Op, Patch, Route

if TYPE_CHECKING:
    from yamltrip._types import KeyPart


class DiffMode(Enum):
    """Controls how _compute_patches diffs values."""

    SYNC = "sync"
    """Exact sync: remove extra keys, diff lists element-wise."""

    MERGE = "merge"
    """Additive merge: keep extra keys, replace lists entirely."""


def compute_patches(
    old_value: Any,
    new_value: Any,
    path: tuple[KeyPart, ...],
    *,
    mode: DiffMode = DiffMode.SYNC,
) -> list[Patch]:
    """Compute minimal patches to transform old_value into new_value at path."""
    if old_value == new_value:
        return []

    old_is_dict = isinstance(old_value, dict)
    new_is_dict = isinstance(new_value, dict)

    if old_is_dict and new_is_dict:
        return _diff_mappings(old_value, new_value, path, mode=mode)

    old_is_list = isinstance(old_value, list)
    new_is_list = isinstance(new_value, list)

    if old_is_list and new_is_list:
        if mode is DiffMode.MERGE:
            route = Route(list(path))
            return [Patch(route=route, operation=Op.replace(new_value))]
        return _diff_lists(old_value, new_value, path)

    # Type mismatch or scalar change — replace
    route = Route(list(path))
    op = Op.replace(new_value)
    return [Patch(route=route, operation=op)]


def _diff_mappings(
    old: dict[str, Any],
    new: dict[str, Any],
    path: tuple[KeyPart, ...],
    *,
    mode: DiffMode = DiffMode.SYNC,
) -> list[Patch]:
    """Diff two mappings and return patches."""
    patches: list[Patch] = []

    # Keys in new that exist in old — recurse
    for key in new:
        if key in old:
            child_patches = compute_patches(old[key], new[key], (*path, key), mode=mode)
            patches.extend(child_patches)
        else:
            # New key — add
            route = Route(list(path))
            op = Op.add(key, new[key])
            patches.append(Patch(route=route, operation=op))

    # Keys in old not in new — remove
    if mode is DiffMode.SYNC:
        for key in old:
            if key not in new:
                route = Route([*path, key])
                op = Op.remove()
                patches.append(Patch(route=route, operation=op))

    return patches


def _diff_lists(
    old: list[Any],
    new: list[Any],
    path: tuple[KeyPart, ...],
) -> list[Patch]:
    """Diff two lists using SequenceMatcher and return patches."""
    if not old and not new:
        return []

    # Replacing with empty list: use a single replace instead of removing items
    if not new:
        route = Route(list(path))
        op = Op.replace([])
        return [Patch(route=route, operation=op)]

    # Map items to integers for SequenceMatcher (handles unhashable items)
    int_old, int_new = _shared_int_sequences(old, new)

    sm = SequenceMatcher(None, int_old, int_new, autojunk=False)
    patches: list[Patch] = []

    # Track offset: as inserts/deletes happen, indices in the original shift
    offset = 0

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        elif tag == "replace":
            replace_patches, offset = _apply_replace(
                old, new, path, (i1, i2, j1, j2), offset
            )
            patches.extend(replace_patches)
        elif tag == "insert":
            # Indices assume patches are applied sequentially (each insert
            # shifts subsequent positions). This matches _core.apply_patches.
            for k in range(j1, j2):
                insert_idx = i1 + offset
                route = Route(list(path))
                insert_op = Op.insert_at(index=insert_idx, value=new[k])
                patches.append(Patch(route=route, operation=insert_op))
                offset += 1
        elif tag == "delete":
            # Remove from highest index to lowest within this block
            for k in reversed(range(i1, i2)):
                idx = k + offset
                route = Route([*path, idx])
                remove_op = Op.remove()
                patches.append(Patch(route=route, operation=remove_op))
            offset -= i2 - i1

    return patches


def _apply_replace(
    old: list[Any],
    new: list[Any],
    path: tuple[KeyPart, ...],
    opcode: tuple[int, int, int, int],
    offset: int,
) -> tuple[list[Patch], int]:
    """Handle a 'replace' opcode block, returning patches and updated offset."""
    i1, i2, j1, j2 = opcode
    replace_count = min(i2 - i1, j2 - j1)
    patches: list[Patch] = []
    for k in range(replace_count):
        old_idx = i1 + k + offset
        child_path = (*path, old_idx)
        if isinstance(old[i1 + k], dict) and isinstance(new[j1 + k], dict):
            child_patches = compute_patches(old[i1 + k], new[j1 + k], child_path)
            patches.extend(child_patches)
        else:
            route = Route(list(child_path))
            replace_op = Op.replace(new[j1 + k])
            patches.append(Patch(route=route, operation=replace_op))

    # More new items than old — insert the extras
    for k in range(replace_count, j2 - j1):
        insert_idx = i1 + replace_count + offset
        route = Route(list(path))
        insert_op = Op.insert_at(index=insert_idx, value=new[j1 + k])
        patches.append(Patch(route=route, operation=insert_op))
        offset += 1

    # More old items than new — remove the extras (reverse order)
    remove_indices = [i1 + k + offset for k in range(replace_count, i2 - i1)]
    for idx in reversed(remove_indices):
        route = Route([*path, idx])
        remove_op = Op.remove()
        patches.append(Patch(route=route, operation=remove_op))
        offset -= 1

    return patches, offset


def _shared_int_sequences(
    old: list[Any], new: list[Any]
) -> tuple[list[int], list[int]]:
    """Map list elements to integers equal iff the objects compare equal."""
    rep: list[Any] = []
    int_old: list[int] = []
    int_new: list[int] = []

    for item in old:
        for idx, rep_item in enumerate(rep):
            if item == rep_item:
                int_old.append(idx)
                break
        else:
            int_old.append(len(rep))
            rep.append(item)

    for item in new:
        for idx, rep_item in enumerate(rep):
            if item == rep_item:
                int_new.append(idx)
                break
        else:
            int_new.append(len(rep))
            rep.append(item)

    return int_old, int_new
