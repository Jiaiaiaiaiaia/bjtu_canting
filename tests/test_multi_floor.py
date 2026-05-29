"""A.2.2 Canteen 多楼层展开 + snapshot 双形状测试（共 4 条）。"""
import simpy
from canteen.simulation.canteen import Canteen


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


# 1. 多楼层 preset 加载
def test_multi_floor_preset_loads():
    env = simpy.Environment()
    c = Canteen(env, make_def([
        {"floor_id": 1, "windows": {"physical_count": 6, "active_count": 6}, "seats": {"count": 172}},
        {"floor_id": 2, "windows": {"physical_count": 13, "active_count": 13}, "seats": {"count": 272}},
        {"floor_id": 3, "windows": {"physical_count": 14, "active_count": 14}, "seats": {"count": 290}},
    ]))
    assert c.active_window_count == 33
    assert len(c.windows) == 33
    assert len(c.seats) == 734
    assert len(c.floors_meta) == 3


# 2. 每个 Window/Seat 带正确 floor_id
def test_multi_floor_window_seat_carry_correct_floor_id():
    env = simpy.Environment()
    c = Canteen(env, make_def([
        {"floor_id": 1, "windows": {"physical_count": 8, "active_count": 8}, "seats": {"count": 60}},
        {"floor_id": 2, "windows": {"physical_count": 0, "active_count": 0}, "seats": {"count": 80}},
    ]))
    assert all(w.floor_id == 1 for w in c.windows)
    assert sum(1 for s in c.seats if s.floor_id == 1) == 60
    assert sum(1 for s in c.seats if s.floor_id == 2) == 80


# 3. flat 字段与 floors[] 分组一致
def test_multi_floor_snapshot_floors_match_flat():
    env = simpy.Environment()
    c = Canteen(env, make_def([
        {"floor_id": 1, "windows": {"physical_count": 4, "active_count": 4}, "seats": {"count": 20}},
        {"floor_id": 2, "windows": {"physical_count": 2, "active_count": 2}, "seats": {"count": 30}},
    ]))
    snap = c.snapshot()
    flat_window_ids = sorted(w["id"] for w in snap["windows"])
    nested_window_ids = sorted(w["id"] for f in snap["floors"] for w in f["windows"])
    assert flat_window_ids == nested_window_ids
    flat_seat_ids = sorted(s["id"] for s in snap["seats"])
    nested_seat_ids = sorted(s["id"] for f in snap["floors"] for s in f["seats"])
    assert flat_seat_ids == nested_seat_ids


# 4. 单层食堂 floors[] 长度恰为 1
def test_multi_floor_single_floor_canteen_floors_length_one():
    env = simpy.Environment()
    c = Canteen(env, make_def([
        {"floor_id": 1, "windows": {"physical_count": 6, "active_count": 6}, "seats": {"count": 100}}
    ]))
    snap = c.snapshot()
    assert len(snap["floors"]) == 1
    assert snap["floors"][0]["floor_id"] == 1
