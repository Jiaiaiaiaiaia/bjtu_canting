"""就餐仿真模块 —— 管理座位分配、就餐计时、离场释放。"""
import random


class Seat:
    """餐桌座位。"""

    def __init__(self, seat_id):
        self.id = seat_id
        self.status = 'empty'  # 'empty' 或 'occupied'
        self.student = None
        self.eat_end_time = None  # 预计离座时刻（秒），由引擎按 current_time 动态换算剩余时间


def pick_nearest_seat(seats, window_id, window_count):
    """就近策略：按座位 ID 与窗口位置的映射关系选择空闲座位。"""
    empty = [s for s in seats if s.status == 'empty']
    if not empty:
        return None
    seats_per_window = max(1, len(seats) // max(1, window_count))
    target_id = window_id * seats_per_window
    return min(empty, key=lambda s: abs(s.id - target_id))


def sample_eat_time(avg_eat_minutes, rng=None, z_score=None):
    """正态分布采样就餐时长（秒）。"""
    avg_seconds = avg_eat_minutes * 60
    std = avg_seconds * 0.2
    if z_score is None:
        source = rng if rng is not None else random
        eat_time = source.normalvariate(avg_seconds, std)
    else:
        eat_time = avg_seconds + z_score * std
    return max(60.0, eat_time)
