import random
from simulation.arrival_schedule import ArrivalSchedule

def test_constant_is_constant_flag():
    s = ArrivalSchedule.constant(rate_per_sec=0.5)
    assert s.is_constant is True
    assert abs(s.lambda_at(0) - 0.5) < 1e-12
    assert abs(s.lambda_at(999) - 0.5) < 1e-12

def test_integral_normalized_to_expected_total():
    s = ArrivalSchedule(total_arrivals=600, horizon_seconds=1800,
                        baseline=0.1, ramp=(300, 900, 1.0),
                        pulses=[(600, 0.5, 60)])
    integral = sum(s.lambda_at(t) for t in range(1800))
    assert abs(integral - 600) / 600 < 0.02
    assert s.is_constant is False

def test_thinning_sequence_deterministic_same_seed():
    s = ArrivalSchedule(total_arrivals=300, horizon_seconds=1200,
                        baseline=0.1, ramp=(200, 600, 1.0), pulses=[])
    a = s.sample_arrivals(random.Random(7))
    b = s.sample_arrivals(random.Random(7))
    assert a == b and len(a) > 0

def test_constant_schedule_arrivals_match_legacy_expovariate():
    """硬验收首测：常量 schedule 经新路径产生的到达时刻序列
    与旧 build_single_canteen_traces 逐项一致（同 seed，仿真语义层）。"""
    from simulation.random_streams import build_random_streams
    from simulation.student_trace import build_single_canteen_traces
    cfg = {"arrival_rate": 6.0, "total_time": 30}
    t1 = [round(t.arrival_at, 9)
          for t in build_single_canteen_traces(cfg, build_random_streams(99))]
    t2 = [round(t.arrival_at, 9)
          for t in build_single_canteen_traces(cfg, build_random_streams(99))]
    assert t1 == t2 and len(t1) > 0   # 确定性
    # 与历史基线对齐：未配 λ(t) 时必须仍是恒定速率 expovariate（旁路）
    import random
    rate = cfg["arrival_rate"] / 60.0
    streams = build_random_streams(99)
    expect, acc = [], 0.0
    while True:
        acc += streams.arrival.expovariate(rate)
        if acc >= cfg["total_time"] * 60.0:
            break
        expect.append(round(acc, 9))
    assert t1 == expect
