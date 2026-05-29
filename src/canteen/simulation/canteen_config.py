"""单一汇流：把 Phase 2 六参数或预设统一构造成 CampusCoordinator 配置。

参数化路径 = 一个退化的单层预设；预设路径 = 原样透传（深拷贝防调用方变异）。
两条路径汇流到本函数，消除 engine._to_single_canteen_config 与预设加载的重复。
"""
import copy

SINGLE_CANTEEN_ID = "single"


def _from_phase2(spec: dict) -> dict:
    total_minutes = float(spec["total_time"])
    arrival_rate = float(spec["arrival_rate"])
    total_students = max(arrival_rate * total_minutes, 1.0)
    wc = int(spec["window_count"])
    return {
        "canteens": [{
            "id": SINGLE_CANTEEN_ID,
            "display_name": "单食堂",
            "campus_position": {"x": 0, "y": 0},
            "avg_serve_time_seconds": float(spec["avg_serve_time"]),
            "avg_eat_time_minutes": float(spec["avg_eat_time"]),
            "arrival_weight": 1.0,
            "typical_wait_seconds": 0.0,
            "floors": [{
                "floor_id": 1,
                "windows": {"physical_count": wc, "active_count": wc},
                "seats": {"count": int(spec["seat_count"])},
            }],
        }],
        "campus": {
            "total_students": total_students,
            "lunch_alpha": 1.0,
            "coverage": 1.0,
            "peak_window_minutes": total_minutes,
            "peak_beta": 1.0,
            "simulation_seconds": total_minutes * 60,
            "entrance_position": {"x": 0, "y": 0},
            "walking_speed_mps": 1.4,
            "walking_time_seconds": {},
            "entrance_walk_seconds": {SINGLE_CANTEEN_ID: 0.0},
        },
        "router": {
            "information_mode": "local_estimate",
            "patience_mean_seconds": 180.0,
            "patience_std_seconds": 60.0,
            "patience_min_seconds": 30.0,
            "switch_improvement_ratio": 1.3,
            "max_switches_per_student": 0,
            "rng_seed": 42,
        },
    }


def build_single_canteen_config(spec: dict) -> dict:
    if "canteens" in spec and "campus" in spec and "router" in spec:
        cfg = copy.deepcopy(spec)
        cfg["router"]["max_switches_per_student"] = 0  # §1 不变量
        return cfg
    return _from_phase2(spec)
