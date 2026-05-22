from yamltrip._display import format_path


class TestFormatPath:
    def test_single_string_key(self):
        assert format_path(("repos",)) == "repos"

    def test_multi_key_path(self):
        assert format_path(("repos", 0, "steps")) == "repos > 0 > steps"

    def test_integer_index(self):
        assert format_path(("items", 2)) == "items > 2"

    def test_empty_tuple_returns_root(self):
        assert format_path(()) == "<root>"
