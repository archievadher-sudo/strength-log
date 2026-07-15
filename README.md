# Strength Log

A self-contained web dashboard for tracking a GPP S&C training programme — week-by-week
strength progression, collapsible session blocks (weight / reps columns), a filterable
summary, and per-exercise estimated-1RM charts.

**Live site:** published from `docs/` via GitHub Pages.

## Structure
- `dashboard-fair.html` — the app. Single self-contained file (Bricolage font inlined as a
  data-URI, data + CSS + JS all inline; no build step, no external requests).
- `tracker_data.json` — parsed training data the app reads (generated).
- `build_tracker.py` — parses a RepCount CSV export → `tracker_data.json`
  (filters to the programme start, reconstructs supersets, fixes a logging typo).
- `build_xlsx.py` — optional: emits an `.xlsx` working log.
- `bricolage-b64.txt` — base64 of the Bricolage Grotesque woff2, injected at build.
- `docs/index.html` — the published copy served by GitHub Pages.

## Update flow
1. Edit `dashboard-fair.html` (or re-run `build_tracker.py` with a fresh export, then
   re-inject font + data).
2. `cp dashboard-fair.html docs/index.html`
3. Commit on a branch → open a PR → merge to `main`. Pages redeploys automatically.

## The chart
Each point is the best set that week, converted to an estimated 1-rep max via the Epley
formula: `weight × (1 + reps / 30)`. Bodyweight moves plot top-set reps instead.
