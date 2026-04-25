"""就餐仿真模块单元测试 —— Seat / pick_nearest_seat / sample_eat_time。"""
import pytest

from simulation.dining_sim import Seat, pick_nearest_seat, sample_eat_time


class TestSeat:
    def test_initial_state(self):
        s = Seat(7)
        assert s.id == 7
        assert s.status == 'empty'
        assert s.student is None
        assert s.eat_end_time is None  # 不再用 remaining_time 静态字段


class TestPickNearestSeat:
    def test_none_when_all_occupied(self):
        seats = [Seat(i) for i in range(5)]
        for s in seats:
            s.status = 'occupied'
        assert pick_nearest_seat(seats, 0, 4) is None

    def test_picks_seat_close_to_window(self):
        seats = [Seat(i) for i in range(20)]
        # 4 个窗口 * 5 个座位/窗口；窗口 0 应映射到前段，窗口 3 应映射到尾段
        chosen_w0 = pick_nearest_seat(seats, 0, 4)
        chosen_w3 = pick_nearest_seat(seats, 3, 4)
        assert chosen_w0.id <= 4
        assert chosen_w3.id >= 10

    def test_skips_occupied_seats(self):
        seats = [Seat(i) for i in range(8)]
        seats[0].status = 'occupied'
        seats[1].status = 'occupied'
        chosen = pick_nearest_seat(seats, 0, 2)
        assert chosen.status == 'empty'
        assert chosen.id >= 2


class TestSampleEatTime:
    def test_lower_bound_60_seconds(self):
        for _ in range(500):
            # 即使输入很小，也应保证至少 60 秒
            assert sample_eat_time(0.1) >= 60.0

    def test_mean_close_to_input(self):
        samples = [sample_eat_time(15) for _ in range(2000)]  # 15 分钟 = 900 秒
        mean = sum(samples) / len(samples)
        # 期望值 ~900 秒，允许较宽的 ±50 秒误差
        assert 850 < mean < 950
