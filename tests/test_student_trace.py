from canteen.simulation.random_streams import build_random_streams
from canteen.simulation.router import RouterConfig
from canteen.simulation.student_trace import build_single_canteen_traces


BASE_CONFIG = {
    "window_count": 4,
    "seat_count": 80,
    "avg_serve_time": 30,
    "avg_eat_time": 15,
    "arrival_rate": 5,
    "total_time": 20,
}


def trace_inputs(traces):
    return [
        (trace.arrival_at, trace.patience_z, trace.service_z, trace.eat_z)
        for trace in traces
    ]


def test_single_canteen_trace_is_reproducible():
    a = build_single_canteen_traces(BASE_CONFIG, build_random_streams(42))
    b = build_single_canteen_traces(BASE_CONFIG, build_random_streams(42))

    assert a == b
    assert a
    assert a[0].arrival_at > 0


def test_capacity_changes_do_not_change_student_random_inputs():
    adjusted = dict(BASE_CONFIG, window_count=6, seat_count=120)

    a = build_single_canteen_traces(BASE_CONFIG, build_random_streams(42))
    b = build_single_canteen_traces(adjusted, build_random_streams(42))

    assert trace_inputs(a) == trace_inputs(b)


def test_service_or_eat_mean_changes_do_not_change_student_random_inputs():
    adjusted = dict(BASE_CONFIG, avg_serve_time=24, avg_eat_time=12)

    a = build_single_canteen_traces(BASE_CONFIG, build_random_streams(42))
    b = build_single_canteen_traces(adjusted, build_random_streams(42))

    assert trace_inputs(a) == trace_inputs(b)


def test_trace_converts_patience_z_with_router_config():
    trace = build_single_canteen_traces(BASE_CONFIG, build_random_streams(42))[0]
    zero = type(trace)(
        arrival_at=trace.arrival_at,
        patience_z=0.0,
        service_z=trace.service_z,
        eat_z=trace.eat_z,
    )
    very_low = type(trace)(
        arrival_at=trace.arrival_at,
        patience_z=-100.0,
        service_z=trace.service_z,
        eat_z=trace.eat_z,
    )
    router_cfg = RouterConfig(
        patience_mean_seconds=180.0,
        patience_std_seconds=60.0,
        patience_min_seconds=30.0,
    )

    assert zero.to_patience_seconds(router_cfg) == 180.0
    assert very_low.to_patience_seconds(router_cfg) == 30.0
