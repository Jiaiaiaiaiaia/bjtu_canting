"""SimulationEngine 兼容门面。

Phase 2 对外仍暴露 ``SimulationEngine(config, config_id=None, rng_seed=None)``，
内部改为用单食堂 ``CampusCoordinator`` 跑 SimPy 生命周期。API 和前端需要的
字段保持 Phase 2 形状。
"""

import simpy
from simpy.core import EmptySchedule

from .coordinator import CampusCoordinator
from .random_streams import build_random_streams
from .student import Student
from .student_trace import build_single_canteen_traces


class SimulationEngine:
    """单食堂模式兼容门面。"""

    SINGLE_CANTEEN_ID = "single"

    def __init__(self, config, config_id=None, rng_seed=None):
        self.config = config
        self.config_id = config_id
        self.total_time = float(config["total_time"]) * 60
        self._streams = build_random_streams(rng_seed)
        self._rng = self._streams.routing
        self._env = simpy.Environment()
        self._planned_students: list[Student] = []
        self._student_traces = build_single_canteen_traces(config, self._streams)
        self.coordinator = CampusCoordinator(
            self._env,
            self._to_single_canteen_config(config),
            self._rng,
            random_streams=self._streams,
        )
        self._canteen = self.coordinator.canteens[self.SINGLE_CANTEEN_ID]

        self.windows = self._canteen.windows
        self.seats = self._canteen.seats
        self.waiting_queue = self._canteen.seat_waiting_students

        self.history = []
        self.peak_queue_length = 0
        self.peak_total_in_queue = 0
        self._is_started = False
        self._is_ended = False

    # ------------------------------------------------------------------ 兼容属性
    @property
    def students(self):
        """Phase 2 兼容：start() 后暴露可索引的真实 Student 对象列表。"""
        return self._planned_students if self._is_started else []

    @property
    def event_queue(self):
        """Phase 2 兼容：暴露 SimPy 待调度事件，避免旧代码拿到 None 占位。"""
        if not self._is_started or self._is_ended:
            return []
        # SimPy 4.x Environment._queue item shape is (time, priority, eid, event).
        # Keep this small private-field bridge only for the old Phase 2 event_queue contract.
        return [item[3] for item in self._env._queue]

    @property
    def current_time(self):
        return self._env.now

    @property
    def total_arrived(self):
        return self.coordinator.total_arrived

    @property
    def total_served(self):
        return self.coordinator.total_served

    # ------------------------------------------------------------------ 配置转换
    def _to_single_canteen_config(self, config):
        """把 Phase 2 六字段配置转成校园模式的单食堂配置。"""
        total_minutes = float(config["total_time"])
        arrival_rate = float(config["arrival_rate"])
        # ArrivalGenerator 使用 N * alpha * coverage / T；这里取 alpha=coverage=1。
        total_students = max(arrival_rate * total_minutes, 1.0)
        return {
            "canteens": [{
                "id": self.SINGLE_CANTEEN_ID,
                "display_name": "单食堂",
                "campus_position": {"x": 0, "y": 0},
                "avg_serve_time_seconds": float(config["avg_serve_time"]),
                "avg_eat_time_minutes": float(config["avg_eat_time"]),
                "arrival_weight": 1.0,
                "typical_wait_seconds": 0.0,
                "floors": [{
                    "floor_id": 1,
                    "windows": {
                        "physical_count": int(config["window_count"]),
                        "active_count": int(config["window_count"]),
                    },
                    "seats": {"count": int(config["seat_count"])},
                }],
            }],
            "campus": {
                "total_students": total_students,
                "lunch_alpha": 1.0,
                "coverage": 1.0,
                "peak_window_minutes": total_minutes,
                "peak_beta": 1.0,
                "simulation_seconds": self.total_time,
                "entrance_position": {"x": 0, "y": 0},
                "walking_speed_mps": 1.4,
                "walking_time_seconds": {},
                "entrance_walk_seconds": {self.SINGLE_CANTEEN_ID: 0.0},
                "_planned_students": self._planned_students,
                "_student_traces": self._student_traces,
            },
            "router": {
                "information_mode": "local_estimate",
                "patience_mean_seconds": 180.0,
                "patience_std_seconds": 60.0,
                "patience_min_seconds": 30.0,
                "switch_improvement_ratio": 1.3,
                "max_switches_per_student": 0,
                "rng_seed": 42,
            },
        }

    # ------------------------------------------------------------------ 启动与推进
    def start(self):
        if self._is_started:
            return
        self._is_started = True
        if self._student_traces:
            planned_count = len(self._student_traces)
        else:
            planned_count = max(
                1,
                int(float(self.config["arrival_rate"]) * float(self.config["total_time"]) * 3) + 100,
            )
        if not self._planned_students:
            self._planned_students.extend(
                Student(id=i, state="arriving")
                for i in range(planned_count)
            )

    def step(self):
        if not self._is_started:
            self.start()
        if self._is_ended:
            return self._build_state("end", is_ended=True)

        before = self._semantic_metrics()
        after, is_ended = self._advance_until_visible_change(before)
        event_type = self._infer_event_type(before, after, is_ended)
        state = self._build_state(event_type, is_ended=is_ended)
        self.history.append(self._compact_snapshot(state))
        if is_ended:
            self._is_ended = True
        return state

    def _advance_until_visible_change(self, before):
        """把多个 SimPy 微事件合并成一个 Phase 2 语义 step。

        SimPy 会把 process 启动、timeout(0)、resource grant 等拆成多个内部事件；
        前端和旧 API 需要的是 arrival / service_end / eat_end 这种可见状态变化。
        """
        try:
            while True:
                self._env.step()
                after = self._semantic_metrics()
                if after != before:
                    self._drain_current_time_micro_events()
                    return self._semantic_metrics(), self._env.peek() == float("inf")
                if self._env.peek() == float("inf"):
                    return after, True
        except EmptySchedule:
            return self._semantic_metrics(), True

    def _drain_current_time_micro_events(self):
        """消化同一时间戳上的零时长内部事件，让状态停在稳定可渲染点。"""
        current = self.current_time
        while self._env.peek() == current:
            try:
                self._env.step()
            except EmptySchedule:
                break

    def _semantic_metrics(self):
        snap = self._canteen.snapshot()
        return {
            "total_arrived": self.total_arrived,
            "total_served": self.total_served,
            "total_in_queue": snap["total_in_queue"],
            "total_eating": snap["total_eating"],
            "empty_seats": snap["empty_seats"],
            "window_served": tuple(w.total_served for w in self.windows),
            "students": tuple(
                (s["id"], s["position"], s["position_detail"])
                for s in snap["students"]
            ),
        }

    def _infer_event_type(self, before, after, is_ended):
        if after["total_served"] > before["total_served"]:
            return "eat_end"
        if (
            sum(after["window_served"]) > sum(before["window_served"])
            or after["total_eating"] != before["total_eating"]
            or after["empty_seats"] != before["empty_seats"]
        ):
            return "service_end"
        if after["total_arrived"] > before["total_arrived"]:
            return "arrival"
        if is_ended:
            return "end"
        return "step"

    # ------------------------------------------------------------------ 状态与快照
    def _build_state(self, event_type, is_ended=False):
        snap = self._canteen.snapshot()
        student_by_id = {s.id: s for s in self.coordinator.all_students}

        students_payload = []
        for item in snap["students"]:
            student = student_by_id.get(item["id"])
            position = item["position"]
            position_detail = item["position_detail"]
            students_payload.append({
                "id": item["id"],
                "arrival_time": student.arrived_at if student else None,
                "position": position,
                "position_detail": position_detail,
                "window_id": position_detail if position in ("window_queue", "being_served") else None,
                "seat_id": position_detail if position == "seated" else None,
            })

        windows_payload = [{
            "id": w.id,
            "queue_length": w.queue_length,
            "is_serving": w.current_serving is not None,
            "total_served": w.total_served,
            "current_student_id": w.current_serving.id if w.current_serving else None,
        } for w in self.windows]

        seats_payload = [{
            "id": s.id,
            "status": s.status,
            "remaining_time": max(0.0, s.eat_end_time - self.current_time) if s.student else 0,
            "student_id": s.student.id if s.student else None,
        } for s in self.seats]

        total_in_queue = snap["total_in_queue"]
        self.peak_total_in_queue = max(self.peak_total_in_queue, total_in_queue)
        self.peak_queue_length = max(
            self.peak_queue_length,
            max((w.queue_length for w in self.windows), default=0),
        )

        return {
            "is_ended": is_ended,
            "event_type": event_type,
            "current_time": self.current_time,
            "total_time": self.total_time,
            "total_arrived": self.total_arrived,
            "total_served": self.total_served,
            "total_in_queue": total_in_queue,
            "total_eating": snap["total_eating"],
            "empty_seats": snap["empty_seats"],
            "avg_waiting_time": self.coordinator.stats.avg_waiting_time(),
            "waiting_queue_length": snap["waiting_queue_length"],
            "windows": windows_payload,
            "seats": seats_payload,
            "students": students_payload,
        }

    def _compact_snapshot(self, state):
        queue_details = [{
            "window_id": w.id,
            "queue_length": w.queue_length,
            "total_served": w.total_served,
        } for w in self.windows]
        return {
            "config_id": self.config_id,
            "current_time": state["current_time"],
            "total_arrived": state["total_arrived"],
            "total_served": state["total_served"],
            "total_in_queue": state["total_in_queue"],
            "total_eating": state["total_eating"],
            "empty_seats": state["empty_seats"],
            "queue_details": queue_details,
            "event_type": state["event_type"],
        }

    # ------------------------------------------------------------------ 统计
    def get_statistics(self):
        served = [s for s in self.coordinator.all_students if s.state == "left"]
        waiting_times = [s.wait_time for s in served]
        service_times = [s.service_time for s in served]
        eating_times = [s.eat_time for s in served]

        avg_waiting = sum(waiting_times) / len(waiting_times) if waiting_times else 0
        avg_service = sum(service_times) / len(service_times) if service_times else 0
        avg_eating = sum(eating_times) / len(eating_times) if eating_times else 0

        effective_time = max(self.total_time, self.current_time)
        total_seat_time = self.config["seat_count"] * effective_time
        used_seat_time = sum(eating_times)
        seat_utilization = (used_seat_time / total_seat_time * 100) if total_seat_time > 0 else 0

        return {
            "total_arrived": self.total_arrived,
            "total_served": self.total_served,
            "avg_waiting_time": avg_waiting,
            "avg_service_time": avg_service,
            "avg_eating_time": avg_eating,
            "window_served": [w.total_served for w in self.windows],
            "seat_utilization": seat_utilization,
            "peak_queue_length": self.peak_total_in_queue,
            "queue_timeline": self._aggregate_timeline("total_in_queue"),
            "seat_util_timeline": self._aggregate_timeline(
                "total_eating",
                normalize=self.config["seat_count"],
            ),
        }

    def _aggregate_timeline(self, field, normalize=None):
        """按分钟采样的时间序列：覆盖全部仿真过程。"""
        if not self.history:
            return {"x": [], "y": []}
        effective_time = max(self.total_time, self.history[-1]["current_time"])
        total_minutes = max(1, int(effective_time // 60) + 1)
        buckets = [None] * total_minutes
        for snap in self.history:
            minute = min(total_minutes - 1, int(snap["current_time"] // 60))
            value = snap[field]
            if normalize:
                value = value / normalize * 100
            buckets[minute] = value
        last = 0
        xs, ys = [], []
        for i, v in enumerate(buckets):
            if v is None:
                v = last
            else:
                last = v
            xs.append(i)
            ys.append(round(v, 2))
        return {"x": xs, "y": ys}
