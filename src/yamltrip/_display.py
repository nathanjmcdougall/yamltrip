"""Display helpers for human-readable formatting."""

from __future__ import annotations


def format_path(keys: tuple[str | int, ...]) -> str:
    """Format a key tuple as a human-readable path string.

    Examples:
        >>> format_path(("repos",))
        'repos'
        >>> format_path(("repos", 0, "steps"))
        'repos > 0 > steps'
        >>> format_path(("a", "b>c"))
        "a > 'b>c'"
        >>> format_path(())
        '<root>'
    """
    if not keys:
        return "<root>"

    def _fmt(k: str | int) -> str:
        s = str(k)
        if ">" in s:
            return f"'{s}'"
        return s

    return " > ".join(_fmt(k) for k in keys)
