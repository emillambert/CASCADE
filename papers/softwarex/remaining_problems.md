# SoftwareX Remaining Problems

Last checked: 2026-05-05.

This file tracks only unresolved, conditional, or externally blocked items for the CASCADE SoftwareX submission. Confirmed-good and fixed-local items have been removed. When an item is resolved, delete it from this file rather than keeping a victory lap.

## Hard Blockers

### B2. C2 release tag does not exist

- Status: Open, external.
- Problem: C2 points to `v1.0.0`, but neither local nor remote tag checks currently find `v1.0.0`. Submitting with a dead release URL would fail the permanent-link requirement.
- Evidence: `git ls-remote --tags origin refs/tags/v1.0.0 refs/tags/v1.0.0^{}` returns no tag.
- Next action: after review-ready content is merged upstream, create and publish `v1.0.0` on GitHub, verify the release URL resolves, then recheck C2 and `Current executable software version`.

### B3. Final word-count evidence still needed

- Status: Open, external.
- Problem: The local helper reports a safe count, but it is not `texcount`.
- Evidence: `word_count.py` reports `1562 (conservative fallback; texcount not installed)`.
- Next action: install/use `texcount` or use Overleaf's word count on submission day and keep the evidence with the submission notes.

### B4. Elsevier declarations-tool document missing

- Status: Open, external.
- Problem: The in-manuscript competing-interest declaration is not enough for Elsevier submission.
- Evidence: No generated Elsevier declarations-tool `.doc` or `.docx` is present in the SoftwareX bundle.
- Next action: complete the Elsevier declarations tool and upload the generated `.doc` or `.docx` separately in Editorial Manager.

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
python papers/softwarex/word_count.py
pdftotext papers/softwarex/cascade_softwarex.pdf - | rg '\b(nite|ight|in uence|xture|xtures|rst|nal|speci c|con rm|veri c|satis es|modi ed)\b'
```

The `pdftotext` command should print nothing. Replace the local word-count helper with `texcount` or Overleaf evidence for the final submission record.
