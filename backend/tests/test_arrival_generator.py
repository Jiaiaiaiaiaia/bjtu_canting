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
@pytest.mark.skip(reason="待 A.7 lifecycle + A.8 Coordinator 完成后解封")
def test_arrival_generator_drains_after_simulation_seconds():
    """v1.3 bug 2 回归：simulation_seconds 后 _run 应停止生成；
    已生成学生由 SimPy 调度自然 drain；coordinator.total_arrived 不再增长。

    依赖 A.8 Coordinator 提供 total_arrived 统计与 student_lifecycle 完整路径。
    现在写测试名占位，A.8 完成后回到本文件解封。
    """
    env = simpy.Environment()
    cfg = {
        "total_students": 1000,
        "lunch_alpha": 0.5,
        "coverage": 0.8,
        "peak_window_minutes": 60,
        "simulation_seconds": 60,  # 1 分钟截止
    }
    # coordinator = make_coord(env, cfg)
    # env.run(until=120)  # 跑 2 分钟
    # arrivals_at_60 = coordinator.snapshot_at_time(60).total_arrived
    # arrivals_at_120 = coordinator.total_arrived
    # assert arrivals_at_120 == arrivals_at_60
