"""Campus 拓扑（spec §2.8）：入口 / 食堂坐标 / 步行时间矩阵 / 在路上学生进度。

纯查找/计算工具，不持有 SimPy 资源。后续 A.7.1 lifecycle 与 A.8.1 Coordinator 都会依赖它。
"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .canteen import Canteen
    from .student import Student


class Campus:
    """封装校园拓扑：入口位置、食堂坐标、步行时间矩阵、在路上学生进度。"""

    def __init__(self, campus_config: dict, canteens: dict):
        self.config = campus_config
        self.canteens = canteens
        self.entrance_pos = campus_config["entrance_position"]
        self.walking_speed = campus_config.get("walking_speed_mps", 1.4)  # 1.4 m/s ≈ 普通步行速度
        self._matrix = campus_config.get("walking_time_seconds", {})
        self._entrance_walks = campus_config.get("entrance_walk_seconds", {})
        if self.walking_speed <= 0:
            raise ValueError("walking_speed_mps must be positive")

    def walking_time_from_entrance(self, canteen_id: str) -> float:
        """学生从校园入口走到指定食堂的时间（秒）。
        优先用预设手测值；缺失则按欧氏距离 / walking_speed 估算。
        """
        if canteen_id in self._entrance_walks:
            return self._entrance_walks[canteen_id]
        c = self.canteens[canteen_id]
        dx = c.campus_position["x"] - self.entrance_pos["x"]
        dy = c.campus_position["y"] - self.entrance_pos["y"]
        return ((dx * dx + dy * dy) ** 0.5) / self.walking_speed

    def walking_time(self, from_id: str, to_id: str) -> float:
        """两个食堂之间的步行时间（秒），对称。
        优先用预设手测值；缺失则按欧氏距离 / walking_speed 估算。
        """
        if from_id == to_id:
            return 0.0
        m = self._matrix.get(from_id, {})
        if to_id in m:
            return m[to_id]
        # 反向键查找（matrix 对称）
        m_rev = self._matrix.get(to_id, {})
        if from_id in m_rev:
            return m_rev[from_id]
        # Fallback：欧氏距离 / walking_speed
        a = self.canteens[from_id].campus_position
        b = self.canteens[to_id].campus_position
        dx = a["x"] - b["x"]
        dy = a["y"] - b["y"]
        return ((dx * dx + dy * dy) ** 0.5) / self.walking_speed

    def transit_progress(self, student: "Student", now: float) -> float:
        """学生当前走路完成度（0.0-1.0），给前端 3D 在路上插值用。
        在 student.state == 'walking' 或 'switching' 期间有意义。
        """
        if student.walking_start_time <= 0:
            return 0.0
        from_id = student.current_canteen_id
        to_id = student.target_canteen_id
        if to_id is None:
            raise ValueError("target_canteen_id is required while walking")
        if from_id is None:
            total = self.walking_time_from_entrance(to_id)
        else:
            total = self.walking_time(from_id, to_id)
        if total <= 0:
            return 1.0  # 零耗时路径视为已到达
        elapsed = now - student.walking_start_time
        return max(0.0, min(1.0, elapsed / total))
