"""Campus preset loader for teacher-facing demo configs."""
from __future__ import annotations

import copy
import json
from pathlib import Path


PRESET_DIR = Path(__file__).resolve().parent
CANTEEN_FILES = ("minghu_xueyi.json", "xuehuo.json", "xuesi.json")
DEMO_CAMPUS_OVERRIDES = {
    "total_students": 180,
    "peak_window_minutes": 20,
    "simulation_seconds": 300,
}
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


def _demo_campus_config(campus: dict) -> tuple[dict, dict]:
    source_scale = {
        "total_students": campus["total_students"],
        "peak_window_minutes": campus["peak_window_minutes"],
        "simulation_seconds": campus["simulation_seconds"],
    }
    demo = copy.deepcopy(campus)
    demo.update(DEMO_CAMPUS_OVERRIDES)
    demo["demo_runtime"] = True
    demo["source_scale"] = source_scale
    return demo, source_scale


def load_default_campus_preset() -> dict:
    campus = _read_json(PRESET_DIR / "_campus.json")
    campus, source_scale = _demo_campus_config(campus)
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
        "source_scale": source_scale,
        "demo_runtime": True,
    }


def load_single_canteen_preset() -> dict:
    """N=1 单食堂（明湖学一 3 层）；envelope 与 load_default_campus_preset 完全一致，
    前端 applyCampusPresetMetadata 零分叉。/presets/default 不动。"""
    base = load_default_campus_preset()
    minghu = next(c for c in base["config"]["canteens"]
                  if c["id"] == "minghu_xueyi")
    cfg = copy.deepcopy(base["config"])
    cfg["canteens"] = [copy.deepcopy(minghu)]
    cfg["router"]["max_switches_per_student"] = 0
    # demo 规模重标定：default 继承的 simulation_seconds=300 配明湖学一
    # avg_eat_time=15min(900s) 会导致零学生完成，复现/演示与 C1 复现测试均空转。
    # 实测（seed=123）：N=2400+sim=3600 时排队峰值 ≈87（远超 observed_peak_queue=25）、
    # 座位满载，served=2128 名学生在窗口内完成；N≈1800 到达率低于窗口/座位吞吐、
    # 队列恒为 0、无拥堵叙事。
    cfg["campus"]["simulation_seconds"] = 3600
    cfg["campus"]["total_students"] = 2400
    # spec §3.5/§5.1：D3 已接线 live 路径——ArrivalGenerator 现消费
    # arrival_schedule，与 trace 共用同一 ArrivalSchedule，产生窗口内
    # 先升后落的 λ(t)：队列在 ramp/pulse 段攀升，随后在到达仍持续时于
    # horizon 结束前回落（非到达截止后的 drain）。
    # ramp/pulse 基于下方 sim_s 动态计算，重标定后自动跟随。
    sim_s = float(cfg["campus"]["simulation_seconds"])
    cfg["campus"]["arrival_schedule"] = {
        "baseline": 0.1,
        "ramp": [sim_s * 0.15, sim_s * 0.75, 1.0],
        "pulses": [[sim_s * 0.5, 0.6, sim_s * 0.08]],
    }
    visible = [c for c in base["visible_canteens"] if c["id"] == "minghu_xueyi"]
    return {
        "config": cfg,
        "visible_canteens": visible,
        "pending_canteens": [],
        "source_scale": base["source_scale"],
        "demo_runtime": True,
    }
