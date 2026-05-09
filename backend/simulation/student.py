"""Student dataclass（spec §2.4）。lifecycle 函数留待 A.7.1 实现。"""
from dataclasses import dataclass
from typing import Literal, Optional


@dataclass
class Student:
    id: int
    state: Literal[
        "arriving", "walking", "queueing", "switching",
        "serving", "waiting_seat", "eating", "left"
    ]
    current_canteen_id: Optional[str] = None
    current_window_id: Optional[int] = None
    target_canteen_id: Optional[str] = None
    arrived_at: float = 0.0
    walk_time: float = 0.0
    wait_time: float = 0.0
    service_time: float = 0.0
    eat_time: float = 0.0
    switch_count: int = 0
    patience_threshold: float = 180.0   # 创建时按正态分布采样覆盖
    walking_start_time: float = 0.0     # Coordinator 维护，给 Campus.transit_progress 用
