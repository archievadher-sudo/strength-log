#!/usr/bin/env python3
"""Parse the RepCount CSV export into a structured week-by-week training tracker.

- Filters to the programme start (>= 2026-06-28).
- Reconstructs superset blocks (the one thing RepCount loses) from a hand-coded
  programme definition keyed on normalised exercise names.
- Emits a JSON blob (consumed by the dashboard) and an .xlsx working log.
"""
import csv, json, re, unicodedata
from collections import defaultdict, OrderedDict
from datetime import datetime

CSV_PATH = "/Users/fmy-235/Downloads/export_15 Jul 2026.csv"
OUT_DIR = "/Users/fmy-235/Desktop/Training-Tracker"
START = "2026-06-28"

# ---- name normalisation -------------------------------------------------
def norm(s):
    s = unicodedata.normalize("NFKC", s).strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s

# canonical display names + fixes for the source typos
CANON = {
    "ffe split squat": "FFE split squat",
    "prone t": "Prone T",
    "goblet squat": "Goblet squat",
    "arnold press": "Arnold press",
    "push up should tap": "Push-up shoulder tap",
    "b stance rdl": "B-stance RDL",
    "seated cable press": "Seated cable press",
    "1 arm 3 point": "1-arm 3-point row",
    "frontal plane lunge": "Frontal plane lunge",
    "iso split squat": "Iso split squat",
    "inclune tension curl": "Incline tension curl",
    "lying tricep extension": "Lying tricep extension",
    "single leg hip raise": "Single-leg hip raise",
    "cable cross back": "Cable cross-back",
    "rdl": "RDL",
    "single arm overhead press": "Single-arm overhead press",
    "deadbug": "Deadbug",
    "split squat": "Split squat",
    "floor chest press": "Floor chest press",
    "dumbbell row bench": "Dumbbell row (bench)",
    "seated db lateral raise": "Seated DB lateral raise",
    "seated db curl to press": "Seated DB curl-to-press",
    "tricep pushdown cable rope": "Tricep pushdown (rope)",
}

# ---- programme definition: superset blocks per session ------------------
# block label -> list of canonical exercise names, in order
PROGRAMME = {
    "GPP S&C 1": [
        ("Prep",  ["FFE split squat", "Prone T"]),
        ("Block 1", ["Goblet squat", "Arnold press", "Push-up shoulder tap"]),
        ("Block 2", ["B-stance RDL", "Seated cable press", "1-arm 3-point row"]),
        ("Block 3", ["Frontal plane lunge", "Iso split squat"]),
        ("Block 4", ["Incline tension curl", "Lying tricep extension"]),
    ],
    "GPP S&C 2": [
        ("Prep",  ["Single-leg hip raise", "Cable cross-back"]),
        ("Block 1", ["RDL", "Single-arm overhead press", "Deadbug"]),
        ("Block 2", ["Split squat", "Floor chest press", "Dumbbell row (bench)"]),
        ("Block 3", ["Seated DB lateral raise", "Seated DB curl-to-press", "Tricep pushdown (rope)"]),
    ],
}

# which CSV "Name" maps to which session key
SESSION_MAP = {
    "gpp s&c": "GPP S&C 1",
    "gpp s&c2": "GPP S&C 2",
    "gpp s&c 3": "GPP S&C 3",  # future
}

# ---- parse CSV ----------------------------------------------------------
# structure: data[session][date][canon_exercise] = [(w,reps), ...]
data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
with open(CSV_PATH, newline="") as f:
    for r in csv.DictReader(f):
        start = r["Workout Start"]
        if not start or start[:10] < START:
            continue
        date = start[:10]
        sess_raw = norm(r["Name"])
        if sess_raw not in SESSION_MAP:
            continue
        session = SESSION_MAP[sess_raw]
        ex = CANON.get(norm(r["Exercise"]), r["Exercise"].strip())
        try:
            w = float(r["Weight"]) if r["Weight"] else 0.0
        except ValueError:
            w = 0.0
        try:
            reps = int(float(r["Reps"])) if r["Reps"] else 0
        except ValueError:
            reps = 0
        # fix the obvious "12.5 x 80" typo on 1-arm 3-point row -> 10 reps
        if ex == "1-arm 3-point row" and reps == 80:
            reps = 10
        data[session][date][ex].append((w, reps))

# ---- helpers ------------------------------------------------------------
def fmt_set(w, reps):
    wt = "BW" if w == 0 else (f"{w:g}")
    return f"{wt}×{reps}"

def sets_cell(sets):
    return " · ".join(fmt_set(w, r) for w, r in sets)

def top_set_kg(sets):
    return max((w for w, _ in sets), default=0.0)

def total_volume(sets):
    # bodyweight sets contribute 0 to load-volume; kept simple
    return sum(w * r for w, r in sets)

# ---- assemble structured output ----------------------------------------
out = {"generated": None, "start": START, "sessions": OrderedDict()}
for session, blocks in PROGRAMME.items():
    dates = sorted(data.get(session, {}).keys())
    weeks = [{"n": i + 1, "date": d} for i, d in enumerate(dates)]
    sess_obj = {"weeks": weeks, "blocks": []}
    for label, exercises in blocks:
        block = {"label": label, "exercises": []}
        for ex in exercises:
            row = {"name": ex, "byweek": []}
            for d in dates:
                sets = data[session][d].get(ex, [])
                row["byweek"].append({
                    "cell": sets_cell(sets) if sets else "",
                    "sets": [[w, r] for (w, r) in sets],
                    "top": top_set_kg(sets),
                    "vol": total_volume(sets),
                    "nsets": len(sets),
                })
            block["exercises"].append(row)
        sess_obj["blocks"].append(block)
    out["sessions"][session] = sess_obj

with open(f"{OUT_DIR}/tracker_data.json", "w") as f:
    json.dump(out, f, indent=2)

# quick console summary
for session, s in out["sessions"].items():
    print(f"\n== {session} ==")
    print("weeks:", [f"W{w['n']} {w['date']}" for w in s["weeks"]])
    for b in s["blocks"]:
        for e in b["exercises"]:
            cells = " | ".join(c["cell"] or "-" for c in e["byweek"])
            print(f"  [{b['label']:7}] {e['name']:26} {cells}")
print("\nWrote tracker_data.json")
