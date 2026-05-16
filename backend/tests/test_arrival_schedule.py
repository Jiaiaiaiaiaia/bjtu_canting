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
