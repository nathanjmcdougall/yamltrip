import pytest

from yamltrip._core import Op, Patch, Route, apply_patches


class TestOpConstructors:
    def test_replace(self):
        op = Op.replace("bar")
        assert op is not None

    def test_add(self):
        op = Op.add("new_key", "new_value")
        assert op is not None

    def test_remove(self):
        op = Op.remove()
        assert op is not None

    def test_append(self):
        op = Op.append("item")
        assert op is not None

    def test_merge_into_rejects_nested_dict(self):
        with pytest.raises(ValueError, match="merge_into requires scalar values"):
            Op.merge_into("key", {"child": {"nested": 1}})

    def test_merge_into_rejects_nested_list(self):
        with pytest.raises(ValueError, match="merge_into requires scalar values"):
            Op.merge_into("key", {"items": [1, 2, 3]})


class TestApplyPatches:
    def test_replace_value(self):
        source = "name: foo"
        patches = [Patch(route=Route(["name"]), operation=Op.replace("bar"))]
        result = apply_patches(source, patches)
        assert "bar" in result
        assert "foo" not in result

    def test_add_key(self):
        source = "name: foo"
        patches = [Patch(route=Route([]), operation=Op.add("age", 30))]
        result = apply_patches(source, patches)
        assert "age" in result
        assert "30" in result
        assert "name: foo" in result  # original preserved

    def test_remove_key(self):
        source = "name: foo\nage: 30"
        patches = [Patch(route=Route(["age"]), operation=Op.remove())]
        result = apply_patches(source, patches)
        assert "name: foo" in result
        assert "age" not in result

    def test_append_to_sequence(self):
        source = "items:\n  - a\n  - b"
        patches = [Patch(route=Route(["items"]), operation=Op.append("c"))]
        result = apply_patches(source, patches)
        assert "- c" in result
        assert "- a" in result

    def test_replace_with_dict(self):
        source = "config:\n  key: value\n"
        patches = [Patch(route=Route(["config"]), operation=Op.replace({"a": 1}))]
        result = apply_patches(source, patches)
        assert "a: 1" in result
        assert "key: value" not in result

    def test_replace_with_list(self):
        source = "repos: []\n"
        patches = [
            Patch(route=Route(["repos"]), operation=Op.replace([{"repo": "local"}]))
        ]
        result = apply_patches(source, patches)
        assert "repo: local" in result

    def test_batch_scalar_then_complex_then_scalar(self):
        source = "name: foo\nconfig: old\nversion: 1\n"
        patches = [
            Patch(route=Route(["name"]), operation=Op.replace("bar")),
            Patch(route=Route(["config"]), operation=Op.replace({"a": 1})),
            Patch(route=Route(["version"]), operation=Op.replace(2)),
        ]
        result = apply_patches(source, patches)
        assert "name: bar" in result
        assert "a: 1" in result
        assert "version: 2" in result

    def test_preserves_comments(self):
        source = "# top comment\nname: foo  # inline"
        patches = [Patch(route=Route(["name"]), operation=Op.replace("bar"))]
        result = apply_patches(source, patches)
        assert "# top comment" in result
        assert "# inline" in result
        assert "bar" in result

    def test_preserves_indentation(self):
        source = "a:\n    b: 1\n    c: 2"
        patches = [Patch(route=Route(["a", "b"]), operation=Op.replace(99))]
        result = apply_patches(source, patches)
        assert "    b: 99" in result
        assert "    c: 2" in result


class TestOpInsertAt:
    def test_constructor(self):
        op = Op.insert_at(index=1, value="item")
        assert op is not None
        assert op.kind == "insert_at"

    def test_repr(self):
        op = Op.insert_at(index=2, value="hello")
        assert "insert_at" in repr(op)
        assert "2" in repr(op)

    def test_negative_index(self):
        op = Op.insert_at(index=-1, value="item")
        assert op.kind == "insert_at"


class TestApplyPatchesInsertAt:
    def test_insert_at_middle(self):
        source = "items:\n  - a\n  - b\n  - c\n"
        patches = [
            Patch(route=Route(["items"]), operation=Op.insert_at(index=1, value="x"))
        ]
        result = apply_patches(source, patches)
        assert "- a" in result
        assert "- x" in result
        assert "- b" in result
        assert "- c" in result

    def test_insert_at_beginning(self):
        source = "items:\n  - a\n  - b\n"
        patches = [
            Patch(route=Route(["items"]), operation=Op.insert_at(index=0, value="x"))
        ]
        result = apply_patches(source, patches)
        assert "- x" in result
        assert "- a" in result

    def test_insert_at_end_acts_as_append(self):
        source = "items:\n  - a\n  - b\n"
        patches = [
            Patch(route=Route(["items"]), operation=Op.insert_at(index=2, value="x"))
        ]
        result = apply_patches(source, patches)
        assert "- x" in result
        assert "- b" in result

    def test_insert_at_negative_index(self):
        source = "items:\n  - a\n  - b\n  - c\n"
        patches = [
            Patch(route=Route(["items"]), operation=Op.insert_at(index=-1, value="x"))
        ]
        result = apply_patches(source, patches)
        # -1 means before the last item (c), so order should be a, b, x, c
        lines = result.strip().split("\n")
        item_lines = [line.strip() for line in lines if line.strip().startswith("- ")]
        assert item_lines == ["- a", "- b", "- x", "- c"]

    def test_insert_at_clamps_large_positive(self):
        source = "items:\n  - a\n  - b\n"
        patches = [
            Patch(route=Route(["items"]), operation=Op.insert_at(index=100, value="x"))
        ]
        result = apply_patches(source, patches)
        # Should append at end
        lines = result.strip().split("\n")
        item_lines = [line.strip() for line in lines if line.strip().startswith("- ")]
        assert item_lines[-1] == "- x"

    def test_insert_at_clamps_large_negative(self):
        source = "items:\n  - a\n  - b\n"
        patches = [
            Patch(route=Route(["items"]), operation=Op.insert_at(index=-100, value="x"))
        ]
        result = apply_patches(source, patches)
        # Should prepend
        lines = result.strip().split("\n")
        item_lines = [line.strip() for line in lines if line.strip().startswith("- ")]
        assert item_lines[0] == "- x"

    def test_insert_at_complex_value(self):
        source = "repos:\n  - repo: a\n  - repo: c\n"
        patches = [
            Patch(
                route=Route(["repos"]),
                operation=Op.insert_at(
                    index=1, value={"repo": "b", "hooks": [{"id": "check"}]}
                ),
            )
        ]
        result = apply_patches(source, patches)
        assert "repo: a" in result
        assert "repo: b" in result
        assert "repo: c" in result
        assert "id: check" in result

    def test_insert_at_preserves_comments(self):
        source = "items:\n  # first item\n  - a\n  # third item\n  - c\n"
        patches = [
            Patch(route=Route(["items"]), operation=Op.insert_at(index=1, value="b"))
        ]
        result = apply_patches(source, patches)
        assert "# first item" in result
        assert "# third item" in result
        assert "- b" in result
