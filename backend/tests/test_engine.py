"""仿真驱动模块单元测试 —— SimulationEngine 完整生命周期与不变量。"""
import pytest

from simulation import SimulationEngine


@pytest.fixture
def basic_config():
    return {
        'window_count': 3,
        'seat_count': 30,
        'avg_serve_time': 15,
        'avg_eat_time': 5,
        'arrival_rate': 20,
        'total_time': 5,
    }


@pytest.fixture
def engine(basic_config):
    return SimulationEngine(basic_config, config_id=0, rng_seed=42)


class TestInitialState:
    def test_wraps_single_canteen_coordinator(self, engine):
        """A.9.1: SimulationEngine 应作为单食堂 CampusCoordinator 兼容门面。"""
        assert hasattr(engine, 'coordinator')
        assert list(engine.coordinator.canteens.keys()) == ['single']

    def test_counters_zero_before_start(self, engine):
        assert engine.total_arrived == 0
        assert engine.total_served == 0
        assert engine.current_time == 0.0
        assert engine._is_started is False
        assert engine._is_ended is False
        assert engine.event_queue == []

    def test_windows_and_seats_initialized(self, engine, basic_config):
        assert len(engine.windows) == basic_config['window_count']
        assert len(engine.seats) == basic_config['seat_count']


class TestStartGuard:
    """重复调用 start() 不应再次预生成事件，避免 total_arrived 翻倍。"""

    def test_idempotent_start(self, engine):
        engine.start()
        e1 = (len(engine.event_queue), len(engine.students))
        engine.start()
        e2 = (len(engine.event_queue), len(engine.students))
        assert e1 == e2
        assert engine._is_started is True


class TestArrivalCounting:
    """total_arrived 应该按 step() 单调递增，不应在 start() 时一次性预填满。"""

    def test_total_arrived_zero_right_after_start(self, engine):
        engine.start()
        # start 之后应该只是预生成了事件队列，arrived 仍为 0
        assert engine.total_arrived == 0
        assert len(engine.students) > 0  # 但学生对象已就绪

    def test_total_arrived_monotonic(self, engine):
        engine.start()
        prev = 0
        for _ in range(100):
            st = engine.step()
            if st['is_ended']:
                break
            assert st['total_arrived'] >= prev
            prev = st['total_arrived']

    def test_total_arrived_capped_by_predefined_students(self, engine):
        engine.start()
        max_possible = len(engine.students)
        for _ in range(10000):
            st = engine.step()
            if st['is_ended']:
                break
        assert engine.total_arrived <= max_possible


class TestSeatRemainingTime:
    """座位 remaining_time 应该随 current_time 动态递减，而不是入座时锁定的静态值。"""

    def test_remaining_time_decreases_for_same_seat(self, engine):
        engine.start()
        captured_first = None
        for _ in range(500):
            st = engine.step()
            if st['is_ended']:
                break
            occ = [s for s in st['seats'] if s['status'] == 'occupied']
            if not occ:
                continue
            sid = occ[0]['id']
            r0 = occ[0]['remaining_time']
            # 推进若干步，看同一座位 remaining_time 是否下降
            for _ in range(10):
                st2 = engine.step()
                if st2['is_ended']:
                    break
                m = [s for s in st2['seats'] if s['id'] == sid and s['status'] == 'occupied']
                if m and m[0]['remaining_time'] < r0:
                    captured_first = (r0, m[0]['remaining_time'])
                    break
            if captured_first:
                break
        assert captured_first is not None, '未观察到任何已就餐座位 remaining_time 下降'
        assert captured_first[1] < captured_first[0]

    def test_empty_seats_have_zero_remaining(self, engine):
        engine.start()
        for _ in range(20):
            st = engine.step()
            if st['is_ended']:
                break
            for s in st['seats']:
                if s['status'] == 'empty':
                    assert s['remaining_time'] == 0


class TestAvgWaitingTime:
    def test_build_state_includes_avg_waiting_time(self, engine):
        engine.start()
        for _ in range(50):
            engine.step()
        state = engine.step()
        assert 'avg_waiting_time' in state
        assert isinstance(state['avg_waiting_time'], (int, float))
        assert state['avg_waiting_time'] >= 0


class TestRunToCompletion:
    def test_arrived_equals_served_at_end(self, engine):
        engine.start()
        for _ in range(20000):
            st = engine.step()
            if st['is_ended']:
                break
        assert engine.total_arrived == engine.total_served
        assert engine.total_arrived > 0

    def test_no_residual_state(self, engine):
        engine.start()
        for _ in range(20000):
            st = engine.step()
            if st['is_ended']:
                break
        assert all(s.status == 'empty' for s in engine.seats)
        assert all(not w.queue and w.current_serving is None for w in engine.windows)
        assert engine.waiting_queue == []


class TestStatistics:
    def test_basic_invariants(self, engine):
        engine.start()
        for _ in range(20000):
            st = engine.step()
            if st['is_ended']:
                break
        stats = engine.get_statistics()
        assert stats['total_arrived'] == engine.total_arrived
        assert stats['total_served'] == engine.total_served
        assert 0 <= stats['seat_utilization'] <= 100, '座位利用率不能超过 100%'
        assert sum(stats['window_served']) == stats['total_served']
        assert stats['avg_waiting_time'] >= 0
        assert stats['avg_service_time'] >= 0
        assert stats['avg_eating_time'] >= 60

    def test_timelines_have_data(self, engine):
        engine.start()
        for _ in range(20000):
            st = engine.step()
            if st['is_ended']:
                break
        stats = engine.get_statistics()
        assert len(stats['queue_timeline']['x']) > 0
        assert len(stats['queue_timeline']['y']) == len(stats['queue_timeline']['x'])
        # 每分钟一个采样点，至少覆盖 total_time 那么多分钟
        assert len(stats['queue_timeline']['x']) >= 5
