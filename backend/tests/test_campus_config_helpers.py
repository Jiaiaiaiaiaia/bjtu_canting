"""Campus API config helper tests."""

from api.campus_config_helpers import campus_config_summary, validate_campus_config


def make_payload():
    return {
        "campus": {
            "total_students": 120,
            "lunch_alpha": 0.5,
            "coverage": 0.8,
            "peak_window_minutes": 10,
            "simulation_seconds": 600,
            "entrance_position": {"x": 0, "y": 0},
            "walking_speed_mps": 1.4,
        },
        "canteens": [
            {
                "id": "minghu_xueyi",
                "display_name": "明湖",
                "campus_position": {"x": 0, "y": 0},
                "avg_serve_time_seconds": 30,
                "avg_eat_time_minutes": 15,
                "floors": [
                    {
                        "floor_id": 1,
                        "windows": {"active_count": 2, "avg_serve_time_seconds": 20},
                        "seats": {"count": 40},
                    },
                    {
                        "floor_id": 2,
                        "windows": {"active_count": 1},
                        "seats": {"count": 20},
                    },
                ],
            }
        ],
        "router": {
            "information_mode": "local_estimate",
            "patience_mean_seconds": 180,
            "patience_std_seconds": 30,
            "patience_min_seconds": 30,
            "switch_improvement_ratio": 1.3,
            "max_switches_per_student": 0,
            "rng_seed": 42,
        },
    }


def test_validate_campus_config_accepts_complete_payload():
    assert validate_campus_config(make_payload()) is None


def test_validate_campus_config_rejects_missing_required_campus_field():
    payload = make_payload()
    del payload["campus"]["walking_speed_mps"]

    assert validate_campus_config(payload) == "缺少 campus 参数：walking_speed_mps"


def test_campus_config_summary_keeps_existing_active_window_semantics():
    summary = campus_config_summary(make_payload())

    assert summary == {
        "window_count": 3,
        "seat_count": 60,
        "avg_serve_time": (20 + 20 + 30) / 3,
        "avg_eat_time": 15,
        "arrival_rate": 120 * 0.5 * 0.8 / 10,
        "total_time": 10,
    }
