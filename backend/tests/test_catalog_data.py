"""Sanity checks on the generated catalog so a bad import cannot slip in."""
import json
from pathlib import Path

from app.core.vocab import ActivityDifficulty, Limitation

CATALOG = json.loads((Path(__file__).resolve().parents[1] / "data" / "catalog.json").read_text("utf-8"))


def test_catalog_entries_are_well_formed(t):
    regions = set(t["scope"]["supported_regions"])
    for e in CATALOG:
        assert set(e["body_regions"]) <= regions, e["id"]
        assert e["difficulty"] in (1, 2, 3), e["id"]
        assert 1 <= e["sets_min"] <= e["sets_max"], e["id"]
        assert 1 <= e["reps_min"] <= e["reps_max"], e["id"]
        assert set(e["contraindications"]) <= set(Limitation), e["id"]
        assert set(e["targets_activities"]) <= set(ActivityDifficulty), e["id"]


def test_every_region_has_level_one_exercises(t):
    for region in t["scope"]["supported_regions"]:
        n = sum(1 for e in CATALOG if region in e["body_regions"] and e["difficulty"] == 1)
        assert n >= t["plan"]["min_exercises"], region
