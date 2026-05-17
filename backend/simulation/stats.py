"""CampusStats 聚合类（spec §2.10）。"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .student import Student


MAX_REPORTED_SEAT_UTILIZATION_PERCENT = 99.0


def reported_seat_utilization_percent(value: float) -> float:
    """Return a user-facing utilization percent without reporting perfect full use."""
    return min(MAX_REPORTED_SEAT_UTILIZATION_PERCENT, max(0.0, float(value)))


class CampusStats:
    """聚合"已完成学生"的关键指标，给 snapshot.campus_totals.avg_waiting_time 等用。

    设计原则：
    - 单一职责：仅做学生级指标聚合（wait/walk/switch_count）
    - 不反向读取 Canteen / Coordinator 状态；接收 Student 对象、读字段、append 到列表即可
    - switch_rate 分母用已记录完成样本数（_switch_counts 长度），不用当前在场人数
    """

    def __init__(self):
        self._wait_times: list[float] = []
        self._walk_times: list[float] = []
        self._switch_counts: list[int] = []

    def record_wait(self, student: "Student"):
        """student_lifecycle 在拿到资源 / 进入服务态时调用。"""
        self._wait_times.append(student.wait_time)

    def record_completion(self, student: "Student"):
        """student_lifecycle 在 'left' 态时调用，记录全过程指标。"""
        self._walk_times.append(student.walk_time)
        self._switch_counts.append(student.switch_count)

    def avg_waiting_time(self) -> float:
        if not self._wait_times:
            return 0.0
        return sum(self._wait_times) / len(self._wait_times)

    def avg_walk_time(self) -> float:
        if not self._walk_times:
            return 0.0
        return sum(self._walk_times) / len(self._walk_times)

    def switch_rate(self) -> float:
        """切换学生比例 = 至少切换 1 次的学生 / 总记录完成学生。"""
        if not self._switch_counts:
            return 0.0
        switched = sum(1 for c in self._switch_counts if c > 0)
        return switched / len(self._switch_counts)
