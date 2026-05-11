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
    def queue(self) -> list:
        """Phase 2 兼容别名：旧 SimulationEngine 测试读取 window.queue。"""
        return self.waiting_students

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

    @property
    def status(self) -> str:
        """Phase 2 兼容字段：旧前端与测试使用 occupied/empty。"""
        return "occupied" if self.student else "empty"


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
            # 30 秒是调研缺失时的保守默认服务时长（秒）：仅当 preset 既没顶层
            # avg_serve_time_seconds、也没任何楼层级值时回退到此默认值。
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

        # v1.3 robustness：防 shortest_window() 在空窗口列表上崩。
        # 用 raise ValueError 而非 assert，避免 python -O 关掉断言时绕过此校验，
        # 也用更精确的异常类：active_window_count <= 0 是输入配置错。
        if self.active_window_count <= 0:
            raise ValueError(
                f"Canteen {self.id!r} must have at least one active window; "
                f"preset 配置错误或所有楼层 active_count 都为 0"
            )

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

    def snapshot(self) -> dict:
        """输出双形状：flat（Phase 2 兼容）+ 嵌套 floors[]（v1.3 新前端用）。

        ``floors[].windows / seats / students`` 是对 flat 字段按 ``floor_id``
        的分区：每个 Window/Seat 在 ``__init__`` 时被赋了整数 ``floor_id``，
        分别归入对应楼层；学生中"等座"状态因不绑定楼层用 ``floor_id=None``，
        因此除等座学生外，flat 与 ``sum(floors[].*)`` 形成完整分区，不应丢失或重复。
        """
        flat_windows = [
            {
                "id": w.id,
                "floor_id": w.floor_id,
                "queue_length": w.queue_length,
                "is_serving": w.current_serving is not None,
                "total_served": w.total_served,
            }
            for w in self.windows
        ]
        flat_seats = [
            {
                "id": s.id,
                "floor_id": s.floor_id,
                # status 沿用 Phase 2 语义："occupied" / "empty"，不要写 "free"
                "status": "occupied" if s.student else "empty",
                "remaining_time": max(0, s.eat_end_time - self.env.now),
            }
            for s in self.seats
        ]

        students = []
        for w in self.windows:
            for idx, s in enumerate(w.waiting_students):
                students.append({
                    "id": s.id, "position": "window_queue",
                    "position_detail": w.id, "queue_index": idx,
                    "floor_id": w.floor_id,
                })
            if w.current_serving:
                students.append({
                    "id": w.current_serving.id, "position": "being_served",
                    "position_detail": w.id,
                    "floor_id": w.floor_id,
                })
        for idx, s in enumerate(self.seat_waiting_students):
            students.append({
                "id": s.id, "position": "waiting_queue", "position_detail": idx,
                "floor_id": None,   # 等座学生不绑定具体楼层
            })
        for seat in self.seats:
            if seat.student:
                students.append({
                    "id": seat.student.id, "position": "seated",
                    "position_detail": seat.id,
                    "floor_id": seat.floor_id,
                })

        # 嵌套形状：按 floor_id 分组
        # 不变量：每个 Window/Seat 都在 __init__ 时显式被赋了整数 floor_id；
        # 学生中"等座"状态因不绑定楼层用 None，因此不会被任何 floor 块收编。
        # flat[*] 与 sum(floors[].*) 形成完全分区（除等座学生外）。
        floors_block = []
        for meta in self.floors_meta:
            fid = meta.floor_id
            floors_block.append({
                "floor_id": fid,
                "layout": meta.layout,
                "windows": [w for w in flat_windows if w["floor_id"] == fid],
                "seats": [s for s in flat_seats if s["floor_id"] == fid],
                "students": [
                    st for st in students
                    if st["floor_id"] == fid
                ],
            })

        return {
            "id": self.id,
            "display_name": self.display_name,
            "campus_position": self.campus_position,
            # === Phase 2 顶层统计字段（前端 updateInfoPanel 直接读） ===
            "current_time": self.env.now,
            "total_arrived": self.total_arrived,
            "total_served": self.total_served,
            "total_in_queue": (
                sum(w.queue_length for w in self.windows) + self.seat_waiting_count
            ),
            "total_eating": sum(1 for s in self.seats if s.student is not None),
            "empty_seats": sum(1 for s in self.seats if s.student is None),
            # avg_waiting_time 占位值；A.5.1 加 CampusStats 后由 Coordinator
            # 在 campus snapshot 里替换为按食堂分组的均值。Canteen 自身不维护等待时间序列。
            "avg_waiting_time": 0.0,
            # === flat 形状（Phase 2 兼容） ===
            "windows": flat_windows,
            "seats": flat_seats,
            "students": students,
            "waiting_queue_length": self.seat_waiting_count,
            # === 嵌套形状（v1.3 新增） ===
            "floors": floors_block,
        }
