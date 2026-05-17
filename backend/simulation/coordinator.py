"""CampusCoordinator 校园协调器（spec §2.6）。

接 Canteen / Campus / Router / ArrivalGenerator / CampusStats / student_lifecycle，
为校园模式提供端到端骨架（共享时钟 + 钩子 + snapshot）。

SimulationEngine 单食堂兼容门面也会用只含一个 Canteen 的 CampusCoordinator。
"""
import random
import simpy
from typing import TYPE_CHECKING

from .canteen import Canteen
from .campus import Campus
from .router import RouterConfig, StudentRouter
from .stats import CampusStats
from .arrival_generator import ArrivalGenerator
from .student import Student

if TYPE_CHECKING:
    pass


class CampusCoordinator:
    """管理 N 个 Canteen + 调度共享时钟；N=1 时服务单食堂兼容门面。"""

    def __init__(
        self,
        env: simpy.Environment,
        config: dict,
        rng: random.Random,
        random_streams=None,
    ):
        self.env = env
        self.canteens: dict[str, Canteen] = {
            d["id"]: Canteen(env, d) for d in config["canteens"]
        }
        self.campus = Campus(config["campus"], self.canteens)
        self.routing_rng = random_streams.routing if random_streams is not None else rng
        self.arrival_rng = random_streams.arrival if random_streams is not None else rng
        self.service_rng = random_streams.service if random_streams is not None else None
        self.eat_rng = random_streams.eat if random_streams is not None else None
        # config["router"] 是来自 JSON 的 dict，转成 dataclass 再传给 Router
        router_cfg = RouterConfig(**config["router"])
        self.router = StudentRouter(env, router_cfg, self.campus, self.routing_rng)
        self.stats = CampusStats()
        self.arrival_generator = ArrivalGenerator(
            env, config["campus"], self.canteens, self.router,
            self.campus, self, self.arrival_rng
        )

        # 校园级累计：不依赖 sum(canteen.total_arrived)。
        # sum(canteen.total_arrived) 与 self.total_arrived 之间存在两类差异：
        #   (a) 在路上的学生已"到达校园"但尚未到达任何食堂；
        #   (b) 跨食堂迁移会让一名学生在多个 canteen.total_arrived 上各 +1，
        #       即 sum 值会因切换次数而高估。
        self.all_students: list[Student] = []
        self.transit_students: list[Student] = []
        self.total_arrived: int = 0
        self.total_served: int = 0

        # E2：窗口开关运行时干预流水；每次 toggle_window 尝试（applied/rejected）
        # 都追加一条事件，snapshot() 透出，E3 落库。
        self.interventions: list = []

    def on_student_arrived(self, student: Student):
        self.total_arrived += 1
        self.all_students.append(student)

    def on_student_walking_start(self, student: Student):
        self.transit_students.append(student)
        student.walking_start_time = self.env.now      # 给 Campus.transit_progress 用

    def on_student_walking_end(self, student: Student):
        if student in self.transit_students:
            self.transit_students.remove(student)
        student.walking_start_time = 0.0

    def on_student_left(self, student: Student):
        self.total_served += 1

    def toggle_window(self, canteen_id: str, window_id: int, open: bool) -> dict:
        c = self.canteens[canteen_id]
        w = next((w for w in c.windows if w.id == window_id), None)
        if w is None:
            ev = {"time": self.env.now, "canteen_id": canteen_id,
                  "floor_id": None, "window_id": window_id,
                  "action": "open" if open else "close",
                  "status": "rejected", "reason": "unknown window"}
            self.interventions.append(ev); return ev
        if not open and w.is_open and c.open_window_count <= 1:
            ev = {"time": self.env.now, "canteen_id": canteen_id,
                  "floor_id": w.floor_id, "window_id": window_id,
                  "action": "close", "status": "rejected",
                  "reason": "cannot close last open window"}
            self.interventions.append(ev); return ev
        w.is_open = bool(open)   # idempotent: 同态重复无副作用
        ev = {"time": self.env.now, "canteen_id": canteen_id,
              "floor_id": w.floor_id, "window_id": window_id,
              "action": "open" if open else "close", "status": "applied"}
        self.interventions.append(ev); return ev

    def advance(self, display_tick_seconds: float):
        """推进仿真时间。前端 /api/campus/step 按展示时间片调用。"""
        target_time = self.env.now + display_tick_seconds
        self.env.run(until=target_time)

    def _campus_total_in_queue(self) -> int:
        """校园级排队总数 = 各食堂窗口排队 + 各食堂等座队列。
        与 Phase 2 单食堂 total_in_queue 同口径。
        """
        total = 0
        for c in self.canteens.values():
            total += sum(w.queue_length for w in c.windows)
            total += c.seat_waiting_count
        return total

    def snapshot(self) -> dict:
        all_canteens = list(self.canteens.values())
        return {
            "current_time": self.env.now,
            "mode": "campus",
            "canteens": {cid: c.snapshot() for cid, c in self.canteens.items()},
            "canteen_order": list(self.canteens.keys()),
            "in_transit": [
                {
                    "id": s.id,
                    "from_canteen_id": s.current_canteen_id,
                    "to_canteen_id": s.target_canteen_id,
                    "progress": self.campus.transit_progress(s, self.env.now),
                }
                for s in self.transit_students
            ],
            "campus_totals": {
                "total_arrived": self.total_arrived,
                "total_served": self.total_served,
                "total_in_transit": len(self.transit_students),
                "total_switches": sum(s.switch_count for s in self.all_students),
                "total_in_queue": self._campus_total_in_queue(),
                "total_eating": sum(
                    1 for c in all_canteens for s in c.seats if s.student is not None
                ),
                "empty_seats": sum(
                    1 for c in all_canteens for s in c.seats if s.student is None
                ),
                "avg_waiting_time": self.stats.avg_waiting_time(),
                "avg_walk_time": self.stats.avg_walk_time(),
                "switch_rate": self.stats.switch_rate(),
            },
            "interventions": list(self.interventions),
        }
