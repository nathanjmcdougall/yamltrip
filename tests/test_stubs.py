"""Validate that _core.pyi stubs match the actual native module."""

import subprocess
import sys

import pytest


def test_stubtest_core():
    """Run mypy stubtest against yamltrip._core to catch stub drift."""
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "mypy.stubtest",
                "yamltrip._core",
                "--ignore-disjoint-bases",
            ],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        pytest.skip("mypy not installed")

    assert result.returncode == 0, (
        f"stubtest found stub mismatches:\n{result.stdout}\n{result.stderr}"
    )
