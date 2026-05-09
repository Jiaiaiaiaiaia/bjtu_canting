"""A.2.1 Window/Seat dataclass + Window 方法的单元测试（共 5 条）。"""
import simpy
import pytest
from simulation.canteen import Window, Seat
from simulation.student import Student


def make_window(env=None, floor_id=1):
    env = env or simpy.Environment()
    return Window(
        id=0,
        floor_id=floor_id,
        canteen_avg_serve_time=30.0,
        resource=simpy.Resource(env, capacity=1),
    )


def _occupy_resource(env, res):
    """让 simpy.Resource.count == 1 的稳定方法：跑一个长 hold 进程占住它。"""
    def hold(env, res):
        with res.request() as req:
            yield req
            yield env.timeout(100)
    env.process(hold(env, res))
    env.run(until=0.001)


def test_window_join_and_leave_queue():
    w = make_window()
    s = Student(id=1, state="queueing")
    w.join_queue(s)
    assert w.queue_length == 1
    w.leave_queue(s)
    assert w.queue_length == 0


def test_window_leave_queue_idempotent():
    """v1.3 测试：finally 兜底重复调用不抛异常。"""
    w = make_window()
    s = Student(id=1, state="queueing")
    w.join_queue(s)
    w.leave_queue(s)
    w.leave_queue(s)  # 第二次调用必须不抛
    assert w.queue_length == 0
    assert s not in w.waiting_students


def test_window_queue_load_includes_serving():
    """queue_load = resource.count + len(waiting_students)。
    与 Phase 2 queue_sim.py:14 queue_load() 语义一致——正在服务的人也算压力。"""
    env = simpy.Environment()
    res = simpy.Resource(env, capacity=1)
    _occupy_resource(env, res)
    assert res.count == 1
    w = Window(id=0, floor_id=1, canteen_avg_serve_time=30.0, resource=res)
    s = Student(id=1, state="serving")
    w.join_queue(s)
    # queue_load == count(1) + waiting(1) == 2
    assert w.queue_load == 2


def test_window_estimated_wait_includes_current_serving():
    """学生在队首时，估值应包含正在服务的那 1 位。
    spec §2.3 estimated_wait_for: (ahead + resource.count) * canteen_avg_serve_time"""
    env = simpy.Environment()
    res = simpy.Resource(env, capacity=1)
    _occupy_resource(env, res)
    assert res.count == 1
    w = Window(id=0, floor_id=1, canteen_avg_serve_time=30.0, resource=res)
    s = Student(id=2, state="queueing")
    w.join_queue(s)
    # ahead=0 + count=1 → 1 × 30 = 30s
    assert w.estimated_wait_for(s) == 30.0


def test_window_floor_id_preserved():
    """v1.3 multi-floor：Window 必须带 floor_id 字段，前端按此分组渲染。"""
    w = make_window(floor_id=2)
    assert w.floor_id == 2
    # 也确认默认 floor_id 不会成 0 或 None — 必须显式传
    with pytest.raises(TypeError):
        Window(id=99, canteen_avg_serve_time=30.0,
               resource=simpy.Resource(simpy.Environment(), capacity=1))
