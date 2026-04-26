# Submission Checklist

Derived from "V11 ship list - SE&AD refinements + paper audit." Unchecked items are remaining work. If time is tight, ship Tier A first.

## Tier A - Factual corrections from paper audit

- [x] Fix Kintex naming: replace `AMD Kintex UltraScale+ XQR` with `Kintex UltraScale XQR (XQRKU060)` and keep the flight-qualified rad-tolerant details tied to the XQRKU060 part.
- [x] Fix YAM naming: replace `Your Attitude Module` with `Yet Another Mission`.
- [x] Move the `30-60%` Africa maize-loss citation from Mutanga et al. 2017 to Ward et al. 1999, and keep Dhau/Mutanga 2017 only for remote-sensing detection methodology.
- [x] Rewrite the AeroDelft / HAPSS line so it says HAPSS is led by Conscious Aerospace, AeroDelft is one partner alongside NLR and TU Delft, KLM is a separate Project Phoenix partner, and Airbus is not in HAPSS.
- [x] Reframe `<= 90 min` latency, `<= 30 m` GSD, `<= 15%` FP, and SWAP compliance as CASCADE self-imposed engineering targets rather than NASA challenge mandates.
- [x] Ensure the `8 B lb pesticides` figure is clearly labeled as global, not U.S. Current draft no longer uses that figure.
- [x] Update the Candela et al. citation title to `Dynamic Targeting to Improve Earth Science Missions`.
- [x] Reframe the Westlands `2024-07-27` example as early thermal / VI stress detection rather than drought detection.
- [x] Replace or verify the Katie Gold `2026-02-12` webinar citation so a judge can independently match it.
- [x] Confirm the submitted PDF filename is `EmilLambert_CASCADE.pdf`.

## Tier B - SE&AD ship-now edits

- [x] Reword the FIFRA sentence in section 3 so it is clearly a benchmarked pilot-farm scenario, not an efficacy-style outcome claim.
- [x] Add the three-SKU paragraph in section 4: grower polygon, parametric insurance index, and FAO-ASIS-grid raster from the same onboard alert stream.
- [x] Add a read-only scope line in section 2 or section 5: at TRL-5 CASCADE delivers overlay data only, with no prescription write-back to JDOC / FieldView equipment controllers.
- [x] Split latency framing in section 2 / Table 2 into a defensible two-part budget: space segment `<= 90 min`, end-to-end acquisition-to-grower-tool `<= 6 h` baseline / `<= 1 h` stretch.

## Tier C - Park unless backed by calcs

- [ ] If you mention commissioning / cross-calibration, keep it to the concept only and remove unsupported hard numbers such as `60 days` or `<= 5%` radiometric agreement unless backed by internal analysis.
- [ ] Do not add the `3 satellites -> <= 30 min revisit at 45 deg latitude` claim unless there is a citeable coverage-geometry calculation ready to reference.

## Pre-submission technical QA gate

- [ ] Verify the GitHub repo is publicly accessible while logged out, including the repo root, `README`, `LICENSE`, and `artifacts/`.
- [x] Sync README headline metrics to match the paper / `artifacts/benchmark/simulation_metrics.json`.
- [x] Clean `requirements.txt` so it reflects the actual reproducibility path and removes unused or overly aggressive pins. The stale extra pins noted in the audit are not present locally.
- [x] Run `real_modis_replay.py` from a clean install and confirm the tracked `artifacts/replay/westlands_ca_2024-06-01_2024-10-31/` artifacts reproduce. The current calibrated policy intentionally yields zero `FUSE_PRIORITY` windows for this quiet, sub-threshold season.
- [ ] Run a PDF integrity pass: embedded fonts, `>= 11 pt` everywhere, U.S. Letter, left-justified text, 5 content pages plus references, figures `>= 200 dpi`, no tracked changes/comments, and clean open in an external viewer. Current local PDF is U.S. Letter but still totals `8` pages and `pdffonts` shows Type 3 fonts in figure assets.
- [ ] Compute and record a SHA-256 hash for the submitted PDF.
- [ ] Make an explicit release decision: `Pass`, `Conditional pass`, `Hold`, or `Do not submit`.

## Pitch video

- [ ] Add one ~5-second business-line sentence that the same engine supports insurance parametric triggers and food-security early warning, not just grower alerts.
- [ ] If any on-screen caption spells out YAM, update it to `Yet Another Mission`; otherwise leave captions alone.

## Advisor outreach

- [ ] Keep advisor framing explicitly review-only, with no IPR claim and no critical-path dependency.

## Judge Q&A prep

- [ ] Add the `three SKUs off one alert stream` answer for the `Does this only help growers?` question.
- [ ] Add the `overlay only at TRL-5; no write-back` answer for the `Does it write spray prescriptions back to the tractor?` question.
- [ ] Add the decomposed latency answer: `<= 90 min` to first ground contact plus `<= 6 h` baseline / `<= 1 h` stretch into the grower tool.
- [ ] Add the `self-imposed engineering targets, not NASA mandates` answer for threshold questions.
- [ ] Add the corrected Kintex flight-qualified part answer: `XQRKU060`, `20 nm`, `100 krad(Si)` TID, SEL immunity `>80 MeV*cm^2/mg`.

## Risk register updates

- [ ] Mark EPA FIFRA `Sec. 12(a)(1)(B)` marketing-claim exposure as medium until the section 3 reword ships, then low.
- [ ] Mark single-channel business framing as low once the three-SKU paragraph is in place.
- [ ] Mark unsourced commissioning / revisit numbers as medium risk if added without support; resolved if parked.
- [ ] Mark the paper-audit factual errors as medium until Tier A ships, then low.
- [ ] Mark repo public-verifiability as high until confirmed public and README-synced.
- [ ] Mark paper-to-README metric mismatch as medium until the README sync is done.

## Do not touch

- Leave the Loft Orbital hosted-payload / YAM baseline unchanged for V11.
- Leave the current NASA pathway scope unchanged unless a later round needs expansion.
- Keep the `$4/ha/year` Y1-Y5 table; only add a design-to-cost ceiling if it fits naturally.

## Suggested execution order

- Under 30 minutes: do Tier A items 1, 2, 7, 6, and 10, plus QA gate items for repo public verification and PDF integrity.
- Around 60 minutes: finish all Tier A items and sync the README.
- Around 90 minutes: finish Tier A, do Tier B items 1 and 2, and sync the README.
- Around 2 hours: finish Tier A, all Tier B edits, and the full technical QA gate.
- Everything else belongs to the AIST round or finalist-pitch layer unless it materially affects this submission.
