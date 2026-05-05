# SoftwareX Remaining Problems

Last checked: 2026-05-05.

This file tracks only unresolved, conditional, or externally blocked items for the CASCADE SoftwareX submission. Confirmed-good and fixed-local items have been removed. When an item is resolved, delete it from this file rather than keeping a victory lap.

## Hard Blockers

### B2. C2 release tag does not exist

- Status: Open, external.
- Problem: C2 points to `v1.0.0`, but neither local nor remote tag checks currently find `v1.0.0`. Submitting with a dead release URL would fail the permanent-link requirement.
- Evidence: `git ls-remote --tags origin refs/tags/v1.0.0 refs/tags/v1.0.0^{}` returns no tag.
- Next action: after review-ready content is merged upstream, create and publish `v1.0.0` on GitHub, verify the release URL resolves, then recheck C2 and `Current executable software version`.

## Conditional Items

### C3. Optional Zenodo DOI

- Status: Conditional / external.
- Problem: Zenodo is recommended for citation durability but cannot replace the GitHub URL in C2.
- Evidence: No Zenodo DOI is recorded for `v1.0.0`.
- Next action: mint a Zenodo DOI for the accepted `v1.0.0` GitHub release if the GitHub-Zenodo integration is ready, then cite it in README/data availability text.

## Final Checks For Remaining Items

Run these immediately before submission:

```bash
git ls-remote --tags origin refs/tags/v1.0.0 'refs/tags/v1.0.0^{}'
latexmk -pdf -interaction=nonstopmode -halt-on-error cascade_softwarex.tex
perl /tmp/cascade-texcount/texcount.pl -inc -sum papers/softwarex/cascade_softwarex.tex
pdftotext papers/softwarex/cascade_softwarex.pdf - | rg '\b(nite|ight|in uence|xture|xtures|rst|nal|speci c|con rm|veri c|satis es|modi ed)\b'
```

The `pdftotext` command should print nothing. The latest `texcount` evidence is recorded in `word_count_evidence.txt`.
