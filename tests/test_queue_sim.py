"""排队仿真模块单元测试 —— Window / pick_shortest_window / sample_serve_time。"""
import pytest

from canteen.simulation.queue_sim import Window, pick_shortest_window, sample_serve_time


class TestWindow:
    def test_initial_state(self):
        w = Window(2, 30)
        assert w.id == 2
        assert w.queue == []
        assert w.current_serving is None
        assert w.total_served == 0
        assert w.avg_serve_time == 30
        assert w.queue_load() == 0

    def test_queue_load_includes_current_serving(self):
        w = Window(0, 30)
        assert w.queue_load() == 0
        w.current_serving = object()
        assert w.queue_load() == 1
        w.queue.extend(['s1', 's2', 's3'])
        assert w.queue_load() == 4


class TestPickShortestWindow:
    def test_returns_least_loaded(self):
        ws = [Window(i, 30) for i in range(3)]
        ws[0].queue = ['a', 'b', 'c']
        ws[1].queue = ['a']
        ws[2].queue = ['a', 'b']
        assert pick_shortest_window(ws).id == 1

    def test_serving_counts_toward_load(self):
        ws = [Window(i, 30) for i in range(2)]
        ws[0].queue = ['a']
        ws[1].current_serving = object()  # 正在打饭也算压力
        ws[1].queue = ['a']
        # 0 号压力 1，1 号压力 2，应选 0
        assert pick_shortest_window(ws).id == 0


class TestSampleServeTime:
    def test_accepts_z_score(self):
        assert sample_serve_time(30, z_score=0.0) == 30
        assert sample_serve_time(30, z_score=-100.0) == 1.0

    def test_lower_bound_one_second(self):
        for _ in range(500):
            assert sample_serve_time(1.0) >= 1.0

    def test_mean_close_to_input(self):
        samples = [sample_serve_time(30) for _ in range(2000)]
        mean = sum(samples) / len(samples)
        # 正态分布 stddev=20%，2000 次采样均值应接近 30，允许 ±2 误差
        assert 28 < mean < 32

    def test_no_negative_values(self):
        for _ in range(500):
            assert sample_serve_time(5) > 0
