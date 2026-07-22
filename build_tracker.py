#!/usr/bin/env python3
"""Parse the RepCount CSV export into a structured week-by-week training tracker.

- Filters to the programme start (>= 2026-06-28).
- Reconstructs superset blocks (the one thing RepCount loses) from a hand-coded
  programme definition keyed on normalised exercise names.
- Emits a JSON blob (consumed by the dashboard) and an .xlsx working log.
"""
import csv, json, re, sys, unicodedata
from collections import defaultdict, OrderedDict
from datetime import datetime

# CSV path can be passed as arg 1 (RepCount export filenames change per export)
CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else "/Users/fmy-235/Downloads/export_15 Jul 2026 (1).csv"
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
    # GPP S&C 3
    "3 point lunge": "3-point lunge",
    "chest supported w": "Chest-supported W-raise",
    "trap bar deadlift": "Trap-bar deadlift",
    "inverted row": "Inverted row",
    "plank tap": "Plank tap",
    "rfe split squat": "RFE split squat",
    "supine dumbell press": "Supine dumbbell press",
    "single arm cable high to low": "Single-arm cable high-to-low",
    "kettlebell squats": "Kettlebell squat",
    "single leg calf raises": "Single-leg calf raise",
    "cable curl": "Cable curl",
    "seated tricep extension": "Seated tricep extension",
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
    "GPP S&C 3": [
        ("Prep",  ["3-point lunge", "Chest-supported W-raise"]),
        ("Block 1", ["Trap-bar deadlift", "Inverted row", "Plank tap"]),
        ("Block 2", ["RFE split squat", "Supine dumbbell press", "Single-arm cable high-to-low"]),
        ("Block 3", ["Kettlebell squat", "Single-leg calf raise"]),
        ("Block 4", ["Cable curl", "Seated tricep extension"]),
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
runs_raw = defaultdict(list)  # keyed by Workout Start -> list of cardio intervals
with open(CSV_PATH, newline="") as f:
    for r in csv.DictReader(f):
        start = r["Workout Start"]
        if not start or start[:10] < START:
            continue
        date = start[:10]
        # --- cardio / runs (Kcal ignored; Distance=m, Duration=s, Notes=speed kmph) ---
        if r["Category"].strip() == "Cardio":
            try:
                dist = float(r["Distance"]) if r["Distance"] else 0.0
            except ValueError:
                dist = 0.0
            try:
                dur = float(r["Duration"]) if r["Duration"] else 0.0
            except ValueError:
                dur = 0.0
            # keep dist==0 intervals: RepCount intermittently drops the distance on
            # one rep of an otherwise uniform interval set (hit on 15 Jul and 22 Jul).
            # They're backfilled below rather than silently vanishing from the total.
            if dur > 0:
                runs_raw[start].append({"name": r["Exercise"].strip(),
                                        "dist_m": dist, "dur_s": dur,
                                        "note": r["Notes"].strip()})
            continue
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

# ---- backfill dropped interval distances --------------------------------
# RepCount sometimes exports one interval of a uniform set with a blank Distance.
# When every *recorded* interval in that workout ran the same distance, the blank
# is that distance too (same duration, same speed note) -- so fill it in rather
# than under-reporting the session. If the recorded intervals disagree we can't
# infer it, so the blank is dropped and reported.
for start, ivs in list(runs_raw.items()):
    known = {iv["dist_m"] for iv in ivs if iv["dist_m"] > 0}
    missing = [iv for iv in ivs if iv["dist_m"] <= 0]
    if not missing:
        continue
    if len(known) == 1:
        fill = known.pop()
        for iv in missing:
            iv["dist_m"] = fill
        print(f"  [backfill] {start[:10]}: {len(missing)} interval(s) missing Distance "
              f"-> {fill:.0f}m (all recorded intervals ran {fill:.0f}m)")
    else:
        runs_raw[start] = [iv for iv in ivs if iv["dist_m"] > 0]
        print(f"  [WARN] {start[:10]}: {len(missing)} interval(s) missing Distance and "
              f"recorded distances differ ({sorted(known)}) -- dropped, totals will be low")

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

# ---- assemble runs ------------------------------------------------------
def run_type(name):
    return "sprint" if "sprint" in name.lower() else "long"

runs = []
for start in sorted(runs_raw.keys()):
    intervals = runs_raw[start]
    name = intervals[0]["name"] or "Run"
    tot_d = sum(iv["dist_m"] for iv in intervals)
    tot_t = sum(iv["dur_s"] for iv in intervals)
    avg_kmph = round((tot_d / tot_t) * 3.6, 1) if tot_t else 0.0
    runs.append({
        "type": run_type(name),
        "date": start[:10],
        "name": name.rstrip(),
        "intervals": [{
            "dist_m": iv["dist_m"], "dur_s": iv["dur_s"],
            "kmph": round((iv["dist_m"] / iv["dur_s"]) * 3.6, 1) if iv["dur_s"] else 0.0,
        } for iv in intervals],
        "total_dist_m": tot_d,
        "total_dur_s": tot_t,
        "avg_kmph": avg_kmph,
        "pace_s_per_km": round(tot_t / (tot_d / 1000)) if tot_d else 0,
    })
out["runs"] = runs

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
print("\n== RUNS ==")
for rn in out["runs"]:
    m, s = divmod(rn["pace_s_per_km"], 60)
    print(f"  {rn['date']} {rn['type']:6} {rn['name']}: {len(rn['intervals'])}x "
          f"{rn['intervals'][0]['dist_m']:.0f}m | {rn['total_dist_m']/1000:.2f}km "
          f"| {rn['avg_kmph']} km/h | {m}:{s:02d}/km")
print("\nWrote tracker_data.json")
