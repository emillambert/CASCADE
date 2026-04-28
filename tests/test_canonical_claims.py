from __future__ import annotations

import pytest

from cascade.replay import replay


def test_westlands_2014_peak():
    res = replay(year=2014)
    assert res["source"] == "artifacts"
    assert res["peak_csc"] == pytest.approx(0.869, abs=0.005)
    assert res["fuse_priority_windows"] == 6
