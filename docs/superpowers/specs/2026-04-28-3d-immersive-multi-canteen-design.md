# 北京交通大学就餐仿真系统：多食堂联合仿真与沉浸式可视化扩展 — 技术方案设计文档

**项目**：北京交通大学就餐仿真系统
**阶段**：集成阶段 + 部署与总结阶段（基于 Phase 2 开发阶段成果的扩展）
**编制日期**：2026-04-28
**编制人**：朱思思（24281153，后端 / 小组长）
**协作组员**：宋嘉桐（24281139，前端）、贾文霞（24281131，配置与分析）

---

## 0. 文档导读

本文档描述在 Phase 2（开发阶段）已交付的"通用单食堂仿真系统"基础上，集成阶段与部署阶段计划进行的两类扩展：

1. **多食堂联合仿真**：从单一通用食堂扩展为北京交通大学主校区 4 个真实食堂的联合仿真，引入学生跨食堂迁移决策模型；
2. **沉浸式可视化**：在部署阶段将 2D Canvas 升级为 Three.js 3D 校园场景与食堂内部场景，提供 2D / 3D 双视图。

**Phase 2 交付物（开发阶段，2026-05-03 提交）不修改、不替换。** 本文档所述全部改动以"在已稳定单食堂内核基础上叠加新能力"的方式实施，对外保留单食堂模式与原 API 完全兼容，新增校园联合模式走独立 API 入口。

---

## 1. 系统总体架构

### 1.1 三层抽象

```
CampusCoordinator       校园协调器（新增）
        │
        ├─ Canteen #1   食堂实例（新增；封装单个食堂的仿真状态与资源）
        ├─ Canteen #2
        │   ...
        └─ Canteen #N

每个 Canteen 内部仍是 SimPy 进程式离散事件仿真
        │
        ├─ windows[]      每窗口独立 simpy.Resource(capacity=1)
        ├─ seat_pool      simpy.Store 管理座位资源
        └─ students       学生作为 simpy.Process（生成器）
```

### 1.2 两种运行模式

| 模式 | 行为 | API 入口 |
|---|---|---|
| 单食堂模式 | `Coordinator` 仅激活一个 `Canteen`；行为完全等价于 Phase 2 现状，对前端 / 数据库 / 测试零破坏 | `/api/config`、`/api/simulation/*`（保留） |
| 校园联合模式 | 所有 `Canteen` 共享同一仿真时钟；`StudentRouter` 在校园入口分流学生；学生在排队过程中可能跨食堂迁移 | `/api/campus/config`、`/api/campus/*`（新增） |

### 1.3 学生 lifecycle 两种模式对比

| 阶段 | 单食堂 | 校园联合 |
|---|---|---|
| 学生生成位置 | 食堂入口 | 校园入口（到达点） |
| 食堂选择 | 直接进入唯一食堂 | StudentRouter 按"距离 / 受欢迎度 / 服务能力"软概率分派 |
| 跨食堂迁移 | 不发生 | 排队超过个体耐心阈值时评估，满足条件即迁移 |
| 食堂内部窗口选择 | 最短队（Phase 2 已实现） | 最短队（Phase 2 算法不变） |
| 座位获取 | 等位队列直至有座 | 等位队列直至有座 |

### 1.4 技术选型变更说明

> 本阶段并非否定原 DES 模型，而是在 SimPy 的进程式 DES 框架下重构仿真内核，使多食堂资源竞争、学生个体决策和跨食堂移动过程能够统一建模。

以上句作为《集成阶段实训报告》"技术选型"章节的标准措辞。

---

## 2. 后端模块结构

### 2.1 文件布局

```
backend/
├── simulation/
│   ├── __init__.py
│   ├── engine.py            # SimulationEngine 兼容门面（类签名不变）
│   ├── env.py               # SimPy Environment 工厂、仿真时钟管理
│   ├── canteen.py           # Canteen 类、Window 类、Seat 类
│   ├── student.py           # Student 数据类、student_lifecycle 进程函数
│   ├── router.py            # StudentRouter 决策模型
│   ├── coordinator.py       # CampusCoordinator 校园协调器
│   ├── stats.py             # 统计指标采集（按 canteen_id 分组）
│   └── presets/             # 北交大食堂参数预设（JSON）
│       ├── xueyi.json
│       ├── xueer.json
│       └── ...
├── api/
│   ├── routes.py            # 已有 10 个接口保留
│   └── campus_routes.py     # 新增 /api/campus/* Blueprint
└── tests/
    ├── test_api.py                # Phase 2 已有，保留
    ├── test_engine.py             # Phase 2 已有，保留
    ├── test_dining_sim.py         # Phase 2 已有，保留
    ├── test_queue_sim.py          # Phase 2 已有，保留
    ├── test_simpy_canteen.py      # 新增
    ├── test_window.py             # 新增
    ├── test_router.py             # 新增
    ├── test_coordinator.py        # 新增
    ├── test_campus_api.py         # 新增
    └── test_db_migration.py       # 新增
```

### 2.2 兼容门面：`SimulationEngine` 保留

`backend/api/routes.py` 现状是 `from simulation import SimulationEngine`，前端通过 `/api/simulation/step` 强依赖返回的 `windows[] / seats[] / students[]` 形状。为保证 Phase 2 接口零变更：

- `SimulationEngine` 类签名不变：`start() / step() / get_statistics() / pause()` 等方法名与行为保持
- 内部实现改为包装一个仅含单个 `Canteen` 的 `Coordinator`
- 单元测试组中 Phase 2 现有的 39 条用例继续通过这个门面跑（不重命名测试文件、不迁移测试代码）

### 2.3 Canteen 与 Window

```python
@dataclass
class Window:
    id: int
    canteen_avg_serve_time: float            # 由 Canteen 注入，估值用
    resource: simpy.Resource                 # capacity=1，每窗口独立排队
    waiting_students: list["Student"] = field(default_factory=list)
    current_serving: Optional["Student"] = None
    total_served: int = 0

    @property
    def queue_length(self) -> int:
        return len(self.waiting_students)

    @property
    def queue_load(self) -> int:
        # 与 Phase 2 queue_sim.py:14 queue_load() 语义一致：
        # 正在打饭的学生也算压力。
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
```

```python
@dataclass
class Seat:
    id: int
    student: Optional["Student"] = None
    eat_end_time: float = 0.0  # 绝对时刻；前端按 current_time 算 remaining_time

class Canteen:
    def __init__(self, env: simpy.Environment, definition: dict):
        self.env = env
        self.id = definition["id"]
        self.display_name = definition["display_name"]
        self.campus_position = definition["campus_position"]
        self.active_window_count = definition["windows"]["active_count"]
        self.physical_window_count = definition["windows"]["physical_count"]
        self.avg_serve_time = definition["windows"]["avg_serve_time_seconds"]
        self.avg_eat_time = definition["avg_eat_time_minutes"] * 60.0  # 转为秒
        self.arrival_weight = definition["arrival_weight"]
        self.typical_wait_seconds = definition.get("typical_wait_seconds", 120.0)

        # 窗口资源：每窗口独立 Resource，便于按窗口统计
        self.windows = [
            Window(
                id=i,
                canteen_avg_serve_time=self.avg_serve_time,
                resource=simpy.Resource(env, capacity=1),
            )
            for i in range(self.active_window_count)
        ]

        # 座位：物理对象列表
        self.seats = [Seat(id=i) for i in range(definition["seats"]["count"])]

        # 座位资源池：simpy.Store 负责"谁抢到座位"的调度
        self.seat_pool = simpy.Store(env)
        for s in self.seats:
            self.seat_pool.put(s)

        # 等座可视化/统计：与 Window.waiting_students 同模式
        # SimPy Store.get_queue 里是 GetEvent，不是 Student 对象，
        # 前端要画"等座队列圆点"必须自己维护学生列表。
        self.seat_waiting_students: list["Student"] = []

        # 食堂级累计统计
        self.total_arrived: int = 0      # 进入本食堂的学生数（含切换进来的）
        self.total_served: int = 0       # 在本食堂吃完离开的学生数

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
        """输出兼容 Phase 2 前端的 windows/seats/students 形状。"""
        students = []
        for w in self.windows:
            for idx, s in enumerate(w.waiting_students):
                students.append({
                    "id": s.id, "position": "window_queue",
                    "position_detail": w.id, "queue_index": idx,
                })
            if w.current_serving:
                students.append({
                    "id": w.current_serving.id, "position": "being_served",
                    "position_detail": w.id,
                })
        for idx, s in enumerate(self.seat_waiting_students):
            students.append({
                "id": s.id, "position": "waiting_queue", "position_detail": idx,
            })
        for seat in self.seats:
            if seat.student:
                students.append({
                    "id": seat.student.id, "position": "seated",
                    "position_detail": seat.id,
                })
        return {
            "id": self.id,
            "display_name": self.display_name,
            "windows": [
                {
                    "id": w.id,
                    "queue_length": w.queue_length,
                    "is_serving": w.current_serving is not None,
                    "total_served": w.total_served,
                }
                for w in self.windows
            ],
            "seats": [
                {
                    "id": s.id,
                    "status": "occupied" if s.student else "free",
                    "remaining_time": max(0, s.eat_end_time - self.env.now),
                }
                for s in self.seats
            ],
            "students": students,
            "waiting_queue_length": self.seat_waiting_count,
            "campus_position": self.campus_position,
        }
```

### 2.4 Student 数据类

```python
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
    patience_threshold: float = 180.0  # 创建时按正态分布采样
```

显式存储所有状态字段，不依赖生成器隐式状态。

### 2.5 student_lifecycle 进程函数

```python
def student_lifecycle(env, student, router, canteens, campus, coordinator):
    """学生从到达校园到离开的完整生命周期。

    canteens 是 dict[str, Canteen]；本函数中一律使用 dict 取值或 .values() 迭代。
    """
    student.state = "arriving"
    student.arrived_at = env.now
    coordinator.on_student_arrived(student)

    # 1. 校园入口选食堂
    target = router.pick_initial(student, canteens)
    student.target_canteen_id = target.id
    student.state = "walking"
    walk = campus.walking_time_from_entrance(target.id)
    yield env.timeout(walk)
    student.walk_time += walk
    student.current_canteen_id = target.id
    canteens[target.id].total_arrived += 1

    # 2. 排队（含跨食堂迁移）
    queue_phase_total_wait = 0.0
    while True:
        canteen = canteens[student.current_canteen_id]
        window = canteen.shortest_window()
        student.current_window_id = window.id
        student.state = "queueing"

        # 顺序关键：先入队 waiting_students，再 request 资源。
        # 保证前端 waiting_students 索引顺序与 SimPy 内部 request 等待顺序一致。
        window.join_queue(student)

        try:
            with window.resource.request() as req:
                wait_start = env.now
                result = yield req | env.timeout(student.patience_threshold)

                if req not in result:
                    # 耐心超时
                    alt = router.try_switch(
                        student, canteens, exclude_id=canteen.id
                    )
                    if alt is not None:
                        # 迁移：仅在切换分支累计这段等待
                        window.leave_queue(student)
                        queue_phase_total_wait += env.now - wait_start
                        student.switch_count += 1
                        student.state = "switching"
                        walk = campus.walking_time(canteen.id, alt.id)
                        yield env.timeout(walk)
                        student.walk_time += walk
                        canteens[canteen.id].total_arrived  # 不变
                        student.current_canteen_id = alt.id
                        canteens[alt.id].total_arrived += 1
                        continue  # with 退出 → req 释放
                    # 没替代：硬等
                    yield req

                # 拿到资源（可能是首次 req 满足，也可能是硬等满足）
                queue_phase_total_wait += env.now - wait_start
                student.wait_time = queue_phase_total_wait

                window.start_serving(student)
                student.state = "serving"
                service_duration = sample_serve_time(canteen.avg_serve_time)
                try:
                    yield env.timeout(service_duration)
                    student.service_time = service_duration
                    window.finish_serving()
                except simpy.Interrupt:
                    # 第一版不会发生；预留给"窗口关停 / 学生退服务"等扩展。
                    raise
                finally:
                    if window.current_serving is student:
                        window.current_serving = None
        finally:
            # 异常路径兜底：leave_queue 是 idempotent，正常路径无副作用
            window.leave_queue(student)
        break

    # 3. 找座位 + 就餐
    canteen = canteens[student.current_canteen_id]
    student.state = "waiting_seat"
    canteen.join_seat_queue(student)

    try:
        seat = yield canteen.seat_pool.get()
        canteen.leave_seat_queue(student)
        seat.student = student
        student.state = "eating"
        eat_duration = sample_eat_time(canteen.avg_eat_time)
        seat.eat_end_time = env.now + eat_duration
        yield env.timeout(eat_duration)
        seat.student = None
        student.eat_time = eat_duration
        canteen.seat_pool.put(seat)
        student.state = "left"
        canteen.total_served += 1
        coordinator.on_student_left(student)
    finally:
        canteen.leave_seat_queue(student)  # 异常路径兜底
```

### 2.6 CampusCoordinator

```python
class CampusCoordinator:
    def __init__(self, env: simpy.Environment, config: dict, rng: random.Random):
        self.env = env
        self.canteens: dict[str, Canteen] = {
            d["id"]: Canteen(env, d) for d in config["canteens"]
        }
        self.campus = Campus(config["campus"], self.canteens)
        self.router = StudentRouter(env, config["router"], self.campus, rng)
        self.stats = CampusStats()

        # 校园级累计：不依赖 sum(canteen.total_arrived)，因为在路上的学生
        # 已经"到达校园"但尚未关联到任何食堂。
        self.all_students: list[Student] = []
        self.transit_students: list[Student] = []
        self.total_arrived: int = 0
        self.total_served: int = 0

    def on_student_arrived(self, student: Student):
        self.total_arrived += 1
        self.all_students.append(student)

    def on_student_left(self, student: Student):
        self.total_served += 1

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
            },
        }
```

### 2.7 StudentRouter

```python
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
    def __init__(self, env, config: RouterConfig, campus, rng: random.Random):
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

    def pick_initial(self, student, canteens: dict) -> Canteen:
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

    def try_switch(self, student, canteens: dict, exclude_id: str) -> Optional[Canteen]:
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
```

### 2.8 学生决策模型说明（写入实训报告）

> **学生跨食堂迁移采用基于个体耐心阈值与总耗时估算的决策模型。** 每个学生在创建时按正态分布采样耐心阈值，模拟群体差异。当排队等待超过该阈值，学生估算其他食堂的"走路时间 + 预期等待"——预期等待来源默认为"局部估计"模式（基于食堂调研得到的典型等待时间，模拟学生凭经验/口碑判断），可切换至"实时拥挤"模式（模拟校园 App 提供实时数据）作为对照。仅当当前队伍剩余等待 > 候选食堂总耗时 × switch_improvement_ratio（默认 1.3）时学生才迁移；同时设置每学生最大切换次数防止无意义振荡。该模型在不引入全知优化的前提下，能够再现"看到队太长就走"的现实行为，并为参数敏感度分析提供研究空间。

---

## 3. 实地调研与真实数据接入

### 3.1 食堂候选清单（待 2026-05-04 至 2026-05-05 实地核验）

主校区候选 4 个学生食堂，最终名称以现场为准：

```
1. 学一食堂（待核验）
2. 学二食堂（待核验）
3. 学苑食堂 / 学苑餐厅（待核验，名字以现场为准）
4. 思源食堂（待核验，或调研后确定的主校区学生主要去向）
```

**第一版排除**：
- 教职工食堂（学生流量低）
- 民族餐厅（饮食偏好约束需要扩展 Router 模型，第一版不涉及；如部署阶段有时间再加）

### 3.2 食堂参数预设字段（presets/&lt;canteen_id&gt;.json）

```json
{
  "id": "xueyi",
  "display_name": "学一食堂",
  "campus_position": {"x": 120, "y": 80},
  "floors": 1,
  "entrances": 2,
  "windows": {
    "physical_count": 12,
    "active_count": 8,
    "by_type": {"rice": 3, "noodle": 2, "specialty": 3},
    "avg_serve_time_seconds": 30,
    "service_time_notes": "测了普通窗 28s/人 与 最慢特色窗 45s/人，加权平均 30s"
  },
  "seats": {
    "count": 240,
    "layout_hint": "8x30 grid"
  },
  "peak_hours": [
    {"name": "lunch",  "start": "11:30", "end": "13:00", "intensity": 1.0},
    {"name": "dinner", "start": "17:00", "end": "19:00", "intensity": 0.7}
  ],
  "avg_eat_time_minutes": 15,
  "observed_peak_queue": 25,
  "arrival_weight": 1.0,
  "typical_wait_seconds": 300,
  "notes": "二楼座位本次先按一楼建模"
}
```

**字段语义**：

| 字段 | 含义 | 来源 |
|---|---|---|
| `windows.physical_count` | 现场可见的窗口总数（数标牌） | 调研记录 |
| `windows.active_count` | 高峰期实际开放窗口数 | 调研观察；**仿真使用此值** |
| `windows.avg_serve_time_seconds` | 平均服务时长（秒） | 调研：测 2 组（普通窗 5 人 + 最慢窗 5 人）加权 |
| `seats.count` | 座位估算总数 | 调研：数 1-2 排乘以排数 |
| `arrival_weight` | 学生初次选择的相对受欢迎度 | 由组内根据调研观察人流量经验确定，默认 1.0 |
| `typical_wait_seconds` | "凭印象/口碑"的典型等待时长 | 调研：观察当日中午高峰最长等待估算 |

进入 Coordinator 时统一转换：`avg_serve_time_seconds → avg_serve_time`（秒）、`avg_eat_time_minutes → avg_eat_time`（秒），与 Phase 2 旧字段语义对齐。

### 3.3 实地调研操作流程

每食堂约 20 分钟，4 食堂可在一个中午高峰期完成。建议时间：5/4-5/5 中午。

**采集项目**：

| 项目 | 方法 |
|---|---|
| `physical_window_count` | 拍墙上窗口标牌，数 |
| `active_window_count` | 12:00 现场目测开放数；**仿真用此值** |
| `avg_serve_time_seconds` | 用计时器测连续 5 个学生的服务间隔，普通窗 1 组、最慢窗 1 组，加权平均 |
| `seats.count` | 数 1-2 排桌椅，乘以排数；误差 ±20% 可接受 |
| `observed_peak_queue` | 12:15 拍 1 张全景照，回看数最长队人头 |
| 食堂间步行时间 | 手机记录步行秒数；4 食堂间共 6 对 |
| 平面图 / 标牌 / 菜单 | 拍照存档，作为 3D 场景设计参考 |

报告记录两个口径：仿真用 `active_count`，背景说明里写 `physical_count`，避免被问"现场 12 窗 vs 仿真 8 窗哪个对"。

### 3.4 BJTU 总人数 → 校园到达率换算

**全局参数**（写入 campus 配置）：

```text
λ_avg  = N × α × coverage / T          单位：人/分钟
λ_peak = λ_avg × β                     仅 12:00-12:30 等短时高峰使用
```

| 参数 | 含义 | 默认值 |
|---|---|---|
| N | 主校区在校学生总数 | 由组内提供（如 28000） |
| α | 食堂午餐覆盖率（在食堂吃午饭的比例） | 0.65（取自校园生活调查文献中位估计） |
| coverage | 本次建模 4 食堂在主校区学生食堂总流量中的占比 | 0.78（按调研结果定） |
| T | 午餐高峰窗口长度（分钟） | 90 |
| β | 短时峰值放大系数 | 1.5（仅作压力测试场景） |

**实训报告口径**：

> 校园平均到达率按 N × α × coverage / T 估算；峰值阶段使用 β 作为短时流强放大系数，用于模拟 12:00-12:30 等集中到达场景。

### 3.5 食堂间步行时间矩阵

**主方案**：手测，单位秒，存 `walking_time` 表（对称）。

**Fallback**：若某两食堂未测，按 `√((Δx)² + (Δy)²) / 1.4 m/s` 自动估算（1.4 m/s = 普通步速）。

代码层 `Campus.walking_time(a, b)` 先查表，缺失再计算。理由：校园路非直线，楼门、楼梯、人流影响实际感知时间。

---

## 4. API 接口

### 4.1 单食堂模式（保留 Phase 2 不变）

| Method | Path | 说明 |
|---|---|---|
| POST | `/api/config` | 提交单食堂参数配置 |
| POST | `/api/simulation/start` | 启动单食堂仿真 |
| GET  | `/api/simulation/step` | 单步推进 |
| GET  | `/api/simulation/status` | 查询当前状态（响应中新增 `mode` 字段） |
| POST | `/api/simulation/pause` | 暂停 |
| POST | `/api/simulation/finish` | 跑完剩余事件 |
| POST | `/api/simulation/reset` | 重置 |
| GET  | `/api/statistics` | 统计 |
| GET  | `/api/history/configs` | 历史配置列表 |
| GET  | `/api/history` | 历史快照查询 |

集成阶段唯一改动：`/api/config` 与 `/api/simulation/status` 响应增加 `"mode": "single"` 字段，便于前端做模式确认。

### 4.2 校园联合模式（新增 `/api/campus/*` Blueprint）

| Method | Path | 说明 |
|---|---|---|
| POST | `/api/campus/config` | 提交校园联合配置（含食堂列表 + 全局参数 + Router 配置） |
| POST | `/api/campus/start` | 启动联合仿真 |
| GET  | `/api/campus/step?display_tick_seconds=10` | 推进展示时间片，返回校园联合状态 |
| GET  | `/api/campus/status` | 查询当前状态 |
| POST | `/api/campus/finish` | 跑完剩余事件 |
| POST | `/api/campus/reset` | 重置 |
| GET  | `/api/campus/statistics` | 联合统计（每食堂分别 + 校园层面） |

`/api/campus/step` 与单食堂 `/api/simulation/step` 的关键区别：

> 校园模式下事件密度高（高峰期可达数百事件/分钟），逐事件返回不利于前端流畅渲染。`/api/campus/step` 按"展示时间片推进"——默认每次推进 10 秒仿真时间，返回该时刻的聚合状态；前端按 200-500 ms 一次轮询，本地用线性插值平滑学生位置变化。

### 4.3 校园联合 step 响应形状

```json
{
  "current_time": 1230.5,
  "mode": "campus",
  "canteens": {
    "xueyi": { "...": "Canteen.snapshot() 的输出，与 Phase 2 形状兼容" },
    "xueer": { "..." : "..." },
    "xueyuan": { "..." : "..." },
    "siyuan": { "..." : "..." }
  },
  "canteen_order": ["xueyi", "xueer", "xueyuan", "siyuan"],
  "in_transit": [
    {
      "id": 1023,
      "from_canteen_id": "xueyi",
      "to_canteen_id": "xueer",
      "progress": 0.42
    }
  ],
  "campus_totals": {
    "total_arrived": 875,
    "total_served": 643,
    "total_in_transit": 12,
    "total_switches": 38,
    "total_in_queue": 95,
    "total_eating": 124,
    "empty_seats": 432,
    "avg_waiting_time": 142.3
  }
}
```

### 4.4 会话状态统一管理

```python
# backend/api/routes.py
_session = {
    "mode": None,                 # "single" | "campus"
    "engine": None,               # SimulationEngine 兼容门面（单食堂模式）
    "coordinator": None,          # CampusCoordinator（校园模式）
    "config_id": None,
    "is_running": False,
    "snapshot_buffer": [],
}
```

任意时刻仅有一个模式活跃；切换模式时强制先 reset。`/api/simulation/status` 与 `/api/campus/status` 都返回 `mode` 字段供前端校验。

---

## 5. 数据库迁移

### 5.1 旧表增量 ALTER（不破坏 Phase 2 历史记录接口）

```sql
ALTER TABLE simulation_config ADD COLUMN mode TEXT DEFAULT 'single';
ALTER TABLE simulation_config ADD COLUMN campus_config_json TEXT;
```

`/api/history/configs` 与 `/api/history` 接口在 `mode='single'` 数据上行为完全不变。

### 5.2 校园模式专用快照表（新增）

```sql
CREATE TABLE campus_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id INTEGER,
    current_time REAL NOT NULL,
    campus_totals_json TEXT,    -- 见 4.3 campus_totals
    canteens_json TEXT,         -- 见 4.3 canteens
    in_transit_json TEXT,       -- 见 4.3 in_transit
    event_type TEXT,
    FOREIGN KEY (config_id) REFERENCES simulation_config(id)
);
```

校园模式落库走 `campus_snapshot`，与单食堂模式的 `simulation_snapshot` 物理隔离，避免相互污染。

### 5.3 校园元数据表（新增）

```sql
CREATE TABLE canteen_definition (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,             -- "xueyi" 等
    display_name TEXT NOT NULL,            -- "学一食堂"
    location_x REAL,
    location_y REAL,
    physical_window_count INTEGER,
    active_window_count INTEGER,
    seat_count INTEGER,
    avg_serve_time REAL,
    avg_eat_time REAL,
    arrival_weight REAL,
    typical_wait_seconds REAL,
    notes TEXT
);

CREATE TABLE walking_time (
    from_code TEXT,
    to_code TEXT,
    walk_seconds REAL,
    PRIMARY KEY (from_code, to_code)
);
```

---

## 6. 前端架构

### 6.1 集成阶段（保留 Phase 2 Canvas，扩展控制层与 namespace）

**最小改动原则**：`drawWindows / drawSeats / drawStudentDots` 三个绘制函数一行不动；运行控制层（`tick / fetch / finish / reset / loadStatistics`）按 mode 分派。

**文件结构**：

```
frontend/static/js/
├── main.js          # 现有；控制层重构 + 通过 window.CanteenApp 暴露公共面
├── campus.js        # 新增；校园联合模式适配与渲染（约 200 行）
└── vendor/
    └── echarts.min.js
```

**namespace 暴露**（`main.js`）：

```javascript
// 顶部仅声明 namespace，不引用尚未声明的变量
window.CanteenApp = window.CanteenApp || {};

// Phase 2 现有 const state 等声明保留位置不动
const state = {
    mode: 'single',          // 由表单决定，submit 时设
    lastData: null,
    timer: null,
    speed: 2,
    charts: {},
    studentPrev: {},
    activeCanteenId: null,
    canteenOrder: [],
};

// 文件底部统一挂出公共面（此时所有引用对象均已声明）
window.CanteenApp.state = state;
window.CanteenApp.drawCanteen = drawCanteen;
window.CanteenApp.updateInfoPanel = updateInfoPanel;
window.CanteenApp.renderCharts = renderCharts;
window.CanteenApp.disposeCharts = disposeCharts;
```

**主流程分派**（`main.js` 内）：

```javascript
async function dispatchStep() {
    const path = state.mode === 'campus' ? '/campus/step' : '/simulation/step';
    const res = await fetch(API_BASE + path);
    if (!res.ok) return null;
    const data = await res.json();

    if (state.mode === 'single') {
        drawCanteen(data);
        updateInfoPanel(data);
    } else if (window.CanteenApp.refreshCampusView) {
        window.CanteenApp.refreshCampusView(data);
    }
    state.lastData = data;
    return data;
}
```

**职责切分**：

| 模块 | 职责 |
|---|---|
| `main.js` | mode 分派；`configForm.submit` / `tick` / `endBtn` / `restartBtn` / `loadStatistics` 主流程 |
| `campus.js` | `pickCanteenView` / `fillCanteenSelect` / `refreshCampusView` / `renderCampusCharts`；不持有控制流 |

`campus.js` 关键实现：

```javascript
(function() {
    const App = window.CanteenApp;
    let lastCanteenOrderKey = null;

    function fillCanteenSelect(canteenOrder, canteens) {
        const sel = document.getElementById('active-canteen-select');
        const orderKey = canteenOrder.join(',');
        if (orderKey === lastCanteenOrderKey) return;  // 顺序未变，不重建
        lastCanteenOrderKey = orderKey;

        const prevSelected = sel.value;
        sel.innerHTML = '';
        for (const cid of canteenOrder) {
            const opt = document.createElement('option');
            opt.value = cid;
            opt.textContent = canteens[cid].display_name;
            sel.appendChild(opt);
        }
        if (canteenOrder.includes(prevSelected)) {
            sel.value = prevSelected;
        } else if (canteenOrder.length > 0) {
            sel.value = canteenOrder[0];
        }
        App.state.activeCanteenId = sel.value;  // 统一同步
    }

    function refreshCampusView(snapshot) {
        // 兜底：第一帧来时下拉还没初始化
        if (!App.state.activeCanteenId && snapshot.canteen_order.length > 0) {
            App.state.activeCanteenId = snapshot.canteen_order[0];
        }
        fillCanteenSelect(snapshot.canteen_order, snapshot.canteens);

        const canteenView = snapshot.canteens[App.state.activeCanteenId];
        if (!canteenView) {
            console.warn('activeCanteenId not in snapshot:', App.state.activeCanteenId);
            return;
        }
        App.drawCanteen(canteenView);
        App.updateInfoPanel(canteenView);
        updateCampusOverview(snapshot);
    }

    function updateCampusOverview(snapshot) {
        const t = snapshot.campus_totals;
        document.getElementById('campus-total-arrived').textContent = t.total_arrived;
        document.getElementById('campus-total-served').textContent = t.total_served;
        document.getElementById('campus-in-transit').textContent = t.total_in_transit;
        document.getElementById('campus-total-switches').textContent = t.total_switches;
        document.getElementById('campus-avg-waiting').textContent =
            `${t.avg_waiting_time.toFixed(1)} s`;
    }

    document.getElementById('active-canteen-select')
        .addEventListener('change', (e) => {
            App.state.activeCanteenId = e.target.value;
            if (App.state.lastData) refreshCampusView(App.state.lastData);
        });

    App.refreshCampusView = refreshCampusView;
    App.fillCanteenSelect = fillCanteenSelect;
})();
```

**index.html 增量**：
- 参数配置页：运行模式 radio + 单食堂表单 / 校园表单切换
- 仿真运行页：校园总览面板（campus 模式 visible）+ 食堂切换 dropdown（campus 模式 visible）
- 数据分析页：Tab 切换（总览 / 单食堂 / 切换分析）
- 历史记录页：mode 列

**集成阶段宋嘉桐工作量**：约 420 行（main.js 控制层 ~80 行 + campus.js ~200 行 + index.html ~80 行 + style.css ~60 行）。

### 6.2 部署阶段：Three.js 3D 化

新增 `frontend/static/js/three/` 目录：

```
three/
├── scene.js           # THREE.Scene 初始化、相机、灯光、resize
├── campus_view.js     # 校园 3D 场景（地面 + N 个食堂建筑 + 入口）
├── canteen_view.js    # 食堂内部 3D（窗口柜台 + 座位区 + 学生）
├── student_render.js  # 学生 3D 模型 + 帧间插值（沿用 Phase 2 lerp）
├── transition.js      # 校园 → 食堂 缩放穿越动画
└── vendor/
    └── three.min.js   # Three.js r155+，离线 vendor
```

**视觉风格**：low-poly 几何方块（BoxGeometry / CylinderGeometry / CapsuleGeometry），不依赖外部 glTF 资产，控制开发与渲染成本。

**学生颜色编码**：

| 状态 | 颜色 |
|---|---|
| queueing | 黄 |
| serving | 红 |
| waiting_seat | 紫 |
| seated/eating | 绿 |
| walking/switching | 灰 |

**相机**：默认 `OrbitControls` 鸟瞰；按 `V` 切到 `PointerLockControls` 第一人称漫游（WASD 移动 + 鼠标视角）。

**性能优化**：
- `InstancedMesh` 共享 Geometry，单 draw call 渲染所有学生
- WebGL 不可用时 UI 自动 fallback 到 2D 视图
- 提供"低画质"按钮（关闭阴影、降低多边形数）

**2D / 3D 切换**：仿真运行页头部加 `[2D] [3D]` 按钮组，默认 3D，演示出问题可一键切回 2D 救场。

### 6.3 后端为 3D 增加的字段

`Canteen.snapshot()` 在 Phase 2 兼容形状基础上额外增加：

```json
{
  "campus_position": {"x": 120, "y": 80},
  "layout": {
    "floor_size": [40, 30],
    "window_positions": [[5, 2], [8, 2]],
    "seat_grid": [[10, 10], [12, 10]]
  }
}
```

`layout` 由调研时填进 preset，作为 3D 场景生成依据。

### 6.4 部署阶段宋嘉桐工作量

约 800 行 Three.js 代码（5 个 three/ 模块），4 周完成（含模型搭建、动画调试、性能优化、演示打磨）。

---

## 7. 测试策略

### 7.1 测试矩阵

| 测试组 | 用例数（约） | 覆盖内容 |
|---|---:|---|
| Phase 2 兼容回归测试组（不重命名、不迁移） | 39 | 现有 `test_api.py / test_engine.py / test_dining_sim.py / test_queue_sim.py`；通过 `SimulationEngine` 兼容门面跑 |
| `test_simpy_canteen.py` | 6 | Canteen 单实例：windows 资源 / seats Store / shortest_window / snapshot 形状 / total_arrived / total_served |
| `test_window.py` | 4 | join_queue / leave_queue / leave_queue_idempotent / estimated_wait_for（含 current_serving） |
| `test_router.py` | 8 | pick_initial 分布 / no_switch_when_close / switch_when_clearly_better / oscillation_prevented / max_switches_capped / walk_time_in_decision / uses_current_window / live_congestion_mode |
| `test_coordinator.py` | 6 | 校园协调器：单 / 联合模式启停 / 时钟一致性 / canteens dict 形状 / snapshot 含 campus_totals / total_in_queue 含等座 |
| `test_campus_api.py` | 5 | `/api/campus/config` `/start` `/step` `/finish` `/status` |
| `test_db_migration.py` | 3 | ALTER 后旧 `simulation_config` 仍可读 / `campus_snapshot` 新表 / 旧 `/api/history` 仍能查单食堂数据 |
| **集成阶段目标** | **不少于 70 条** | |

### 7.2 关键回归用例

- `test_engine_compat_total_arrived_zero_right_after_start`（Phase 2 已有，回归保留）
- `test_engine_compat_seat_remaining_time_decreases`（Phase 2 已有，回归保留）
- `test_simpy_canteen_snapshot_shape_matches_phase2`（新增；新引擎输出形状必须与 Phase 2 单测期望一致）
- `test_canteen_leave_seat_queue_idempotent`（新增）

### 7.3 可复现性

- 所有涉及随机性的测试用 `random.Random(seed=42)` 固定种子
- SimPy 仿真本身确定性，配合固定种子 → 测试结果可复现

---

## 8. 文档变更清单

### 8.1 Phase 2 已交付文档（不修改）

| 文档 | 处理 |
|---|---|
| 《北京交通大学就餐仿真系统设计规格说明书》（立项阶段） | 不动 |
| 《立项阶段实训报告》（个人 ×3） | 不动 |
| 《立项阶段小组沟通交流记录》 | 不动 |
| 《软件开发环境搭建说明》 | 不动 |
| 《软件综合实训课程任务书》 | 不动 |
| 《单元测试报告》（个人 ×3） | 不动 |
| 《开发阶段实训报告》（个人 ×3） | 不动 |
| 《小组开发任务划分说明》 | 不动 |
| 《开发阶段小组沟通交流记录》 | 不动 |
| 三份个人源代码归档包 | 不动 |

### 8.2 集成阶段（5/24 ddl）需新写文档（共 6 份）

**团队文档（3 份）**：

| 文档 | 责任人主笔 | 内容要点 |
|---|---|---|
| 《联调测试报告》 | 朱思思 | 多食堂联合仿真联调过程 / Phase 2 兼容回归通过情况 / 70+ 单测全绿 / 双模式 e2e 演练 |
| 《集成阶段小组沟通交流记录》 | 朱思思 | 4/28 起的方案讨论与会议纪要、调研协调、联调对接 |
| 团队源码归档包（提交时按教师模板转为 RAR） | 朱思思 | 整体打包，`SRC_03小组` 顶层目录 |

**个人文档（3 份《集成阶段实训报告》）**：

每份报告统一章节：
1. 集成阶段任务（个人承担）
2. 技术选型变更（含本文档 §1.4 标准措辞）
3. 多食堂扩展：架构图 + StudentRouter 决策模型说明
4. 实地调研：4 食堂数据采集结果（朱思思那份重点写）
5. 联调过程与典型问题解决
6. 工具使用与 AI 使用记录
7. 进入部署阶段前的准备

### 8.3 部署与总结阶段（6/21 ddl）需新写文档（共 12 份）

**团队文档（6 份）**：

| 文档 | 责任人主笔 | 内容要点 |
|---|---|---|
| 《部署阶段小组沟通交流记录》 | 团队 | 5/25 起的会议纪要 |
| 《系统部署环境搭建说明》 | 贾文霞 | Three.js vendor 引入 / SimPy 环境 / Flask 启动 |
| 团队部署程序包（提交时按教师模板转为 RAR） | 朱思思 | 含 vendor 资产，开箱即跑 |
| 《系统使用手册》 | 宋嘉桐 | 单食堂 / 校园模式 / 2D 3D 切换的操作截图 |
| 《系统设计开发总结报告》 | 朱思思 | 含**参数灵敏度分析**章节（见 §10） |
| 《小组成员贡献度确认表》 | 团队 | 按教师模板填写 |

**个人文档（6 份）**：

每人提交《部署阶段实训报告》+《课程总结》各一份，共 6 份。课程总结需含 AI 使用过程附录。

### 8.4 命名规范

按课程《软件综合实训文档命名规范》执行：

- **个人文档**：`软件综合实训_[学号]_[姓名]_[文档名称].pdf`
- **团队文档**：`[分组编号]_[文档名称].pdf`（03 小组）
- **个人源代码包**：`软件综合实训_[学号]_[姓名]_XXX模块源代码.rar`
- **团队源代码包**：`软件综合实训_系统源代码.rar`
- **工程文件夹**：`SRC_[学号]` 或 `SRC_[分组编号]`

---

## 9. 实施时间线

### 9.1 集成阶段（4/28 → 5/24，共 27 天）

| 周次 | 日期 | 朱思思 | 宋嘉桐 | 贾文霞 |
|---|---|---|---|---|
| 第 9 周 | 4/28-5/3 | 多食堂联合仿真方案设计、技术路线论证、接口草案与调研计划制定 + Phase 2 收尾打包 | 现有 main.js 抽 namespace 准备工作 | 协助调研规划 + Phase 2 文档收尾 |
| 第 9 周末 | 5/3 | **Phase 2 开发阶段交付（任务书 ddl）** | 同 | 同 |
| 第 10 周 | 5/4-5/10 | 实地调研 4 食堂（5/4-5/5 周一二中午高峰）+ SimPy 重构 `engine.py` 兼容门面骨架 | `main.js` 控制层重构（namespace + dispatchStep） | 调研数据回填 `presets/*.json` |
| 第 11 周 | 5/11-5/17 | `canteen.py / student.py / router.py / coordinator.py / campus_routes.py` 主体 + DB 迁移 | `campus.js` 主体 + index.html 表单/Tab + style.css | 跑参数标定 / 文献查 α 值 / 校园总览图设计 |
| 第 12 周 | 5/18-5/22 | 单测全部铺开（约 70 条），跑通联调 | 校园 ECharts 对比图 + Tab 切换 + 联调 | 联调测试报告草稿 + 沟通记录 |
| 第 12 周末 | 5/23 | 全队跑过验收 demo（单食堂 / 校园 双模式） | 同 | 同 |
| 第 12 周末 | 5/24 | 6 份集成阶段交付物提交 | 同 | 同 |

### 9.2 部署与总结阶段（5/25 → 6/21，4 周）

| 周次 | 日期 | 朱思思 | 宋嘉桐 | 贾文霞 |
|---|---|---|---|---|
| 第 13 周 | 5/25-5/31 | 6 组灵敏度实验 + 总结报告技术章节 | Three.js scene / canteen_view / 3D 模型搭建 | 灵敏度结果统计图 + 参数章节 |
| 第 14 周 | 6/1-6/7 | API 性能调优（campus step 推进时间片优化） | student_render（InstancedMesh）+ transition 动画 | 部署环境说明 |
| 第 15 周 | 6/8-6/14 | 帮 demo 排练 + 写《课程总结》 | 2D/3D toggle + 第一人称漫游 + 性能降级 | 系统使用手册 + 截图 |
| 第 16 周 | 6/15-6/20 | 全队 demo 彩排 ×2 + 问题修复 | 同 | 同 |
| 第 16 周末 | 6/21 | 12 份部署阶段交付物提交 | 同 | 同 |

### 9.3 风险与缓冲

| 风险 | 缓冲计划 |
|---|---|
| 5/4-5/5 调研食堂高峰段时间不够 | 方案设计已 4/28 完成，预设字段提前定，调研当天只填值 |
| SimPy 重构 5/13 没完成 | 旧 `engine.py` 保留作兼容门面，coordinator 先包一层适配；最坏推迟到 5/15 |
| Phase 2 开发阶段 5/3 ddl 冲突 | 4/28-5/3 主要做规划/调研准备，不动 Phase 2 代码；Phase 2 已稳，本周无新代码风险 |
| 3D 性能不达标（部署阶段） | 2D 兜底已在 §6.2 设计 |
| 团队成员请假 | 每个 milestone 设"上一周完成度 ≥ 80% 才进入下一周"的 gate；每周三例会确认 |

---

## 10. 部署阶段参数灵敏度分析（写入《系统设计开发总结报告》）

部署阶段跑 6 组实验（保持其他变量恒定，统一种子），记录 4 个核心指标：

| 实验 | switch_improvement_ratio | max_switches | information_mode | avg_waiting_time | switch_rate | avg_extra_walk | 食堂利用率方差 |
|---|---|---|---|---|---|---|---|
| baseline | 1.3 | 2 | local_estimate | TBD | TBD | TBD | TBD |
| sens-1 | 1.1 | 2 | local_estimate | | | | |
| sens-2 | 1.6 | 2 | local_estimate | | | | |
| sens-3 | 1.3 | 3 | local_estimate | | | | |
| info-mode | 1.3 | 2 | live_congestion | | | | |
| no-switch | ∞ | 0 | local_estimate | | | | |

最后一组（禁用切换）作为对照组，证明"切换机制带来的福利增益"。

---

## 11. 验收标准（Definition of Done）

### 11.1 集成阶段（5/24 ddl）

- [ ] 单测目标不少于 70 条（Phase 2 兼容回归 39 条 + 新增约 30 条）全部通过
- [ ] 单食堂模式与 Phase 2 行为完全一致（手测 + 自动回归）
- [ ] 校园模式：4 食堂联合跑通、能切换、能下钻、有跨食堂学生迁移现象
- [ ] 4 个 BJTU 食堂 preset 含真实调研数据
- [ ] 6 份新文档（团队 3 份：联调测试报告 / 集成阶段沟通交流记录 / 团队源码归档包；个人 3 份：朱思思 / 宋嘉桐 / 贾文霞 各《集成阶段实训报告》）全部按命名规范提交

### 11.2 部署与总结阶段（6/21 ddl）

- [ ] 6 组灵敏度实验结果入《系统设计开发总结报告》
- [ ] 3D 校园 + 3D 食堂内部 + 2D toggle 全部可演示
- [ ] 12 份新文档（团队 6 份：部署阶段沟通记录 / 系统部署环境搭建说明 / 团队部署程序包 / 系统使用手册 / 系统设计开发总结报告 / 小组成员贡献度确认表；个人 6 份：每人《部署阶段实训报告》+《课程总结》各一份）全部按命名规范提交
- [ ] 演示彩排至少 2 轮全员到位

---

## 12. 依赖与版本

```text
# requirements.txt 新增
simpy>=4.1.1

# 已有保留
flask>=3.0.0
flask-cors>=4.0.0

# 不引入 pyyaml：preset 用 JSON 格式
```

前端 vendor：
- `echarts.min.js`（Phase 2 已有）
- `three.min.js`（部署阶段新增；版本 r155+；离线 vendor，避免 CDN 依赖）

---

## 13. 已交付物处理原则（合规说明）

> Phase 2 立项与开发阶段已交付的全部团队 / 个人文档与源代码归档包不修改、不替换。本扩展工作以"在已稳定的单食堂内核基础上叠加新能力"的方式实施：单食堂模式 100% 保留与 Phase 2 行为一致；新能力走独立 API 入口、独立数据表、独立测试组。

集成阶段实训报告中明确写入：

> 本阶段在 Phase 2 单食堂 DES 引擎基础上，扩展为基于 SimPy 的多食堂联合仿真，引入跨食堂学生决策模型。原单食堂模式 100% 保留，对应 Phase 2 已交付文档与单元测试组继续生效。

---

## 14. 文档版本

| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v1.0 | 2026-04-28 | 初稿：完成多食堂扩展 + 沉浸式可视化的总体方案设计、模块边界、接口草案、测试矩阵、时间线 | 朱思思 |
