from simulation.canteen_config import build_single_canteen_config

PHASE2 = {"window_count": 6, "seat_count": 200, "avg_serve_time": 30,
          "avg_eat_time": 15, "arrival_rate": 5, "total_time": 60}

def test_parametric_is_degenerate_single_floor():
    cfg = build_single_canteen_config(PHASE2)
    assert list(cfg.keys()) == ["canteens", "campus", "router"] or \
        {"canteens", "campus", "router"} <= set(cfg)
    c = cfg["canteens"][0]
    assert len(c["floors"]) == 1
    f = c["floors"][0]
    assert f["windows"]["active_count"] == 6
    assert f["windows"]["physical_count"] == 6
    assert f["seats"]["count"] == 200
    assert cfg["router"]["max_switches_per_student"] == 0

def test_preset_passthrough_is_multifloor():
    preset = {"canteens": [{"id": "minghu_xueyi", "floors": [{}, {}, {}]}],
              "campus": {"x": 1}, "router": {"max_switches_per_student": 0}}
    cfg = build_single_canteen_config(preset)
    assert len(cfg["canteens"][0]["floors"]) == 3
    assert cfg is not preset  # deep-copied, no caller mutation
