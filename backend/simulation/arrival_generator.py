"""校园模式下的学生工厂：ArrivalGenerator（spec §2.9 / §3.4）。

按 Poisson 过程从校园入口生成学生，交给 student_lifecycle 处理。
simulation_seconds 后停止生成新学生；已生成学生由 SimPy 自然 drain。

单食堂模式不使用本类；SimulationEngine 兼容门面继续走 Phase 2 原有路径。
"""
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import simpy
    from .canteen import Canteen
    from .router import StudentRouter
    from .campus import Campus
    from .coordinator import CampusCoordinator

from .student import Student


class ArrivalGenerator:
    """校园模式下的学生工厂：按 Poisson 过程从校园入口生成学生，
    交给 student_lifecycle 处理。simulation_seconds 后停止生成。

    单食堂模式不使用本类；SimulationEngine 兼容门面继续走 Phase 2 原有的
    _generate_arrival_events 路径。
    """

    def __init__(self, env, campus_config, canteens, router,
                 campus, coordinator, rng):
        self.env = env
        self.config = campus_config
        self.canteens = canteens
        self.router = router
        self.campus = campus
        self.coordinator = coordinator
        self.rng = rng
        self._next_student_id = 0
        # 早期校验：rate <= 0 会让 rng.expovariate(0) 抛 ValueError；
        # 在 __init__ 立刻发现比延迟到 _run 第一帧炸更易定位（与 A.3.1 walking_speed_mps
        # 同一防御模式）。
        rate_per_minute = self._compute_arrival_rate_per_minute()
        if rate_per_minute <= 0:
            raise ValueError(
                "arrival rate must be positive; "
                "check total_students / lunch_alpha / coverage / peak_window_minutes"
            )
        self._process = env.process(self._run())

    def _compute_arrival_rate_per_minute(self) -> float:
        """根据 §3.4 公式计算 λ_avg（人/分钟），用于 _run 的恒定到达过程。

        第一版只读取 N / α / coverage / T 四个字段；
        config["campus"]["peak_beta"] 字段会被 §10 部署阶段灵敏度实验单独读取使用，
        不参与本方法返回值计算。
        """
        N = self.config["total_students"]
        alpha = self.config["lunch_alpha"]
        coverage = self.config["coverage"]
        T = self.config["peak_window_minutes"]
        return N * alpha * coverage / T

    def _spawn_student(self) -> Student:
        student = Student(
            id=self._next_student_id,
            state="arriving",
            patience_threshold=self.router.sample_patience(),
        )
        self._next_student_id += 1
        return student

    def _run(self):
        """Poisson 到达过程，每名学生 yield 一个 student_lifecycle 进程。

        到达过程到 simulation_seconds 截止后停止生成新学生；
        已生成的学生会被 SimPy 调度执行完毕，env.run(until=...) 自然 drain。
        这是 /api/campus/finish 能正确返回最终统计的前提。
        """
        # Lazy import：A.6.1 实施时 student_lifecycle 还没建（A.7.1 才建）。
        # 函数内 import 让本模块能独立加载，跑测试时只要测试不实际调用 _run 就不爆。
        from .student import Student  # noqa: F401  (Student 已在模块顶 import；这里仅做防御)

        rate_per_sec = self._compute_arrival_rate_per_minute() / 60.0
        # 到达截止时间：单位秒。若未在 config 中显式指定，
        # 默认与午餐高峰窗口一致，即 peak_window_minutes * 60。
        stop_after = self.config.get(
            "simulation_seconds",
            self.config["peak_window_minutes"] * 60.0,
        )
        while self.env.now < stop_after:
            interval = self.rng.expovariate(rate_per_sec)
            if self.env.now + interval >= stop_after:
                # 下一个到达落在截止后，不再生成
                yield self.env.timeout(stop_after - self.env.now)
                return
            yield self.env.timeout(interval)
            student = self._spawn_student()
            # 这里要调 student_lifecycle，但 A.7.1 还没建。lazy import 在用时拉。
            # 测试 1/2 不会触发 _run 的这一段。drain 测试 skip 等 A.7/A.8 完成后解封。
            from .student import student_lifecycle  # type: ignore[attr-defined]
            self.env.process(student_lifecycle(
                self.env, student, self.router,
                self.canteens, self.campus, self.coordinator,
            ))
