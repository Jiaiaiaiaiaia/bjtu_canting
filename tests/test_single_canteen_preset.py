import simpy

from canteen.simulation.coordinator import CampusCoordinator
from canteen.simulation.presets.loader import (
    load_single_canteen_preset, load_default_campus_preset)
from canteen.simulation.random_streams import build_random_streams


def test_single_preset_same_envelope_keys_as_default():
    d = load_default_campus_preset()
    s = load_single_canteen_preset()
    assert set(s.keys()) == set(d.keys())  # config/visible_canteens/pending_canteens/source_scale/demo_runtime（loader 不含 mode）


def test_single_preset_is_n1_minghu_only():
    s = load_single_canteen_preset()
    canteens = s["config"]["canteens"]
    assert [c["id"] for c in canteens] == ["minghu_xueyi"]
    assert [c["display_name"] for c in canteens] == ["明湖"]
    assert s["pending_canteens"] == []
    assert [c["id"] for c in s["visible_canteens"]] == ["minghu_xueyi"]
    assert [c["display_name"] for c in s["visible_canteens"]] == ["明湖"]
    assert s["config"]["router"]["max_switches_per_student"] == 0


def test_single_preset_carries_arrival_schedule_for_lambda_demo():
    sch = load_single_canteen_preset()["config"]["campus"]["arrival_schedule"]
    assert sch["ramp"] is not None and len(sch["pulses"]) >= 1


def test_single_preset_demo_peak_queue_is_calibrated_to_field_observation():
    preset = load_single_canteen_preset()
    cfg = preset["config"]
    observed_peak_queue = cfg["canteens"][0]["observed_peak_queue"]
    streams = build_random_streams(cfg["router"]["rng_seed"])
    env = simpy.Environment()
    coordinator = CampusCoordinator(
        env, cfg, streams.routing, random_streams=streams
    )

    peak_total_queue = 0
    horizon = float(cfg["campus"]["simulation_seconds"])
    while env.now < horizon:
        coordinator.advance(min(60, horizon - env.now))
        peak_total_queue = max(
            peak_total_queue,
            coordinator.snapshot()["campus_totals"]["total_in_queue"],
        )

    # 跨层路由使峰值低于无路由基准，允许低至 observed 的 80%
    assert observed_peak_queue * 0.8 <= peak_total_queue <= observed_peak_queue * 4


def test_default_preset_unchanged():
    d = load_default_campus_preset()
    ids = sorted(c["id"] for c in d["visible_canteens"])
    assert ids == ["minghu_xueyi", "xuehuo", "xuesi"]
    assert d["pending_canteens"] == ["xuehuo"]
