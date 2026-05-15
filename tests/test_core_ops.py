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
