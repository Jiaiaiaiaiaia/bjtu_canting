import simpy, random
from simulation.coordinator import CampusCoordinator
from simulation.random_streams import build_random_streams
from simulation.presets.loader import load_single_canteen_preset


def _run(seed):
    cfg = load_single_canteen_preset()["config"]
    streams = build_random_streams(seed)
    coord = CampusCoordinator(simpy.Environment(), cfg,
                              random.Random(seed), random_streams=streams)
    coord.env.run(until=cfg["campus"]["simulation_seconds"])
    served = [s for s in coord.all_students if s.state == "left"]
    return (coord.total_arrived, coord.total_served,
            tuple(round(s.service_time, 6) for s in served), len(served))


def test_single_preset_demo_scale_completes_students():
    *_, n = _run(123)
    assert n > 0  # 根因修验收：retune 后必须真有完成学生（否则复现测试空转）


def test_same_seed_same_streams_semantically_identical():
    a = _run(123); b = _run(123)
    assert a[3] > 0      # 非空，杜绝空转通过
    assert a == b        # 同 seed → 仿真语义完全一致（含 service_time）
