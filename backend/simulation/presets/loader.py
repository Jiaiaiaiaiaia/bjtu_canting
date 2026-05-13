"""Campus preset loader for teacher-facing demo configs."""
from __future__ import annotations

import copy
import json
from pathlib import Path


PRESET_DIR = Path(__file__).resolve().parent
CANTEEN_FILES = ("minghu_xueyi.json", "xuehuo.json", "xuesi.json")
FIELD_STATUS = {
    "minghu_xueyi": {
        "data_status": "field_collected_pending_review",
        "runtime_included": True,
        "evidence_doc": "docs/phase3/canteen_field_research.md",
    },
    "xuesi": {
        "data_status": "field_collected_pending_review",
        "runtime_included": True,
        "evidence_doc": "docs/phase3/canteen_field_research.md",
    },
    "xuehuo": {
        "data_status": "missing",
        "runtime_included": False,
        "evidence_doc": "docs/phase3/canteen_field_research.md",
    },
}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _annotate_canteen(item: dict) -> dict:
    item = copy.deepcopy(item)
    status = FIELD_STATUS[item["id"]]
    item["pending_data"] = bool(item.get("_TODO_field_research_pending"))
    item.update(status)
    return item


def load_default_campus_preset() -> dict:
    campus = _read_json(PRESET_DIR / "_campus.json")
    visible_canteens = [
        _annotate_canteen(_read_json(PRESET_DIR / name))
        for name in CANTEEN_FILES
    ]
    runtime_canteens = [
        canteen for canteen in visible_canteens
        if canteen["runtime_included"]
    ]

    return {
        "config": {
            "campus": campus,
            "canteens": runtime_canteens,
            "router": {
                "information_mode": "local_estimate",
                "patience_mean_seconds": 180,
                "patience_std_seconds": 60,
                "patience_min_seconds": 30,
                "switch_improvement_ratio": 1.3,
                "max_switches_per_student": 2,
                "rng_seed": 42,
            },
        },
        "visible_canteens": visible_canteens,
        "pending_canteens": [
            canteen["id"] for canteen in visible_canteens
            if not canteen["runtime_included"]
        ],
    }
