"""StudentRouter 决策模型测试（spec §2.7 / §4.7 / plan A.4.1）。

8 条测试覆盖：
1. pick_initial 软概率分布（arrival_weight 影响选取）
2. try_switch 当前队和候选差不多时不切换（防抖）
3. try_switch 当前队明显差时切换
4. try_switch max_switches 上限
5. 走路时间纳入决策
6. 防止双堵食堂之间反复横跳
7. 用学生当前窗口估当前等待，不是 shortest_window
8. local_estimate vs live_congestion 模式切换

3 食堂契约（v1.6）：fixture 只用 minghu_xueyi / xuehuo / xuesi。
"""
import random
from collections import Counter

import pytest
import simpy

from simulation.canteen import Canteen
from simulation.campus import Campus
from simulation.router import RouterConfig, StudentRouter
from simulation.student import Student


def make_3_canteens(env, weights=(1.0, 1.0, 1.0), windows=(6, 5, 9)):
    """3 食堂 fixture：minghu_xueyi / xuehuo / xuesi。"""
    base = {
        "avg_serve_time_seconds": 30,
        "avg_eat_time_minutes": 15,
        "typical_wait_seconds": 200,
    }
    minghu = {**base, "id": "minghu_xueyi", "display_name": "明湖学一",
              "campus_position": {"x": 0, "y": 0},
              "arrival_weight": weights[0],
              "floors": [{"floor_id": 1,
                          "windows": {"physical_count": windows[0], "active_count": windows[0]},
                          "seats": {"count": 100}}]}
    xuehuo = {**base, "id": "xuehuo", "display_name": "学活",
              "campus_position": {"x": 100, "y": 0},
              "arrival_weight": weights[1],
              "floors": [{"floor_id": 1,
                          "windows": {"physical_count": windows[1], "active_count": windows[1]},
                          "seats": {"count": 100}}]}
    xuesi = {**base, "id": "xuesi", "display_name": "学四",
             "campus_position": {"x": 0, "y": 100},
             "arrival_weight": weights[2],
             "floors": [{"floor_id": 1,
                         "windows": {"physical_count": windows[2], "active_count": windows[2]},
                         "seats": {"count": 100}}]}
    return {
        "minghu_xueyi": Canteen(env, minghu),
        "xuehuo": Canteen(env, xuehuo),
        "xuesi": Canteen(env, xuesi),
    }


def make_campus(canteens, walking_seconds=None, entrance_walks=None):
    cfg = {
        "entrance_position": {"x": 0, "y": 0},
        "walking_speed_mps": 1.4,
        "walking_time_seconds": walking_seconds or {},
        "entrance_walk_seconds": entrance_walks or {
            "minghu_xueyi": 60, "xuehuo": 60, "xuesi": 60,
        },
    }
    return Campus(cfg, canteens)


def make_router(canteens, *, info_mode="local_estimate", switch_ratio=1.3,
                max_switches=2, walking_seconds=None, entrance_walks=None,
                seed=42):
    env = simpy.Environment()
    cfg = RouterConfig(
        information_mode=info_mode,
        switch_improvement_ratio=switch_ratio,
        max_switches_per_student=max_switches,
        rng_seed=seed,
    )
    campus = make_campus(canteens, walking_seconds, entrance_walks)
    rng = random.Random(seed)
    return StudentRouter(env, cfg, campus, rng), campus


# 1. pick_initial 概率分布大致符合 weights × capacity / walk
def test_router_pick_initial_distribution():
    """大量样本下，arrival_weight=2.0 的食堂被选概率应明显高于 weight=1.0。"""
    env = simpy.Environment()
    canteens = make_3_canteens(env, weights=(2.0, 1.0, 1.0))
    router, _ = make_router(canteens)
    s = Student(id=1, state="arriving")
    counter = Counter()
    for _ in range(3000):
        chosen = router.pick_initial(s, canteens)
        counter[chosen.id] += 1
    # weight 2 食堂应被选 > 40%（理论 ~50% 在均等容量/距离时）
    assert counter["minghu_xueyi"] > counter["xuehuo"]
    assert counter["minghu_xueyi"] > counter["xuesi"]
    assert counter["minghu_xueyi"] / 3000 > 0.40


# 2. 当前队和候选差不多时不切换（防抖动）
def test_router_no_switch_when_close():
    """边界场景：current_est 与候选 cost 接近时，switch_improvement_ratio 防抖应阻止切换。

    设计参数：
      minghu 窗口 0 前面 9 人 → s 在 index 9 → current_est = (9 + 0) × 30 = 270
      xuehuo 候选 cost = walk(30) + typical_wait(200) = 230
      230 × 1.3 = 299 > 270 → 不切换（差距 29s，margin 较窄但仍触发防抖）

    重点：current_est 必须明确非零，避免落入"任何阈值都不切换"的假阳性。
    """
    env = simpy.Environment()
    canteens = make_3_canteens(env)
    router, _ = make_router(
        canteens,
        walking_seconds={"minghu_xueyi": {"xuehuo": 30}},
    )
    s = Student(id=1, state="queueing",
                current_canteen_id="minghu_xueyi", current_window_id=0,
                target_canteen_id="minghu_xueyi", switch_count=0)
    # 9 个 dummy 学生塞队首，s 进 index 9
    for i in range(9):
        canteens["minghu_xueyi"].windows[0].join_queue(Student(id=900 + i, state="queueing"))
    canteens["minghu_xueyi"].windows[0].join_queue(s)

    # 显式断言 current_est：保证测试真的在测阈值，不是因为 0 等待 trivially 不切
    assert canteens["minghu_xueyi"].windows[0].estimated_wait_for(s) == 270
    assert router.try_switch(s, canteens, exclude_id="minghu_xueyi") is None


# 3. 当前队明显比候选差很多 → 切换
def test_router_switch_when_clearly_better():
    env = simpy.Environment()
    canteens = make_3_canteens(env)
    router, _ = make_router(
        canteens,
        walking_seconds={"minghu_xueyi": {"xuehuo": 30}},
        entrance_walks={"minghu_xueyi": 60, "xuehuo": 60, "xuesi": 60},
    )
    # 学生站在 minghu，前面 30 人 → current_est = 30 × 30 = 900s
    s = Student(id=1, state="queueing",
                current_canteen_id="minghu_xueyi", current_window_id=0,
                target_canteen_id="minghu_xueyi", switch_count=0)
    # 把 30 个 dummy 学生塞进 minghu 窗口 0 队列，s 在最后
    for i in range(30):
        canteens["minghu_xueyi"].windows[0].join_queue(Student(id=100 + i, state="queueing"))
    canteens["minghu_xueyi"].windows[0].join_queue(s)
    # 候选 xuehuo typical_wait_seconds=200 + walk 30 = 230
    # 230 × 1.3 = 299 < 900 → 切到 xuehuo
    alt = router.try_switch(s, canteens, exclude_id="minghu_xueyi")
    assert alt is not None
    assert alt.id == "xuehuo"


# 4. max_switches_per_student 上限生效
def test_router_max_switches_capped():
    env = simpy.Environment()
    canteens = make_3_canteens(env)
    router, _ = make_router(canteens, max_switches=2)
    # 学生已切换 2 次，即使其他食堂明显更好也不再切
    s = Student(id=1, state="queueing",
                current_canteen_id="minghu_xueyi", current_window_id=0,
                target_canteen_id="minghu_xueyi", switch_count=2)
    for i in range(50):
        canteens["minghu_xueyi"].windows[0].join_queue(Student(id=200 + i, state="queueing"))
    canteens["minghu_xueyi"].windows[0].join_queue(s)
    assert router.try_switch(s, canteens, exclude_id="minghu_xueyi") is None


# 5. 走路时间纳入决策
def test_router_walk_time_in_decision():
    """即使候选食堂队伍完全空，如果走路时间超长，学生也不切换。"""
    env = simpy.Environment()
    canteens = make_3_canteens(env)
    router, _ = make_router(
        canteens,
        walking_seconds={"minghu_xueyi": {"xuehuo": 5000, "xuesi": 5000}},
        entrance_walks={"minghu_xueyi": 60, "xuehuo": 5000, "xuesi": 5000},
    )
    # 学生在 minghu 队，前面 5 人 → current_est = 5 × 30 = 150s
    s = Student(id=1, state="queueing",
                current_canteen_id="minghu_xueyi", current_window_id=0,
                target_canteen_id="minghu_xueyi", switch_count=0)
    for i in range(5):
        canteens["minghu_xueyi"].windows[0].join_queue(Student(id=300 + i, state="queueing"))
    canteens["minghu_xueyi"].windows[0].join_queue(s)
    # 候选 cost = 5000 walk + 200 typical_wait = 5200，5200 × 1.3 = 6760 > 150 → 不换
    assert router.try_switch(s, canteens, exclude_id="minghu_xueyi") is None


# 6. 防止双堵食堂之间反复横跳
def test_router_oscillation_prevented():
    """两个食堂队伍长度相近时，单步 try_switch 不应给出"换过去"建议（switch_improvement_ratio 防抖）。"""
    env = simpy.Environment()
    canteens = make_3_canteens(env)
    router, _ = make_router(canteens, switch_ratio=1.3,
                            walking_seconds={"minghu_xueyi": {"xuehuo": 30}})
    # minghu 队前面 5 人 → current_est=150
    # xuehuo typical_wait=200 + walk=30 = 230 候选 cost
    # 230 × 1.3 = 299 > 150 → 不换；正向不换
    s = Student(id=1, state="queueing",
                current_canteen_id="minghu_xueyi", current_window_id=0,
                target_canteen_id="minghu_xueyi", switch_count=0)
    for i in range(5):
        canteens["minghu_xueyi"].windows[0].join_queue(Student(id=400 + i, state="queueing"))
    canteens["minghu_xueyi"].windows[0].join_queue(s)
    assert router.try_switch(s, canteens, exclude_id="minghu_xueyi") is None
    # 反向：把学生放到 xuehuo 队前面 5 人，再问换 minghu？同样应不换。
    s2 = Student(id=2, state="queueing",
                 current_canteen_id="xuehuo", current_window_id=0,
                 target_canteen_id="xuehuo", switch_count=0)
    for i in range(5):
        canteens["xuehuo"].windows[0].join_queue(Student(id=500 + i, state="queueing"))
    canteens["xuehuo"].windows[0].join_queue(s2)
    assert router.try_switch(s2, canteens, exclude_id="xuehuo") is None


# 7. 必须用学生自己窗口估当前等待，不能用 shortest_window
def test_router_uses_current_window_not_shortest_window():
    """学生站在窗口 0（前面 30 人），同食堂窗口 1 是空的。
    current_est 应基于窗口 0 的 30 × 30 = 900s，而不是窗口 1 的 0s。
    candidate cost (xuehuo) = 200 typical + 60 walk = 260
    260 × 1.3 = 338 < 900 → 应切；
    如果错误使用 shortest_window，current_est ≈ 0 + 0 = 0，260 × 1.3 = 338 > 0 → 不换。
    """
    env = simpy.Environment()
    canteens = make_3_canteens(env, windows=(2, 3, 3))  # minghu 至少 2 窗口
    router, _ = make_router(canteens)
    s = Student(id=1, state="queueing",
                current_canteen_id="minghu_xueyi", current_window_id=0,
                target_canteen_id="minghu_xueyi", switch_count=0)
    # 把 30 人塞窗口 0；窗口 1 留空
    for i in range(30):
        canteens["minghu_xueyi"].windows[0].join_queue(Student(id=600 + i, state="queueing"))
    canteens["minghu_xueyi"].windows[0].join_queue(s)
    alt = router.try_switch(s, canteens, exclude_id="minghu_xueyi")
    assert alt is not None  # 用窗口 0 估当前等待 → 应切到 xuehuo


# 8. local_estimate vs live_congestion 模式开关
def test_router_live_congestion_mode_toggle():
    """live_congestion 模式下，候选估值用 shortest_window().queue_load × avg_serve_time（实时）；
    local_estimate 用 typical_wait_seconds（口碑）。两种模式行为应有可观察差异。

    fixture：xuehuo 配成单窗口，50 人全挤进唯一窗口，shortest_window 即 50 人队，
    est_wait = 50 × 30 = 1500，与 spec §2.7 的"shortest_window 估值"模型一致。
    """
    env = simpy.Environment()
    # 关键改动：xuehuo 只配 1 个 active 窗口（windows=(6, 1, 9)）
    canteens = make_3_canteens(env, windows=(6, 1, 9))
    # 给 xuehuo 唯一窗口 0 塞 50 人
    for i in range(50):
        canteens["xuehuo"].windows[0].join_queue(Student(id=700 + i, state="queueing"))

    s = Student(id=1, state="queueing",
                current_canteen_id="minghu_xueyi", current_window_id=0,
                target_canteen_id="minghu_xueyi", switch_count=0)
    # minghu 队 5 人 → current_est=150
    for i in range(5):
        canteens["minghu_xueyi"].windows[0].join_queue(Student(id=800 + i, state="queueing"))
    canteens["minghu_xueyi"].windows[0].join_queue(s)

    # local_estimate：xuehuo 估 typical_wait=200 + walk=60 ≈ 260；260×1.3=338 > 150 → 不换
    router_local, _ = make_router(canteens, info_mode="local_estimate")
    assert router_local.try_switch(s, canteens, exclude_id="minghu_xueyi") is None

    # live_congestion：xuehuo shortest_window 即唯一窗口，queue_load=50 → est_wait=50×30=1500
    # candidate cost = 60 walk + 1500 = 1560 → 远大于 minghu 队 150
    # 而 xuesi 几乎空：shortest_window queue_load=0 → est_wait=0；cost = 60+0 = 60；60×1.3=78 < 150 → 切到 xuesi
    router_live, _ = make_router(canteens, info_mode="live_congestion")
    alt = router_live.try_switch(s, canteens, exclude_id="minghu_xueyi")
    assert alt is not None
    assert alt.id == "xuesi"
