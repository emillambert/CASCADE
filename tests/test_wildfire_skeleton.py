from __future__ import annotations

from examples.wildfire_skeleton import main


def test_wildfire_skeleton_example_stdout(capsys) -> None:
    assert main() == 0

    assert capsys.readouterr().out == (
        "custom index: wildfire skeleton\n"
        "peak risk: 0.970\n"
        "action: FUSE\n"
        "priority downlink: True\n"
    )
