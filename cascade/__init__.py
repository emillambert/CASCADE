from __future__ import annotations

from pathlib import Path

# Source-tree convenience: allow `python -m cascade.*` without requiring an
# editable install. This mirrors the packaging layout (actual code lives in
# `src/cascade/`) while keeping judge workflows one-command simple.
_SRC_ROOT = (Path(__file__).resolve().parent.parent / "src" / "cascade").resolve()
if _SRC_ROOT.is_dir():
    __path__.append(str(_SRC_ROOT))  # type: ignore[name-defined]

