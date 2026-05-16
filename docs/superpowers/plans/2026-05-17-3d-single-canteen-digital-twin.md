# 3D 单食堂数字孪生升级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把仿真页升级为单食堂多层 3D 数字孪生主体验，支持运行中开/关窗口真改后端排队，并加入时变到达高峰，全程后端 snapshot 为唯一真值源。

**Architecture:** 复用既有 `CampusCoordinator`/`Canteen`（已原生多层）以 N=1 单食堂（明湖学一 3 层）承载；Phase 2 `/api/config`+`/api/simulation/*` 不动；新体验走 `/api/campus/*`。前端 `scene3d.js` 拆为 core/canteen_scene/intervention_ui/state_adapter，对外仍只暴露 `window.CanteenApp3D.init/render/dispose`。

**Tech Stack:** Python · Flask · SimPy · SQLite · 原生 JS · Three.js（已 vendored）· pytest · `node --check`

**Authoritative spec:** `docs/superpowers/specs/2026-05-16-3d-single-canteen-digital-twin-design.md`（reviewer 两轮 Approved）

**Hard constraints（每个 commit 都遵守）：**
- Phase 2 `/api/config`、`/api/simulation/*`、`SimulationEngine._build_state` flat 形状一字不改。
- `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q` 始终 `184+ passed`，新测试只增不破。
- `test_multi_floor.py:29`（`active_window_count==33`）、`/api/campus/presets/default` 及 `test_campus_preset_loader.py`/`test_campus_api.py` 不破。
- 选择性 staged：每个 commit 只 `git add` 本任务明确列出的路径；**绝不 `git add -A` / `git add .`**；绝不触及 `docs/phase2/*`、未跟踪 `docs/superpowers/plans/2026-05-12-threejs-canteen-v7-plan.md`。
- 旧 5 份过时 3D 文档清理**不在本计划范围**（评审通过后单独 commit）。
- TDD：先写失败测试 → 跑红 → 最小实现 → 跑绿 → commit。

---

## File Structure

**新增（backend）**
- `backend/simulation/canteen_config.py` — 单一汇流：`build_single_canteen_config(spec)`；参数化=退化单层预设。
- `backend/simulation/arrival_schedule.py` — `ArrivalSchedule`（baseline+ramp+pulse，积分归一，`is_constant`，thinning），per-student trace 含 `service_z/eat_z`。

**修改（backend）**
- `backend/simulation/presets/loader.py` — 新增 `load_single_canteen_preset()`（同 default envelope，N=1 明湖学一）。
- `backend/simulation/canteen.py` — `Window.is_open`；实例化全部 `physical_count`；`open_window_count`/`open_window_capacity_score`；`shortest_window()` 仅取 `is_open`；构造守卫=初始≥1 开放窗。
- `backend/simulation/router.py:57` — capacity 改用 `open_window_capacity_score`。
- `backend/simulation/student_trace.py` — 经 `ArrivalSchedule` 生成 trace；常量旁路=旧 `expovariate` 仿真语义一致。
- `backend/simulation/arrival_generator.py` — 实时生成器共用同一 `ArrivalSchedule`+thinning+`streams.arrival`。
- `backend/simulation/engine.py` — `_to_single_canteen_config` 经汇流 builder（flat 输出不变）。
- `backend/api/campus_routes.py` — `/presets/single-canteen`；`/config` 用 `build_random_streams(rng_seed)`；窗口干预 endpoint；干预即时 append+flush；`interventions` 持久化全链（campus 版方法）。
- `backend/api/db_migrate.py` — 幂等 ALTER 给 `campus_snapshot` 加 `interventions_json`。

**新增（frontend，均在 `frontend/static/js/three/`）**
- `canteen_scene.js` — 多层堆叠 + A+C 相机状态机（总览剖面 ⇄ 单层聚焦滑开）+ 路径高亮 + 点名追踪 + 冷青 identity。
- `intervention_ui.js` — 三段运维台（KPI/窗口网格/干预事件流）→ 调干预 API。
- `state_adapter.js` — 离散 snapshot → 连续插值目标。

**修改（frontend）**
- `frontend/static/js/three/scene3d.js` — 收为 core；保持 `window.CanteenApp3D.init/render/dispose` + `visibleCanteens/pendingCanteens` token。
- `frontend/static/js/main.js` — preset-first 改调 `/api/campus/presets/single-canteen`；`renderMode` 默认 `3d`（保 2D 兜底）；接干预 API。
- `frontend/templates/index.html`、`frontend/static/css/style.css` — 3D 主屏 + 三段面板 + 冷青配色。

**测试（backend/tests/，新增除非注明）**
- `test_canteen_config.py`、`test_single_canteen_preset.py`、`test_window_intervention.py`、`test_arrival_schedule.py`、`test_campus_intervention_api.py`、`test_campus_reproducibility_ab.py`；`test_db_migration.py`（修改）；`test_frontend_three_js_contract.py`（修改）。

---

## Phase A — 汇流 config builder + 单食堂预设

### Task A1: `build_single_canteen_config` 汇流构造

**Files:**
- Create: `backend/simulation/canteen_config.py`
- Test: `backend/tests/test_canteen_config.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_canteen_config.py
from simulation.canteen_config import build_single_canteen_config

PHASE2 = {"window_count": 6, "seat_count": 200, "avg_serve_time": 30,
          "avg_eat_time": 15, "arrival_rate": 5, "total_time": 60}

def test_parametric_is_degenerate_single_floor():
    cfg = build_single_canteen_config(PHASE2)
    assert list(cfg.keys()) == ["canteens", "campus", "router"] or \
        {"canteens", "campus", "router"} <= set(cfg)
    c = cfg["canteens"][0]
    assert len(c["floors"]) == 1
    f = c["floors"][0]
    assert f["windows"]["active_count"] == 6
    assert f["windows"]["physical_count"] == 6
    assert f["seats"]["count"] == 200
    assert cfg["router"]["max_switches_per_student"] == 0

def test_preset_passthrough_is_multifloor():
    preset = {"canteens": [{"id": "minghu_xueyi", "floors": [{}, {}, {}]}],
              "campus": {"x": 1}, "router": {"max_switches_per_student": 0}}
    cfg = build_single_canteen_config(preset)
    assert len(cfg["canteens"][0]["floors"]) == 3
    assert cfg is not preset  # deep-copied, no caller mutation
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_canteen_config.py -q`
Expected: FAIL `ModuleNotFoundError: No module named 'simulation.canteen_config'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/simulation/canteen_config.py
"""单一汇流：把 Phase 2 六参数或预设统一构造成 CampusCoordinator 配置。

参数化路径 = 一个退化的单层预设；预设路径 = 原样透传（深拷贝防调用方变异）。
两条路径汇流到本函数，消除 engine._to_single_canteen_config 与预设加载的重复。
"""
import copy

SINGLE_CANTEEN_ID = "single"


def _from_phase2(spec: dict) -> dict:
    total_minutes = float(spec["total_time"])
    arrival_rate = float(spec["arrival_rate"])
    total_students = max(arrival_rate * total_minutes, 1.0)
    wc = int(spec["window_count"])
    return {
        "canteens": [{
            "id": SINGLE_CANTEEN_ID,
            "display_name": "单食堂",
            "campus_position": {"x": 0, "y": 0},
            "avg_serve_time_seconds": float(spec["avg_serve_time"]),
            "avg_eat_time_minutes": float(spec["avg_eat_time"]),
            "arrival_weight": 1.0,
            "typical_wait_seconds": 0.0,
            "floors": [{
                "floor_id": 1,
                "windows": {"physical_count": wc, "active_count": wc},
                "seats": {"count": int(spec["seat_count"])},
            }],
        }],
        "campus": {
            "total_students": total_students,
            "lunch_alpha": 1.0,
            "coverage": 1.0,
            "peak_window_minutes": total_minutes,
            "peak_beta": 1.0,
            "simulation_seconds": total_minutes * 60,
            "entrance_position": {"x": 0, "y": 0},
            "walking_speed_mps": 1.4,
            "walking_time_seconds": {},
            "entrance_walk_seconds": {SINGLE_CANTEEN_ID: 0.0},
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


def build_single_canteen_config(spec: dict) -> dict:
    if "canteens" in spec and "campus" in spec and "router" in spec:
        cfg = copy.deepcopy(spec)
        cfg["router"]["max_switches_per_student"] = 0  # §1 不变量
        return cfg
    return _from_phase2(spec)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_canteen_config.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/simulation/canteen_config.py backend/tests/test_canteen_config.py
git commit -m "feat(sim): single-canteen config 汇流 builder (parametric=degenerate 1-floor preset)"
```

### Task A2: `engine._to_single_canteen_config` 改走汇流（Phase 2 flat 不变）

**Files:**
- Modify: `backend/simulation/engine.py` (`_to_single_canteen_config`, 约 77-124)
- Test: `backend/tests/test_engine_facade.py` (既有，回归)

- [ ] **Step 1: Add a characterization test (failing only if shape drifts)**

```python
# append to backend/tests/test_engine_facade.py
def test_engine_build_state_flat_shape_unchanged():
    from simulation import SimulationEngine
    cfg = {"window_count": 3, "seat_count": 20, "avg_serve_time": 5,
           "avg_eat_time": 1, "arrival_rate": 10, "total_time": 1}
    e = SimulationEngine(cfg, config_id=1, rng_seed=7)
    e.start()
    s = e.step()
    assert set(s) >= {"is_ended","event_type","current_time","total_time",
        "total_arrived","total_served","total_in_queue","total_eating",
        "empty_seats","avg_waiting_time","waiting_queue_length",
        "windows","seats","students"}
    assert "floors" not in s  # Phase 2 flat：不得新增 floors[]
```

- [ ] **Step 2: Run to verify it passes on current code (characterization baseline)**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_engine_facade.py -q`
Expected: PASS (records current Phase 2 contract before refactor)

- [ ] **Step 3: Refactor `_to_single_canteen_config` to delegate**

Replace the body of `SimulationEngine._to_single_canteen_config` so it calls the shared builder and re-injects the facade-only keys **inside this method** into `cfg["campus"]`（`_planned_students`/`_student_traces` 与原 `__init__` 流程等价；**不要改 `__init__`**）：

```python
def _to_single_canteen_config(self, config):
    from .canteen_config import build_single_canteen_config
    cfg = build_single_canteen_config(config)
    cfg["campus"]["simulation_seconds"] = self.total_time
    cfg["campus"]["_planned_students"] = self._planned_students
    cfg["campus"]["_student_traces"] = self._student_traces
    return cfg
```

- [ ] **Step 4: Run full backend regression**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q`
Expected: `185 passed` (184 baseline + new A1/A2). Zero failures. If any Phase 2 test fails, the refactor changed flat shape — revert Step 3 and reconcile.

- [ ] **Step 5: Commit**

```bash
git add backend/simulation/engine.py backend/tests/test_engine_facade.py
git commit -m "refactor(sim): route engine single-config through 汇流 builder, Phase 2 flat unchanged"
```

### Task A3: `load_single_canteen_preset()` 同 envelope

**Files:**
- Modify: `backend/simulation/presets/loader.py`
- Test: `backend/tests/test_single_canteen_preset.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_single_canteen_preset.py
from simulation.presets.loader import (
    load_single_canteen_preset, load_default_campus_preset)

def test_single_preset_same_envelope_keys_as_default():
    d = load_default_campus_preset()
    s = load_single_canteen_preset()
    assert set(s.keys()) == set(d.keys())  # config/visible_canteens/pending_canteens/source_scale/demo_runtime（loader 不含 mode；mode 仅由 /presets/* endpoint 包裹）

def test_single_preset_is_n1_minghu_only():
    s = load_single_canteen_preset()
    canteens = s["config"]["canteens"]
    assert [c["id"] for c in canteens] == ["minghu_xueyi"]
    assert s["pending_canteens"] == []
    assert [c["id"] for c in s["visible_canteens"]] == ["minghu_xueyi"]
    assert s["config"]["router"]["max_switches_per_student"] == 0

def test_single_preset_carries_arrival_schedule_for_lambda_demo():
    # spec §5.1/§3.5：单食堂预设必须带午高峰+下课脉冲，否则 3D 演示
    # λ(t) 叙事（拥堵爆发→开窗→回落）端到端不会触发。
    sch = load_single_canteen_preset()["config"]["campus"]["arrival_schedule"]
    assert sch["ramp"] is not None and len(sch["pulses"]) >= 1

def test_default_preset_unchanged():
    d = load_default_campus_preset()
    ids = sorted(c["id"] for c in d["visible_canteens"])
    assert ids == ["minghu_xueyi", "xuehuo", "xuesi"]
    assert d["pending_canteens"] == ["xuehuo"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_single_canteen_preset.py -q`
Expected: FAIL `ImportError: cannot import name 'load_single_canteen_preset'`

- [ ] **Step 3: Implement (add to loader.py, do not touch `load_default_campus_preset`)**

```python
def load_single_canteen_preset() -> dict:
    """N=1 单食堂（明湖学一 3 层）；envelope 与 load_default_campus_preset 完全一致，
    前端 applyCampusPresetMetadata 零分叉。/presets/default 不动。"""
    base = load_default_campus_preset()
    minghu = next(c for c in base["config"]["canteens"]
                  if c["id"] == "minghu_xueyi")
    cfg = copy.deepcopy(base["config"])
    cfg["canteens"] = [copy.deepcopy(minghu)]
    cfg["router"]["max_switches_per_student"] = 0
    # spec §3.5/§5.1：带午高峰爬升 + 下课脉冲，驱动 3D 演示 λ(t) 叙事。
    # 数值与 demo simulation_seconds 对齐；非常量 → 走 thinning（D3）。
    sim_s = float(cfg["campus"]["simulation_seconds"])
    cfg["campus"]["arrival_schedule"] = {
        "baseline": 0.1,
        "ramp": [sim_s * 0.15, sim_s * 0.75, 1.0],
        "pulses": [[sim_s * 0.5, 0.6, sim_s * 0.08]],
    }
    visible = [c for c in base["visible_canteens"] if c["id"] == "minghu_xueyi"]
    return {
        "config": cfg,
        "visible_canteens": visible,
        "pending_canteens": [],
        "source_scale": base["source_scale"],
        "demo_runtime": True,
    }
```

(Ensure `import copy` exists at top of loader.py — it already does.)

- [ ] **Step 4: Run test + regression**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_single_canteen_preset.py backend/tests/test_campus_preset_loader.py -q`
Expected: PASS, and `test_campus_preset_loader.py` still green (default unchanged).

- [ ] **Step 5: Commit**

```bash
git add backend/simulation/presets/loader.py backend/tests/test_single_canteen_preset.py
git commit -m "feat(presets): add load_single_canteen_preset (N=1 明湖学一, same envelope)"
```

---

## Phase B — Window 开放状态机

### Task B1: `Window.is_open` + 全 `physical_count` 实例化 + open counts

**Files:**
- Modify: `backend/simulation/canteen.py` (`Window` dataclass; `Canteen.__init__` 约 107-165; `shortest_window` 167-168)
- Test: `backend/tests/test_window_intervention.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_window_intervention.py
import simpy
from simulation.canteen import Canteen

DEF = {"id": "c", "display_name": "C", "campus_position": {"x":0,"y":0},
       "avg_serve_time_seconds": 10, "avg_eat_time_minutes": 5,
       "arrival_weight": 1.0, "typical_wait_seconds": 0.0,
       "floors": [{"floor_id": 1,
                   "windows": {"physical_count": 5, "active_count": 3},
                   "seats": {"count": 10}}]}

def _canteen():
    return Canteen(simpy.Environment(), DEF)

def test_all_physical_windows_instantiated():
    c = _canteen()
    assert len(c.windows) == 5            # physical, not active
    assert sum(w.is_open for w in c.windows) == 3   # initial open subset
    assert c.open_window_count == 3
    assert c.active_window_count == 3     # config-active 含义不变

def test_shortest_window_only_open():
    c = _canteen()
    for w in c.windows:
        if w.is_open:
            w.waiting_students.extend([object()] * 9)  # 占满开放窗
    # 关掉的 2 个窗即便 queue_load=0 也不能被选
    assert c.shortest_window().is_open is True

def test_open_window_capacity_score_excludes_closed():
    c = _canteen()
    # 5 窗同 serve_time=10 → 仅 3 个开放 → 3 * (1/10)
    assert abs(c.open_window_capacity_score - 3 * (1/10)) < 1e-9
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_window_intervention.py -q`
Expected: FAIL (`len(c.windows)==3`, no `is_open`, no `open_window_count`).

- [ ] **Step 3: Implement in `canteen.py`**

In `Window` dataclass add field: `is_open: bool = True` (place after `total_served`).

In `Canteen.__init__`, change the window instantiation loop (currently `for _ in range(wdef.get("active_count", 0))`) to instantiate **all physical** with the first `active_count` open:

```python
phys = wdef.get("physical_count", wdef.get("active_count", 0))
act = wdef.get("active_count", 0)
for k in range(phys):
    self.windows.append(Window(
        id=next_window_id, floor_id=fid,
        canteen_avg_serve_time=floor_serve_time,
        resource=simpy.Resource(env, capacity=1),
        is_open=(k < act),
    ))
    next_window_id += 1
```

Add properties:

```python
@property
def open_window_count(self) -> int:
    return sum(1 for w in self.windows if w.is_open)

@property
def open_window_capacity_score(self) -> float:
    return sum(1.0 / w.canteen_avg_serve_time
               for w in self.windows if w.is_open)
```

Change `shortest_window`:

```python
def shortest_window(self) -> "Window":
    open_windows = [w for w in self.windows if w.is_open]
    if not open_windows:
        raise RuntimeError(f"Canteen {self.id!r}: no open window")
    return min(open_windows, key=lambda w: w.queue_load)
```

Keep the existing `active_window_count` accumulation (`self.active_window_count += wdef.get("active_count", 0)`) **unchanged** (test_multi_floor.py:29 == 33). Keep the construction guard `if self.active_window_count <= 0: raise ValueError(...)`.

- [ ] **Step 4: Run test + regression**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_window_intervention.py backend/tests/test_multi_floor.py backend/tests/test_window.py backend/tests/test_engine.py -q`
Expected: PASS, including `test_multi_floor.py:29` (`active_window_count==33`) **and** `:30` (`len(c.windows)==33`) — both survive B1 because that fixture sets `physical_count==active_count` on every floor (6/6, 13/13, 14/14), so全 physical 实例化后窗口数与 active 数仍相等。Then full `pytest backend/tests -q` green. Note: `campus_routes.py:257`（`served_by_window=[w.total_served for w in canteen.windows]`）此后也会列出已关闭窗口——正确且 additive 的 snapshot 形状变化，由 `test_campus_api.py` 回归门覆盖，无需特殊处理。

- [ ] **Step 5: Commit**

```bash
git add backend/simulation/canteen.py backend/tests/test_window_intervention.py
git commit -m "feat(sim): Window.is_open, all-physical instantiation, open_window_count/capacity, shortest_window filters open"
```

### Task B2: `router.py:57` capacity 改用 `open_window_capacity_score`

**Files:**
- Modify: `backend/simulation/router.py` (`pick_initial`, line 57)
- Test: `backend/tests/test_router.py` (既有，回归) + add 1 case

- [ ] **Step 1: Write the failing test**

```python
# append to backend/tests/test_router.py
def test_pick_initial_capacity_uses_open_windows(monkeypatch):
    # N=1 单元素 choices 必返回该食堂；此处仅断言权重计算不再用 active_window_count
    import simulation.router as R
    src = open(R.__file__, encoding="utf-8").read()
    assert "open_window_capacity_score" in src
    assert "active_window_count / " not in src
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_router.py -q`
Expected: FAIL (`open_window_capacity_score` not yet referenced).

- [ ] **Step 3: Implement**

In `router.py` `pick_initial`, replace:
`capacity_score = c.active_window_count / c.avg_serve_time`
with:
`capacity_score = c.open_window_capacity_score`

- [ ] **Step 4: Run test + regression**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_router.py backend/tests/test_coordinator.py -q` then full `pytest backend/tests -q`.
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add backend/simulation/router.py backend/tests/test_router.py
git commit -m "fix(router): capacity_score uses open_window_capacity_score (excludes closed windows)"
```

---

## Phase C — campus N=1 可复现（random_streams 接线）

### Task C1: `/api/campus/config` 用 `build_random_streams(rng_seed)`

**Files:**
- Modify: `backend/api/campus_routes.py` (`submit_campus_config`, 约 331-376, line 362)
- Test: `backend/tests/test_campus_api.py` (既有，回归) + `backend/tests/test_campus_reproducibility_ab.py` (新, scaffold here)

- [ ] **Step 1: Write the failing test (reproducibility scaffold)**

```python
# backend/tests/test_campus_reproducibility_ab.py
import simpy, random
from simulation.coordinator import CampusCoordinator
from simulation.random_streams import build_random_streams
from simulation.presets.loader import load_single_canteen_preset

def _run(seed):
    cfg = load_single_canteen_preset()["config"]
    streams = build_random_streams(seed)
    coord = CampusCoordinator(simpy.Environment(), cfg,
                              random.Random(seed), random_streams=streams)
    coord.env.run(until=cfg["campus"]["simulation_seconds"])
    served = [s for s in coord.all_students if s.state == "left"]
    return (coord.total_arrived, coord.total_served,
            tuple(round(s.service_time, 6) for s in served[:50]))

def test_same_seed_same_streams_semantically_identical():
    assert _run(123) == _run(123)   # 无干预、同 seed → 仿真语义一致
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_campus_reproducibility_ab.py -q`
Expected: FAIL — `service_time` differs run-to-run because `coordinator.service_rng` is `None` → `sample_serve_time` falls back to global `random` (this is exactly the §3.5 defect).

- [ ] **Step 3: Implement — thread random_streams into campus config**

In `campus_routes.py` `submit_campus_config`, replace:
```python
rng = random.Random(payload['router'].get('rng_seed', 42))
coordinator = CampusCoordinator(simpy.Environment(), payload, rng)
```
with:
```python
from simulation.random_streams import build_random_streams
rng_seed = payload['router'].get('rng_seed', 42)
streams = build_random_streams(rng_seed)
coordinator = CampusCoordinator(
    simpy.Environment(), payload, random.Random(rng_seed),
    random_streams=streams)
```
(Keep `import random` and `import simpy` as-is at top of file.)

- [ ] **Step 4: Run test + regression**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_campus_reproducibility_ab.py backend/tests/test_campus_api.py backend/tests/test_coordinator.py -q` then full suite.
Expected: reproducibility test PASS; campus api/coordinator unchanged green.

- [ ] **Step 5: Commit**

```bash
git add backend/api/campus_routes.py backend/tests/test_campus_reproducibility_ab.py
git commit -m "fix(campus): thread build_random_streams(rng_seed) into CampusCoordinator (N=1 service/eat reproducible)"
```

---

## Phase D — ArrivalSchedule λ(t) + per-student trace + 常量旁路

### Task D1: `ArrivalSchedule` — 积分归一 + is_constant + thinning

**Files:**
- Create: `backend/simulation/arrival_schedule.py`
- Test: `backend/tests/test_arrival_schedule.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_arrival_schedule.py
import random
from simulation.arrival_schedule import ArrivalSchedule

def test_constant_is_constant_flag():
    s = ArrivalSchedule.constant(rate_per_sec=0.5)
    assert s.is_constant is True
    assert abs(s.lambda_at(0) - 0.5) < 1e-12
    assert abs(s.lambda_at(999) - 0.5) < 1e-12

def test_integral_normalized_to_expected_total():
    # 期望总到达 = total ; 形状随便给，∫λ dt 必须 == total
    s = ArrivalSchedule(total_arrivals=600, horizon_seconds=1800,
                        baseline=0.1, ramp=(300, 900, 1.0),
                        pulses=[(600, 0.5, 60)])
    integral = sum(s.lambda_at(t) for t in range(1800))  # Δt=1s 黎曼和
    assert abs(integral - 600) / 600 < 0.02
    assert s.is_constant is False

def test_thinning_sequence_deterministic_same_seed():
    s = ArrivalSchedule(total_arrivals=300, horizon_seconds=1200,
                        baseline=0.1, ramp=(200, 600, 1.0), pulses=[])
    a = s.sample_arrivals(random.Random(7))
    b = s.sample_arrivals(random.Random(7))
    assert a == b and len(a) > 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_arrival_schedule.py -q`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# backend/simulation/arrival_schedule.py
"""时变到达日程：baseline + 午高峰爬升 + 离散下课脉冲。

不变量：∫₀ᵀ λ(t) dt == total_arrivals（仅时间再分布，不改总量）。
常量场景走 is_constant 旁路，调用方据此用旧 expovariate 路径，
保证与今日行为在仿真语义层完全一致（不额外抽 acceptance）。
trace/实时生成器共用本类同一实例 + 同一 thinning + 同一 streams.arrival。
"""
from dataclasses import dataclass, field
import math


@dataclass
class ArrivalSchedule:
    total_arrivals: float
    horizon_seconds: float
    baseline: float = 1.0
    ramp: tuple = None          # (start_s, end_s, height) 三角爬升；None=无
    pulses: list = field(default_factory=list)  # [(center_s, height, half_width_s)]
    _k: float = field(default=1.0, init=False)
    is_constant: bool = field(default=False, init=False)

    def __post_init__(self):
        self.is_constant = (self.ramp is None and not self.pulses)
        if self.is_constant:
            # 常量：λ ≡ total/horizon（与旧恒定 rate 同口径）
            self._k = 1.0
            self._const = self.total_arrivals / self.horizon_seconds
            return
        # 数值积分原始形状 s(t)，求归一系数 k 使 ∫ k·s = total
        raw = sum(self._shape(t) for t in self._grid())
        self._k = self.total_arrivals / raw if raw > 0 else 0.0

    @classmethod
    def constant(cls, rate_per_sec: float, horizon_seconds: float = 1.0):
        obj = cls(total_arrivals=rate_per_sec * horizon_seconds,
                  horizon_seconds=horizon_seconds)
        return obj

    def _grid(self):
        n = max(1, int(self.horizon_seconds))
        return range(n)

    def _shape(self, t: float) -> float:
        v = self.baseline
        if self.ramp:
            a, b, h = self.ramp
            if a <= t <= b:
                mid = (a + b) / 2.0
                v += h * (1.0 - abs(t - mid) / max(1e-9, (b - a) / 2.0))
        for c, h, w in self.pulses:
            if abs(t - c) <= w:
                v += h * (1.0 - abs(t - c) / max(1e-9, w))
        return max(0.0, v)

    def lambda_at(self, t: float) -> float:
        if self.is_constant:
            return self._const
        return self._k * self._shape(t)

    def lambda_max(self) -> float:
        if self.is_constant:
            return self._const
        return max(self.lambda_at(t) for t in self._grid())

    def sample_arrivals(self, rng) -> list:
        """非齐次泊松 thinning（Lewis–Shedler）。返回到达时刻列表。
        常量场景：调用方应改走旧 expovariate 路径，不应调用本方法。"""
        out, t = [], 0.0
        lmax = self.lambda_max()
        if lmax <= 0:
            return out
        while True:
            t += rng.expovariate(lmax)
            if t >= self.horizon_seconds:
                return out
            if rng.random() <= self.lambda_at(t) / lmax:
                out.append(t)
```

- [ ] **Step 4: Run test to verify pass**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_arrival_schedule.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/simulation/arrival_schedule.py backend/tests/test_arrival_schedule.py
git commit -m "feat(sim): ArrivalSchedule λ(t) — integral-normalized, is_constant bypass, thinning"
```

### Task D2: 常量旁路 — `build_single_canteen_traces` 等价首测（硬验收）

**Files:**
- Modify: `backend/simulation/student_trace.py` (`build_single_canteen_traces`, 约 20-40)
- Test: `backend/tests/test_arrival_schedule.py` (append) + `backend/tests/test_student_trace.py` (regression)

- [ ] **Step 1: Write the failing test (constant ≡ legacy, 仿真语义一致)**

```python
# append to backend/tests/test_arrival_schedule.py
def test_constant_schedule_arrivals_match_legacy_expovariate():
    """硬验收首测：常量 schedule 经新路径产生的到达时刻序列
    与旧 build_single_canteen_traces 逐项一致（同 seed，仿真语义层）。"""
    from simulation.random_streams import build_random_streams
    from simulation.student_trace import build_single_canteen_traces
    cfg = {"arrival_rate": 6.0, "total_time": 30}
    t1 = [round(t.arrival_at, 9)
          for t in build_single_canteen_traces(cfg, build_random_streams(99))]
    t2 = [round(t.arrival_at, 9)
          for t in build_single_canteen_traces(cfg, build_random_streams(99))]
    assert t1 == t2 and len(t1) > 0   # 确定性
    # 与历史基线对齐：未配 λ(t) 时必须仍是恒定速率 expovariate（旁路）
    import random
    rate = cfg["arrival_rate"] / 60.0
    streams = build_random_streams(99)
    expect, acc = [], 0.0
    while True:
        acc += streams.arrival.expovariate(rate)
        if acc >= cfg["total_time"] * 60.0:
            break
        expect.append(round(acc, 9))
    assert t1 == expect
```

- [ ] **Step 2: Run to verify it fails or passes**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_arrival_schedule.py::test_constant_schedule_arrivals_match_legacy_expovariate -q`
Expected: PASS already if `build_single_canteen_traces` unchanged (it currently *is* legacy expovariate). This test **locks** the bypass invariant before D3 touches the file.

- [ ] **Step 3: Add `service_z/eat_z` already present — assert trace fields**

`StudentTrace` already has `arrival_at, patience_z, service_z, eat_z` (student_trace.py:5). No code change in this task; the test above guarantees D3 must not break legacy constant behavior.

- [ ] **Step 4: Run regression**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_student_trace.py backend/tests/test_arrival_schedule.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_arrival_schedule.py
git commit -m "test(sim): lock constant-schedule≡legacy expovariate hard-acceptance (semantic identity)"
```

### Task D3: trace 生成器 + 实时生成器共用 ArrivalSchedule（非常量启用 λ(t)）

**Files:**
- Modify: `backend/simulation/student_trace.py` (`build_single_canteen_traces`)
- Modify: `backend/simulation/arrival_generator.py` (`_run`, 约 84-131; `_compute_arrival_rate_per_minute`)
- Test: `backend/tests/test_arrival_schedule.py` (append) + regressions `test_arrival_generator.py`

- [ ] **Step 1: Write the failing test (shared model: trace replay == live)**

```python
# append to backend/tests/test_arrival_schedule.py
def test_trace_and_live_share_schedule_same_seed():
    """非常量 λ(t)：trace 预生成与实时生成器在同 seed 下到达时刻序列一致。"""
    from simulation.arrival_schedule import ArrivalSchedule
    from simulation.random_streams import build_random_streams
    sch = ArrivalSchedule(total_arrivals=200, horizon_seconds=600,
                          baseline=0.1, ramp=(150, 450, 1.0), pulses=[(300,0.6,40)])
    a = sch.sample_arrivals(build_random_streams(5).arrival)
    b = sch.sample_arrivals(build_random_streams(5).arrival)
    assert a == b and len(a) > 0
```

- [ ] **Step 2: Run to verify pass** (ArrivalSchedule already deterministic)

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_arrival_schedule.py -q`
Expected: PASS.

- [ ] **Step 3: Wire schedule into trace + live generators (non-constant only)**

In `student_trace.py` `build_single_canteen_traces`: if `config` carries an `arrival_schedule` dict (peak params), build `ArrivalSchedule` and use `sample_arrivals(streams.arrival)`; **else keep the existing constant `expovariate` loop verbatim** (preserves D2 lock). For each arrival emit `StudentTrace(arrival_at=t, patience_z=streams.routing.normalvariate(0,1), service_z=streams.service.normalvariate(0,1), eat_z=streams.eat.normalvariate(0,1))` exactly as today.

In `arrival_generator.py` `_run`: when `config["campus"]` carries an `arrival_schedule`, build the **same** `ArrivalSchedule` and replay its `sample_arrivals(self.rng)` (the rng here is `streams.arrival` via coordinator); else keep the existing constant path. Pre-generated `_student_traces` path (already in `_run`) stays the authoritative replay for the single-canteen facade.

- [ ] **Step 4: Run targeted + full regression**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_arrival_generator.py backend/tests/test_student_trace.py backend/tests/test_arrival_schedule.py backend/tests/test_engine.py -q` then full `pytest backend/tests -q`.
Expected: all green, constant-bypass lock (D2) still PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/simulation/student_trace.py backend/simulation/arrival_generator.py backend/tests/test_arrival_schedule.py
git commit -m "feat(sim): trace+live generators share ArrivalSchedule; constant path bypass preserved"
```

---

## Phase E — 窗口干预 API + interventions 持久化全链 + 即时可查

### Task E1: `db_migrate` 幂等加 `interventions_json`

**Files:**
- Modify: `backend/api/db_migrate.py` (`migrate`, 约 20-71)
- Test: `backend/tests/test_db_migration.py` (既有，append)

- [ ] **Step 1: Write the failing test**

```python
# append to backend/tests/test_db_migration.py
import sqlite3, tempfile, os
from api.db_migrate import migrate

def test_interventions_json_column_idempotent():
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
    try:
        migrate(path); migrate(path)  # 重入幂等
        with sqlite3.connect(path) as c:
            cols = [r[1] for r in c.execute("PRAGMA table_info(campus_snapshot)")]
        assert "interventions_json" in cols
    finally:
        os.unlink(path)
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_db_migration.py -q`
Expected: FAIL (`interventions_json` not in columns).

- [ ] **Step 3: Implement — mirror the existing idempotent ALTER pattern**

In `db_migrate.migrate`, after the `campus_snapshot` `CREATE TABLE IF NOT EXISTS` block, add:

```python
if _table_exists(c, "campus_snapshot") and not _column_exists(
        c, "campus_snapshot", "interventions_json"):
    c.execute("ALTER TABLE campus_snapshot ADD COLUMN interventions_json TEXT")
```

(Uses existing `_table_exists`/`_column_exists` helpers; `conn.commit()` already at end.)

- [ ] **Step 4: Run test + regression**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_db_migration.py -q` then full suite.
Expected: PASS, idempotent.

- [ ] **Step 5: Commit**

```bash
git add backend/api/db_migrate.py backend/tests/test_db_migration.py
git commit -m "feat(db): idempotent interventions_json column on campus_snapshot"
```

### Task E2: `CampusCoordinator.interventions[]` + window toggle 后端语义

**Files:**
- Modify: `backend/simulation/coordinator.py` (`__init__`, `snapshot`); add `toggle_window`
- Test: `backend/tests/test_window_intervention.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to backend/tests/test_window_intervention.py
import simpy
from simulation.coordinator import CampusCoordinator
from simulation.presets.loader import load_single_canteen_preset
from simulation.random_streams import build_random_streams
import random

def _coord():
    cfg = load_single_canteen_preset()["config"]
    return CampusCoordinator(simpy.Environment(), cfg,
        random.Random(1), random_streams=build_random_streams(1))

def test_toggle_close_then_open_idempotent_and_event_logged():
    co = _coord(); cid = next(iter(co.canteens)); c = co.canteens[cid]
    w = next(w for w in c.windows if w.is_open)
    r1 = co.toggle_window(cid, w.id, open=False)
    assert r1["status"] == "applied" and w.is_open is False
    r2 = co.toggle_window(cid, w.id, open=False)   # 重复关
    assert r2["status"] == "applied"               # idempotent 返回
    assert co.toggle_window(cid, w.id, open=True)["status"] == "applied"
    assert w.is_open is True
    assert any(e["action"] in ("open","close") for e in co.interventions)

def test_cannot_close_last_open_window():
    co = _coord(); cid = next(iter(co.canteens)); c = co.canteens[cid]
    opened = [w for w in c.windows if w.is_open]
    for w in opened[:-1]:
        co.toggle_window(cid, w.id, open=False)
    last = opened[-1]
    res = co.toggle_window(cid, last.id, open=False)
    assert res["status"] == "rejected" and last.is_open is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_window_intervention.py -q`
Expected: FAIL (`toggle_window`/`interventions` missing).

- [ ] **Step 3: Implement in `coordinator.py`**

In `__init__` add: `self.interventions: list = []`.

Add method:

```python
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
```

In `snapshot()` add to the returned dict: `"interventions": list(self.interventions)`.

- [ ] **Step 4: Run test + regression**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_window_intervention.py backend/tests/test_coordinator.py -q` then full suite.
Expected: all green. Drain semantics (no SimPy request touched) hold because `toggle_window` only flips `is_open`.

- [ ] **Step 5: Commit**

```bash
git add backend/simulation/coordinator.py backend/tests/test_window_intervention.py
git commit -m "feat(sim): CampusCoordinator.toggle_window + interventions[] + reject-last-open + snapshot透出"
```

### Task E3: 干预 API endpoint + 即时 append+flush + 持久化全链

**Files:**
- Modify: `backend/api/campus_routes.py` (`_compact_snapshot` 106-114, `_flush_campus_snapshots` 121-147, `_load_campus_history_rows` 150-172; add toggle route)
- Test: `backend/tests/test_campus_intervention_api.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_campus_intervention_api.py
import json, pytest
from app import create_app

@pytest.fixture
def client(tmp_path, monkeypatch):
    import api.routes as r
    monkeypatch.setattr(r, "DB_PATH", str(tmp_path / "t.db"))
    app = create_app(); app.config.update(TESTING=True)
    return app.test_client()

def _start_single(client):
    pre = client.get("/api/campus/presets/single-canteen").get_json()
    client.post("/api/campus/config", json=pre["config"])
    client.post("/api/campus/start")

def test_intervention_visible_in_history_immediately(client):
    _start_single(client)
    client.get("/api/campus/step?display_tick_seconds=5")
    cfg = client.get("/api/campus/status").get_json()
    cid = cfg["canteen_order"][0]
    res = client.post(f"/api/campus/canteens/{cid}/windows/0/toggle",
                       json={"open": False})
    assert res.status_code == 200
    body = res.get_json()
    assert body["interventions"][-1]["window_id"] == 0
    # 立即查 history 必须能看到该 intervention（不等 flush 阈值）
    hist = client.get("/api/campus/history").get_json()
    assert any(h.get("interventions") and
               any(i["window_id"] == 0 for i in h["interventions"])
               for h in hist)
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_campus_intervention_api.py -q`
Expected: FAIL (route 404 / history lacks interventions).

- [ ] **Step 3: Implement**

(a) `_compact_snapshot(state, event_type)` — add `"interventions": state.get("interventions", [])` to the returned dict.

(b) `_flush_campus_snapshots()` — extend INSERT column list + values to include `interventions_json`:
```python
'''INSERT INTO campus_snapshot
   (config_id, current_time, campus_totals_json, canteens_json,
    in_transit_json, interventions_json, event_type)
   VALUES (?, ?, ?, ?, ?, ?, ?)'''
```
with `json.dumps(s.get('interventions', []), ensure_ascii=False)` in the tuple. **同时改两处**：SQL 列清单/占位符 **和** `_flush_campus_snapshots` 第 134-144 行的列表推导式 values 元组，二者按位置一一对应（只改 SQL 不改元组会写错列）。

(c) `_load_campus_history_rows()` — add `s.interventions_json` to SELECT and `item['interventions'] = json.loads(item.pop('interventions_json') or '[]')`.

(d) Add route:
```python
@campus_bp.post('/canteens/<cid>/windows/<int:wid>/toggle')
def toggle_window(cid, wid):
    coordinator, error = _ensure_campus_initialized()
    if error is not None:
        return error
    open_ = bool((request.get_json(silent=True) or {}).get('open', True))
    ev = coordinator.toggle_window(cid, wid, open=open_)
    state = _snapshot('intervention')
    _session()['snapshot_buffer'].append(_compact_snapshot(state, 'intervention'))
    _flush_campus_snapshots()       # 立即落库，保证 history 即时可查
    return jsonify(state)
```

- [ ] **Step 4: Run test + regression**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_campus_intervention_api.py backend/tests/test_campus_api.py -q` then full `pytest backend/tests -q`.
Expected: all green; Phase 2 `simulation_snapshot`/`engine._compact_snapshot` untouched.

- [ ] **Step 5: Commit**

```bash
git add backend/api/campus_routes.py backend/tests/test_campus_intervention_api.py
git commit -m "feat(campus): window toggle API + interventions persistence chain + immediate flush"
```

---

## Phase F — 同 seed A/B 硬验收

### Task F1: baseline vs intervention 差异归因于干预

**Files:**
- Test: `backend/tests/test_campus_reproducibility_ab.py` (append)

- [ ] **Step 1: Write the test**

```python
# append to backend/tests/test_campus_reproducibility_ab.py
def test_intervention_changes_attributable_not_rng():
    import simpy, random
    from simulation.coordinator import CampusCoordinator
    from simulation.random_streams import build_random_streams
    from simulation.presets.loader import load_single_canteen_preset

    def run(seed, close_at=None):
        cfg = load_single_canteen_preset()["config"]
        co = CampusCoordinator(simpy.Environment(), cfg,
            random.Random(seed), random_streams=build_random_streams(seed))
        cid = next(iter(co.canteens))
        sim_s = cfg["campus"]["simulation_seconds"]
        if close_at is None:
            co.env.run(until=sim_s)
        else:
            co.env.run(until=close_at)
            for w in [w for w in co.canteens[cid].windows if w.is_open][:1]:
                co.toggle_window(cid, w.id, open=False)
            co.env.run(until=sim_s)
        snap = co.snapshot()
        return snap["campus_totals"], len(co.interventions)

    base_a = run(2024); base_b = run(2024)
    assert base_a == base_b                       # 无干预、同 seed → 完全一致
    interv, n = run(2024, close_at=60)
    assert n >= 1                                 # 干预确实发生
    assert interv != base_a                       # 差异来自干预（非随机噪声）
```

- [ ] **Step 2: Run to verify it passes**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_campus_reproducibility_ab.py -q`
Expected: PASS (3 passed: same-seed identity, intervention attributable).

- [ ] **Step 3: Full regression gate**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q`
Expected: all green (≥ 184 + new). This is the §6.2 hard-acceptance proof of "not fake animation".

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_campus_reproducibility_ab.py
git commit -m "test(campus): same-seed A/B hard acceptance — intervention-attributable, no RNG noise"
```

---

## Phase G — 前端 scene3d 拆分（facade 保持）+ state_adapter

### Task G1: state_adapter + scene3d core split（契约不破）

**Files:**
- Create: `frontend/static/js/three/state_adapter.js`, `frontend/static/js/three/canteen_scene.js`, `frontend/static/js/three/intervention_ui.js`
- Modify: `frontend/static/js/three/scene3d.js`
- Modify: `backend/tests/test_frontend_three_js_contract.py` (扩展契约)
- Modify: `frontend/templates/index.html` (加载新模块)

- [ ] **Step 1: Write the failing contract test**

```python
# extend backend/tests/test_frontend_three_js_contract.py
from pathlib import Path
THREE_DIR = Path(__file__).resolve().parents[2] / "frontend/static/js/three"

def test_scene3d_modules_exist_and_facade_preserved():
    s = (THREE_DIR / "scene3d.js").read_text(encoding="utf-8")
    for snippet in ("window.CanteenApp3D = {", "init(container)",
                    "render(snapshot, appState)", "dispose()",
                    "visibleCanteens", "pendingCanteens"):
        assert snippet in s              # 既有契约不破
    for m in ("state_adapter.js", "canteen_scene.js", "intervention_ui.js"):
        assert (THREE_DIR / m).exists()
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py -q`
Expected: FAIL (new modules absent).

- [ ] **Step 3: Implement split**

- `state_adapter.js`: export `window.CanteenApp3D = window.CanteenApp3D || {}`; `CanteenApp3D.adapt(prevSnap, nextSnap, tNorm)` → interpolated render targets (no statistics invented; jitter only anti-overlap).
- `canteen_scene.js`: multi-floor stack build + A+C camera state machine (overview stacked-cutaway ⇄ focus single floor with non-focused floors slid away), flow-path highlight + single-student track, 冷青 palette (reuse scene3d colors `0x07111d`/`0x315467`/`0x2dd4bf`, congestion teal→amber→red).
- `intervention_ui.js`: 三段运维台 DOM (KPI / per-floor window grid / intervention log) + `POST /api/campus/canteens/<cid>/windows/<wid>/toggle`.
- `scene3d.js`: keep `init/render/dispose` + `visibleCanteens/pendingCanteens` tokens; delegate scene build to `canteen_scene`, interpolation to `state_adapter`. Public facade unchanged.
- `index.html`: add `<script>` tags for the 3 new modules after scene3d importmap (keep module type as existing).

- [ ] **Step 4: Verify contract + JS syntax**

Run:
```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py -q
node --input-type=module --check < frontend/static/js/three/scene3d.js
node --input-type=module --check < frontend/static/js/three/canteen_scene.js
node --input-type=module --check < frontend/static/js/three/state_adapter.js
node --input-type=module --check < frontend/static/js/three/intervention_ui.js
```
Expected: pytest PASS; all `node --check` exit 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/static/js/three/scene3d.js frontend/static/js/three/canteen_scene.js frontend/static/js/three/state_adapter.js frontend/static/js/three/intervention_ui.js frontend/templates/index.html backend/tests/test_frontend_three_js_contract.py
git commit -m "feat(3d): split scene3d into core/canteen_scene/state_adapter/intervention_ui (facade preserved)"
```

---

## Phase H — 前端主入口绑定 + 3D 默认 + 冷青 identity

### Task H1: main.js preset-first → single-canteen；renderMode 默认 3d（保 2D）

**Files:**
- Modify: `frontend/static/js/main.js` — add `loadSingleCanteenPreset()`; repoint default-entry callers `syncModeForms`(~147)/`getCampusConfigForSubmit`(~203-214); **keep `loadDefaultCampusPreset()` + its `/campus/presets/default` literal intact (legacy/manual path)**; change **both** `renderMode` occurrences to `'3d'` — state init (line 14 `renderMode: '2d'`) **and** `resetSimulationState()` (line 343 `state.renderMode = '2d';`); keep 2D fallback branches.
- Modify: `frontend/static/css/style.css` (three-stage / 三段面板 / 冷青)
- Test: `backend/tests/test_frontend_main_js_contract.py` — **deliberately** update line 35 assertion `renderMode: '2d'` → `renderMode: '3d'` (this pinned the OLD default; user-approved spec makes 3D default — intentional contract change, not silent breakage); the legacy literals at lines 49-50 (`async function loadDefaultCampusPreset()`, `/campus/presets/default`) **must stay green** (legacy fn retained); add new single-canteen assertions.

- [ ] **Step 1: Write the failing contract test**

```python
# 1) DELIBERATE edit to existing test_main_js_state_has_campus_control_fields:
#    change the pinned default `renderMode: '2d'` → `renderMode: '3d'` (line 35).
# 2) ADD the new contract test below. It asserts the NEW single-canteen
#    default entry AND that the legacy loadDefaultCampusPreset literals are
#    retained (so test_main_js_loads_campus_preset_without_hiding_manual_json_edits
#    at lines 42-61 stays green).
from pathlib import Path
MAIN = Path(__file__).resolve().parents[2] / "frontend/static/js/main.js"

def test_preset_first_uses_single_canteen_and_3d_default():
    s = MAIN.read_text(encoding="utf-8")
    # new default entry → single-canteen
    assert "async function loadSingleCanteenPreset()" in s
    assert "/api/campus/presets/single-canteen" in s
    # legacy path retained (keeps existing contract test green)
    assert "async function loadDefaultCampusPreset()" in s
    assert "/campus/presets/default" in s
    # 3D default in BOTH spots; no residual '2d' default
    assert "renderMode: '3d'" in s
    assert "state.renderMode = '3d';" in s
    assert "renderMode: '2d'" not in s
    assert "state.renderMode = '2d';" not in s
    # 2D fallback code path still present (WebGL-unavailable)
    assert "canvas_renderer" in s.lower() or "CanvasRenderer" in s
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_main_js_contract.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement (explicit reconciliation — do not break existing contract)**

- **Keep** `async function loadDefaultCampusPreset()` and its `fetch('/campus/presets/default')` literal **defined and intact** (legacy/manual path). This keeps `test_main_js_loads_campus_preset_without_hiding_manual_json_edits` (contract :42-61) green.
- **Add** `async function loadSingleCanteenPreset()` that fetches `/api/campus/presets/single-canteen` and runs the same `applyCampusPresetMetadata(data)` flow.
- Repoint the **default-entry** callers to the single-canteen path: in `syncModeForms()` (~147) and `getCampusConfigForSubmit()` (~203-214), call `loadSingleCanteenPreset()` instead of `loadDefaultCampusPreset()`. `loadDefaultCampusPreset()` remains reachable only via the explicit manual/legacy branch (not the default).
- Change **both** `renderMode` occurrences to `'3d'`: state initializer `main.js:14` (`renderMode: '2d'` → `renderMode: '3d'`) **and** `resetSimulationState()` `main.js:343` (`state.renderMode = '2d';` → `state.renderMode = '3d';`). Keep every 2D fallback branch (`CanvasRenderer`/WebGL-unavailable) intact.
- **Deliberately** edit `backend/tests/test_frontend_main_js_contract.py:35`: change the pinned `"renderMode: '2d'"` assertion to `"renderMode: '3d'"`. Rationale (state in commit msg): that assertion encoded the OLD default; the user-approved spec §4/§1 makes 3D the default — this is an intentional, reviewed contract update, not silent weakening. Do **not** touch lines 49-50.
- CSS: dark teal `#07111d` stage bg, three-section ops panel, congestion legend; keep existing classes.

- [ ] **Step 4: Verify (whole contract file + full suite, prove no regression)**

Run:
```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_main_js_contract.py -q
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q
node --check frontend/static/js/main.js
```
Expected: contract file all green — `test_main_js_loads_campus_preset_without_hiding_manual_json_edits` (legacy literals retained), updated `test_main_js_state_has_campus_control_fields` (now `renderMode: '3d'`), new `test_preset_first_uses_single_canteen_and_3d_default` all PASS. Full suite ≥184+new green. `node` exit 0. If `test_main_js_loads_campus_preset_without_hiding_manual_json_edits` is red → the legacy `loadDefaultCampusPreset`/`/campus/presets/default` literals were removed; restore them (legacy fn must stay defined).

- [ ] **Step 5: Commit**

```bash
git add frontend/static/js/main.js frontend/static/css/style.css backend/tests/test_frontend_main_js_contract.py
git commit -m "feat(frontend): preset-first → single-canteen, 3D default main screen, 2D fallback kept"
```

---

## Phase I — 集成 + 浏览器 E2E 证据 + 全量回归

### Task I1: 全量回归 + 浏览器 E2E 证据闭环

**Files:**
- Modify: `docs/phase3/browser_e2e_check.md`, `docs/phase3/screenshots/` (证据), `docs/phase3/screenshots/three-result.json`

- [ ] **Step 1: Full backend regression gate**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q`
Expected: all green (≥ 184 + all new Phase A–H tests). Any red → stop, fix before E2E.

- [ ] **Step 2: JS syntax gate**

Run:
```bash
node --check frontend/static/js/main.js
node --check frontend/static/js/canvas_renderer.js
for f in scene3d canteen_scene state_adapter intervention_ui; do
  node --input-type=module --check < frontend/static/js/three/$f.js; done
```
Expected: all exit 0.

- [ ] **Step 3: Browser E2E (record real evidence per spec §6.4)**

Start `PYTHONPATH=backend ./.venv/bin/python backend/app.py`, drive headless Chrome:
- 默认进 3D 主屏（明湖学一 3 层堆叠剖面，冷青）
- λ(t) 高峰下三层排队/热力变化
- 下钻 2F（非焦点层滑开）+ 路径高亮 + 点名追踪
- 三段运维台开/关窗口 → 干预事件流落条 → 立即 `GET /api/campus/history` 含该 intervention
- console error == 0；canvas 非空像素；WebGL 不可用回退；窄屏控件不重叠
Record: screenshots → `docs/phase3/screenshots/`; metrics → `docs/phase3/screenshots/three-result.json`; narrative → `docs/phase3/browser_e2e_check.md`.

- [ ] **Step 4: Commit evidence**

```bash
git add docs/phase3/browser_e2e_check.md docs/phase3/screenshots
git commit -m "test(e2e): 3D single-canteen digital twin browser evidence + intervention causality"
```

---

## Out of scope (单独后续 commit，需评审)
- 删除 5 份过时 3D 文档（spec §0 列表）。
- `docs/phase2/*` 既有未提交改动（与本计划无关，绝不夹带）。

## Plan-level done criteria
- Backend `pytest backend/tests -q` 全绿（184 + 新增 A–F）。
- Phase 2 `/api/config`/`/api/simulation/*`/`_build_state` flat 形状逐字未改；`test_multi_floor.py:29`、default preset 测试不破。
- 同 seed A/B 硬验收通过（无干预完全一致；干预差异可归因）。
- 干预后 `GET /api/campus/history` 即时可见。
- 3D 默认主屏 + 2D 兜底；`CanteenApp3D` 契约不破；E2E 证据落 `docs/phase3/`。
