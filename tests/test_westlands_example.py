# SPDX-License-Identifier: MIT
"""Snapshot test for the SoftwareX worked example."""

from __future__ import annotations

from examples.westlands_replay import main


def test_westlands_replay_example_stdout(capsys) -> None:
    assert main([]) == 0

    assert capsys.readouterr().out == (
        "CASCADE Westlands replay (2014)\n"
        "source: artifacts\n"
        "peak CSC: 0.869\n"
        "FUSE_PRIORITY windows: 6\n"
        "action distribution:\n"
        "  SKIP: 0\n"
        "  MOD13: 0\n"
        "  FUSE: 0\n"
        "  FUSE_PRIORITY: 6\n"
    )
