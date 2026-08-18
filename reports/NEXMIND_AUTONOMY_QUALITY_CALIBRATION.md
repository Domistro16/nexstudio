# NexMind Autonomous Creative Authority — Quality / Taste Calibration

**Status:** IMPLEMENTED / REAL CALIBRATION DATASET EMPTY / AUTONOMOUS COMMERCIAL LOCK DISABLED

## Calibration model

Studio does not use one aggregate quality score. The Final Producer keeps hard gates, craft, taste, divergence, confidence, multimodal evidence and machine↔human calibration separate so a strong average cannot hide a weak dimension.

### Automated acceptance floors

- all hard gates must PASS;
- craft mean >= 9.0;
- taste mean >= 9.0;
- every craft/taste dimension >= 8.5;
- critical dimensions >= 9.0;
- novelty >= 6.5;
- template similarity <= 4.0;
- zero LOW-confidence scored dimensions;
- complete hash-bound video/audio multimodal evidence.

### Calibration required to remove routine humans

The first 12 real blind reviews only make correlation computation eligible. Routine no-human Creative Lock requires all of the following:

- >= 36 non-synthetic independent blind reviews;
- >= 12 distinct productions;
- >= 6 reviews for each of Explainer, Whiteboard, Stickman and Editorial Motion;
- mean machine↔human correlation >= 0.80;
- every measured dimension correlation >= 0.60;
- mean absolute error <= 0.70;
- maximum per-dimension absolute error <= 1.00;
- maximum machine optimism bias <= 0.35;
- zero machine false accepts against a failed human elite gate.

Synthetic reviews never count. Each calibration record binds the exact machine final review, blind human review and multimodal evidence hash.

## Current measured calibration state

- real eligible blind review records: **0**;
- distinct calibrated productions: **0**;
- family coverage: **0/4**;
- correlation / error / optimism metrics: **not computable**;
- autonomous commercial Creative Lock: **disabled by policy**;
- human bridge: **still mandatory after automated quality passes**.

No score is inferred from deterministic fixtures. This is an evidence absence, not a failed correlation score.
