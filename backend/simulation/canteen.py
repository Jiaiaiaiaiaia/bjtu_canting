"""Window / Seat / FloorMeta dataclass（spec §2.3）。Canteen 类留待 A.2.2 实现。"""
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING
import simpy

if TYPE_CHECKING:
    from .student import Student


@dataclass
class Window:
    id: int
    floor_id: int                                    # v1.3 新增；前端按此分组渲染
    canteen_avg_serve_time: float                    # 由 Canteen 注入，估值用
    resource: simpy.Resource                         # capacity=1，每窗口独立排队
    waiting_students: list = field(default_factory=list)
    current_serving: Optional["Student"] = None
    total_served: int = 0

    @property
    def queue_length(self) -> int:
        return len(self.waiting_students)

    @property
    def queue_load(self) -> int:
        # 与 Phase 2 queue_sim.py:14 queue_load() 语义一致：正在打饭的学生也算压力
        return self.resource.count + len(self.waiting_students)

    def join_queue(self, student: "Student"):
        self.waiting_students.append(student)

    def leave_queue(self, student: "Student"):
        # idempotent：finally 兜底重复调用安全
        if student in self.waiting_students:
            self.waiting_students.remove(student)

    def start_serving(self, student: "Student"):
        self.leave_queue(student)
        self.current_serving = student

    def finish_serving(self):
        self.current_serving = None
        self.total_served += 1

    def estimated_wait_for(self, student: "Student") -> float:
        """学生估算自己从当前位置打到饭的剩余时间。
        简化：前面排队人数 × 平均服务时间 + 当前正在服务的人按 1 个补偿。
        """
        try:
            ahead = self.waiting_students.index(student)
        except ValueError:
            return 0.0
        return (ahead + self.resource.count) * self.canteen_avg_serve_time


@dataclass
class Seat:
    id: int
    floor_id: int                                    # v1.3 新增
    student: Optional["Student"] = None
    eat_end_time: float = 0.0   # 绝对时刻；前端按 current_time 算 remaining_time


@dataclass
class FloorMeta:
    """每楼层的元数据；不持有仿真资源，仅供 snapshot 输出与 3D 渲染参考。"""
    floor_id: int
    layout: dict = field(default_factory=dict)       # {floor_size, window_positions, seat_grid}
    notes: str = ""
