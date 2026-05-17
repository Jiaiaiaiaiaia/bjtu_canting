"""Window / Seat / FloorMeta dataclass + Canteen 类（spec §2.3）。"""
import random
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
    is_open: bool = True                              # B1：物理窗口可被关停，关停后不再分流新学生

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

    STAIR_TRAVEL_SECONDS_PER_FLOOR = 12.0

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

            # B1：实例化全部 physical_count 窗口；前 active_count 个初始开放，
            # 其余初始关停（is_open=False）。关停窗口不参与 shortest_window 分流，
            # 但 SimPy 资源仍在，已排队学生自然 drain。
            phys = wdef.get("physical_count", wdef.get("active_count", 0))
            act = wdef.get("active_count", 0)
            for k in range(phys):
                self.windows.append(Window(
                    id=next_window_id,
                    floor_id=fid,
                    canteen_avg_serve_time=floor_serve_time,
                    resource=simpy.Resource(env, capacity=1),
                    is_open=(k < act),
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

        # 座位资源池：FilterStore 保持 Store 兼容，同时支持同楼层优先取座。
        self.seat_pool = simpy.FilterStore(env)
        for s in self.seats:
            self.seat_pool.put(s)

        # 等座可视化/统计：与 Window.waiting_students 同模式
        self.seat_waiting_students: list = []
        self.floor_transit_students: list = []

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

    @property
    def open_window_count(self) -> int:
        return sum(1 for w in self.windows if w.is_open)

    @property
    def open_window_capacity_score(self) -> float:
        return sum(1.0 / w.canteen_avg_serve_time
                   for w in self.windows if w.is_open)

    def add_window(self, floor_id: int) -> Window:
        """运行时向指定楼层添加一个开放服务窗口。"""
        try:
            floor_id = int(floor_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid floor_id: {floor_id!r}") from exc

        meta = next(
            (floor for floor in self.floors_meta if floor.floor_id == floor_id),
            None,
        )
        if meta is None:
            raise ValueError(f"unknown floor_id: {floor_id!r}")

        floor_windows = [w for w in self.windows if w.floor_id == floor_id]
        floor_serve_time = (
            floor_windows[-1].canteen_avg_serve_time
            if floor_windows else self.avg_serve_time
        )
        next_window_id = max((w.id for w in self.windows), default=-1) + 1
        window = Window(
            id=next_window_id,
            floor_id=floor_id,
            canteen_avg_serve_time=floor_serve_time,
            resource=simpy.Resource(self.env, capacity=1),
            is_open=True,
        )
        self.windows.append(window)
        self.physical_window_count += 1
        self.active_window_count += 1
        self._append_runtime_window_position(meta)
        return window

    def _append_runtime_window_position(self, meta: FloorMeta) -> None:
        layout = meta.layout if isinstance(meta.layout, dict) else {}
        positions = layout.get("window_positions")
        if not isinstance(positions, list) or not positions:
            return
        step = 4
        if len(positions) >= 2:
            step = positions[-1][0] - positions[-2][0]
        last_x, last_y = positions[-1]
        positions.append([last_x + step, last_y])

    def _open_windows(self) -> list[Window]:
        # B1：只在开放窗口中选；关停窗口不接收新学生（已排队的自然 drain）。
        open_windows = [w for w in self.windows if w.is_open]
        if not open_windows:
            raise RuntimeError(f"Canteen {self.id!r}: no open window")
        return open_windows

    def shortest_window(self) -> Window:
        return min(self._open_windows(), key=lambda w: w.queue_load)

    def floor_ids_with_open_windows(self) -> list[int]:
        return sorted({w.floor_id for w in self._open_windows()})

    def _random_choice(self, items: list, rng=None):
        source = rng if rng is not None else random
        return source.choice(items)

    def choose_initial_floor(self, rng=None) -> int:
        """学生进入食堂后的初始楼层：在开放楼层中真随机抽样。"""
        floor_ids = self.floor_ids_with_open_windows()
        return self._random_choice(floor_ids, rng)

    def stair_travel_time(self, from_floor_id: int, target_floor_id: int) -> float:
        """同一食堂内通过楼梯换层的通行时间。"""
        return max(
            self.STAIR_TRAVEL_SECONDS_PER_FLOOR,
            abs(int(target_floor_id) - int(from_floor_id))
            * self.STAIR_TRAVEL_SECONDS_PER_FLOOR,
        )

    # 当前楼层总队列比其他楼层平均总队列长超过此阈值时，允许跨层路由。
    CROSS_FLOOR_QUEUE_THRESHOLD = 10

    def choose_window(self, rng=None, current_floor_id: Optional[int] = None) -> Window:
        """学生选窗口：优先同楼层，但当同楼层总队列比其他楼层明显更长时跨层路由。"""
        open_windows = self._open_windows()
        current_floor_windows = [
            w for w in open_windows
            if current_floor_id is not None and w.floor_id == current_floor_id
        ]
        if not current_floor_windows:
            return self._random_choice(open_windows, rng)

        # 按楼层分组，比较总队列长度
        other_floor_windows = [w for w in open_windows if w.floor_id != current_floor_id]
        if other_floor_windows:
            cur_total = sum(w.queue_length for w in current_floor_windows)
            # 其他楼层中队列最短的
            other_floors: dict = {}
            for w in other_floor_windows:
                other_floors.setdefault(w.floor_id, []).append(w)
            best_other_total = min(
                sum(w.queue_length for w in ws) for ws in other_floors.values()
            )
            if cur_total - best_other_total >= self.CROSS_FLOOR_QUEUE_THRESHOLD:
                # 路由到队列最短的那个楼层
                best_fid = min(
                    other_floors, key=lambda fid: sum(w.queue_length for w in other_floors[fid])
                )
                return self._random_choice(other_floors[best_fid], rng)

        return self._random_choice(current_floor_windows, rng)

    def start_floor_transfer(self, student: "Student", from_floor_id: int, target_floor_id: int):
        student.current_floor_id = from_floor_id
        student.target_floor_id = target_floor_id
        student.floor_switch_start_time = self.env.now
        student.floor_switch_duration = self.stair_travel_time(from_floor_id, target_floor_id)
        if student not in self.floor_transit_students:
            self.floor_transit_students.append(student)

    def finish_floor_transfer(self, student: "Student"):
        if student in self.floor_transit_students:
            self.floor_transit_students.remove(student)

    def join_seat_queue(self, student: "Student"):
        self.seat_waiting_students.append(student)

    def leave_seat_queue(self, student: "Student"):
        if student in self.seat_waiting_students:
            self.seat_waiting_students.remove(student)

    def get_seat_prefer_floor(self, floor_id: Optional[int]):
        """取座位：同楼层有空座时优先同楼层，否则换到任意可用楼层。"""
        if floor_id is not None and any(
            seat.floor_id == floor_id for seat in self.seat_pool.items
        ):
            return self.seat_pool.get(lambda seat: seat.floor_id == floor_id)
        return self.seat_pool.get()

    @property
    def seat_waiting_count(self) -> int:
        return len(self.seat_waiting_students)

    def snapshot(self) -> dict:
        """输出双形状：flat（Phase 2 兼容）+ 嵌套 floors[]（v1.3 新前端用）。

        ``floors[].windows / seats / students`` 是对 flat 字段按 ``floor_id``
        的分区：每个 Window/Seat 在 ``__init__`` 时被赋了整数 ``floor_id``，
        分别归入对应楼层；等座学生沿用刚服务的楼层，供前端显示在原楼层等座区。
        """
        flat_windows = [
            {
                "id": w.id,
                "floor_id": w.floor_id,
                "queue_length": w.queue_length,
                "is_serving": w.current_serving is not None,
                "total_served": w.total_served,
                "is_open": w.is_open,
                "closing": (not w.is_open) and (
                    w.queue_length > 0 or w.current_serving is not None
                ),
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
                "floor_id": s.current_floor_id,
            })
        for s in self.floor_transit_students:
            duration = max(0.001, getattr(s, "floor_switch_duration", 0.0) or 0.0)
            progress = min(
                1.0,
                max(0.0, (self.env.now - getattr(s, "floor_switch_start_time", self.env.now)) / duration),
            )
            students.append({
                "id": s.id,
                "position": "floor_switching",
                "position_detail": "stairs",
                "floor_id": s.current_floor_id,
                "from_floor_id": s.current_floor_id,
                "target_floor_id": s.target_floor_id,
                "floor_switch_progress": progress,
                "stair_step": min(7, int(progress * 8)),
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
        # 学生按当前窗口、等座楼层或座位楼层收编到对应 floor 块。
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
