# SPDX-License-Identifier: MIT
"""SoftwareX word-count helper for the LaTeX manuscript.

Use texcount when it is installed so the submission-day evidence is externally
defensible. Fall back to a conservative local counter for development machines
without texcount.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


TEX = Path(__file__).with_name("cascade_softwarex.tex")


def clean_latex(text: str) -> str:
    text = re.sub(r"%.*", " ", text)
    text = re.sub(r"\\begin\{verbatim\}.*?\\end\{verbatim\}", " ", text, flags=re.S)
    text = re.sub(r"\\(?:texttt|url|href|emph|textbf|path)\{([^{}]*)\}", r" \1 ", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^{}]*\})?", " ", text)
    text = re.sub(r"\$[^$]*\$", " ", text)
    text = re.sub(r"[^A-Za-z0-9.%-]+", " ", text)
    return text


def counted_text(source: str) -> str:
    parts: list[str] = []
    abstract = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", source, re.S)
    if abstract:
        parts.append(abstract.group(1))

    main = re.search(
        r"\\section\{Motivation and significance\}(.*?)(?=\\bibliographystyle)",
        source,
        re.S,
    )
    if main:
        parts.append(main.group(1))

    parts.extend(re.findall(r"\\caption\{(.*?)\}", source, re.S))
    return "\n".join(parts)


def conservative_count() -> int:
    text = clean_latex(counted_text(TEX.read_text(encoding="utf-8")))
    words = [word for word in text.split() if re.search(r"[A-Za-z0-9]", word)]
    return len(words)


def texcount_count() -> int | None:
    if shutil.which("texcount") is None:
        return None

    result = subprocess.run(
        ["texcount", "-inc", "-sum", str(TEX)],
        check=True,
        capture_output=True,
        text=True,
    )
    matches = re.findall(r"\b\d+\b", result.stdout)
    if not matches:
        raise RuntimeError(f"Could not parse texcount output:\n{result.stdout}")
    return int(matches[-1])


def main() -> int:
    texcount_words = texcount_count()
    fallback_words = conservative_count()

    if texcount_words is None:
        print(f"{fallback_words} (conservative fallback; texcount not installed)")
        return 0

    print(f"{texcount_words} (texcount)")
    print(f"{fallback_words} (conservative SoftwareX-scope fallback)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
