"""仿真驱动模块 —— 离散事件驱动核心。

事件类型：
  - arrival: 学生到达食堂
  - service_end: 窗口打饭完成
  - eat_end: 学生就餐完成并离场
"""
import heapq
import random

from .queue_sim import Window, pick_shortest_window, sample_serve_time
from .dining_sim import Seat, pick_nearest_seat, sample_eat_time


class Student:
    def __init__(self, student_id, arrival_time):
        self.id = student_id
        self.arrival_time = arrival_time
        self.start_service_time = None
        self.end_service_time = None
        self.start_eat_time = None
        self.end_eat_time = None
        self.window_id = None
        self.seat_id = None


class Event:
    __slots__ = ('event_time', 'seq', 'event_type', 'student', 'window', 'seat')

    def __init__(self, event_time, seq, event_type, student=None, window=None, seat=None):
        self.event_time = event_time
        self.seq = seq
        self.event_type = event_type
        self.student = student
        self.window = window
        self.seat = seat

    def __lt__(self, other):
        if self.event_time != other.event_time:
            return self.event_time < other.event_time
        return self.seq < other.seq


class SimulationEngine:
    """离散事件驱动的就餐仿真核心。"""

    def __init__(self, config, config_id=None, rng_seed=None):
        if rng_seed is not None:
            random.seed(rng_seed)

        self.config = config
        self.config_id = config_id
        self.total_time = float(config['total_time']) * 60  # 秒

        self.windows = [Window(i, config['avg_serve_time']) for i in range(config['window_count'])]
        self.seats = [Seat(i) for i in range(config['seat_count'])]
        self.students = []
        self.waiting_queue = []

        self.event_queue = []
        self._seq = 0

        self.current_time = 0.0
        self.total_arrived = 0
        self.total_served = 0
        self.peak_queue_length = 0
        self.peak_total_in_queue = 0

        self.history = []  # 逐事件快照（内存）
        self._is_started = False
        self._is_ended = False

    # ------------------------------------------------------------------ 启动
    def start(self):
        if self._is_started:
            return
        self._is_started = True
        self._generate_arrival_events()

    def _push(self, event_time, event_type, **kwargs):
        self._seq += 1
        heapq.heappush(self.event_queue, Event(event_time, self._seq, event_type, **kwargs))

    def _generate_arrival_events(self):
        """基于泊松过程（到达间隔服从指数分布）预生成所有到达事件。

        注意：这里只分配学生 ID 并排入事件队列，不增加 total_arrived。
        total_arrived 代表"截至 current_time 已经到达的人数"，在 _handle_arrival 里累加。
        """
        rate_per_second = self.config['arrival_rate'] / 60.0
        t = 0.0
        next_id = 0
        while True:
            inter = random.expovariate(rate_per_second) if rate_per_second > 0 else float('inf')
            t += inter
            if t >= self.total_time:
                break
            next_id += 1
            student = Student(next_id, t)
            self.students.append(student)
            self._push(t, 'arrival', student=student)

    # ------------------------------------------------------------------ 单步推进
    def step(self):
        if self._is_ended or not self.event_queue:
            self._is_ended = True
            return self._build_state('end', is_ended=True)

        event = heapq.heappop(self.event_queue)
        self.current_time = event.event_time

        if event.event_type == 'arrival':
            self._handle_arrival(event.student)
        elif event.event_type == 'service_end':
            self._handle_service_end(event.student, event.window)
        elif event.event_type == 'eat_end':
            self._handle_eat_end(event.student, event.seat)

        self._update_peaks()
        is_ended = self._check_end_condition()
        state = self._build_state(event.event_type, is_ended=is_ended)
        self.history.append(self._compact_snapshot(event.event_type))
        if is_ended:
            self._is_ended = True
        return state

    # ------------------------------------------------------------------ 事件处理
    def _handle_arrival(self, student):
        self.total_arrived += 1
        window = pick_shortest_window(self.windows)
        student.window_id = window.id
        if window.current_serving is None:
            self._start_serving(student, window)
        else:
            window.queue.append(student)

    def _start_serving(self, student, window):
        window.current_serving = student
        student.start_service_time = self.current_time
        serve_time = sample_serve_time(window.avg_serve_time)
        self._push(self.current_time + serve_time, 'service_end', student=student, window=window)

    def _handle_service_end(self, student, window):
        window.current_serving = None
        window.total_served += 1
        student.end_service_time = self.current_time

        # 队列下一个继续打饭
        if window.queue:
            next_student = window.queue.pop(0)
            self._start_serving(next_student, window)

        # 已打饭学生找座位
        seat = pick_nearest_seat(self.seats, window.id, len(self.windows))
        if seat is not None:
            self._seat_student(student, seat)
        else:
            self.waiting_queue.append(student)

    def _seat_student(self, student, seat):
        seat.status = 'occupied'
        seat.student = student
        student.seat_id = seat.id
        student.start_eat_time = self.current_time
        eat_time = sample_eat_time(self.config['avg_eat_time'])
        seat.eat_end_time = self.current_time + eat_time
        self._push(seat.eat_end_time, 'eat_end', student=student, seat=seat)

    def _handle_eat_end(self, student, seat):
        seat.status = 'empty'
        seat.student = None
        seat.eat_end_time = None
        student.end_eat_time = self.current_time
        self.total_served += 1

        # 有等位学生则立即入座
        if self.waiting_queue:
            next_student = self.waiting_queue.pop(0)
            self._seat_student(next_student, seat)

    # ------------------------------------------------------------------ 状态与快照
    def _update_peaks(self):
        total_in_queue = sum(len(w.queue) for w in self.windows) + len(self.waiting_queue)
        self.peak_total_in_queue = max(self.peak_total_in_queue, total_in_queue)
        max_window_q = max((len(w.queue) for w in self.windows), default=0)
        self.peak_queue_length = max(self.peak_queue_length, max_window_q)

    def _check_end_condition(self):
        no_events = not self.event_queue
        if no_events:
            return True
        if self.current_time < self.total_time:
            return False
        all_seats_empty = all(s.status == 'empty' for s in self.seats)
        all_windows_clear = all(not w.queue and w.current_serving is None for w in self.windows)
        return all_seats_empty and all_windows_clear and not self.waiting_queue

    def _resolve_position(self, student):
        """推断学生当前位置，供前端渲染动画。"""
        for w in self.windows:
            if w.current_serving is student:
                return 'being_served', w.id
            if student in w.queue:
                return 'window_queue', w.id
        if student in self.waiting_queue:
            return 'waiting_queue', self.waiting_queue.index(student)
        if student.seat_id is not None and student.end_eat_time is None:
            return 'seated', student.seat_id
        if student.end_eat_time is not None:
            return 'left', None
        return 'unknown', None

    def _build_state(self, event_type, is_ended=False):
        students_payload = []
        for student in self.students:
            position, detail = self._resolve_position(student)
            if position == 'unknown' or (position == 'left' and student.end_eat_time is not None):
                # 减少已离场学生的传输量
                if position == 'left':
                    continue
                if position == 'unknown' and student.start_service_time is None and self.current_time < student.arrival_time:
                    continue
            students_payload.append({
                'id': student.id,
                'arrival_time': student.arrival_time,
                'position': position,
                'position_detail': detail,
                'window_id': student.window_id,
                'seat_id': student.seat_id,
            })

        total_in_queue = sum(len(w.queue) for w in self.windows) + len(self.waiting_queue)
        total_eating = sum(1 for s in self.seats if s.status == 'occupied')
        empty_seats = sum(1 for s in self.seats if s.status == 'empty')

        _served_rt = [s for s in self.students if s.start_service_time is not None]
        _wt = [s.start_service_time - s.arrival_time for s in _served_rt]
        _avg_waiting_rt = sum(_wt) / len(_wt) if _wt else 0.0

        return {
            'is_ended': is_ended,
            'event_type': event_type,
            'current_time': self.current_time,
            'total_time': self.total_time,
            'total_arrived': self.total_arrived,
            'total_served': self.total_served,
            'total_in_queue': total_in_queue,
            'total_eating': total_eating,
            'empty_seats': empty_seats,
            'avg_waiting_time': _avg_waiting_rt,
            'waiting_queue_length': len(self.waiting_queue),
            'windows': [{
                'id': w.id,
                'queue_length': len(w.queue),
                'is_serving': w.current_serving is not None,
                'total_served': w.total_served,
                'current_student_id': w.current_serving.id if w.current_serving else None,
            } for w in self.windows],
            'seats': [{
                'id': s.id,
                'status': s.status,
                'remaining_time': max(0.0, s.eat_end_time - self.current_time) if s.eat_end_time is not None else 0,
                'student_id': s.student.id if s.student else None,
            } for s in self.seats],
            'students': students_payload,
        }

    def _compact_snapshot(self, event_type):
        """写入数据库使用的精简快照。"""
        total_in_queue = sum(len(w.queue) for w in self.windows) + len(self.waiting_queue)
        total_eating = sum(1 for s in self.seats if s.status == 'occupied')
        empty_seats = sum(1 for s in self.seats if s.status == 'empty')
        queue_details = [{
            'window_id': w.id,
            'queue_length': len(w.queue),
            'total_served': w.total_served,
        } for w in self.windows]
        return {
            'config_id': self.config_id,
            'current_time': self.current_time,
            'total_arrived': self.total_arrived,
            'total_served': self.total_served,
            'total_in_queue': total_in_queue,
            'total_eating': total_eating,
            'empty_seats': empty_seats,
            'queue_details': queue_details,
            'event_type': event_type,
        }

    # ------------------------------------------------------------------ 统计
    def get_statistics(self):
        served = [s for s in self.students if s.end_eat_time is not None]

        waiting_times = [s.start_service_time - s.arrival_time for s in served if s.start_service_time is not None]
        service_times = [s.end_service_time - s.start_service_time for s in served
                         if s.start_service_time is not None and s.end_service_time is not None]
        eating_times = [s.end_eat_time - s.start_eat_time for s in served
                        if s.start_eat_time is not None and s.end_eat_time is not None]

        avg_waiting = sum(waiting_times) / len(waiting_times) if waiting_times else 0
        avg_service = sum(service_times) / len(service_times) if service_times else 0
        avg_eating = sum(eating_times) / len(eating_times) if eating_times else 0

        window_served = [w.total_served for w in self.windows]

        # 有效仿真时间 = max(配置时长, 实际结束时间)，因为学生可能在 total_time 后继续就餐
        effective_time = max(self.total_time, self.current_time)
        total_seat_time = self.config['seat_count'] * effective_time
        used_seat_time = sum(eating_times)
        seat_utilization = (used_seat_time / total_seat_time * 100) if total_seat_time > 0 else 0

        queue_timeline = self._aggregate_timeline('total_in_queue')
        seat_util_timeline = self._aggregate_timeline('total_eating', normalize=self.config['seat_count'])

        return {
            'total_arrived': self.total_arrived,
            'total_served': self.total_served,
            'avg_waiting_time': avg_waiting,
            'avg_service_time': avg_service,
            'avg_eating_time': avg_eating,
            'window_served': window_served,
            'seat_utilization': seat_utilization,
            'peak_queue_length': self.peak_total_in_queue,
            'queue_timeline': queue_timeline,
            'seat_util_timeline': seat_util_timeline,
        }

    def _aggregate_timeline(self, field, normalize=None):
        """按分钟采样的时间序列：覆盖全部仿真过程（含 total_time 之后的离场尾部）。"""
        if not self.history:
            return {'x': [], 'y': []}
        effective_time = max(self.total_time, self.history[-1]['current_time'])
        total_minutes = max(1, int(effective_time // 60) + 1)
        buckets = [None] * total_minutes
        for snap in self.history:
            minute = min(total_minutes - 1, int(snap['current_time'] // 60))
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
        return {'x': xs, 'y': ys}
