"""排队仿真模块 —— 管理窗口队列、窗口分配、打饭服务时长。"""
import random


class Window:
    """食堂打饭窗口。"""

    def __init__(self, window_id, avg_serve_time):
        self.id = window_id
        self.queue = []
        self.avg_serve_time = avg_serve_time
        self.current_serving = None
        self.total_served = 0

    def queue_load(self):
        """当前窗口排队压力（含正在打饭的人）。"""
        return len(self.queue) + (1 if self.current_serving else 0)


def pick_shortest_window(windows):
    """最短队列策略：将新到学生分配到排队人数最少的窗口。"""
    return min(windows, key=lambda w: w.queue_load())


def sample_serve_time(avg_serve_time):
    """正态分布采样打饭时长（秒），下限 1 秒。"""
    serve_time = random.normalvariate(avg_serve_time, avg_serve_time * 0.2)
    return max(1.0, serve_time)
