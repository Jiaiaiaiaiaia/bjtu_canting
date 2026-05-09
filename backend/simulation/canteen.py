"""Window / Seat / FloorMeta dataclass + Canteen 类（spec §2.3）。"""
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


class Canteen:
    """单食堂仿真容器：多楼层 Window/Seat 展开 + shortest_window + snapshot 双形状。"""

    def __init__(self, env: simpy.Environment, definition: dict):
        self.env = env
        self.id = definition["id"]
        self.display_name = definition["display_name"]
        self.campus_position = definition["campus_position"]
        # 单位约定（与 Phase 2 的 sample_serve_time / sample_eat_time 输入对齐）：
        #   avg_serve_time —— 秒
        #   avg_eat_time   —— 分钟（Phase 2 sample_eat_time 输入即分钟）
        self.avg_eat_time = definition["avg_eat_time_minutes"]
        self.arrival_weight = definition["arrival_weight"]
        self.typical_wait_seconds = definition.get("typical_wait_seconds", 120.0)

        # 楼层数据从 preset["floors"] 展开
        self.floors_meta: list[FloorMeta] = []
        self.windows: list[Window] = []
        self.seats: list[Seat] = []
        self.physical_window_count: int = 0
        self.active_window_count: int = 0

        # preset 顶层可提供 default avg_serve_time，每层可覆盖
        default_serve_time = definition.get("avg_serve_time_seconds")

        next_window_id = 0
        next_seat_id = 0
        for floor_def in definition["floors"]:
            fid = floor_def["floor_id"]
            self.floors_meta.append(FloorMeta(
                floor_id=fid,
                layout=floor_def.get("layout", {}),
                notes=floor_def.get("notes", ""),
            ))
            wdef = floor_def.get("windows", {})
            sdef = floor_def.get("seats", {})

            self.physical_window_count += wdef.get("physical_count", wdef.get("active_count", 0))
            self.active_window_count += wdef.get("active_count", 0)
            floor_serve_time = wdef.get("avg_serve_time_seconds", default_serve_time)

            for _ in range(wdef.get("active_count", 0)):
                self.windows.append(Window(
                    id=next_window_id,
                    floor_id=fid,
                    canteen_avg_serve_time=floor_serve_time,
                    resource=simpy.Resource(env, capacity=1),
                ))
                next_window_id += 1

            for _ in range(sdef.get("count", 0)):
                self.seats.append(Seat(id=next_seat_id, floor_id=fid))
                next_seat_id += 1

        # 食堂级"代表性服务时间"：StudentRouter 估值用；取所有窗口加权平均
        if self.windows:
            self.avg_serve_time = sum(
                w.canteen_avg_serve_time for w in self.windows
            ) / len(self.windows)
        else:
            self.avg_serve_time = default_serve_time or 30.0

        # 座位资源池：simpy.Store 负责"谁抢到座位"的调度（跨楼层共享）
        self.seat_pool = simpy.Store(env)
        for s in self.seats:
            self.seat_pool.put(s)

        # 等座可视化/统计：与 Window.waiting_students 同模式
        self.seat_waiting_students: list = []

        # 食堂级累计统计
        self.total_arrived: int = 0
        self.total_served: int = 0

    def shortest_window(self) -> Window:
        return min(self.windows, key=lambda w: w.queue_load)

    def join_seat_queue(self, student: "Student"):
        self.seat_waiting_students.append(student)

    def leave_seat_queue(self, student: "Student"):
        if student in self.seat_waiting_students:
            self.seat_waiting_students.remove(student)

    @property
    def seat_waiting_count(self) -> int:
        return len(self.seat_waiting_students)
