"""StudentRouter 决策模型（spec §2.7 / §4.2 / §4.4 / plan A.4.1）。

仅做决策，不修改学生状态：
- pick_initial：学生到达校园第一次选食堂（基于 weights × capacity / walk 软概率抽样）
- try_switch：学生超时后判断是否迁移、迁移到哪个食堂（返回 Canteen 或 None）
- sample_patience：从正态分布采样耐心阈值（带下限 clamp）

随机性统一用 random.Random（不引入 numpy）。
状态变更全部交给 student_lifecycle（A.7.1）做。
"""
import random
from dataclasses import dataclass
from typing import Literal, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .canteen import Canteen
    from .campus import Campus


@dataclass
class RouterConfig:
    information_mode: Literal["local_estimate", "live_congestion"] = "local_estimate"
    patience_mean_seconds: float = 180.0
    patience_std_seconds: float = 60.0
    patience_min_seconds: float = 30.0
    switch_improvement_ratio: float = 1.3
    max_switches_per_student: int = 2
    rng_seed: int = 42


class StudentRouter:
    def __init__(self, env, config: RouterConfig, campus: "Campus", rng: random.Random):
        self.env = env
        self.config = config
        self.campus = campus
        self.rng = rng

    def sample_patience(self) -> float:
        return max(
            self.config.patience_min_seconds,
            self.rng.gauss(
                self.config.patience_mean_seconds,
                self.config.patience_std_seconds,
            ),
        )

    def pick_initial(self, student, canteens: dict) -> "Canteen":
        """学生到达校园后第一次选食堂。

        不依赖其他食堂的实时队伍长度（与"刚到校园看不见食堂内部"的现实一致），
        基于"受欢迎程度 × 服务吞吐能力 / 步行成本"的软概率分布抽样。
        """
        canteen_list = list(canteens.values())
        weights = []
        for c in canteen_list:
            walk_min = max(1.0, self.campus.walking_time_from_entrance(c.id) / 60.0)
            capacity_score = c.active_window_count / c.avg_serve_time
            score = c.arrival_weight * capacity_score / walk_min
            weights.append(score)
        return self.rng.choices(canteen_list, weights=weights, k=1)[0]

    def try_switch(self, student, canteens: dict, exclude_id: str) -> Optional["Canteen"]:
        """学生超时后决定是否迁移、迁移到哪个食堂。

        返回新食堂或 None。返回 None 表示当前队伍硬等。
        """
        if student.switch_count >= self.config.max_switches_per_student:
            return None

        current = canteens[exclude_id]
        # 学生估算自己当前队伍剩余等待，而非该食堂最短队
        current_window = current.windows[student.current_window_id]
        current_est = current_window.estimated_wait_for(student)

        candidates = []
        for c in canteens.values():
            if c.id == exclude_id:
                continue
            walk = self.campus.walking_time(current.id, c.id)
            if self.config.information_mode == "live_congestion":
                # 演示模式：可解释为"校园 App 提供实时拥挤信息"
                # 学生看到的是该食堂最短窗口的队伍长度和服务时间，与 spec §2.7 一致。
                target_window = c.shortest_window()
                est_wait = target_window.queue_load * c.avg_serve_time
            else:  # "local_estimate"
                # 学生靠经验/口碑估，不依赖其他食堂的 live 状态
                est_wait = c.typical_wait_seconds
            candidates.append((c, walk + est_wait))

        if not candidates:
            return None
        candidates.sort(key=lambda x: x[1])
        best, best_cost = candidates[0]

        # 仅当当前队伍剩余等待 > 候选总耗时 × switch_improvement_ratio 才换
        if best_cost * self.config.switch_improvement_ratio < current_est:
            return best
        return None
