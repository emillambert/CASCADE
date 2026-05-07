# arXiv Paper Remaining Tasks

This checklist tracks the few remaining external/manual blockers for posting
the corrected arXiv technical report. All manuscript-side items from the
deep-review checklist were closed in commit `e7685be` (`papers/02_arxiv/manuscript/cascade_arxiv.tex`,
PDF rebuilt with `papers/02_arxiv/scripts/build_arxiv.sh`).

## Clearance And Release (still open: external blockers)

- [ ] Run `gh auth login` and create the matching **GitHub release** for tag
  `v1.1.0-arxiv`. After authentication, the release can be created with:
  `gh release create v1.1.0-arxiv --title "CASCADE v1.1.0-arxiv" --notes-file CHANGELOG.md`.
  This step requires interactive credentials and was not run from this agent
  pass.
- [ ] After arXiv assigns an identifier/DOI, add it to:
  - `CITATION.cff` (replace the `arXiv identifier/DOI: TODO after assignment.`
    sentinel and add a `doi:` field),
  - `README.md` (top-of-file citation block),
  - `papers/02_arxiv/manuscript/cascade_arxiv.tex` (Data and Code Availability
    section: replace the `v1.1.0-arxiv` tag-only sentence with the assigned
    arXiv ID/DOI).

## Final Manual Review (still open: human-only checks)

- [ ] Visually inspect the rebuilt PDF
  (`papers/02_arxiv/manuscript/cascade_arxiv.pdf`, 15 pages) end-to-end, not
  only Figure 3, paying particular attention to: Eq. (1) numbering, the new
  TP/FP tile-counting paragraph in Section 3.2, the cliff-edge discussion
  after Figure 6, and the new Acknowledgements section.
- [ ] Confirm no NASA submission files were edited for the arXiv paper.
  Repository currently has pending changes under `papers/01_nasa-space-to-soil/`
  and `papers/03_softwarex/` from prior work; this pass only modified
  `papers/02_arxiv/manuscript/cascade_arxiv.tex` and `papers/02_arxiv/remaining-tasks.md`.

## Posting Rule

Do not post arXiv until clearance is complete and the repository tag/release
state matches the Data and Code Availability statement.
