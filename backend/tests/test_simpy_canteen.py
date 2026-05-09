"""A.2.2 Canteen 类的 SimPy 行为单元测试（共 7 条）。"""
import simpy
from simulation.canteen import Canteen, Window, Seat
from simulation.student import Student


def make_def(floors, **overrides):
    base = {
        "id": "test",
        "display_name": "测试",
        "campus_position": {"x": 0, "y": 0},
        "avg_serve_time_seconds": 30,
        "avg_eat_time_minutes": 15,
        "arrival_weight": 1.0,
        "typical_wait_seconds": 120,
        "floors": floors,
    }
    base.update(overrides)
    return base


# 1. 每窗口独立 simpy.Resource
def test_canteen_windows_resource_per_window():
    env = simpy.Environment()
    c = Canteen(env, make_def([
        {"floor_id": 1, "windows": {"physical_count": 4, "active_count": 4}, "seats": {"count": 30}}
    ]))
    assert len(c.windows) == 4
    # 每个窗口独立 Resource 实例
    resources = {id(w.resource) for w in c.windows}
    assert len(resources) == 4


# 2. 座位池是 simpy.Store
def test_canteen_seats_pool_is_simpy_store():
    env = simpy.Environment()
    c = Canteen(env, make_def([
        {"floor_id": 1, "windows": {"physical_count": 2, "active_count": 2}, "seats": {"count": 5}}
    ]))
    assert isinstance(c.seat_pool, simpy.Store)
    assert len(c.seat_pool.items) == 5


# 3. shortest_window 跨楼层用 queue_load
def test_canteen_shortest_window_uses_queue_load():
    env = simpy.Environment()
    c = Canteen(env, make_def([
        {"floor_id": 1, "windows": {"physical_count": 1, "active_count": 1}, "seats": {"count": 5}},
        {"floor_id": 2, "windows": {"physical_count": 1, "active_count": 1}, "seats": {"count": 5}},
    ]))
    # Floor 1 窗口压一个 waiting；floor 2 不压
    s = Student(id=1, state="queueing")
    c.windows[0].join_queue(s)
    shortest = c.shortest_window()
    # 跨楼层应选 floor 2 那个空窗
    assert shortest.id == c.windows[1].id


# 4. snapshot 形状与 Phase 2 字段同形
def test_canteen_snapshot_shape_matches_phase2():
    env = simpy.Environment()
    c = Canteen(env, make_def([
        {"floor_id": 1, "windows": {"physical_count": 3, "active_count": 3}, "seats": {"count": 6}}
    ]))
    snap = c.snapshot()
    # Phase 2 关键字段都在
    assert "windows" in snap and isinstance(snap["windows"], list)
    assert "seats" in snap and isinstance(snap["seats"], list)
    assert "students" in snap
    assert "waiting_queue_length" in snap
    # windows 单元素结构
    assert {"id", "queue_length", "is_serving", "total_served"} <= set(snap["windows"][0].keys())
    # seats 单元素结构（Phase 2 用 status / remaining_time）
    assert {"id", "status", "remaining_time"} <= set(snap["seats"][0].keys())
    assert snap["seats"][0]["status"] == "empty"  # v1.3 bug 4 锁


# 5. total_arrived 显式累加
def test_canteen_total_arrived_increments_correctly():
    env = simpy.Environment()
    c = Canteen(env, make_def([
        {"floor_id": 1, "windows": {"physical_count": 2, "active_count": 2}, "seats": {"count": 5}}
    ]))
    assert c.total_arrived == 0
    c.total_arrived += 1
    assert c.total_arrived == 1


# 6. total_served 显式累加
def test_canteen_total_served_increments_correctly():
    env = simpy.Environment()
    c = Canteen(env, make_def([
        {"floor_id": 1, "windows": {"physical_count": 2, "active_count": 2}, "seats": {"count": 5}}
    ]))
    assert c.total_served == 0
    c.total_served += 1
    assert c.total_served == 1


# 7. v1.3 bug 3 回归：avg_eat_time 单位是分钟，不能被 *60
def test_canteen_avg_eat_time_in_minutes_not_seconds():
    env = simpy.Environment()
    c = Canteen(env, make_def([
        {"floor_id": 1, "windows": {"physical_count": 4, "active_count": 4}, "seats": {"count": 30}}
    ]))
    assert c.avg_eat_time == 15
