"""Build the approved exercise catalog from free-exercise-db and report coverage.

    python -m scripts.import_catalog                 # fetch, tag, write data/catalog.json + coverage report
    python -m scripts.import_catalog --source x.json # use a local copy instead of downloading
    python -m scripts.import_catalog --load          # also upsert into the database
    python -m scripts.import_catalog --load-only     # just load the committed data/catalog.json

Everything here is a first-pass heuristic for the team to review (M1). Curate the
result with data/catalog_overrides.yaml rather than editing catalog.json by hand.
"""
import argparse
import json
import sys
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import yaml

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.core.vocab import ActivityDifficulty as A  # noqa: E402
from app.core.vocab import Limitation as L  # noqa: E402

SOURCE_URL = "https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/dist/exercises.json"
MEDIA_BASE = "https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/exercises/"
OUT_JSON = BACKEND / "data" / "catalog.json"
OVERRIDES = BACKEND / "data" / "catalog_overrides.yaml"
REPORT = BACKEND.parent / "docs" / "dataset-coverage.md"

SUPPORTED_REGIONS = ["lower_back", "shoulder", "knee", "ankle"]

# Scope: low-intensity stretching and light strength work only.
ALLOWED_CATEGORIES = {"stretching", "strength"}
ALLOWED_LEVELS = {"beginner": 1, "intermediate": 2}  # "expert" is always excluded
ALLOWED_EQUIPMENT = {None, "body only", "bands", "foam roll", "exercise ball"}
# High-impact movements are never low-intensity, whatever their category says.
HIGH_IMPACT_KEYWORDS = ["jump", "hop", "bound", "sprint", "explosive", "plyo", "burpee"]

# Primary muscle -> supported body region(s)
MUSCLE_REGIONS: dict[str, list[str]] = {
    "lower back": ["lower_back"],
    "middle back": ["lower_back"],
    "abdominals": ["lower_back"],
    "glutes": ["lower_back", "knee"],
    "shoulders": ["shoulder"],
    "traps": ["shoulder"],
    "quadriceps": ["knee"],
    "hamstrings": ["knee"],
    "adductors": ["knee"],
    "abductors": ["knee"],
    "calves": ["ankle"],
}

# Primary muscle -> everyday activities it supports (used by fallback ranking)
MUSCLE_ACTIVITIES: dict[str, list[str]] = {
    "lower back": [A.BENDING, A.LIFTING, A.SITTING_LONG],
    "middle back": [A.SITTING_LONG, A.LIFTING],
    "abdominals": [A.LIFTING, A.BENDING],
    "glutes": [A.CLIMBING_STAIRS, A.WALKING, A.SQUATTING],
    "shoulders": [A.REACHING_OVERHEAD, A.LIFTING],
    "traps": [A.REACHING_OVERHEAD, A.SITTING_LONG],
    "quadriceps": [A.CLIMBING_STAIRS, A.SQUATTING, A.WALKING],
    "hamstrings": [A.BENDING, A.WALKING, A.RUNNING],
    "adductors": [A.WALKING, A.SQUATTING],
    "abductors": [A.WALKING],
    "calves": [A.WALKING, A.RUNNING, A.CLIMBING_STAIRS],
}

# Keyword heuristics for contraindications (searched in name + instructions)
LIMITATION_KEYWORDS: dict[str, list[str]] = {
    L.CANNOT_KNEEL: ["kneel", "on your knees", "all fours", "quadruped"],
    L.CANNOT_LIE_ON_FLOOR: ["lie ", "lying", "lay on", "supine", "prone", "on the floor", "on your back"],
    L.LIMITED_OVERHEAD_REACH: ["overhead", "above your head", "over your head"],
    L.POOR_BALANCE: ["one leg", "single leg", "single-leg", "one foot", "balance"],
}


def sets_reps(category: str, difficulty: int) -> dict[str, int]:
    if category == "stretching":  # reps = number of ~30 second holds
        return {"sets_min": 1, "sets_max": 3, "reps_min": 1, "reps_max": 3}
    if difficulty <= 2:
        return {"sets_min": 1, "sets_max": 3, "reps_min": 8, "reps_max": 12}
    return {"sets_min": 2, "sets_max": 3, "reps_min": 8, "reps_max": 15}


def difficulty_for(ex: dict[str, Any]) -> int:
    """Stretching keeps its dataset level; strength work is one level harder (max 3)."""
    base = ALLOWED_LEVELS[ex["level"]]
    return min(3, base + (1 if ex["category"] == "strength" else 0))


def tag(ex: dict[str, Any]) -> dict[str, Any] | None:
    if ex["category"] not in ALLOWED_CATEGORIES or ex["level"] not in ALLOWED_LEVELS:
        return None
    if ex.get("equipment") not in ALLOWED_EQUIPMENT:
        return None
    if any(w in ex["name"].lower() for w in HIGH_IMPACT_KEYWORDS):
        return None
    regions = sorted({r for m in ex["primaryMuscles"] for r in MUSCLE_REGIONS.get(m, [])})
    if not regions:
        return None

    text = (ex["name"] + " " + " ".join(ex.get("instructions", []))).lower()
    contra = sorted(lim for lim, words in LIMITATION_KEYWORDS.items() if any(w in text for w in words))
    if ex.get("equipment") not in (None, "body only"):
        contra.append(L.NO_EQUIPMENT)
    activities = sorted({a for m in ex["primaryMuscles"] for a in MUSCLE_ACTIVITIES.get(m, [])})
    diff = difficulty_for(ex)

    return {
        "id": ex["id"],
        "name": ex["name"],
        "body_regions": regions,
        "difficulty": diff,
        "category": ex["category"],
        "equipment": ex.get("equipment"),
        "instructions": ex.get("instructions", []),
        **sets_reps(ex["category"], diff),
        "media": [MEDIA_BASE + p for p in ex.get("images", [])],
        "contraindications": [str(c) for c in contra],
        "targets_activities": [str(a) for a in activities],
    }


def apply_overrides(catalog: list[dict[str, Any]], raw_by_id: dict[str, dict]) -> list[dict[str, Any]]:
    if not OVERRIDES.exists():
        return catalog
    ov = yaml.safe_load(OVERRIDES.read_text(encoding="utf-8")) or {}
    exclude = set(ov.get("exclude", []) or [])
    patches: dict[str, dict] = ov.get("patch", {}) or {}
    out = [dict(e, **patches.get(e["id"], {})) for e in catalog if e["id"] not in exclude]
    return out


def coverage_report(catalog: list[dict[str, Any]], min_needed: int) -> str:
    grid = Counter((r, e["difficulty"]) for e in catalog for r in e["body_regions"])
    lines = [
        "# Exercise dataset coverage",
        "",
        f"Generated by `scripts/import_catalog.py` on {date.today().isoformat()} from free-exercise-db.",
        f"Approved exercises after filtering: **{len(catalog)}**. A plan needs at least "
        f"**{min_needed}** eligible exercises, so any cell below that is flagged.",
        "",
        "## Exercises per region and difficulty",
        "",
        "| Region | Level 1 | Level 2 | Level 3 | Total |",
        "|---|---|---|---|---|",
    ]
    gaps = []
    for r in SUPPORTED_REGIONS:
        cells = []
        for d in (1, 2, 3):
            n = grid[(r, d)]
            cells.append(f"{n} ⚠" if n < min_needed else str(n))
            if n < min_needed:
                gaps.append(f"{r} level {d} ({n})")
        total = sum(1 for e in catalog if r in e["body_regions"])
        lines.append(f"| {r} | " + " | ".join(cells) + f" | {total} |")

    lines += ["", "## Exercises left after one limitation (per region, all levels)", "",
              "| Region | " + " | ".join(str(lim) for lim in L) + " |",
              "|---|" + "---|" * len(L)]
    for r in SUPPORTED_REGIONS:
        in_region = [e for e in catalog if r in e["body_regions"]]
        row = [str(sum(1 for e in in_region if str(lim) not in e["contraindications"])) for lim in L]
        lines.append(f"| {r} | " + " | ".join(row) + " |")

    lines += ["", "## Gaps to resolve", ""]
    lines += [f"- {g}" for g in gaps] or ["- None. Every region and level has enough exercises."]
    lines += ["", "Options for gaps: hand-tag more exercises in `data/catalog_overrides.yaml`, "
              "switch `filtering.difficulty_match` to `at_most`, or narrow the supported scope."]
    return "\n".join(lines) + "\n"


def load_into_db(catalog: list[dict[str, Any]]) -> None:
    from app.core.database import SessionLocal
    from app.modules.catalog.models import Exercise

    with SessionLocal() as db:
        for row in catalog:
            db.merge(Exercise(**row))
        db.commit()
    print(f"Upserted {len(catalog)} exercises into the database")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", help="local path to exercises.json (default: download)")
    p.add_argument("--load", action="store_true", help="also upsert into the database")
    p.add_argument("--load-only", action="store_true", help="load data/catalog.json without re-importing")
    args = p.parse_args()

    if args.load_only:
        load_into_db(json.loads(OUT_JSON.read_text(encoding="utf-8")))
        return

    if args.source:
        raw = json.loads(Path(args.source).read_text(encoding="utf-8"))
    else:
        with urllib.request.urlopen(SOURCE_URL, timeout=30) as resp:
            raw = json.load(resp)

    catalog = [t for ex in raw if (t := tag(ex))]
    catalog = apply_overrides(catalog, {e["id"]: e for e in raw})
    catalog.sort(key=lambda e: e["id"])

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    thresholds = yaml.safe_load((BACKEND / "config" / "thresholds.yaml").read_text(encoding="utf-8"))
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(coverage_report(catalog, thresholds["plan"]["min_exercises"]), encoding="utf-8")
    print(f"{len(raw)} source exercises -> {len(catalog)} approved. Wrote {OUT_JSON.name} and {REPORT.name}")

    if args.load:
        load_into_db(catalog)


if __name__ == "__main__":
    main()
