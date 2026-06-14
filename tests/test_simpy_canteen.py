"""A.2.2 Canteen 类的 SimPy 行为单元测试（共 8 条）。"""
import pytest
import simpy
from canteen.simulation.canteen import Canteen, Window, Seat
from canteen.simulation.student import Student


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


# 8. v1.3 robustness：preset 全 active_count=0 时 __init__ 必须明确失败
def test_canteen_init_rejects_zero_active_windows():
    """preset 全 active_count=0 时 __init__ 必须明确失败，不延迟到 shortest_window 才崩。"""
    env = simpy.Environment()
    bad_def = {
        "id": "bad", "display_name": "坏", "campus_position": {"x": 0, "y": 0},
        "avg_serve_time_seconds": 30, "avg_eat_time_minutes": 15,
        "arrival_weight": 1.0, "typical_wait_seconds": 120,
        "floors": [{"floor_id": 1, "windows": {"physical_count": 5, "active_count": 0}, "seats": {"count": 30}}],
    }
    with pytest.raises(ValueError, match="active window"):
        Canteen(env, bad_def)


# 9. Phase 2 顶层统计字段检查
def test_canteen_snapshot_includes_phase2_top_level_stats():
    """前端 updateInfoPanel(data) 直接读这 7 个顶层字段，必须全部出现。"""
    env = simpy.Environment()
    c = Canteen(env, make_def([
        {"floor_id": 1, "windows": {"physical_count": 4, "active_count": 4}, "seats": {"count": 10}}
    ]))
    snap = c.snapshot()
    # 7 个 Phase 2 顶层字段
    assert "current_time" in snap
    assert "total_arrived" in snap
    assert "total_served" in snap
    assert "total_in_queue" in snap
    assert "total_eating" in snap
    assert "empty_seats" in snap
    assert "avg_waiting_time" in snap
    # 初始值
    assert snap["current_time"] == 0  # env.now 起始 0
    assert snap["total_arrived"] == 0
    assert snap["total_served"] == 0
    assert snap["total_in_queue"] == 0
    assert snap["total_eating"] == 0
    assert snap["empty_seats"] == 10  # 全部空着
    assert snap["avg_waiting_time"] == 0.0


# 10. total_in_queue 包含窗口 + 等座两段
def test_canteen_snapshot_total_in_queue_includes_windows_and_seat_waiting():
    """total_in_queue 必须 = 窗口排队 + 等座队列两段，与 Phase 2 单食堂语义一致。"""
    env = simpy.Environment()
    c = Canteen(env, make_def([
        {"floor_id": 1, "windows": {"physical_count": 3, "active_count": 3}, "seats": {"count": 5}}
    ]))
    # 给窗口 0 塞 2 人
    c.windows[0].join_queue(Student(id=1, state="queueing"))
    c.windows[0].join_queue(Student(id=2, state="queueing"))
    # 给等座队列塞 3 人
    c.join_seat_queue(Student(id=10, state="waiting_seat"))
    c.join_seat_queue(Student(id=11, state="waiting_seat"))
    c.join_seat_queue(Student(id=12, state="waiting_seat"))
    snap = c.snapshot()
    assert snap["total_in_queue"] == 2 + 3  # 5


def test_canteen_choose_window_uses_random_choice_when_not_congested():
    """窗口没有明显拥堵时，学生应随机选窗口，而不是默认最短队。"""
    env = simpy.Environment()
    c = Canteen(env, make_def([
        {"floor_id": 1, "windows": {"physical_count": 3, "active_count": 3}, "seats": {"count": 5}}
    ]))

    class PickThird:
        def choice(self, items):
            return items[2]

    chosen = c.choose_window(PickThird())

    assert chosen.id == c.windows[2].id


def test_canteen_choose_initial_floor_always_returns_ground_floor():
    """初始楼层应始终返回最低开放楼层（一楼入口），不受 rng 影响。"""
    env = simpy.Environment()
    c = Canteen(env, make_def([
        {"floor_id": 1, "windows": {"physical_count": 1, "active_count": 1}, "seats": {"count": 5}},
        {"floor_id": 2, "windows": {"physical_count": 1, "active_count": 1}, "seats": {"count": 5}},
    ]))
    for i in range(5):
        c.windows[1].join_queue(Student(id=400 + i, state="queueing"))

    class PickSecondEvenIfChoicesExists:
        def choice(self, items):
            return items[1]

    rng = PickSecondEvenIfChoicesExists()
    floor_id = c.choose_initial_floor(rng)

    assert floor_id == 1


def test_canteen_choose_window_uses_true_random_not_queue_weight():
    """窗口选择应是真随机，不应按队伍压力偏向短队窗口。"""
    env = simpy.Environment()
    c = Canteen(env, make_def([
        {"floor_id": 1, "windows": {"physical_count": 2, "active_count": 2}, "seats": {"count": 5}}
    ]))
    for i in range(3):
        c.windows[0].join_queue(Student(id=500 + i, state="queueing"))

    class PickFirstEvenIfChoicesExists:
        def __init__(self):
            self.choice_called = False
            self.choices_called = False

        def choices(self, items, weights, k):
            self.choices_called = True
            return [items[weights.index(max(weights))]]

        def choice(self, items):
            self.choice_called = True
            return items[0]

    rng = PickFirstEvenIfChoicesExists()
    chosen = c.choose_window(rng, current_floor_id=1)

    assert chosen.id == c.windows[0].id
    assert rng.choice_called is True
    assert rng.choices_called is False


def test_canteen_choose_window_keeps_random_choice_when_crowded():
    """随机选中的窗口拥堵时，也不应因队伍压力改去更空窗口。"""
    env = simpy.Environment()
    c = Canteen(env, make_def([
        {"floor_id": 1, "windows": {"physical_count": 2, "active_count": 2}, "seats": {"count": 5}}
    ]))

    for i in range(4):
        c.windows[0].join_queue(Student(id=100 + i, state="queueing"))

    class PickFirst:
        def choice(self, items):
            return items[0]

    chosen = c.choose_window(PickFirst())

    assert chosen.id == c.windows[0].id


def test_canteen_choose_window_does_not_reroute_from_crowded_start_floor():
    """学生初始楼层拥堵时，不应因为其他楼层更空而自动换层。"""
    env = simpy.Environment()
    c = Canteen(env, make_def([
        {"floor_id": 1, "windows": {"physical_count": 1, "active_count": 1}, "seats": {"count": 5}},
        {"floor_id": 2, "windows": {"physical_count": 1, "active_count": 1}, "seats": {"count": 5}},
    ]))

    for i in range(4):
        c.windows[0].join_queue(Student(id=300 + i, state="queueing"))

    class PickFirst:
        def choice(self, items):
            return items[0]

    chosen = c.choose_window(PickFirst(), current_floor_id=1)

    assert chosen.id == c.windows[0].id
    assert chosen.floor_id == 1


def test_canteen_choose_window_keeps_random_choice_for_small_queue():
    """只有少量排队时，不应把随机选择强行改成最短队。"""
    env = simpy.Environment()
    c = Canteen(env, make_def([
        {"floor_id": 1, "windows": {"physical_count": 2, "active_count": 2}, "seats": {"count": 5}}
    ]))

    for i in range(3):
        c.windows[0].join_queue(Student(id=200 + i, state="queueing"))

    class PickFirst:
        def choice(self, items):
            return items[0]

    chosen = c.choose_window(PickFirst())

    assert chosen.id == c.windows[0].id
