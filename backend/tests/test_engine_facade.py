"""A.9.1 SimulationEngine SimPy 兼容门面回归测试。"""
import random

from simulation import SimulationEngine


def make_engine(**overrides):
    config = {
        "window_count": 3,
        "seat_count": 30,
        "avg_serve_time": 15,
        "avg_eat_time": 5,
        "arrival_rate": 20,
        "total_time": 5,
    }
    config.update(overrides)
    return SimulationEngine(config, config_id=0, rng_seed=42)


def run_to_end(config, seed):
    engine = SimulationEngine(config, config_id=0, rng_seed=seed)
    engine.start()
    while True:
        state = engine.step()
        if state["is_ended"]:
            return state


def test_wraps_single_canteen_coordinator():
    engine = make_engine()
    assert hasattr(engine, "coordinator")
    assert list(engine.coordinator.canteens.keys()) == ["single"]


def test_first_step_advances_one_visible_phase2_event():
    """step() 对外应像 Phase 2 一样推进到一个可见语义事件，而非一个 SimPy 微事件。"""
    engine = make_engine()
    engine.start()

    state = engine.step()

    assert state["current_time"] > 0
    assert state["total_arrived"] > 0
    assert len(state["students"]) > 0
    assert state["event_type"] == "arrival"


def test_students_and_event_queue_expose_real_objects_after_start():
    engine = make_engine()
    engine.start()

    assert engine.students
    assert all(student is not None for student in engine.students)
    assert engine.event_queue
    assert all(event is not None for event in engine.event_queue)


def test_empty_schedule_end_state_is_recorded_in_history():
    engine = make_engine(arrival_rate=1, total_time=0.1, window_count=1, seat_count=1)
    engine.start()
    engine._env._queue.clear()

    state = engine.step()

    assert state["is_ended"] is True
    assert state["event_type"] == "end"
    assert engine.history
    assert engine.history[-1]["event_type"] == "end"
    assert engine.history[-1]["current_time"] == state["current_time"]


def test_seeded_engine_does_not_reset_global_random_state():
    random.seed(20260513)
    expected = random.random()

    random.seed(20260513)
    SimulationEngine(make_engine().config, config_id=0, rng_seed=42)
    observed = random.random()

    assert observed == expected


def test_seeded_engine_attaches_trace_to_spawned_students():
    engine = make_engine()
    engine.start()
    engine.step()

    assert engine.coordinator.all_students
    assert engine.coordinator.all_students[0].trace is not None


def test_same_seed_same_config_is_reproducible():
    config = make_engine().config
    a = run_to_end(config, seed=20260513)
    b = run_to_end(config, seed=20260513)

    assert a["total_arrived"] == b["total_arrived"]
    assert a["total_served"] == b["total_served"]
    assert a["avg_waiting_time"] == b["avg_waiting_time"]


def test_same_seed_capacity_change_keeps_same_arrivals():
    config = make_engine().config
    adjusted = dict(config, window_count=config["window_count"] + 1)

    baseline = run_to_end(config, seed=20260513)
    changed = run_to_end(adjusted, seed=20260513)

    assert baseline["total_arrived"] == changed["total_arrived"]


def test_same_seed_service_or_eat_change_keeps_same_arrivals():
    config = make_engine().config
    adjusted = dict(
        config,
        avg_serve_time=config["avg_serve_time"] * 0.8,
        avg_eat_time=config["avg_eat_time"] * 0.8,
    )

    baseline = run_to_end(config, seed=20260513)
    changed = run_to_end(adjusted, seed=20260513)

    assert baseline["total_arrived"] == changed["total_arrived"]
