from simulation.presets.loader import (
    load_single_canteen_preset, load_default_campus_preset)


def test_single_preset_same_envelope_keys_as_default():
    d = load_default_campus_preset()
    s = load_single_canteen_preset()
    assert set(s.keys()) == set(d.keys())  # config/visible_canteens/pending_canteens/source_scale/demo_runtime（loader 不含 mode）


def test_single_preset_is_n1_minghu_only():
    s = load_single_canteen_preset()
    canteens = s["config"]["canteens"]
    assert [c["id"] for c in canteens] == ["minghu_xueyi"]
    assert s["pending_canteens"] == []
    assert [c["id"] for c in s["visible_canteens"]] == ["minghu_xueyi"]
    assert s["config"]["router"]["max_switches_per_student"] == 0


def test_single_preset_carries_arrival_schedule_for_lambda_demo():
    sch = load_single_canteen_preset()["config"]["campus"]["arrival_schedule"]
    assert sch["ramp"] is not None and len(sch["pulses"]) >= 1


def test_default_preset_unchanged():
    d = load_default_campus_preset()
    ids = sorted(c["id"] for c in d["visible_canteens"])
    assert ids == ["minghu_xueyi", "xuehuo", "xuesi"]
    assert d["pending_canteens"] == ["xuehuo"]
