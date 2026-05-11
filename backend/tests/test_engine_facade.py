"""A.9.1 SimulationEngine SimPy 兼容门面回归测试。"""
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
