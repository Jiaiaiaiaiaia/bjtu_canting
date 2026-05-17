"""Student dataclass + student_lifecycle 进程函数（spec §2.4 / §2.5）。"""
from dataclasses import dataclass
from typing import Literal, Optional

import simpy

from .queue_sim import sample_serve_time
from .dining_sim import sample_eat_time


@dataclass
class Student:
    id: int
    state: Literal[
        "arriving", "walking", "queueing", "switching",
        "floor_switching", "serving", "waiting_seat", "eating", "left"
    ]
    current_canteen_id: Optional[str] = None
    current_window_id: Optional[int] = None
    current_floor_id: Optional[int] = None
    target_floor_id: Optional[int] = None
    target_canteen_id: Optional[str] = None
    arrived_at: float = 0.0
    walk_time: float = 0.0
    wait_time: float = 0.0
    service_time: float = 0.0
    eat_time: float = 0.0
    switch_count: int = 0
    floor_switch_count: int = 0
    floor_switch_start_time: float = 0.0
    floor_switch_duration: float = 0.0
    patience_threshold: float = 180.0   # 创建时按正态分布采样覆盖
    walking_start_time: float = 0.0     # Coordinator 维护，给 Campus.transit_progress 用
    trace: object = None


def student_lifecycle(env, student, router, canteens, campus, coordinator):
    """学生从到达校园到离开的完整生命周期。

    canteens 是 dict[str, Canteen]；本函数中一律使用 dict 取值或 .values() 迭代。
    """
    student.state = "arriving"
    student.arrived_at = env.now
    coordinator.on_student_arrived(student)

    # 1. 校园入口选食堂
    target = router.pick_initial(student, canteens)
    student.target_canteen_id = target.id
    student.state = "walking"
    walk = campus.walking_time_from_entrance(target.id)
    coordinator.on_student_walking_start(student)
    yield env.timeout(walk)
    coordinator.on_student_walking_end(student)
    student.walk_time += walk
    student.current_canteen_id = target.id
    canteens[target.id].total_arrived += 1

    # 2. 排队（含跨食堂迁移）
    queue_phase_total_wait = 0.0
    while True:
        canteen = canteens[student.current_canteen_id]
        if student.current_floor_id is None:
            student.current_floor_id = canteen.choose_initial_floor(
                getattr(router, "rng", None)
            )
        window = canteen.choose_window(
            getattr(router, "rng", None),
            current_floor_id=student.current_floor_id,
        )
        if window.floor_id != student.current_floor_id:
            from_floor_id = student.current_floor_id
            target_floor_id = window.floor_id
            student.state = "floor_switching"
            student.floor_switch_count += 1
            canteen.start_floor_transfer(student, from_floor_id, target_floor_id)
            try:
                floor_walk = canteen.stair_travel_time(from_floor_id, target_floor_id)
                yield env.timeout(floor_walk)
                student.walk_time += floor_walk
                student.current_floor_id = target_floor_id
            finally:
                canteen.finish_floor_transfer(student)
            student.target_floor_id = None

        student.current_window_id = window.id
        student.current_floor_id = window.floor_id
        student.state = "queueing"

        # 顺序关键：先入队 waiting_students，再 request 资源。
        # 保证前端 waiting_students 索引顺序与 SimPy 内部 request 等待顺序一致。
        window.join_queue(student)

        try:
            with window.resource.request() as req:
                wait_start = env.now
                result = yield req | env.timeout(student.patience_threshold)

                if req not in result:
                    # 耐心超时
                    alt = router.try_switch(
                        student, canteens, exclude_id=canteen.id
                    )
                    if alt is not None:
                        # 迁移：仅在切换分支累计这段等待
                        window.leave_queue(student)
                        queue_phase_total_wait += env.now - wait_start
                        student.switch_count += 1
                        student.state = "switching"
                        # 必须先更新 target，再 on_student_walking_start。
                        # in_transit[].to_canteen_id 与 Campus.transit_progress
                        # 都依赖此字段反映"正在走向哪个食堂"。
                        student.target_canteen_id = alt.id
                        walk = campus.walking_time(canteen.id, alt.id)
                        coordinator.on_student_walking_start(student)
                        yield env.timeout(walk)
                        coordinator.on_student_walking_end(student)
                        student.walk_time += walk
                        # 注意：原食堂 total_arrived 不递减；切换会让
                        # sum(canteens.total_arrived) > coordinator.total_arrived。
                        student.current_canteen_id = alt.id
                        student.current_floor_id = None
                        student.target_floor_id = None
                        canteens[alt.id].total_arrived += 1
                        continue  # with 退出 → req 释放
                    # 没替代：硬等
                    yield req

                # 拿到资源（可能是首次 req 满足，也可能是硬等满足）
                queue_phase_total_wait += env.now - wait_start
                student.wait_time = queue_phase_total_wait
                coordinator.stats.record_wait(student)

                window.start_serving(student)
                student.state = "serving"
                trace = getattr(student, "trace", None)
                service_duration = sample_serve_time(
                    canteen.avg_serve_time,
                    rng=getattr(coordinator, "service_rng", None),
                    z_score=getattr(trace, "service_z", None),
                )
                try:
                    yield env.timeout(service_duration)
                    student.service_time = service_duration
                    window.finish_serving()
                except simpy.Interrupt:
                    # 第一版不会发生；预留给"窗口关停 / 学生退服务"等扩展。
                    raise
                finally:
                    if window.current_serving is student:
                        window.current_serving = None
        finally:
            # 异常路径兜底：leave_queue 是 idempotent，正常路径无副作用
            window.leave_queue(student)
        break

    # 3. 找座位 + 就餐
    canteen = canteens[student.current_canteen_id]
    student.state = "waiting_seat"
    canteen.join_seat_queue(student)

    try:
        seat = yield canteen.get_seat_prefer_floor(student.current_floor_id)
        canteen.leave_seat_queue(student)
        seat.student = student
        student.current_floor_id = seat.floor_id
        student.state = "eating"
        trace = getattr(student, "trace", None)
        eat_duration = sample_eat_time(
            canteen.avg_eat_time,
            rng=getattr(coordinator, "eat_rng", None),
            z_score=getattr(trace, "eat_z", None),
        )
        seat.eat_end_time = env.now + eat_duration
        yield env.timeout(eat_duration)
        seat.student = None
        student.eat_time = eat_duration
        canteen.seat_pool.put(seat)
        student.state = "left"
        canteen.total_served += 1
        coordinator.on_student_left(student)
        coordinator.stats.record_completion(student)
    finally:
        canteen.leave_seat_queue(student)  # 异常路径兜底
