# MASFE 7-Slide Video Script

Target runtime: `2:50`

## Slide 1 - Problem and challenge fit (`0:00-0:22`)

Space-to-Soil asks how to turn Earth observation into something actionable for people on the ground. MASFE answers that by moving crop-stress triage onboard, so the spacecraft decides what matters before the data ever hits the ground.

## Slide 2 - Architecture (`0:22-0:46`)

MASFE is a two-stage hosted payload. A MOD13A1-style EVI screen runs every pass, a MOD11A1-style thermal confirmation runs only on suspicious patches, and a LEON4FT-class policy engine decides whether to skip, screen, fuse, or priority-downlink alerts.

## Slide 3 - Real-scene replay (`0:46-1:13`)

This is the strongest real-scene proof point: a Westlands/Firebaugh replay on official MODIS products. On July 27, 2024, the unchanged policy issued a confirmed FUSE_PRIORITY alert, showing real-time scheduler behavior on real scenes rather than just synthetic data.

## Slide 4 - Monte Carlo benchmark (`1:13-1:40`)

Across 100 synthetic seeds, MASFE reduces downlink by 96.4% versus raw collection, saves 20.6% payload energy, retains 100% disease-event recall, and keeps false-positive rate at 1.4%. Relative to a fixed onboard baseline, the adaptive layer still saves 3.5% payload energy by deferring Stage 2 to anomaly-bearing passes.

## Slide 5 - Business rollout (`1:40-2:05`)

The business starts with a paid San Joaquin Valley pilot, scales through Climate FieldView and John Deere Operations Center, then expands internationally through xarvio and CropX. In the low design-to-cost case, MASFE reaches U.S.-scale profitability in Year 3 at 2.5 million hectares without changing the onboard architecture.

## Slide 6 - Next steps (`2:05-2:28`)

The next milestone is hardware-in-the-loop timing validation on a LEON4FT-class platform under the NASA AIST pathway, followed by a hosted-payload pilot. The key non-technical gap after that is agronomy-side validation of the Year 1 paid-pilot assumptions and partner plausibility.

## Slide 7 - Close (`2:28-2:50`)

MASFE is not just a crop-monitoring concept. It is an onboard resource-allocation engine that uses existing NASA algorithms more intelligently, turning passive collection into real-time, on-orbit decision-making.
