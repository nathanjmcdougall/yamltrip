"""Validate that _core.pyi stubs match the actual native module."""

import subprocess
import sys

import pytest


def _stubtest_supports_ignore_disjoint_bases() -> bool:
    """Check if the installed mypy stubtest supports --ignore-disjoint-bases."""
    result = subprocess.run(
        [sys.executable, "-m", "mypy.stubtest", "--help"],
        capture_output=True,
        text=True,
    )
    return "--ignore-disjoint-bases" in result.stdout


def test_stubtest_core():
    """Run mypy stubtest against yamltrip._core to catch stub drift."""
    cmd = [
        sys.executable,
        "-m",
        "mypy.stubtest",
        "yamltrip._core",
    ]
    if _stubtest_supports_ignore_disjoint_bases():
        cmd.append("--ignore-disjoint-bases")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        pytest.skip("mypy not installed")

    assert result.returncode == 0, (
        f"stubtest found stub mismatches:\n{result.stdout}\n{result.stderr}"
    )
