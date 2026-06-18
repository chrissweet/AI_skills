# /graph-data-extraction — Chart Digitization

A Claude Code skill for recovering numeric data from raster images of charts (scatter, line, bar, histogram) when the underlying numbers aren't available. The output is a calibrated CSV plus a reconstructed re-plot used as a self-check.

## Install

```bash
# from the AI_skills repo root:
bash scripts/install-skills.sh
```

The skill becomes invocable as `/graph-data-extraction` from any Claude Code session. It also triggers on phrasing like "extract the data from this plot", "digitize this graph", "turn this chart into a CSV".

## Quickstart

Example prompts that would invoke this skill:

- "Digitize the curves in `figure_3.png` and give me a CSV."
  Five-phase workflow: render at 300 DPI → calibrate axes from tick labels → extract by chart type → re-plot and compare → deliver with caveats.
- "Get the points out of this scatter plot — there's a regression line in the same color as the markers."
  Triggers the §3b fit-curve subtraction recipe (per-column thin-run subtraction with paired-edge preservation).
- "Extract the marker positions from this grayscale figure where the three series are filled-disk / gray-square / open-diamond."
  Triggers the §2b grayscale-shape classifier (no color cue → classify by area density).

## What it knows

- **The Phase-4 close-the-loop rule** — every extraction must end by re-plotting the CSV and visually comparing against the source. Documented in METHODOLOGY.md: across real extractions, multiple legend-occlusion artifacts have survived Phase 3 and were caught only here.
- **Axis calibration with the y-band crop fix** — cap the y-tick label crop at `bot − 10` so the bottom-left "0" of the x-axis doesn't bleed into the y-tick band and bias the fit.
- **§3a marker-on-line** — for line plots where the line just connects markers at integer-x values, erode by (line_width + 2) px to wipe the connector, then CC + centroid. Replaces the column-thickness peak detection that gives false positives at sharp line bends.
- **§3b fit-curve subtraction** — per-column thin-run subtraction with paired-edge preservation. A thin run with no thin neighbor = curve trace → subtract. Two thin runs at marker-height spacing = an open marker's top/bottom edges → preserve. Documented failure modes: filled-marker-on-solid-curve, dotted curves with marker-height-spaced dots, steep curves, crossing curves.
- **§2b grayscale-shape classifier** — classify markers by area / density when there's no color cue. Filled disk → `gray<50 + erode + CC`. Solid square → `density>0.55, area>30`. Open diamond → `0.15<density<0.5, area 12-90`.
- **§4a bar via outline** — when a bar fill is stippled or dotted and CC fragments it, detect bar tops by scanning for a horizontal dark border (gray<160, run length ≈ bar width).
- **Hazards documented inline** — legend occlusion, gridline color collision, dashed-line fragments (aspect-ratio > 2.5 filter), legend text descenders, x-tick bleed into y-band.

## Performance on a real test set

Benchmarked against eight charts from a published paper, with the paper's pre-existing extraction as ground truth (251 GT points, 239 predicted): **Precision 0.92, Recall 0.88, F1 0.90**. Five of eight charts perfect (F1 = 1.00); the other three hit failure modes called out explicitly in METHODOLOGY.md.

Full per-chart breakdown in [`docs/graph_extraction_eval_R3.pdf`](../../docs/graph_extraction_eval_R3.pdf) and the longer [`docs/graph_extraction_full_report.pdf`](../../docs/graph_extraction_full_report.pdf).

## Source / details

- **Skill body (LLM-facing)**: [`SKILL.md`](SKILL.md) in this directory — what Claude Code loads.
- **Methodology (human-facing)**: [`METHODOLOGY.md`](METHODOLOGY.md) — five-phase workflow rationale + the "what this covers vs not" honest assessment.
- **Recipes**: [`references/extraction_recipes.md`](references/extraction_recipes.md) — per-chart-type code with a chooser table and a Hazards section.
- **Calibration**: [`references/calibration.md`](references/calibration.md) — frame and tick-label detection, linear and log axis fitting.
- **Re-plot validation**: [`references/replot_and_validate.md`](references/replot_and_validate.md) — Matplotlib templates and artifact-detection heuristics.
- **Helper scripts**: `scripts/calibrate.py`, `scripts/extract_markers.py`, `scripts/subtract_curves.py`, `scripts/check_artifacts.py`.
- **Wiki synthesis**: [Skill-graph-data-extraction](https://github.com/chrissweet/AI_skills/wiki/Skill-graph-data-extraction) — methodology summary + failure modes + benchmark results.

## Dependencies

Python 3 with `opencv-python-headless`, `numpy`, `matplotlib`. Optional: `scikit-learn` for overlapping-marker k-means split. Poppler (`pdftoppm`) for getting figures out of PDF pages at 300 DPI.

```bash
pip install opencv-python-headless numpy matplotlib scikit-learn
```

## When NOT to use

- Numbers already printed on the chart or in an adjacent table (just transcribe).
- User supplied the underlying CSV (plot from that instead).
- "Chart" is actually a diagram, schematic, or flowchart with no quantitative axes (describe it instead).
