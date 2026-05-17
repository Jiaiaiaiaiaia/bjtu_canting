"""校园模式下的学生工厂：ArrivalGenerator（spec §2.9 / §3.4）。

按 Poisson 过程从校园入口生成学生，交给 student_lifecycle 处理。
simulation_seconds 后停止生成新学生；已生成学生由 SimPy 自然 drain。

CampusCoordinator 在校园联合模式和 SimulationEngine 单食堂兼容门面中都会使用本类。
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
    """按 Poisson 过程从校园入口生成学生，交给 student_lifecycle 处理。

    SimulationEngine 兼容门面会通过 ``_planned_students`` 注入一组预创建的
    Student 对象，以保留 Phase 2 中 ``engine.students`` 可索引真实对象的外部契约。
    校园联合模式不传该字段，仍按需创建学生。
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

    def _spawn_student(self, trace=None) -> Student:
        planned_students = self.config.get("_planned_students")
        if planned_students is not None and self._next_student_id < len(planned_students):
            student = planned_students[self._next_student_id]
            student.state = "arriving"
        else:
            student = Student(
                id=self._next_student_id,
                state="arriving",
            )
            if planned_students is not None:
                planned_students.append(student)
        if trace is not None:
            student.trace = trace
            student.patience_threshold = trace.to_patience_seconds(self.router.config)
        else:
            student.trace = None
            student.patience_threshold = self.router.sample_patience()
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

        traces = self.config.get("_student_traces")
        if traces is not None:
            last_arrival = 0.0
            for trace in traces:
                delay = max(0.0, trace.arrival_at - last_arrival)
                yield self.env.timeout(delay)
                last_arrival = trace.arrival_at
                student = self._spawn_student(trace)
                from .student import student_lifecycle  # type: ignore[attr-defined]
                self.env.process(student_lifecycle(
                    self.env, student, self.router,
                    self.canteens, self.campus, self.coordinator,
                ))
            return

        rate_per_sec = self._compute_arrival_rate_per_minute() / 60.0
        # 到达截止时间：单位秒。若未在 config 中显式指定，
        # 默认与午餐高峰窗口一致，即 peak_window_minutes * 60。
        stop_after = self.config.get(
            "simulation_seconds",
            self.config["peak_window_minutes"] * 60.0,
        )

        schedule = self.config.get("arrival_schedule")
        if schedule:
            # 非常量 λ(t)：live 生成器与 trace 预生成共用同一 ArrivalSchedule
            # + 同一 thinning（spec §3.5/§5.1）。总量守恒：期望总到达
            # = 恒定速率(N·α·coverage/T) × 时长，只改时间形状不改总量。
            from .arrival_schedule import ArrivalSchedule

            ramp = schedule.get("ramp")
            sch = ArrivalSchedule(
                total_arrivals=rate_per_sec * stop_after,
                horizon_seconds=stop_after,
                baseline=schedule.get("baseline", 1.0),
                ramp=tuple(ramp) if ramp else None,
                pulses=[tuple(p) for p in schedule.get("pulses", [])],
            )
            last_arrival = 0.0
            for arrival_at in sch.sample_arrivals(self.rng):
                yield self.env.timeout(max(0.0, arrival_at - last_arrival))
                last_arrival = arrival_at
                student = self._spawn_student()
                from .student import student_lifecycle  # type: ignore[attr-defined]
                self.env.process(student_lifecycle(
                    self.env, student, self.router,
                    self.canteens, self.campus, self.coordinator,
                ))
            return

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
