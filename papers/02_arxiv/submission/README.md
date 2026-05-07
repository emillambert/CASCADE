# arXiv Source Bundle

Prepare the arXiv source bundle only after the TU Delft I&I / patent decision.

Expected bundle contents:

- `manuscript/cascade_arxiv.tex`
- `manuscript/cascade_arxiv.bbl`
- `references.bib`
- `figures/Figure_1_architecture.pdf`
- `figures/Figure_2_baseline_comparison.pdf`
- `figures/Figure_3_replay_modes.pdf`

Build locally from the repository root:

```bash
MPLBACKEND=Agg python papers/02_arxiv/scripts/render_replay_modes_figure.py
papers/02_arxiv/scripts/build_arxiv.sh
```

The arXiv prerelease should point to the intended tag `v1.1.0-arxiv`, not to the
NASA Space-to-Soil submission freeze. The paper must not reintroduce the stale
Westlands drought-vs-quiet validation claim.
