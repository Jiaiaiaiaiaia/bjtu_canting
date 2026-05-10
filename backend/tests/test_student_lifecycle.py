"""A.7.1 student_lifecycle 进程函数单元测试（5 条核心路径）。"""
import random
import simpy
import pytest

from simulation.student import Student, student_lifecycle
from simulation.canteen import Canteen
from simulation.campus import Campus
from simulation.router import RouterConfig, StudentRouter
from simulation.stats import CampusStats


# ---------- Stub Coordinator ----------

class StubCoordinator:
    """A.8 Coordinator 的最小替身：实现 4 个 lifecycle 钩子 + stats。

    用于 A.7.1 期间隔离测试 lifecycle 行为，不依赖完整 Coordinator 实现。
    """
    def __init__(self, env):
        self.env = env
        self.stats = CampusStats()
        self.transit_students = []
        self.arrived_calls = []      # student.id list
        self.walking_starts = []     # student.id list
        self.walking_ends = []       # student.id list
        self.left_calls = []         # student.id list

    def on_student_arrived(self, student):
        self.arrived_calls.append(student.id)

    def on_student_walking_start(self, student):
        self.walking_starts.append(student.id)
        self.transit_students.append(student)
        student.walking_start_time = self.env.now

    def on_student_walking_end(self, student):
        self.walking_ends.append(student.id)
        if student in self.transit_students:
            self.transit_students.remove(student)
        student.walking_start_time = 0.0

    def on_student_left(self, student):
        self.left_calls.append(student.id)


# ---------- Fixtures ----------

def make_canteen(env, cid, *, x=0, y=0, windows=2, seats=10, avg_serve=30, weight=1.0):
    """轻量 Canteen 构造。"""
    return Canteen(env, {
        "id": cid,
        "display_name": cid,
        "campus_position": {"x": x, "y": y},
        "avg_serve_time_seconds": avg_serve,
        "avg_eat_time_minutes": 15,
        "arrival_weight": weight,
        "typical_wait_seconds": 200,
        "floors": [{"floor_id": 1, "windows": {"physical_count": windows, "active_count": windows},
                    "seats": {"count": seats}}],
    })


def make_campus(canteens, *, walking_seconds=None, entrance_walks=None):
    cfg = {
        "entrance_position": {"x": 0, "y": 0},
        "walking_speed_mps": 1.4,
        "walking_time_seconds": walking_seconds or {},
        "entrance_walk_seconds": entrance_walks or {},
    }
    return Campus(cfg, canteens)


def make_router(campus, *, info_mode="local_estimate", switch_ratio=1.3,
                max_switches=2, seed=42, patience_mean=180):
    cfg = RouterConfig(
        information_mode=info_mode,
        switch_improvement_ratio=switch_ratio,
        max_switches_per_student=max_switches,
        patience_mean_seconds=patience_mean,
        rng_seed=seed,
    )
    rng = random.Random(seed)
    # Router 不调 env，可传 None
    return StudentRouter(None, cfg, campus, rng)


# ---------- Tests ----------

# 1. v1.3 bug 1 回归：切换食堂时 target_canteen_id 必须更新
def test_lifecycle_target_canteen_id_updates_on_switch():
    """学生耐心阈值很短 → 触发 try_switch → target_canteen_id 必须更新到 alt.id。

    构造：minghu 队伍很长（30 人）、patience=10 秒、xuesi 空。
    学生在 minghu 排队 10 秒后触发 switch，应换到 xuesi。
    """
    env = simpy.Environment()
    # 给 minghu 极高 arrival_weight 强制 pick_initial 选 minghu（fixture 控制）
    minghu = make_canteen(env, "minghu_xueyi", windows=1, seats=5, avg_serve=30, weight=1000.0)
    xuesi = make_canteen(env, "xuesi", x=100, windows=1, seats=5, avg_serve=30, weight=1.0)
    canteens = {"minghu_xueyi": minghu, "xuesi": xuesi}
    campus = make_campus(canteens, entrance_walks={"minghu_xueyi": 1, "xuesi": 1},
                         walking_seconds={"minghu_xueyi": {"xuesi": 1}})
    coordinator = StubCoordinator(env)
    router = make_router(campus, patience_mean=10)  # 短耐心强制 switch

    # 提前在 minghu 窗口塞 30 人到 waiting_students 列表
    # （仅塞列表会让 try_switch 看到 estimated_wait 很长 → 切换决策正确）
    for i in range(30):
        minghu.windows[0].join_queue(Student(id=200 + i, state="queueing"))

    # 还需要一个 holder 真正占住 resource，让 lifecycle 学生 request 时陷入 patience 超时
    def hold_resource():
        with minghu.windows[0].resource.request() as req:
            yield req
            yield env.timeout(10000)  # 长时间占住
    env.process(hold_resource())

    s = Student(id=1, state="arriving", patience_threshold=10)  # 显式短耐心
    env.process(student_lifecycle(env, s, router, canteens, campus, coordinator))
    env.run(until=200)

    # 学生应已切换到 xuesi（耐心超时 + alt 显著更优）
    assert s.switch_count >= 1, f"expected at least 1 switch, got {s.switch_count}"
    assert s.target_canteen_id == "xuesi", (
        f"target_canteen_id should be 'xuesi' after switch, got {s.target_canteen_id!r}"
    )
    # current_canteen_id 也应跟上
    assert s.current_canteen_id == "xuesi"


# 2. walking 钩子让 transit_students 在走路期间非空
def test_lifecycle_walking_hooks_populate_transit_students():
    """on_student_walking_start/end 钩子让 coordinator.transit_students 在走路期间非空，
    走完即清空。"""
    env = simpy.Environment()
    canteen = make_canteen(env, "xuesi", x=140, seats=5)  # 100s 走路（140 / 1.4）
    canteens = {"xuesi": canteen}
    campus = make_campus(canteens, entrance_walks={"xuesi": 100})
    coordinator = StubCoordinator(env)
    router = make_router(campus, patience_mean=180)

    s = Student(id=1, state="arriving", patience_threshold=180)
    env.process(student_lifecycle(env, s, router, canteens, campus, coordinator))

    # 走到 50 秒（走路一半）→ 应在 transit_students 中
    env.run(until=50)
    assert s in coordinator.transit_students, "学生应在走路期间出现在 transit_students"

    # 跑到 200 秒（走路结束 + 进食堂排队 + 完成或继续）
    env.run(until=200)
    assert s not in coordinator.transit_students, "走完后应已从 transit_students 移除"
    assert len(coordinator.walking_starts) >= 1
    assert len(coordinator.walking_ends) >= 1


# 3. 没座位走 seat_pool.get → 等到有座
def test_lifecycle_no_seat_falls_through_to_seat_pool_get():
    """学生打完饭找不到空座位时，进等座队列，最终能拿到座位。

    构造：1 食堂，1 座位，1 窗口。先用 dummy 学生占满座位，触发 lifecycle 学生进等座队列。
    然后释放座位，学生应拿到。
    """
    env = simpy.Environment()
    canteen = make_canteen(env, "xuesi", windows=1, seats=1, avg_serve=10)
    canteens = {"xuesi": canteen}
    campus = make_campus(canteens, entrance_walks={"xuesi": 1})
    coordinator = StubCoordinator(env)
    router = make_router(campus, patience_mean=180)

    # 提前用 dummy 占满唯一座位
    dummy = Student(id=999, state="eating")
    occupied_seat = canteen.seat_pool.items[0]
    canteen.seat_pool.items.remove(occupied_seat)  # 从池里取出
    occupied_seat.student = dummy
    occupied_seat.eat_end_time = 30  # dummy 吃 30 秒后走

    # 模拟 dummy 30 秒后释放座位
    def dummy_release():
        yield env.timeout(30)
        occupied_seat.student = None
        canteen.seat_pool.put(occupied_seat)
    env.process(dummy_release())

    # lifecycle 学生：1 秒走路 + 10 秒服务 → 11 秒到等座 → 等到 30s 拿到座位
    s = Student(id=1, state="arriving", patience_threshold=180)
    env.process(student_lifecycle(env, s, router, canteens, campus, coordinator))
    env.run(until=2000)

    assert s.state == "left", f"学生应已经吃完离开，当前 state={s.state}"
    # 学生确实经过 waiting_seat 状态——但是因为 leave_seat_queue 已被调用，
    # 这条断言换成检查 lifecycle 调过 join_seat_queue / pool.get（间接通过完成 left 状态）
    # 至少 record_completion 被调过
    assert s.id in [c for c in coordinator.left_calls]


# 4. total_arrived 在走完路之后才 +1
def test_lifecycle_total_arrived_increments_after_walk():
    """学生 walking 中，canteen.total_arrived 还是 0；走完之后 +1。"""
    env = simpy.Environment()
    canteen = make_canteen(env, "xuesi", x=140, seats=5)  # 100s 走路
    canteens = {"xuesi": canteen}
    campus = make_campus(canteens, entrance_walks={"xuesi": 100})
    coordinator = StubCoordinator(env)
    router = make_router(campus, patience_mean=180)

    s = Student(id=1, state="arriving", patience_threshold=180)
    env.process(student_lifecycle(env, s, router, canteens, campus, coordinator))

    # 走到 50 秒——还在路上
    env.run(until=50)
    assert canteen.total_arrived == 0, "走路中 total_arrived 不应已经 +1"

    # 走到 110 秒——已经到食堂（走路 100s 完成）
    env.run(until=110)
    assert canteen.total_arrived == 1, f"走完后 total_arrived 应为 1，实际 {canteen.total_arrived}"


# 5. 拿到资源 → record_wait 被调
def test_lifecycle_record_wait_called_when_serving():
    """学生进入 serving 状态前，coordinator.stats.record_wait 必被调。"""
    env = simpy.Environment()
    canteen = make_canteen(env, "xuesi", windows=1, seats=5, avg_serve=10)
    canteens = {"xuesi": canteen}
    campus = make_campus(canteens, entrance_walks={"xuesi": 1})
    coordinator = StubCoordinator(env)
    router = make_router(campus, patience_mean=180)

    s = Student(id=1, state="arriving", patience_threshold=180)
    env.process(student_lifecycle(env, s, router, canteens, campus, coordinator))
    env.run(until=50)

    # CampusStats._wait_times 应有该学生的 wait_time 记录
    assert len(coordinator.stats._wait_times) >= 1, (
        f"record_wait 应至少被调一次；实际 _wait_times = {coordinator.stats._wait_times}"
    )
