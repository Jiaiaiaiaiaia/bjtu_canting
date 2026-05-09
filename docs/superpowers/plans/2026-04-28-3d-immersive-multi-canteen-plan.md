# 多食堂联合仿真 + 沉浸式可视化扩展 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于 Phase 2 已交付的单食堂仿真，分两阶段实施扩展：集成阶段（5/24 ddl）完成 SimPy 重构 + 多食堂联合仿真 + 三层视图前端 + 实地调研数据接入；部署阶段（6/21 ddl）完成 Three.js 3D 化 + 灵敏度实验 + 全部交付文档。

**Architecture:** 后端在 SimPy 进程式 DES 框架下重构内核，`CampusCoordinator → Canteen → Floor (Window/Seat with floor_id)`三层结构；学生作为 SimPy `process` 包含跨食堂迁移决策；REST API 单食堂走 `/api/simulation/*`（兼容 Phase 2），校园联合走 `/api/campus/*`；前端三层视图（校园地图 / 食堂下钻 / 楼层 Tab），集成阶段 SVG + Canvas，部署阶段升级到 Three.js 3D。

**Tech Stack:** Python 3.12+ / Flask / SimPy 4.1+ / SQLite / 原生 JS（plain `<script>`，window namespace 风格）/ ECharts 5.4+ / Three.js r155+ / pytest

**Spec reference:** @docs/superpowers/specs/2026-04-28-3d-immersive-multi-canteen-design.md

**Deadlines:**
- 集成阶段（Phase A）：2026-05-24 提交 6 份交付物
- 部署与总结阶段（Phase B）：2026-06-21 提交 12 份交付物

---

## Phase A — 集成阶段（4/28 → 5/24）

### A.0 准备工作

#### 任务 A.0.1：建立工作分支与依赖

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: 切到主分支并确认 Phase 2 测试全绿**

```bash
cd /Users/sissi/PycharmProjects/Canteen
git status
git checkout main
cd backend && python -m pytest tests/ -q
```

Expected: `39 passed`（Phase 2 基线，不允许这一步就有失败）

- [ ] **Step 2: 添加 SimPy 依赖到 requirements.txt**

修改 `requirements.txt`，加一行：
```
simpy>=4.1.1
```

- [ ] **Step 3: 安装新依赖**

```bash
source .venv/bin/activate
pip install -r requirements.txt
python -c "import simpy; print(simpy.__version__)"
```

Expected: `4.1.x` 输出

- [ ] **Step 4: Commit 依赖**

```bash
git add requirements.txt
git commit -m "deps: 加 SimPy 4.1+ 用于多食堂联合仿真"
```

---

### A.1 数据库迁移

参考 spec §5。Phase 2 数据库不动，新增列与新表。

#### 任务 A.1.1：编写迁移脚本

**Files:**
- Create: `backend/api/db_migrate.py`
- Test: `backend/tests/test_db_migration.py`

- [ ] **Step 1: 写失败测试 `test_alter_simulation_config_adds_mode_column`**

```python
import sqlite3
from backend.api.db_migrate import migrate

def test_alter_simulation_config_adds_mode_column(tmp_path):
    db = str(tmp_path / "t.db")
    # 模拟 Phase 2 旧表
    with sqlite3.connect(db) as c:
        c.execute("""CREATE TABLE simulation_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            window_count INTEGER, seat_count INTEGER,
            avg_serve_time REAL, avg_eat_time REAL,
            arrival_rate REAL, total_time INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
    migrate(db)
    with sqlite3.connect(db) as c:
        cols = [r[1] for r in c.execute("PRAGMA table_info(simulation_config)")]
    assert "mode" in cols
    assert "campus_config_json" in cols
```

- [ ] **Step 2: 运行失败**

```bash
cd backend && python -m pytest tests/test_db_migration.py -v
```

Expected: ImportError 或 fail

- [ ] **Step 3: 实现 migrate(db_path)**

参考 spec §5.1 / §5.2 / §5.3。文件应包含：
- ALTER `simulation_config` 加 `mode TEXT DEFAULT 'single'`、`campus_config_json TEXT`
- CREATE `campus_snapshot` 表
- CREATE `canteen_definition` 表
- CREATE `walking_time` 表
- 用 `PRAGMA table_info` 检查避免重复 ALTER

- [ ] **Step 4: 全部 3 条测试通过**

补 `test_creates_campus_snapshot_table` 和 `test_old_history_query_still_works`，跑：

```bash
python -m pytest tests/test_db_migration.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/api/db_migrate.py backend/tests/test_db_migration.py
git commit -m "feat(db): 多食堂模式迁移脚本（保 Phase 2 兼容）"
```

---

### A.2 后端核心数据类（TDD）

#### 任务 A.2.1：Window dataclass

**Files:**
- Create: `backend/simulation/canteen.py`
- Test: `backend/tests/test_window.py`

参考 spec §2.3 Window 完整定义。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_window.py
import simpy
import pytest
from simulation.canteen import Window
from simulation.student import Student

def make_window(env=None):
    env = env or simpy.Environment()
    return Window(id=0, floor_id=1, canteen_avg_serve_time=30.0,
                  resource=simpy.Resource(env, capacity=1))

def test_window_join_and_leave_queue():
    w = make_window()
    s = Student(id=1, state="queueing")
    w.join_queue(s)
    assert w.queue_length == 1
    w.leave_queue(s)
    assert w.queue_length == 0

def test_window_leave_queue_idempotent():
    w = make_window()
    s = Student(id=1, state="queueing")
    w.join_queue(s)
    w.leave_queue(s)
    w.leave_queue(s)  # 第二次不抛
    assert w.queue_length == 0

def test_window_queue_load_includes_serving():
    env = simpy.Environment()
    w = Window(id=0, floor_id=1, canteen_avg_serve_time=30.0,
               resource=simpy.Resource(env, capacity=1))
    # 不容易直接测 resource.count == 1 的状态；用 monkey-patch
    s = Student(id=1, state="serving")
    w.join_queue(s)
    # queue_load == count(0 idle) + 1(in queue)
    assert w.queue_load == 1

def test_window_estimated_wait_includes_current_serving():
    env = simpy.Environment()
    res = simpy.Resource(env, capacity=1)
    # 先抢一个 request 让 count=1
    res.request()
    w = Window(id=0, floor_id=1, canteen_avg_serve_time=30.0, resource=res)
    s = Student(id=2, state="queueing")
    w.join_queue(s)
    # ahead=0 + count=1 → 1 × 30 = 30s
    assert w.estimated_wait_for(s) == 30.0
```

- [ ] **Step 2: 运行失败**

```bash
python -m pytest tests/test_window.py -v
```

Expected: ImportError

- [ ] **Step 3: 创建 backend/simulation/student.py 仅 dataclass**

参考 spec §2.4。只定义 Student dataclass，包括所有字段（含 walking_start_time / current_window_id 等）。

- [ ] **Step 4: 创建 backend/simulation/canteen.py 仅 Window 与 Seat 与 FloorMeta dataclass**

参考 spec §2.3。这步只导出 dataclass，Canteen 类下个任务做。Window/Seat 都带 floor_id 字段。

- [ ] **Step 5: 测试通过**

```bash
python -m pytest tests/test_window.py -v
```

Expected: `5 passed`（含 leave_queue idempotent / estimated_wait 含 current_serving）

- [ ] **Step 6: Commit**

```bash
git add backend/simulation/student.py backend/simulation/canteen.py backend/tests/test_window.py
git commit -m "feat(simulation): Window/Seat/Student/FloorMeta dataclass"
```

---

#### 任务 A.2.2：Canteen 类（多楼层展开）

**Files:**
- Modify: `backend/simulation/canteen.py`
- Test: `backend/tests/test_simpy_canteen.py`, `backend/tests/test_multi_floor.py`

参考 spec §2.3 Canteen 完整定义。

- [ ] **Step 1: 写 test_simpy_canteen.py 全部 7 条（按 spec §7.1）**

测试用例名（含 v1.3 bug 回归）：

```python
# backend/tests/test_simpy_canteen.py — 7 条
test_canteen_windows_resource_per_window           # 每窗口独立 simpy.Resource
test_canteen_seats_pool_is_simpy_store              # 座位用 Store 调度
test_canteen_shortest_window_uses_queue_load        # min by queue_load 跨楼层
test_canteen_snapshot_shape_matches_phase2          # flat 形状与 Phase 2 字段同形
test_canteen_total_arrived_increments_correctly     # 学生进入时累加
test_canteen_total_served_increments_correctly      # 学生离开时累加
test_canteen_avg_eat_time_in_minutes_not_seconds    # v1.3 bug 3 回归
```

加 v1.3 bug 4 回归到一个独立测试：
```python
def test_canteen_seat_status_uses_empty_not_free():
    # snapshot.seats[i].status 必须是 'empty'，不能是 'free'
    ...
```

具体实现细节（make_def helper、断言代码）参考 spec §2.3 的 Canteen 完整代码与 §7.1 / §7.2 测试矩阵。

- [ ] **Step 2: 写 test_multi_floor.py 全部 4 条（按 spec §7.1）**

```python
# backend/tests/test_multi_floor.py — 4 条
test_multi_floor_preset_loads                            # floors[] 嵌套结构能被 Canteen 正确加载
test_multi_floor_window_seat_carry_correct_floor_id      # 每个 Window/Seat 带正确 floor_id
test_multi_floor_snapshot_floors_match_flat              # flat 字段与 floors[] 分组一致
test_multi_floor_single_floor_canteen_floors_length_one  # 单层食堂 floors[] 长度恰为 1
```

实现示例（其余按相同模式）：

```python
def test_multi_floor_window_seat_carry_correct_floor_id():
    env = simpy.Environment()
    c = Canteen(env, make_def([
        {"floor_id": 1, "windows": {"physical_count": 8, "active_count": 8}, "seats": {"count": 60}},
        {"floor_id": 2, "windows": {"physical_count": 0, "active_count": 0}, "seats": {"count": 80}},
    ]))
    assert len(c.windows) == 8
    assert all(w.floor_id == 1 for w in c.windows)
    assert sum(1 for s in c.seats if s.floor_id == 1) == 60
    assert sum(1 for s in c.seats if s.floor_id == 2) == 80
```

- [ ] **Step 3: 运行失败**

```bash
python -m pytest tests/test_simpy_canteen.py tests/test_multi_floor.py -v
```

Expected: AttributeError 或 fail

- [ ] **Step 4: 实现 Canteen 类**

参考 spec §2.3 完整代码：`__init__` 按 floors 展开 / `shortest_window` / `snapshot` 双形状（flat + floors[]）/ join_seat_queue / leave_seat_queue 等。

注意：
- `avg_eat_time = definition["avg_eat_time_minutes"]`（分钟，不要 *60）
- snapshot 里 `"status": "occupied" if s.student else "empty"`
- 每 window 注入 floor 级 `avg_serve_time_seconds`

- [ ] **Step 5: 测试通过**

```bash
python -m pytest tests/test_simpy_canteen.py tests/test_multi_floor.py -v
```

Expected: 11 条通过（test_simpy_canteen.py 7 + test_multi_floor.py 4）

- [ ] **Step 6: Commit**

```bash
git add backend/simulation/canteen.py backend/tests/test_simpy_canteen.py backend/tests/test_multi_floor.py
git commit -m "feat(simulation): Canteen 多楼层展开 + 双形状 snapshot"
```

---

### A.3 Campus（校园拓扑）

#### 任务 A.3.1：Campus 类

**Files:**
- Create: `backend/simulation/campus.py`
- Test: `backend/tests/test_campus.py`

参考 spec §2.8。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_campus.py
from simulation.campus import Campus
from simulation.canteen import Canteen
import simpy

def make_canteens(env):
    def_a = {"id": "a", "display_name": "A", "campus_position": {"x": 0, "y": 0},
             "avg_serve_time_seconds": 30, "avg_eat_time_minutes": 15,
             "arrival_weight": 1.0, "typical_wait_seconds": 120,
             "floors": [{"floor_id": 1, "windows": {"physical_count": 4, "active_count": 4}, "seats": {"count": 30}}]}
    def_b = {**def_a, "id": "b", "display_name": "B", "campus_position": {"x": 100, "y": 0}}
    return {"a": Canteen(env, def_a), "b": Canteen(env, def_b)}

def test_walking_time_uses_matrix_first():
    env = simpy.Environment()
    canteens = make_canteens(env)
    cfg = {"entrance_position": {"x": 0, "y": 0}, "walking_speed_mps": 1.4,
           "walking_time_seconds": {"a": {"b": 99}}, "entrance_walk_seconds": {}}
    campus = Campus(cfg, canteens)
    assert campus.walking_time("a", "b") == 99

def test_walking_time_falls_back_to_euclidean():
    env = simpy.Environment()
    canteens = make_canteens(env)
    cfg = {"entrance_position": {"x": 0, "y": 0}, "walking_speed_mps": 1.4,
           "walking_time_seconds": {}, "entrance_walk_seconds": {}}
    campus = Campus(cfg, canteens)
    # 100 米直线 / 1.4 m/s ≈ 71.4 秒
    assert abs(campus.walking_time("a", "b") - 100/1.4) < 0.01

def test_walking_time_symmetric_via_matrix_or_euclidean():
    env = simpy.Environment()
    canteens = make_canteens(env)
    cfg = {"entrance_position": {"x": 0, "y": 0}, "walking_speed_mps": 1.4,
           "walking_time_seconds": {"a": {"b": 99}}, "entrance_walk_seconds": {}}
    campus = Campus(cfg, canteens)
    assert campus.walking_time("b", "a") == 99  # 反向也找得到

def test_transit_progress_zero_when_not_walking():
    env = simpy.Environment()
    canteens = make_canteens(env)
    cfg = {"entrance_position": {"x": 0, "y": 0}, "walking_speed_mps": 1.4,
           "walking_time_seconds": {}, "entrance_walk_seconds": {}}
    campus = Campus(cfg, canteens)
    from simulation.student import Student
    s = Student(id=1, state="walking", walking_start_time=0)  # 未开始
    assert campus.transit_progress(s, now=0) == 0.0
```

- [ ] **Step 2: 运行失败**

```bash
python -m pytest tests/test_campus.py -v
```

- [ ] **Step 3: 实现 Campus 类**

参考 spec §2.8 完整代码。

- [ ] **Step 4: 测试通过**

```bash
python -m pytest tests/test_campus.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/simulation/campus.py backend/tests/test_campus.py
git commit -m "feat(simulation): Campus 拓扑（步行时间矩阵 + 欧氏距离 fallback）"
```

---

### A.4 StudentRouter

#### 任务 A.4.1：RouterConfig 与 Router 类

**Files:**
- Create: `backend/simulation/router.py`
- Test: `backend/tests/test_router.py`

参考 spec §2.7 / §4.2 / §4.4。

- [ ] **Step 1: 写 8 个测试**

参考 spec §4.7 测试列表：
- `test_router_pick_initial_distribution`
- `test_router_no_switch_when_close`
- `test_router_switch_when_clearly_better`
- `test_router_oscillation_prevented`
- `test_router_max_switches_capped`
- `test_router_walk_time_in_decision`
- `test_router_uses_current_window_not_shortest_window`
- `test_router_live_congestion_mode_toggle`

每条用 `random.Random(42)` 固定种子保证可复现。

```python
# 示例：test_router_max_switches_capped
def test_router_max_switches_capped():
    rng = random.Random(42)
    cfg = RouterConfig(max_switches_per_student=2)
    router = StudentRouter(env, cfg, campus, rng)
    s = Student(id=1, state="queueing", switch_count=2, current_window_id=0)
    # 即使其他食堂明显更好，也返回 None
    assert router.try_switch(s, canteens, exclude_id="a") is None
```

- [ ] **Step 2: 运行失败**

```bash
python -m pytest tests/test_router.py -v
```

- [ ] **Step 3: 实现 Router**

参考 spec §2.7 完整代码：`pick_initial` / `try_switch` / `sample_patience`。注意：
- 用 `random.Random` 不用 numpy
- `pick_initial` 用 `rng.choices(canteen_list, weights=weights, k=1)[0]`
- `try_switch` 用 `student.current_window_id` 取窗口（不是 shortest_window）
- 重命名为 `switch_improvement_ratio`
- 支持 `information_mode = local_estimate / live_congestion`

- [ ] **Step 4: 测试通过**

```bash
python -m pytest tests/test_router.py -v
```

Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add backend/simulation/router.py backend/tests/test_router.py
git commit -m "feat(simulation): StudentRouter 决策模型（耐心阈值 + 总耗时估算）"
```

---

### A.5 CampusStats

#### 任务 A.5.1：CampusStats 聚合类

**Files:**
- Create: `backend/simulation/stats.py`
- Test: `backend/tests/test_stats.py`

参考 spec §2.10。

- [ ] **Step 1: 写 5 个测试（覆盖 §10 灵敏度实验所需的 4 项指标）**

```python
def test_avg_waiting_time_empty_returns_zero():
    s = CampusStats()
    assert s.avg_waiting_time() == 0.0

def test_record_wait_then_avg():
    s = CampusStats()
    s.record_wait(make_student(wait_time=120))
    s.record_wait(make_student(wait_time=180))
    assert s.avg_waiting_time() == 150

def test_avg_walk_time_after_completion():
    s = CampusStats()
    s.record_completion(make_student(walk_time=60))
    s.record_completion(make_student(walk_time=120))
    assert s.avg_walk_time() == 90

def test_switch_rate_zero_when_no_switches():
    s = CampusStats()
    s.record_completion(make_student(switch_count=0))
    s.record_completion(make_student(switch_count=0))
    assert s.switch_rate() == 0

def test_switch_rate_counts_at_least_one_switch():
    s = CampusStats()
    s.record_completion(make_student(switch_count=0))
    s.record_completion(make_student(switch_count=1))
    s.record_completion(make_student(switch_count=2))
    # 3 个学生中 2 个有切换 → 2/3
    assert abs(s.switch_rate() - 2/3) < 0.01
```

- [ ] **Step 2: 运行失败 → 实现 → 通过**

参考 spec §2.10 完整代码。

```bash
python -m pytest tests/test_stats.py -v
```

Expected: 5 passed

- [ ] **Step 3: Commit**

```bash
git add backend/simulation/stats.py backend/tests/test_stats.py
git commit -m "feat(simulation): CampusStats 学生级指标聚合"
```

---

### A.6 ArrivalGenerator

#### 任务 A.6.1：到达生成器

**Files:**
- Create: `backend/simulation/arrival_generator.py`
- Test: `backend/tests/test_arrival_generator.py`

参考 spec §2.9。

- [ ] **Step 1: 写 2 条不依赖 lifecycle 的测试**

```python
def test_arrival_rate_formula():
    """λ_avg = N × α × coverage / T，单位人/分钟"""
    cfg = {"total_students": 28000, "lunch_alpha": 0.65,
           "coverage": 0.78, "peak_window_minutes": 90}
    # ArrivalGenerator 第 1 个参数 env 即可，其他可用 mock。
    gen = ArrivalGenerator(env, cfg, canteens={}, router=None,
                           campus=None, coordinator=None, rng=random.Random(42))
    expected = 28000 * 0.65 * 0.78 / 90
    assert abs(gen._compute_arrival_rate_per_minute() - expected) < 0.01

def test_poisson_interval_distribution():
    """rng.expovariate(rate) 间隔均值应接近 1/rate。"""
    rng = random.Random(42)
    intervals = [rng.expovariate(0.1) for _ in range(1000)]
    avg = sum(intervals) / len(intervals)
    assert 8 < avg < 12  # 均值 10 ± 浮动
```

> **依赖说明**：第 3 条 `test_arrival_generator_drains_after_simulation_seconds`（v1.3 bug 2 回归）需要 `Coordinator` 与 `student_lifecycle` 函数已存在才能跑通（drain 测试要观察 coordinator.total_arrived 是否在 simulation_seconds 后停止增长）。这一条**先写测试名 + 加 `@pytest.mark.skip(reason="待 A.7 lifecycle + A.8 Coordinator 完成后解封")`**，等 A.8 任务完成后回到 A.6 文件解开 skip 跑通。
>
> 同样地，`ArrivalGenerator._run` 内的 `from .student import student_lifecycle` 是模块顶 import；这一步实现时若 student_lifecycle 还没写，可暂时把 import 放到 `_run` 函数内（lazy import）；A.7 完成后再移到模块顶部。

- [ ] **Step 2: 写 drain 测试占位（skip）**

```python
@pytest.mark.skip(reason="待 A.7 lifecycle + A.8 Coordinator 完成后解封")
def test_arrival_generator_drains_after_simulation_seconds():
    """v1.3 bug 2 回归：simulation_seconds 后不再生成新学生。"""
    env = simpy.Environment()
    cfg = {..., "simulation_seconds": 60}
    coordinator = make_coord(env, cfg)
    env.run(until=120)
    arrivals_at_60 = coordinator.total_arrived_at_time(60)
    arrivals_at_120 = coordinator.total_arrived
    assert arrivals_at_120 == arrivals_at_60
```

- [ ] **Step 3: 实现 ArrivalGenerator → 2 条测试通过**

参考 spec §2.9 完整代码。`_run` 内的 student_lifecycle import 用 lazy 形式（函数内 import）规避 A.7 还没完成的依赖。

```bash
python -m pytest tests/test_arrival_generator.py -v
```

Expected: 2 passed + 1 skipped

- [ ] **Step 4: A.8 完成后回到本文件解封 drain 测试**

A.8 完成后：
- 把 `_run` 顶部的 lazy import 移到模块顶部（如有）
- 删 drain 测试的 `@pytest.mark.skip`
- 跑 `python -m pytest tests/test_arrival_generator.py -v`，期望 3 passed

- [ ] **Step 3: Commit**

```bash
git add backend/simulation/arrival_generator.py backend/tests/test_arrival_generator.py
git commit -m "feat(simulation): ArrivalGenerator Poisson 到达 + simulation_seconds 截止"
```

---

### A.7 student_lifecycle 进程函数

#### 任务 A.7.1：学生生命周期（最关键的一段）

**Files:**
- Modify: `backend/simulation/student.py`（加 lifecycle 函数到 dataclass 同文件）
- Test: `backend/tests/test_student_lifecycle.py`

参考 spec §2.5 完整伪代码。

- [ ] **Step 1: 写 5 个测试**

```python
def test_lifecycle_target_canteen_id_updates_on_switch():
    """v1.3 bug 1 回归：切换食堂时 target_canteen_id 必须更新。"""
    # 构造一个学生，让其耐心阈值很短，必触发 switch
    # 跑到 switching 状态时，断言 target_canteen_id == 新食堂

def test_lifecycle_walking_hooks_populate_transit_students():
    """on_student_walking_start/end 钩子让 transit_students 在走路期间非空。"""

def test_lifecycle_no_seat_falls_through_to_seat_pool_get():
    """学生打完饭找不到空座位时，进等座队列，最终能拿到座位。"""

def test_lifecycle_total_arrived_increments_after_walk():
    """学生走到食堂之后才算入 canteen.total_arrived，不在到达校园那刻。"""

def test_lifecycle_record_wait_called_when_serving():
    """学生进入 serving 状态前，coordinator.stats.record_wait 必被调用。"""
```

- [ ] **Step 2: 实现 student_lifecycle 函数**

参考 spec §2.5 完整代码。注意所有细节：
- 入队前 `window.join_queue(student)`
- `try ... finally: window.leave_queue(student)` 兜底
- 切换分支：先 `student.target_canteen_id = alt.id`，再 `coordinator.on_student_walking_start`
- 服务期 try/finally 占位（不实现 interrupt）
- 拿到资源时 `coordinator.stats.record_wait(student)`
- 离开时 `coordinator.stats.record_completion(student)`

- [ ] **Step 3: 测试通过**

```bash
python -m pytest tests/test_student_lifecycle.py -v
```

Expected: 5 passed

- [ ] **Step 4: Commit**

```bash
git add backend/simulation/student.py backend/tests/test_student_lifecycle.py
git commit -m "feat(simulation): student_lifecycle 进程函数（含跨食堂迁移与等座）"
```

---

### A.8 CampusCoordinator

#### 任务 A.8.1：校园协调器

**Files:**
- Create: `backend/simulation/coordinator.py`
- Test: `backend/tests/test_coordinator.py`

参考 spec §2.6。

- [ ] **Step 1: 写 7 个测试**

参考 spec §7.1 测试矩阵 `test_coordinator.py` 覆盖：
- `test_coordinator_init_canteens_dict`
- `test_coordinator_total_arrived_independent_of_canteen_total_arrived`（在路上的学生算 coordinator 不算 canteen）
- `test_walking_hooks_manage_transit_students`
- `test_advance_runs_simpy_until_target_time`
- `test_total_in_queue_includes_seat_waiting`（v1.3 关键）
- `test_target_canteen_id_updates_on_switch`（与 lifecycle 跨测）
- `test_router_config_dict_to_dataclass_conversion`

- [ ] **Step 2: 实现 CampusCoordinator**

参考 spec §2.6 完整代码：含 RouterConfig(**config["router"]) 转换、4 个 on_student_* 方法、advance、_campus_total_in_queue（窗口排队 + 等座）、snapshot（campus_totals 含 9 个字段）。

- [ ] **Step 3: 测试通过**

```bash
python -m pytest tests/test_coordinator.py -v
```

Expected: 7 passed

- [ ] **Step 4: Commit**

```bash
git add backend/simulation/coordinator.py backend/tests/test_coordinator.py
git commit -m "feat(simulation): CampusCoordinator 校园协调器（含 transit hooks 与统一统计）"
```

---

### A.9 SimulationEngine 兼容门面

#### 任务 A.9.1：保持 Phase 2 39 条单测通过

**Files:**
- Modify: `backend/simulation/engine.py`
- Test: 现有 Phase 2 测试组（不动）

> **关键不破坏原则**：原 `from simulation import SimulationEngine` 接口保持，类签名不变。内部改用 SimPy + 单食堂 Coordinator。

- [ ] **Step 1: 跑 Phase 2 测试看现状**

```bash
python -m pytest tests/ -q --ignore=tests/test_window.py --ignore=tests/test_simpy_canteen.py --ignore=tests/test_multi_floor.py --ignore=tests/test_campus.py --ignore=tests/test_router.py --ignore=tests/test_stats.py --ignore=tests/test_arrival_generator.py --ignore=tests/test_student_lifecycle.py --ignore=tests/test_coordinator.py --ignore=tests/test_db_migration.py
```

Expected: `39 passed`（Phase 2 基线）

- [ ] **Step 2: 备份原 engine.py**

```bash
git mv backend/simulation/engine.py backend/simulation/engine_legacy.py
```

(临时备份，commit 时不带 legacy)

- [ ] **Step 3: 写新 engine.py 兼容门面**

`SimulationEngine` 包装一个仅含单 Canteen 的 Coordinator。把 6 字段 config（window_count/seat_count/avg_serve_time/avg_eat_time/arrival_rate/total_time）在内部转成"单楼层 preset"。所有方法（start / step / get_statistics / pause）签名与行为与 Phase 2 一致。

- [ ] **Step 4: 跑 Phase 2 测试**

```bash
python -m pytest tests/test_api.py tests/test_engine.py tests/test_dining_sim.py tests/test_queue_sim.py -v
```

Expected: 39 passed（不能少）。如有 fail，逐条修门面，不动测试。

- [ ] **Step 5: 删除 legacy 备份**

```bash
rm backend/simulation/engine_legacy.py
```

- [ ] **Step 6: Commit**

```bash
git add backend/simulation/engine.py
git commit -m "refactor(simulation): SimulationEngine 改为 SimPy 兼容门面（Phase 2 39 单测全绿）"
```

---

### A.10 Campus API 路由

#### 任务 A.10.1：新增 /api/campus/* Blueprint

**Files:**
- Create: `backend/api/campus_routes.py`
- Modify: `backend/api/routes.py`（统一 _session 结构 + 注册新 Blueprint）
- Modify: `backend/app.py`（注册 Blueprint）
- Test: `backend/tests/test_campus_api.py`

参考 spec §4.2 / §4.3 / §4.4。

- [ ] **Step 1: 统一 _session 加 mode 字段**

修改 `routes.py`：

```python
_session = {
    "mode": None,
    "engine": None,
    "coordinator": None,
    "config_id": None,
    "is_running": False,
    "snapshot_buffer": [],
}
```

并把所有现有 `_session['engine']` 用法相应保留。

- [ ] **Step 2: routes.py 现有响应都加 mode 字段**

`/api/config` / `/api/simulation/status` 响应 dict 加 `"mode": "single"`。

- [ ] **Step 3: 写失败测试**

```python
# backend/tests/test_campus_api.py
def test_post_campus_config_returns_canteen_order():
    payload = {
        "campus": {"total_students": 1000, "lunch_alpha": 0.5, "coverage": 0.8,
                   "peak_window_minutes": 60, "peak_beta": 1.5,
                   "simulation_seconds": 600,
                   "entrance_position": {"x": 0, "y": 0},
                   "walking_speed_mps": 1.4,
                   "walking_time_seconds": {}, "entrance_walk_seconds": {}},
        "canteens": [...4 个 canteen def...],
        "router": {...}
    }
    res = client.post('/api/campus/config', json=payload)
    assert res.status_code == 200
    assert res.json["mode"] == "campus"
    assert "canteen_order" in res.json

def test_campus_step_advances_display_tick():
    """跑一次 /api/campus/step，current_time 至少推进 display_tick_seconds=10"""

def test_campus_finish_drains_simulation():
    """v1.3 bug 2 回归：finish 后能正常返回最终统计"""

def test_campus_status_returns_mode_field():

def test_single_campus_session_isolation():
    """切换模式必须先 reset，否则报错"""
```

- [ ] **Step 4: 实现 campus_routes.py**

参考 spec §4.2 接口列表。每个接口完整实现：config / start / step / status / pause / finish / reset / statistics。

- [ ] **Step 5: app.py 注册新 Blueprint**

```python
from api.campus_routes import campus_bp
app.register_blueprint(campus_bp)
```

- [ ] **Step 6: 测试通过**

```bash
python -m pytest tests/test_campus_api.py -v
```

Expected: 5 passed

- [ ] **Step 7: 跑全部后端测试做总体回归**

```bash
python -m pytest tests/ -q
```

Expected: 不少于 80 条 passed（含 39 Phase 2 兼容 + 11 simpy_canteen/multi_floor + 5 window + 4 campus + 8 router + 5 stats + 3 arrival_generator（其中 1 skip 待 A.8 解封）+ 7 coordinator + 5 campus_api + 3 db_migration）

- [ ] **Step 8: Commit**

```bash
git add backend/api/campus_routes.py backend/api/routes.py backend/app.py backend/tests/test_campus_api.py
git commit -m "feat(api): /api/campus/* Blueprint + 会话统一管理"
```

---

### A.11 食堂 preset 文件骨架（暂用占位数据）

#### 任务 A.11.1：4 个食堂 preset stub

**Files:**
- Create: `backend/simulation/presets/xueyuan.json`
- Create: `backend/simulation/presets/minghu_xueyi.json`
- Create: `backend/simulation/presets/xuehuo.json`
- Create: `backend/simulation/presets/xuesi.json`
- Create: `backend/simulation/presets/_campus.json`（全局校园配置）

> **占位数据**：5/4-5/5 实地调研后回填真实值。先用合理默认值跑通流程。

- [ ] **Step 1: 创建 4 个食堂 preset，按 spec §3.2 schema**

每个文件用占位数据：
- `xueyuan.json`：单层，6 窗口 / 200 座位（学苑食堂）
- `minghu_xueyi.json`：双层（1F 8 窗口 / 100 座位，2F 0 窗口 / 150 座位）（明湖学一食堂）
- `xuehuo.json`：单层，5 窗口 / 150 座位（学活食堂）
- `xuesi.json`：单层，4 窗口 / 120 座位（学四食堂）

每个 preset 都加注释字段 `"_TODO_field_research_pending": true`。

- [ ] **Step 2: 创建 _campus.json 全局配置 stub**

参考 spec §2.8 `config["campus"]` 部分。

- [ ] **Step 3: Commit**

```bash
git add backend/simulation/presets/
git commit -m "data: 4 食堂 preset 骨架（占位数据，5/4 实地调研后回填）"
```

---

### A.12 前端 main.js 重构

#### 任务 A.12.1：namespace + state + dispatchStep

**Files:**
- Modify: `frontend/static/js/main.js`

参考 spec §6.1。

> **关键不破坏原则**：所有 `drawWindows / drawSeats / drawStudentDots` 函数体一行不动。只改控制流与 state 形状。

- [ ] **Step 1: 启动 dev server，记录 Phase 2 单食堂模式行为**

```bash
cd backend && python app.py &
open http://127.0.0.1:5001/
```

走一遍参数配置 → 仿真运行 → 数据分析 → 历史记录，确认全功能正常。

- [ ] **Step 2: 加 namespace 头与 state 扩展**

参考 spec §6.1 namespace 节。修改 main.js：
- 顶部加 `window.CanteenApp = window.CanteenApp || {};`
- state 扩展加 `mode / view / activeCanteenId / activeFloorId / canteenOrder`
- 文件底部挂 `window.CanteenApp.state = state;` + 各 draw 函数

- [ ] **Step 3: 抽出 dispatchStep 函数**

参考 spec §6.1 dispatchStep 完整代码，按 mode 分派 `/api/simulation/step` vs `/api/campus/step`。

替换原有 `tick()` 内的 fetch 调用。

- [ ] **Step 4: configForm.submit / endBtn / restartBtn 按 mode 分派**

每个事件处理函数内开头加：
```javascript
const apiBase = state.mode === 'campus' ? '/api/campus' : '/api/simulation';
```
并改用 apiBase 拼接 URL。

- [ ] **Step 5: 手测——单食堂模式应仍然完全工作**

打开浏览器，跑一遍单食堂仿真。

Expected: 完全等价于 Phase 2 行为。

- [ ] **Step 6: Commit**

```bash
git add frontend/static/js/main.js
git commit -m "refactor(frontend): main.js 加 namespace + 控制层 mode 分派（保 Phase 2 行为）"
```

---

### A.13 前端 campus.js 食堂下钻层

#### 任务 A.13.1：refreshCampusView + filterByFloor

**Files:**
- Create: `frontend/static/js/campus.js`
- Modify: `frontend/templates/index.html`（加 `<script src="campus.js">`）

参考 spec §6.1 campus.js 关键实现。

- [ ] **Step 1: 写 campus.js IIFE 框架**

挂 `window.CanteenApp.refreshCampusView` / `fillCanteenSelect` / `updateCampusOverview`。

- [ ] **Step 2: 实现 fillCanteenSelect（防抖 lastCanteenOrderKey）**

参考 spec §6.1 fillCanteenSelect 完整代码。

- [ ] **Step 3: 实现 refreshCampusView**

参考 spec §6.1 refreshCampusView 完整代码（含三层联动 + 兜底初始化 activeCanteenId）。

- [ ] **Step 4: 实现 filterByFloor**

参考 spec §6.1 filterByFloor 代码。注意 waiting_queue_length 取 canteen 级，不按楼层过滤。

- [ ] **Step 5: 实现 updateCampusOverview**

读 `snapshot.campus_totals.*` 更新 5 个 DOM 节点。

- [ ] **Step 6: 在 index.html 底部加 `<script src="...campus.js">` 在 main.js 之后**

- [ ] **Step 7: 手测：必须能加载且 activeCanteenId 切换不报错**

需要等 A.14 + A.15 完成才能完整测；这一步只验证 JS 加载成功（控制台无 error）。

- [ ] **Step 8: Commit**

```bash
git add frontend/static/js/campus.js frontend/templates/index.html
git commit -m "feat(frontend): campus.js 食堂下钻层（含楼层过滤）"
```

---

### A.14 前端 campus_map.js 校园地图层

#### 任务 A.14.1：SVG 校园地图渲染

**Files:**
- Create: `frontend/static/js/campus_map.js`
- Modify: `frontend/templates/index.html`（加 `<svg id="campus-map-svg">` + 加载 campus_map.js）

参考 spec §6.1 campus_map.js 关键实现。

- [ ] **Step 1: index.html 加 SVG 容器**

```html
<div class="campus-map-container" id="campus-map-container" hidden>
  <svg id="campus-map-svg"></svg>
</div>
```

- [ ] **Step 2: 实现 initSvg：创建 4 个食堂标记**

参考 spec §6.1 initSvg 代码。每个食堂方块绑 click 事件设 `state.view='canteen' + activeCanteenId`。

- [ ] **Step 3: 实现 renderCampusMap：按当前队伍长度更新热度**

参考 spec §6.1 renderCampusMap 代码。每个 rect 颜色由 `totalQueue / 50` 渐变。

- [ ] **Step 4: 实现 renderInTransitDots：在路上学生小点**

```javascript
function renderInTransitDots(snapshot) {
    const layer = ensureLayer('transit-layer');
    layer.innerHTML = '';
    for (const t of snapshot.in_transit) {
        const from = t.from_canteen_id
            ? snapshot.canteens[t.from_canteen_id].campus_position
            : { x: 0, y: 0 };  // null 时从入口出发
        const to = snapshot.canteens[t.to_canteen_id].campus_position;
        const x = from.x + (to.x - from.x) * t.progress;
        const y = from.y + (to.y - from.y) * t.progress;
        const dot = createSvgEl('circle', {cx: x, cy: y, r: 3, fill: '#9333ea'});
        layer.appendChild(dot);
    }
}
```

- [ ] **Step 5: 在 index.html 加 `<script src="...campus_map.js">` 在 campus.js 之后**

- [ ] **Step 6: 手测：跑校园模式，看 SVG 渲染正确**

需要后端先有可跑的校园模式数据；先用 mock JSON 测试也可。

- [ ] **Step 7: Commit**

```bash
git add frontend/static/js/campus_map.js frontend/templates/index.html
git commit -m "feat(frontend): campus_map.js 校园地图 SVG（4 食堂热度 + 在路上学生）"
```

---

### A.15 前端 floor_tabs.js 楼层 Tab 层

#### 任务 A.15.1：楼层切换 Tab

**Files:**
- Create: `frontend/static/js/floor_tabs.js`
- Modify: `frontend/templates/index.html`（加 `<div id="floor-tabs">` + 加载 floor_tabs.js）

参考 spec §6.1 floor_tabs.js 关键实现。

- [ ] **Step 1: index.html 加楼层 Tab 容器**

```html
<div class="floor-tabs" id="floor-tabs"></div>
```

放在 canteen-canvas 上方。

- [ ] **Step 2: 实现 renderFloorTabs**

参考 spec §6.1 完整代码。注意：
- 单层食堂时不显示 Tab
- 多层食堂时显示 `[全楼层] [1F] [2F] ...`
- 用 lastFloorKeyByCanteen 防抖

- [ ] **Step 3: 实现 makeTab + 事件绑定**

按钮点击设 `state.activeFloorId` + 立即调 `refreshCampusView(state.lastData)`。

- [ ] **Step 4: 在 index.html 加 `<script src="...floor_tabs.js">` 在 campus.js 之后**

- [ ] **Step 5: 手测：双层食堂切换 Tab 应正确过滤窗口/座位**

- [ ] **Step 6: Commit**

```bash
git add frontend/static/js/floor_tabs.js frontend/templates/index.html
git commit -m "feat(frontend): floor_tabs.js 楼层 Tab 层（按 floor_id 过滤渲染）"
```

---

### A.16 前端 index.html / style.css 增量

#### 任务 A.16.1：表单 + 视图切换 + 总览面板

**Files:**
- Modify: `frontend/templates/index.html`
- Modify: `frontend/static/css/style.css`

参考 spec §6.1 index.html 增量。

- [ ] **Step 1: 参数配置页加运行模式 radio + 校园配置表单**

参考 spec §6.1 HTML 示例。`#campus-mode-form` 默认 hidden，radio 切换显示。

- [ ] **Step 2: 仿真运行页加视图切换 toggle**

```html
<div class="view-switcher" id="view-switcher" hidden>
  <button data-view="campus">校园地图</button>
  <button data-view="canteen">食堂详情</button>
</div>
```

绑 click 切换 `state.view` + 显示/隐藏对应 div。

- [ ] **Step 3: 仿真运行页加校园总览面板**

```html
<div class="campus-overview-panel" id="campus-overview-panel" hidden>
  <div class="info-item">...</div>
  ...
</div>
```

参考 spec §5 `update message #4` 给的 5 个字段。

- [ ] **Step 4: 仿真运行页加食堂下拉**

```html
<div class="canteen-switcher" id="canteen-switcher" hidden>
  <label>当前查看食堂</label>
  <select id="active-canteen-select"></select>
</div>
```

- [ ] **Step 5: style.css 加新增组件样式**

包括：
- `.campus-map-container` 容器位置
- `#campus-map-svg` 大小（默认隐藏，view='campus' 时显示）
- `.floor-tabs` 按钮组样式
- `.canteen-marker` SVG 食堂方块 hover 效果
- `.campus-overview-panel` 顶部信息条

- [ ] **Step 6: 手测：单食堂 / 校园两模式 UI 都能正常切换显示**

- [ ] **Step 7: Commit**

```bash
git add frontend/templates/index.html frontend/static/css/style.css
git commit -m "feat(frontend): 三层视图 HTML/CSS 框架（视图切换 + 总览面板 + Tab）"
```

---

### A.17 实地调研与 preset 数据回填（5/4-5/5）

#### 任务 A.17.1：现场数据采集

**实地调研日**：2026-05-04（周一中午）+ 2026-05-05（周二中午）

- [ ] **Step 1: 5/3 晚上准备调研工具**
  - 计时器（手机）
  - 笔 + 调研记录卡（按 spec §3.3 字段表打印或手抄）
  - 食堂间步行时间记录用秒表
  - 拍照设备

- [ ] **Step 2: 5/4 周一中午（11:30-13:00）调研 2 个食堂**
  - 学苑食堂 + 学活食堂
  - 每个食堂：physical_window_count / active_window_count / 服务速度（普通窗 5 人 + 最慢窗 5 人）/ 座位数估算 / 高峰队伍长度
  - 拍平面图 / 标牌

- [ ] **Step 3: 5/4 中午食堂间步行时间测量**
  - 学苑 → 学活 / 学苑 → 入口 / 学活 → 入口
  - 用秒表记录

- [ ] **Step 4: 5/5 周二中午调研另 2 个食堂**
  - 明湖学一 + 柳园学四
  - 同 step 2 字段
  - 步行时间补齐：明湖↔柳园、明湖↔学苑、明湖↔学活、柳园↔学苑、柳园↔学活、入口↔明湖、入口↔柳园

- [ ] **Step 5: 回填 4 个 preset JSON 与 _campus.json walking_time_seconds**

修改 `backend/simulation/presets/*.json`，把占位数据替换为真实调研值。删除 `_TODO_field_research_pending` 标记。

- [ ] **Step 6: 跑后端校园模式 e2e 测试（手测）**

```bash
cd backend && python app.py &
```
浏览器访问，提交校园配置（用真实 4 食堂 preset），开始仿真，看是否合理。

- [ ] **Step 7: Commit 调研数据**

```bash
git add backend/simulation/presets/*.json
git commit -m "data: 北交大主校区 4 食堂实地调研真实参数（5/4-5/5）"
```

---

### A.18 端到端联调

#### 任务 A.18.1：双模式 e2e + bug 修

**目标**：单食堂模式 100% 与 Phase 2 一致 + 校园模式 4 食堂能跑全流程，无 console 报错。

- [ ] **Step 1: 单食堂模式回归**

启动 server，浏览器：
- 参数配置（默认值）→ 开始仿真 → 看 Canvas 渲染 → 数据分析页 → 历史记录页

期望：与 Phase 2 行为一致。

- [ ] **Step 2: 校园模式跑通**

参数配置切到校园模式 → 提交校园配置 → 开始仿真。
看：
- 校园地图视图：4 食堂方块 + 热度颜色变化 + 在路上学生小点移动
- 切到食堂视图：下拉选不同食堂 → Canvas 重绘
- 多层食堂：楼层 Tab 显示 + 切换正确过滤
- 校园总览面板：数字增长合理

- [ ] **Step 3: 跑全部后端测试**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: 不少于 80 条全 passed

- [ ] **Step 4: 记录联调发现的 bug**

新建 `docs/phase3/integration_bug_log.md`，列每个 bug 的现象、根因、修复 commit。

- [ ] **Step 5: 修每个 bug，每修一个 commit 一次**

- [ ] **Step 6: 全模式回归测试 + 全单测最终一遍**

```bash
python -m pytest tests/ -q
```

- [ ] **Step 7: Commit 联调日志**

```bash
git add docs/phase3/integration_bug_log.md
git commit -m "docs: 集成阶段联调 bug 日志"
```

---

### A.19 集成阶段交付物

#### 任务 A.19.1：6 份新文档

**Files:**
- Create: `docs/phase3/03小组_联调测试报告.md`
- Create: `docs/phase3/03小组_集成阶段小组沟通交流记录.md`
- Create: `docs/phase3/软件综合实训_24281153_朱思思_集成阶段实训报告.md`
- Create: `docs/phase3/软件综合实训_24281139_宋嘉桐_集成阶段实训报告.md`
- Create: `docs/phase3/软件综合实训_24281131_贾文霞_集成阶段实训报告.md`
- 团队源码归档包：实施时打 RAR

- [ ] **Step 1: 联调测试报告（朱思思主笔）**

内容：
- 集成阶段任务概览
- 多食堂联合仿真联调过程（前后端、数据流、典型问题）
- Phase 2 兼容回归通过情况（39 条单测全绿截图 / 文字说明）
- 不少于 80 条单测全绿（覆盖率截图）
- 双模式 e2e 演练结果（单食堂 + 校园模式手测覆盖）

- [ ] **Step 2: 沟通交流记录（朱思思维护）**

按时间线列出：
- 4/28 方案讨论会
- 5/4 调研后参数标定会
- 5/13 联调对接会
- 5/20 验收预演

每条会议记录：时间 / 出席 / 议题 / 结论 / 行动项。

- [ ] **Step 3: 朱思思集成阶段实训报告（按 spec §8.2 章节模板）**

7 章模板：
1. 集成阶段任务（个人承担：SimPy 重构 + 多食堂内核 + Router + 实地调研主导 + 联调驱动）
2. 技术选型变更（用 spec §1.4 标准措辞）
3. 多食堂扩展架构图 + StudentRouter 决策模型说明
4. 实地调研数据采集结果（4 食堂参数对比表）
5. 联调过程与典型问题解决（5-10 个 bug 解决案例）
6. 工具使用与 AI 使用记录
7. 进入部署阶段前的准备

- [ ] **Step 4: 宋嘉桐集成阶段实训报告（你协助起草模板）**

类似 7 章，前端视角：三层视图实现、main.js 重构、campus.js / campus_map.js / floor_tabs.js 主笔等。

- [ ] **Step 5: 贾文霞集成阶段实训报告（你协助起草模板）**

类似，配置/分析视角：参数标定、α 文献查、调研协作、联调测试报告草稿等。

- [ ] **Step 6: 用 pandoc 把 5 份 .md 转 PDF**

```bash
cd docs/phase3
pandoc -o 03小组_联调测试报告.pdf 03小组_联调测试报告.md
# 同理其他 4 份
```

- [ ] **Step 7: 打团队源码归档包**

```bash
cd /tmp
mkdir SRC_03小组
cp -r /Users/sissi/PycharmProjects/Canteen/backend SRC_03小组/
cp -r /Users/sissi/PycharmProjects/Canteen/frontend SRC_03小组/
cp -r /Users/sissi/PycharmProjects/Canteen/database SRC_03小组/  # 不含 .db
cp /Users/sissi/PycharmProjects/Canteen/requirements.txt SRC_03小组/
cp /Users/sissi/PycharmProjects/Canteen/README.md SRC_03小组/
# 打 RAR 用 macOS 自带 zip 替代再转 RAR：
zip -r 软件综合实训_系统源代码.zip SRC_03小组
# 或安装 rar 后：rar a 软件综合实训_系统源代码.rar SRC_03小组
```

放到课程提交目录。

- [ ] **Step 8: Commit 文档**

```bash
git add docs/phase3/
git commit -m "docs(phase3): 集成阶段 6 份交付物（5/24 提交）"
```

- [ ] **Step 9: 5/24 上交**

按命名规范：
- 团队 3 份：`03小组_*.pdf` + `软件综合实训_系统源代码.rar`
- 个人 3 份：`软件综合实训_[学号]_[姓名]_集成阶段实训报告.pdf`

---

## Phase B — 部署与总结阶段（5/25 → 6/21）

### B.1 灵敏度实验

#### 任务 B.1.1：6 组实验跑数

**Files:**
- Create: `backend/scripts/sensitivity_experiments.py`
- Create: `docs/phase4/sensitivity_results.md`（结果汇总）

参考 spec §10。

- [ ] **Step 1: 写实验脚本**

```python
# backend/scripts/sensitivity_experiments.py
EXPERIMENTS = [
    {"name": "baseline",  "switch_improvement_ratio": 1.3, "max_switches_per_student": 2, "information_mode": "local_estimate"},
    {"name": "sens-1",    "switch_improvement_ratio": 1.1, "max_switches_per_student": 2, "information_mode": "local_estimate"},
    {"name": "sens-2",    "switch_improvement_ratio": 1.6, "max_switches_per_student": 2, "information_mode": "local_estimate"},
    {"name": "sens-3",    "switch_improvement_ratio": 1.3, "max_switches_per_student": 3, "information_mode": "local_estimate"},
    {"name": "info-mode", "switch_improvement_ratio": 1.3, "max_switches_per_student": 2, "information_mode": "live_congestion"},
    {"name": "no-switch", "switch_improvement_ratio": 999, "max_switches_per_student": 0, "information_mode": "local_estimate"},
]

def run(exp):
    # 用真实 4 食堂 preset，跑一次校园仿真，返回 4 项指标
    config = load_campus_config()
    config["router"].update({k: v for k, v in exp.items() if k != "name"})
    coordinator = make_coordinator(config, rng=random.Random(42))
    coordinator.advance(config["campus"]["simulation_seconds"] + 1800)  # +30 min drain
    return {
        "name": exp["name"],
        "avg_waiting_time": coordinator.stats.avg_waiting_time(),
        "switch_rate": coordinator.stats.switch_rate(),
        "avg_extra_walk": coordinator.stats.avg_walk_time(),  # 用 walk_time 代理
        "canteen_utilization_variance": compute_utilization_variance(coordinator),
    }

if __name__ == "__main__":
    results = [run(e) for e in EXPERIMENTS]
    save_to_csv("docs/phase4/sensitivity_results.csv", results)
```

- [ ] **Step 2: 运行 6 组实验**

```bash
cd backend && python scripts/sensitivity_experiments.py
```

每组耗时几十秒到几分钟。

- [ ] **Step 3: 整理结果到 markdown 表格**

把 CSV 转成 spec §10 表格形式，写到 `docs/phase4/sensitivity_results.md`。

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/sensitivity_experiments.py docs/phase4/sensitivity_results.md docs/phase4/sensitivity_results.csv
git commit -m "data: 部署阶段 6 组参数灵敏度实验结果"
```

---

### B.2 Three.js scene 基础

#### 任务 B.2.1：scene.js 初始化

**Files:**
- Create: `frontend/static/js/three/vendor/three.min.js`（下载离线）
- Create: `frontend/static/js/three/scene.js`

参考 spec §6.2。

- [ ] **Step 1: 下载 Three.js r155+ 到 vendor（含 OrbitControls 与 PointerLockControls）**

```bash
cd frontend/static/js/three/vendor
# core
curl -O https://unpkg.com/three@0.155.0/build/three.min.js
# Controls 在 examples/ 下，需要单独下载（r155+ 不再打进 three.min.js）
curl -O https://unpkg.com/three@0.155.0/examples/js/controls/OrbitControls.js
curl -O https://unpkg.com/three@0.155.0/examples/js/controls/PointerLockControls.js
```

> **r155+ 注意**：core 与 examples/js/controls 必须分开引入。index.html 加载顺序：
> ```html
> <script src="...vendor/three.min.js"></script>
> <script src="...vendor/OrbitControls.js"></script>
> <script src="...vendor/PointerLockControls.js"></script>
> <script src="...three/scene.js"></script>
> ```
> 如不分开，`new THREE.OrbitControls(...)` 会抛 `is not a constructor`。

- [ ] **Step 2: 写 scene.js**

参考标准 Three.js 入门：
- `THREE.Scene`
- `PerspectiveCamera` 鸟瞰位置
- `WebGLRenderer` 挂到 `<canvas id="three-canvas">`
- `OrbitControls`
- `AmbientLight + DirectionalLight`
- `requestAnimationFrame` 渲染循环
- resize 处理

挂 `window.CanteenApp.scene3d = { init, render, ... }`。

- [ ] **Step 3: index.html 加 `<canvas id="three-canvas">` + 加载 scene.js**

- [ ] **Step 4: 手测：3D 视图能初始化（黑屏 + 灯光即可）**

- [ ] **Step 5: Commit**

```bash
git add frontend/static/js/three/
git commit -m "feat(3d): Three.js scene.js 基础（场景/相机/灯光/控制器）"
```

---

### B.3 campus_view.js 校园 3D 场景

#### 任务 B.3.1：校园 3D 渲染

**Files:**
- Create: `frontend/static/js/three/campus_view.js`

参考 spec §6.2。

- [ ] **Step 1: 实现校园地面 + 入口**

`PlaneGeometry` 大平面 + 入口 `BoxGeometry` 立柱。

- [ ] **Step 2: 实现 4 食堂建筑（按 campus_position 摆放）**

每个食堂：根 `Group` + `BoxGeometry` 建筑外壳 + `TextSprite` 显示 display_name。点击事件：触发进入食堂内部。

- [ ] **Step 3: 实现在路上学生小点（同 SVG 版本，但 3D Spheres）**

按 `snapshot.in_transit[].progress` 插值位置，沿食堂连线移动。

- [ ] **Step 4: 实现热度颜色（按当前队伍长度）**

每个食堂建筑材质 emissiveColor 按 totalQueue/50 渐变。

- [ ] **Step 5: 手测：跑校园模式应看到 4 个建筑 + 在路上学生**

- [ ] **Step 6: Commit**

```bash
git add frontend/static/js/three/campus_view.js
git commit -m "feat(3d): campus_view.js 校园 3D（4 食堂建筑 + 热度 + 在路上学生）"
```

---

### B.4 canteen_view.js 食堂 3D（多楼层）

#### 任务 B.4.1：多楼层 mesh group 堆叠

**Files:**
- Create: `frontend/static/js/three/canteen_view.js`

参考 spec §6.2 多楼层 3D 渲染策略。

- [ ] **Step 1: 实现 buildCanteenMesh(canteenView)**

为每食堂建一个根 Group。`canteenView.floors[]` 每层：
- 子 Group，y 偏移 = `floor_id × 4` 米
- 楼层底板 PlaneGeometry
- 窗口柜台（BoxGeometry，按 layout.window_positions 摆）
- 座位（CylinderGeometry 桌 + Box 椅，按 seat_grid 摆）

- [ ] **Step 2: 实现 setActiveFloor(floorId)**

- `null` → 全部 mesh.material.opacity = 1.0
- 数字 → 该层 opacity=1，其他层 opacity=0.2

- [ ] **Step 3: 相机自动调整**

设 floorId 时把相机移到该层 y 高度 + 一定距离俯视。用 `transition.js`（B.6）做平滑动画。

- [ ] **Step 4: 集成 floor_tabs.js 的状态变更触发 setActiveFloor**

`window.CanteenApp.state.activeFloorId` 改变时，调 `canteen_view.setActiveFloor(...)`。

- [ ] **Step 5: 手测：双层食堂能看到楼层堆叠 + Tab 切换效果**

- [ ] **Step 6: Commit**

```bash
git add frontend/static/js/three/canteen_view.js
git commit -m "feat(3d): canteen_view.js 多楼层 3D（mesh group 堆叠 + activeFloor 透明度）"
```

---

### B.5 student_render.js 学生 3D + InstancedMesh

#### 任务 B.5.1：高效学生渲染

**Files:**
- Create: `frontend/static/js/three/student_render.js`

参考 spec §6.2。

- [ ] **Step 1: 用 InstancedMesh 渲染学生**

```javascript
const studentGeometry = new THREE.CapsuleGeometry(0.3, 1.0);
const studentMaterial = new THREE.MeshStandardMaterial();
const instancedMesh = new THREE.InstancedMesh(studentGeometry, studentMaterial, MAX_STUDENTS);
```

- [ ] **Step 2: 实现 updateStudents(snapshot, prevPositions, lerp=0.3)**

遍历 snapshot.students，按 position / position_detail 计算目标 3D 坐标：
- `window_queue` → 窗口前面排队槽
- `being_served` → 窗口正前方
- `seated` → 对应座位
- `waiting_seat` → 食堂入口区
帧间插值，沿用 Phase 2 lerp 思路。

- [ ] **Step 3: 状态颜色编码**

按 spec §6.2 颜色表设 `instancedMesh.setColorAt(i, color)`。

- [ ] **Step 4: 手测：校园模式 200+ 学生不掉帧**

```bash
# 浏览器 DevTools 打开性能面板，看 FPS
```

Expected: ≥ 30 FPS

- [ ] **Step 5: Commit**

```bash
git add frontend/static/js/three/student_render.js
git commit -m "feat(3d): student_render.js InstancedMesh 学生渲染（含状态色 + 帧间插值）"
```

---

### B.6 transition.js 楼层 / 校园↔食堂动画

#### 任务 B.6.1：相机平滑切换

**Files:**
- Create: `frontend/static/js/three/transition.js`

- [ ] **Step 1: 实现 cameraToCampusOverview()**

相机移到鸟瞰位置（高 y、远 z），平滑动画 1 秒。用 `requestAnimationFrame` + 缓动函数。

- [ ] **Step 2: 实现 cameraToCanteen(canteenId)**

相机移到该食堂建筑上方俯视。

- [ ] **Step 3: 实现 cameraToFloor(canteenId, floorId)**

相机移到该楼层 y 高度。

- [ ] **Step 4: 触发：`state.view`/`activeCanteenId`/`activeFloorId` 变化时调对应函数**

- [ ] **Step 5: 手测：相机切换平滑无跳变**

- [ ] **Step 6: Commit**

```bash
git add frontend/static/js/three/transition.js
git commit -m "feat(3d): transition.js 相机平滑切换动画（校园↔食堂↔楼层）"
```

---

### B.7 2D / 3D toggle + 性能降级

#### 任务 B.7.1：双视图切换

**Files:**
- Modify: `frontend/static/js/main.js`（dispatchStep 双视图分支）
- Modify: `frontend/templates/index.html`（[2D] [3D] 按钮组）

- [ ] **Step 1: index.html 加切换按钮**

```html
<div class="render-mode-switcher">
  <button data-render="2d">2D</button>
  <button data-render="3d" class="active">3D</button>
</div>
```

- [ ] **Step 2: state 加 renderMode**

```javascript
state.renderMode = 'auto';  // 'auto' | '2d' | '3d'
```

- [ ] **Step 3: WebGL 检测：不支持时强制 2D**

```javascript
function detectRenderMode() {
    if (state.renderMode === '2d') return '2d';
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl');
    return gl ? '3d' : '2d';
}
```

- [ ] **Step 4: dispatchStep 按 renderMode 调对应 view**

3D 模式：调 scene3d.render；2D 模式：维持 Canvas 渲染。

- [ ] **Step 5: 加"低画质"按钮关闭阴影 / 降低多边形数**

- [ ] **Step 6: 手测：2D/3D 切换瞬时 + 不同硬件验证**

- [ ] **Step 7: Commit**

```bash
git add frontend/static/js/main.js frontend/templates/index.html
git commit -m "feat(3d): 2D/3D 双视图 toggle + 性能降级 + WebGL 兜底"
```

---

### B.8 系统使用手册

#### 任务 B.8.1：手册 + 截图

**Files:**
- Create: `docs/phase4/03小组_系统使用手册.md`
- Create: `docs/phase4/screenshots/`（截图目录）

- [ ] **Step 1: 大纲**

1. 系统简介
2. 环境与启动
3. 单食堂模式使用步骤（截图：参数页 → 仿真页 → 分析页 → 历史页）
4. 校园联合模式使用步骤（截图：校园配置 → 校园地图 → 食堂下钻 → 楼层切换）
5. 2D / 3D 切换说明
6. 灵敏度实验复现指引
7. 常见问题（端口被占 / WebGL 不可用 / 等）

- [ ] **Step 2: 完成正文 + 录屏截图（2D / 3D 双版本各一组）**

- [ ] **Step 3: 转 PDF**

- [ ] **Step 4: Commit**

```bash
git add docs/phase4/03小组_系统使用手册.md docs/phase4/screenshots/
git commit -m "docs(phase4): 系统使用手册 + 截图"
```

---

### B.9 系统设计开发总结报告

#### 任务 B.9.1：总结报告（朱思思主笔）

**Files:**
- Create: `docs/phase4/03小组_系统设计开发总结报告.md`

- [ ] **Step 1: 大纲（按 spec §10 + 软件工程总结惯例）**

1. 项目背景与目标
2. 立项与开发阶段回顾（继承 Phase 2 / Phase 3 已写内容）
3. 集成阶段成果（多食堂 + 三层视图 + 实地调研）
4. 部署阶段成果（3D 化 + 灵敏度实验）
5. **参数灵敏度分析**（核心章节，6 组结果对比 + 解读）
6. 系统架构总览图（含 SimPy + Coordinator + 三层前端）
7. 技术挑战与解决方案（按时间顺序列 8-12 个典型问题）
8. 团队协作与分工
9. AI 使用记录
10. 不足与未来展望

- [ ] **Step 2: 完成正文（约 30-40 页）**

- [ ] **Step 3: 转 PDF**

- [ ] **Step 4: Commit**

```bash
git add docs/phase4/03小组_系统设计开发总结报告.md
git commit -m "docs(phase4): 系统设计开发总结报告（含灵敏度分析）"
```

---

### B.10 部署阶段其他交付物

#### 任务 B.10.1：剩余 9 份文档

**Files:**
- Create: `docs/phase4/03小组_部署阶段小组沟通交流记录.md`
- Create: `docs/phase4/03小组_系统部署环境搭建说明.md`
- Create: `docs/phase4/03小组_小组成员贡献度确认表.md`
- Create: `docs/phase4/软件综合实训_24281153_朱思思_部署阶段实训报告.md`
- Create: `docs/phase4/软件综合实训_24281139_宋嘉桐_部署阶段实训报告.md`
- Create: `docs/phase4/软件综合实训_24281131_贾文霞_部署阶段实训报告.md`
- Create: `docs/phase4/软件综合实训_24281153_朱思思_课程总结.md`
- Create: `docs/phase4/软件综合实训_24281139_宋嘉桐_课程总结.md`
- Create: `docs/phase4/软件综合实训_24281131_贾文霞_课程总结.md`
- 团队部署程序包：实施时打 RAR

- [ ] **Step 1: 沟通记录（5/25 起的会议纪要）**

- [ ] **Step 2: 部署环境搭建说明（贾文霞主笔）**

内容：Python 版本 / SimPy 安装 / Three.js vendor / Flask 启动 / 浏览器要求 / 故障排查。

- [ ] **Step 3: 3 份个人部署阶段实训报告**

- [ ] **Step 4: 3 份个人课程总结（含 AI 使用过程附录）**

- [ ] **Step 5: 小组成员贡献度确认表**

按教师模板填，三人签字。

- [ ] **Step 6: 打部署程序包**

```bash
mkdir DEPLOY_03小组
cp -r backend frontend database requirements.txt README.md DEPLOY_03小组/
# 含 vendor/ 全部资产
zip -r 软件综合实训_系统部署程序.zip DEPLOY_03小组
# rar a 软件综合实训_系统部署程序.rar DEPLOY_03小组
```

- [ ] **Step 7: 全部转 PDF**

```bash
cd docs/phase4
for f in *.md; do pandoc -o "${f%.md}.pdf" "$f"; done
```

- [ ] **Step 8: Commit**

```bash
git add docs/phase4/
git commit -m "docs(phase4): 部署阶段 9 份剩余文档（共 12 份完整）"
```

---

### B.11 Demo 彩排

#### 任务 B.11.1：演示彩排 ×2

- [ ] **Step 1: 6/15 第一轮全队彩排**

按演示脚本走流程：
1. 启动 server
2. 单食堂模式 demo（30 秒）
3. 校园模式 2D 视图（1 分钟）
4. 切到 3D 视图（1 分钟）
5. 楼层 Tab 切换（30 秒）
6. 灵敏度对比图展示（1 分钟）
7. Q&A 准备

记录问题 → 修复。

- [ ] **Step 2: 6/18 第二轮彩排（现场设备）**

在课堂演示设备上跑一遍，确认：
- 浏览器 WebGL 可用
- 帧率达标
- 投屏正常

- [ ] **Step 3: 6/21 提交所有交付物**

按命名规范：
- 团队 6 份：`03小组_*.pdf` + `软件综合实训_系统部署程序.rar`
- 个人 6 份：每人《部署阶段实训报告》+《课程总结》

---

## 验收标准

### Phase A 完成条件（5/24）

- [ ] `pytest tests/ -q` 输出 ≥ 80 passed
- [ ] 单食堂模式手测：参数 → 仿真 → 分析 → 历史 全功能 OK
- [ ] 校园模式手测：4 食堂联合跑通、视图切换、楼层 Tab、跨食堂迁移可观察
- [ ] 4 食堂 preset 含真实调研数据（无 `_TODO_field_research_pending`）
- [ ] 6 份交付物按命名规范提交

### Phase B 完成条件（6/21）

- [ ] 6 组灵敏度实验结果入总结报告
- [ ] 3D 视图（校园 + 食堂内部 + 多楼层 + 动画）+ 2D toggle 全部可演示
- [ ] 12 份交付物按命名规范提交
- [ ] 演示彩排 ≥ 2 轮全员到位

---

## 备注

- 整个项目用频繁 commit（每个任务步骤完成都 commit）便于追溯
- 不上 GitHub 不强制，但 git log 干净的 commit history 能给老师查看代码演变
- 实地调研那 2 天若遇暴雨/食堂临时关闭，可往后挪到 5/6-5/7（5/8-5/10 三天回来还能写后端代码追上节奏）
- AI 使用记录每天写一段（"今天用 AI 做了 X、AI 给了 Y、我评估后 Z"）累积进《课程总结》附录
