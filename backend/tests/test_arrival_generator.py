"""A.6.1 ArrivalGenerator 单元测试（2 条立即测试 + 1 条 skip）。"""
import random
import pytest
import simpy

from simulation.arrival_generator import ArrivalGenerator


# 1. λ 公式：N × α × coverage / T，不乘 peak_beta
def test_arrival_rate_formula():
    """λ_avg = N × α × coverage / T，单位人/分钟。
    peak_beta 不参与公式（spec §3.4 / §2.9）。"""
    env = simpy.Environment()
    cfg = {
        "total_students": 28000,
        "lunch_alpha": 0.65,
        "coverage": 0.65,
        "peak_window_minutes": 90,
        "peak_beta": 1.5,  # 故意填上但不应影响结果
        "simulation_seconds": 1000,
    }
    # 其他参数都可以 mock，因为 _compute_arrival_rate_per_minute 只读 cfg
    gen = ArrivalGenerator(
        env, cfg, canteens={}, router=None,
        campus=None, coordinator=None, rng=random.Random(42),
    )
    expected = 28000 * 0.65 * 0.65 / 90
    assert abs(gen._compute_arrival_rate_per_minute() - expected) < 0.01


# 2. Poisson interval 分布：rng.expovariate(rate) 期望均值 ≈ 1/rate
def test_poisson_interval_distribution():
    """rng.expovariate(rate) 的间隔均值应接近 1/rate。"""
    rng = random.Random(42)
    intervals = [rng.expovariate(0.1) for _ in range(2000)]
    avg = sum(intervals) / len(intervals)
    # 期望 1/0.1 = 10；2000 次抽样标准差较小，8-12 区间安全
    assert 8.5 < avg < 11.5


# 3. drain 测试：simulation_seconds 截止后不再生成新学生（v1.3 bug 2 回归）
def test_arrival_generator_drains_after_simulation_seconds():
    """v1.3 bug 2 回归：simulation_seconds 后 ArrivalGenerator 不再 spawn 新学生；
    coordinator.total_arrived 在 simulation_seconds 后不再增长。

    用真实 CampusCoordinator 端到端验证（A.8 解封后）。
    """
    from simulation.coordinator import CampusCoordinator

    env = simpy.Environment()
    cfg = {
        "canteens": [{
            "id": "minghu_xueyi", "display_name": "明湖学一",
            "campus_position": {"x": 0, "y": 0},
            "avg_serve_time_seconds": 30,
            "avg_eat_time_minutes": 15,
            "arrival_weight": 1.0,
            "typical_wait_seconds": 200,
            "floors": [{"floor_id": 1, "windows": {"physical_count": 4, "active_count": 4}, "seats": {"count": 50}}],
        }],
        "campus": {
            "total_students": 1000,
            "lunch_alpha": 0.5,
            "coverage": 0.8,
            "peak_window_minutes": 60,
            "peak_beta": 1.5,
            "simulation_seconds": 60,  # 1 分钟截止
            "entrance_position": {"x": 0, "y": 0},
            "walking_speed_mps": 1.4,
            "walking_time_seconds": {},
            "entrance_walk_seconds": {"minghu_xueyi": 5},
        },
        "router": {
            "information_mode": "local_estimate",
            "patience_mean_seconds": 180,
            "patience_std_seconds": 60,
            "patience_min_seconds": 30,
            "switch_improvement_ratio": 1.3,
            "max_switches_per_student": 2,
            "rng_seed": 42,
        },
    }
    rng = random.Random(42)
    coordinator = CampusCoordinator(env, cfg, rng)

    # 推到 simulation_seconds（60s）
    env.run(until=60)
    arrivals_at_60 = coordinator.total_arrived

    # 推到 120s（远超 simulation_seconds）
    env.run(until=120)
    arrivals_at_120 = coordinator.total_arrived

    # 截止后 coordinator.total_arrived 不再增长
    assert arrivals_at_120 == arrivals_at_60, (
        f"截止后不该再 spawn：60s 时 {arrivals_at_60}，120s 时 {arrivals_at_120}"
    )
    # 至少应该 spawn 过几个（确认测试不是 trivial）
    assert arrivals_at_60 > 0, f"60s 内应至少 spawn 1 个学生，实际 {arrivals_at_60}"


# 4. v1.3 bug 2 边界回归：env.now >= stop_after 时不再 spawn 新学生
def test_arrival_generator_does_not_spawn_after_simulation_seconds(monkeypatch):
    """v1.3 bug 2 边界回归：env.now >= stop_after 时不再 spawn 新学生。

    _run 的 `if self.env.now + interval >= stop_after` 分支必须被覆盖：
    截止时刻之后 _next_student_id 不再增长。

    实现细节：因为 _run 内部 lazy import student_lifecycle（A.7.1 才建），
    本测试用 monkeypatch 注入 stub，让 lazy import 成功。
    """
    # Stub student_lifecycle 让 _run 的 lazy import 成功；stub 是空 generator 不阻塞。
    import simulation.student as student_mod

    def stub_lifecycle(env, student, *args, **kwargs):
        # 必须是 generator function（env.process 要 generator）；不 yield 直接 return 会变成 None 函数
        if False:
            yield
        return

    monkeypatch.setattr(student_mod, "student_lifecycle", stub_lifecycle, raising=False)

    # Stub router 提供 sample_patience（_spawn_student 会调）
    class StubRouter:
        def sample_patience(self):
            return 180.0

    env = simpy.Environment()
    cfg = {
        "total_students": 28000,
        "lunch_alpha": 0.65,
        "coverage": 0.65,
        "peak_window_minutes": 90,
        "simulation_seconds": 60,  # 1 分钟截止
    }
    rng = random.Random(42)
    gen = ArrivalGenerator(
        env, cfg, canteens={}, router=StubRouter(),
        campus=None, coordinator=None, rng=rng,
    )

    # 推进到截止时刻
    env.run(until=60)
    spawn_count_at_60 = gen._next_student_id

    # 继续推进到 2 分钟（截止后）
    env.run(until=120)
    spawn_count_at_120 = gen._next_student_id

    # 截止后不再 spawn
    assert spawn_count_at_120 == spawn_count_at_60, (
        f"spawn count grew from {spawn_count_at_60} to {spawn_count_at_120} "
        f"after simulation_seconds=60, but _run should have stopped."
    )
    # 截止前应已经 spawn 过——否则测试 trivially 通过
    # rate ≈ 28000 × 0.65 × 0.65 / 90 ≈ 131 人/分钟，60 秒应有几十次
    assert spawn_count_at_60 > 5, (
        f"only {spawn_count_at_60} spawned in first 60s; rate likely too low for meaningful test"
    )


# 5. rate=0（如 coverage=0）必须 raise ValueError，不延迟到 _run 第一帧崩
def test_arrival_generator_rejects_zero_rate():
    """rate=0（如 coverage=0）必须 raise ValueError，不延迟到 _run 第一帧崩。"""
    env = simpy.Environment()
    cfg_zero_coverage = {
        "total_students": 28000,
        "lunch_alpha": 0.65,
        "coverage": 0,   # 触发 rate=0
        "peak_window_minutes": 90,
    }
    with pytest.raises(ValueError, match="arrival rate must be positive"):
        ArrivalGenerator(
            env, cfg_zero_coverage, canteens={}, router=None,
            campus=None, coordinator=None, rng=random.Random(42),
        )
