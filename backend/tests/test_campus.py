"""Campus 拓扑测试（spec §2.8 / plan A.3.1）。

3 食堂契约（v1.6）：fixture 只用 minghu_xueyi / xuehuo / xuesi。
"""
import simpy

from simulation.campus import Campus
from simulation.canteen import Canteen
from simulation.student import Student


def make_canteens(env):
    """Fixture：3 食堂契约（minghu_xueyi / xuehuo / xuesi）。
    每食堂用最小占位 preset，campus_position 各异以驱动欧氏距离。
    """
    base_def = {
        "avg_serve_time_seconds": 30,
        "avg_eat_time_minutes": 15,
        "arrival_weight": 1.0,
        "typical_wait_seconds": 120,
        "floors": [{"floor_id": 1,
                    "windows": {"physical_count": 4, "active_count": 4},
                    "seats": {"count": 30}}],
    }
    minghu = {**base_def, "id": "minghu_xueyi", "display_name": "明湖学一",
              "campus_position": {"x": 0, "y": 0}}
    xuehuo = {**base_def, "id": "xuehuo", "display_name": "学活",
              "campus_position": {"x": 100, "y": 0}}
    xuesi = {**base_def, "id": "xuesi", "display_name": "学四",
             "campus_position": {"x": 0, "y": 100}}
    return {
        "minghu_xueyi": Canteen(env, minghu),
        "xuehuo": Canteen(env, xuehuo),
        "xuesi": Canteen(env, xuesi),
    }


def test_walking_time_uses_matrix_first():
    """matrix 命中优先于欧氏距离。"""
    env = simpy.Environment()
    canteens = make_canteens(env)
    cfg = {"entrance_position": {"x": 0, "y": 0}, "walking_speed_mps": 1.4,
           "walking_time_seconds": {"minghu_xueyi": {"xuehuo": 99}},
           "entrance_walk_seconds": {}}
    campus = Campus(cfg, canteens)
    assert campus.walking_time("minghu_xueyi", "xuehuo") == 99


def test_walking_time_falls_back_to_euclidean():
    """matrix 缺失时按欧氏距离 / walking_speed_mps 估算。"""
    env = simpy.Environment()
    canteens = make_canteens(env)
    cfg = {"entrance_position": {"x": 0, "y": 0}, "walking_speed_mps": 1.4,
           "walking_time_seconds": {}, "entrance_walk_seconds": {}}
    campus = Campus(cfg, canteens)
    # 100 米直线 / 1.4 m/s ≈ 71.4 秒
    expected = 100 / 1.4
    assert abs(campus.walking_time("minghu_xueyi", "xuehuo") - expected) < 0.01


def test_walking_time_symmetric_via_matrix_or_euclidean():
    """matrix 反向键也能命中（对称）；欧氏距离天然对称。"""
    env = simpy.Environment()
    canteens = make_canteens(env)
    cfg = {"entrance_position": {"x": 0, "y": 0}, "walking_speed_mps": 1.4,
           "walking_time_seconds": {"minghu_xueyi": {"xuehuo": 99}},
           "entrance_walk_seconds": {}}
    campus = Campus(cfg, canteens)
    # 反向查应该走 m_rev 命中
    assert campus.walking_time("xuehuo", "minghu_xueyi") == 99


def test_transit_progress_zero_when_not_walking():
    """walking_start_time == 0 时 transit_progress 返回 0（学生未在走路态）。"""
    env = simpy.Environment()
    canteens = make_canteens(env)
    cfg = {"entrance_position": {"x": 0, "y": 0}, "walking_speed_mps": 1.4,
           "walking_time_seconds": {}, "entrance_walk_seconds": {}}
    campus = Campus(cfg, canteens)
    s = Student(id=1, state="walking", walking_start_time=0)
    assert campus.transit_progress(s, now=0) == 0.0
