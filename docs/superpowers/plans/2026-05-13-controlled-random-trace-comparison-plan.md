# Controlled Random Trace Scenario Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把“建议方案重跑”升级为受控随机实验：baseline 和 adjusted 使用同一批学生到达、耐心、服务时长、就餐时长随机输入，避免把随机波动误判为方案改善。

**Architecture:** 后端新增独立随机流和学生输入 trace。`SimulationEngine` 仍保持 Phase 2 单食堂兼容门面，但内部不再依赖全局 `random.seed()`；到达、路由/耐心、服务、就餐分别由独立 `random.Random` 流驱动。前端点击建议方案时先用同一 `rng_seed` 重跑 baseline，再重跑 adjusted，并在 UI 中标注“受控对比”。

**Tech Stack:** Flask, SimPy, Python `random.Random`, plain JavaScript, pytest, existing frontend contract tests.

---

## Scope And Guardrails

- 本轮只做单食堂建议方案对比的可信度加固。
- 不改校园 pending 数据边界，不改学活占位策略，不改变 Phase 2 `/api/simulation/*` 返回形状。
- Trace 和受控随机流只由 `SimulationEngine` 单食堂路径注入；`/api/campus/*` 现有校园模式行为必须保持不变，并由 `backend/tests/test_campus_api.py` 回归守住。
- `/api/config` 可以接受可选 `rng_seed`，但原有不传 seed 的调用必须继续可用。
- 不提交或修改现有 5 个 `docs/phase2/...` 脏文件和未跟踪旧 plan。
- 完成后只提交本功能相关文件，严禁 `git add .`。

## File Structure

- Create: `backend/simulation/random_streams.py`
  - 从一个 master seed 派生 `arrival_rng`, `routing_rng`, `service_rng`, `eat_rng`。
  - 保证同 seed 可复现，不同 stream 互不共享状态。

- Create: `backend/simulation/student_trace.py`
  - 定义 `StudentTrace`。
  - 基于配置和 stream 预生成学生输入：`arrival_at`, `patience_z`, `service_z`, `eat_z`。
  - 只固定“学生输入随机性”，不固定窗口/座位资源状态。

- Modify: `backend/simulation/queue_sim.py`
  - `sample_serve_time(avg_serve_time, rng=None, z_score=None)`。
  - 有 `z_score` 时按当前配置均值缩放，保证服务优化方案仍能生效。

- Modify: `backend/simulation/dining_sim.py`
  - `sample_eat_time(avg_eat_minutes, rng=None, z_score=None)`。
  - 有 `z_score` 时按当前配置均值缩放。

- Modify: `backend/simulation/student.py`
  - `Student` 增加可选 `trace` 字段。
  - `student_lifecycle()` 用 `student.trace.service_z` / `student.trace.eat_z` 采样服务和就餐时长。

- Modify: `backend/simulation/arrival_generator.py`
  - 支持 `campus_config["_student_traces"]`。
  - 有 trace 时按固定 `arrival_at` 生成学生；无 trace 时保留原 Poisson 到达逻辑。

- Modify: `backend/simulation/coordinator.py`
  - 保存 `random_streams` 或至少暴露 `service_rng` / `eat_rng` 给生命周期使用。

- Modify: `backend/simulation/engine.py`
  - 接收 `rng_seed` 后创建 stream bundle 和 student trace。
  - 删除或停止使用 `random.seed(rng_seed)` 的全局副作用。
  - `_to_single_canteen_config()` 注入 `_student_traces`。

- Modify: `backend/api/routes.py`
  - `/api/config` 接收可选 `rng_seed`。
  - 用 `SimulationEngine(config, config_id=config_id, rng_seed=rng_seed)` 初始化。
  - 不把 `rng_seed` 写入旧数据库表，避免迁移成本；seed 只存在本次会话配置中。

- Modify: `frontend/static/js/main.js`
  - `runSuggestedScenario()` 生成一次 seed。
  - 用同一 seed 先跑 baseline，再跑 adjusted。
  - 不再直接拿当前页面上一次随机结果当 baseline。

- Modify: `frontend/static/js/analysis_charts.js`
  - comparison summary 支持显示 seed / “受控对比”文案。

- Modify: `frontend/templates/index.html`
  - 在 scenario panel 增加 `id="scenario-seed"` 或复用 `scenario-adjustment` 显示受控 seed。

- Tests:
  - Create: `backend/tests/test_random_streams.py`
  - Create: `backend/tests/test_student_trace.py`
  - Modify: `backend/tests/test_engine_facade.py`
  - Modify: `backend/tests/test_api.py`
  - Modify: `backend/tests/test_frontend_main_js_contract.py`
  - Modify: `backend/tests/test_frontend_analysis_charts_contract.py`

---

### Task 0: Safety Baseline

**Files:**
- Read only: git status and relevant existing files.

- [ ] **Step 1: Check dirty state**

Run:

```bash
git status --short
```

Expected: only the known unrelated `docs/phase2/...` files and old untracked plan are dirty before implementation.

- [ ] **Step 2: Run current focused tests**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_engine_facade.py backend/tests/test_api.py backend/tests/test_frontend_main_js_contract.py backend/tests/test_frontend_analysis_charts_contract.py -q
```

Expected: PASS before edits.

---

### Task 1: Add Independent Random Streams

**Files:**
- Create: `backend/simulation/random_streams.py`
- Test: `backend/tests/test_random_streams.py`

- [ ] **Step 1: Write failing tests**

Add tests:

```python
from simulation.random_streams import build_random_streams


def test_streams_are_reproducible_for_same_master_seed():
    a = build_random_streams(1234)
    b = build_random_streams(1234)

    assert a.arrival.random() == b.arrival.random()
    assert a.routing.random() == b.routing.random()
    assert a.service.random() == b.service.random()
    assert a.eat.random() == b.eat.random()


def test_streams_do_not_share_state_with_each_other():
    untouched = build_random_streams(1234)
    consumed = build_random_streams(1234)

    consumed.arrival.random()
    consumed.arrival.random()

    assert consumed.service.random() == untouched.service.random()
    assert consumed.eat.random() == untouched.eat.random()
```

- [ ] **Step 2: Run red test**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_random_streams.py -q
```

Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement streams**

Create:

```python
"""Independent random streams for controlled simulation experiments."""
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class RandomStreams:
    arrival: random.Random
    routing: random.Random
    service: random.Random
    eat: random.Random


def build_random_streams(master_seed=None) -> RandomStreams:
    master = random.Random(master_seed)
    seeds = [master.randrange(1, 2**31 - 1) for _ in range(4)]
    return RandomStreams(
        arrival=random.Random(seeds[0]),
        routing=random.Random(seeds[1]),
        service=random.Random(seeds[2]),
        eat=random.Random(seeds[3]),
    )
```

- [ ] **Step 4: Run green test**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_random_streams.py -q
```

Expected: PASS.

---

### Task 2: Add Student Input Trace

**Files:**
- Create: `backend/simulation/student_trace.py`
- Test: `backend/tests/test_student_trace.py`

- [ ] **Step 1: Write failing tests**

Add tests:

```python
from simulation.random_streams import build_random_streams
from simulation.router import RouterConfig
from simulation.student_trace import build_single_canteen_traces


BASE_CONFIG = {
    "window_count": 4,
    "seat_count": 80,
    "avg_serve_time": 30,
    "avg_eat_time": 15,
    "arrival_rate": 5,
    "total_time": 20,
}


def test_single_canteen_trace_is_reproducible():
    a = build_single_canteen_traces(BASE_CONFIG, build_random_streams(42))
    b = build_single_canteen_traces(BASE_CONFIG, build_random_streams(42))

    assert a == b
    assert a
    assert a[0].arrival_at > 0


def test_capacity_changes_do_not_change_student_random_inputs():
    adjusted = dict(BASE_CONFIG, window_count=6, seat_count=120)

    a = build_single_canteen_traces(BASE_CONFIG, build_random_streams(42))
    b = build_single_canteen_traces(adjusted, build_random_streams(42))

    assert [(x.arrival_at, x.patience_z, x.service_z, x.eat_z) for x in a] == [
        (x.arrival_at, x.patience_z, x.service_z, x.eat_z) for x in b
    ]


def test_service_or_eat_mean_changes_do_not_change_student_random_inputs():
    adjusted = dict(BASE_CONFIG, avg_serve_time=24, avg_eat_time=12)

    a = build_single_canteen_traces(BASE_CONFIG, build_random_streams(42))
    b = build_single_canteen_traces(adjusted, build_random_streams(42))

    assert [(x.arrival_at, x.patience_z, x.service_z, x.eat_z) for x in a] == [
        (x.arrival_at, x.patience_z, x.service_z, x.eat_z) for x in b
    ]


def test_trace_converts_patience_z_with_router_config():
    trace = build_single_canteen_traces(BASE_CONFIG, build_random_streams(42))[0]
    zero = type(trace)(
        arrival_at=trace.arrival_at,
        patience_z=0.0,
        service_z=trace.service_z,
        eat_z=trace.eat_z,
    )
    very_low = type(trace)(
        arrival_at=trace.arrival_at,
        patience_z=-100.0,
        service_z=trace.service_z,
        eat_z=trace.eat_z,
    )
    router_cfg = RouterConfig(
        patience_mean_seconds=180.0,
        patience_std_seconds=60.0,
        patience_min_seconds=30.0,
    )

    assert zero.to_patience_seconds(router_cfg) == 180.0
    assert very_low.to_patience_seconds(router_cfg) == 30.0
```

- [ ] **Step 2: Run red test**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_student_trace.py -q
```

Expected: FAIL because trace module does not exist.

- [ ] **Step 3: Implement trace generation**

Create `StudentTrace` with `arrival_at`, `patience_z`, `service_z`, `eat_z`, and:

```python
def to_patience_seconds(self, router_config):
    raw = (
        router_config.patience_mean_seconds
        + self.patience_z * router_config.patience_std_seconds
    )
    return max(router_config.patience_min_seconds, raw)
```

Important implementation detail:

```python
interval = streams.arrival.expovariate(float(config["arrival_rate"]) / 60.0)
arrival_at += interval
```

Stop when `arrival_at >= total_time * 60`.

Use `streams.routing.normalvariate(0.0, 1.0)` for patience z, `streams.service.normalvariate(0.0, 1.0)` for service z, and `streams.eat.normalvariate(0.0, 1.0)` for eat z.

- [ ] **Step 4: Run green test**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_student_trace.py -q
```

Expected: PASS.

---

### Task 3: Route Service And Eating Through Trace-Aware Sampling

**Files:**
- Modify: `backend/simulation/queue_sim.py`
- Modify: `backend/simulation/dining_sim.py`
- Modify: `backend/simulation/student.py`
- Test: `backend/tests/test_queue_sim.py`
- Test: `backend/tests/test_dining_sim.py`
- Test: `backend/tests/test_student_lifecycle.py`

- [ ] **Step 1: Add tests for z-score sampling**

Add focused assertions:

```python
def test_sample_serve_time_accepts_z_score():
    assert sample_serve_time(30, z_score=0.0) == 30
    assert sample_serve_time(30, z_score=-100.0) == 1.0


def test_sample_eat_time_accepts_z_score():
    assert sample_eat_time(15, z_score=0.0) == 900
    assert sample_eat_time(15, z_score=-100.0) == 60.0
```

- [ ] **Step 2: Run red tests**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_queue_sim.py backend/tests/test_dining_sim.py -q
```

Expected: FAIL because the functions do not accept `z_score`.

- [ ] **Step 3: Implement optional rng/z-score parameters**

Expected shape:

```python
def sample_serve_time(avg_serve_time, rng=None, z_score=None):
    std = avg_serve_time * 0.2
    if z_score is None:
        source = rng if rng is not None else random
        serve_time = source.normalvariate(avg_serve_time, std)
    else:
        serve_time = avg_serve_time + z_score * std
    return max(1.0, serve_time)
```

Use the same pattern for `sample_eat_time()`, with minutes converted to seconds first.

- [ ] **Step 4: Attach trace to `Student` and consume it**

In `Student`, add:

```python
trace: object = None
```

In `student_lifecycle()`:

```python
trace = getattr(student, "trace", None)
service_duration = sample_serve_time(
    canteen.avg_serve_time,
    rng=coordinator.service_rng,
    z_score=getattr(trace, "service_z", None),
)
```

Use the same pattern for `eat_duration` with `coordinator.eat_rng`.

- [ ] **Step 5: Run focused tests**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_queue_sim.py backend/tests/test_dining_sim.py backend/tests/test_student_lifecycle.py -q
```

Expected: PASS.

---

### Task 4: Use Trace In Single-Canteen SimulationEngine

**Files:**
- Modify: `backend/simulation/coordinator.py`
- Modify: `backend/simulation/engine.py`
- Modify: `backend/simulation/arrival_generator.py`
- Test: `backend/tests/test_engine_facade.py`
- Test: `backend/tests/test_arrival_generator.py`

- [ ] **Step 1: Write failing engine tests**

Add tests:

```python
def run_to_end(config, seed):
    engine = SimulationEngine(config, config_id=0, rng_seed=seed)
    engine.start()
    while True:
        state = engine.step()
        if state["is_ended"]:
            return state


def test_same_seed_same_config_is_reproducible(basic_config):
    a = run_to_end(basic_config, seed=20260513)
    b = run_to_end(basic_config, seed=20260513)

    assert a["total_arrived"] == b["total_arrived"]
    assert a["total_served"] == b["total_served"]
    assert a["avg_waiting_time"] == b["avg_waiting_time"]


def test_same_seed_capacity_change_keeps_same_arrivals(basic_config):
    adjusted = dict(basic_config, window_count=basic_config["window_count"] + 1)

    baseline = run_to_end(basic_config, seed=20260513)
    changed = run_to_end(adjusted, seed=20260513)

    assert baseline["total_arrived"] == changed["total_arrived"]


def test_same_seed_service_or_eat_change_keeps_same_arrivals(basic_config):
    adjusted = dict(
        basic_config,
        avg_serve_time=basic_config["avg_serve_time"] * 0.8,
        avg_eat_time=basic_config["avg_eat_time"] * 0.8,
    )

    baseline = run_to_end(basic_config, seed=20260513)
    changed = run_to_end(adjusted, seed=20260513)

    assert baseline["total_arrived"] == changed["total_arrived"]
```

- [ ] **Step 2: Run red/failing focused test**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_engine_facade.py -q
```

Expected: at least the reproducibility/capacity trace test fails before implementation is wired.

- [ ] **Step 3: Store streams on coordinator**

In `CampusCoordinator`, accept optional `random_streams`; default to streams from `rng` or a new unseeded bundle to preserve non-seeded behavior.

Hard constraint: do not add `_student_traces` in campus preset loading or `/api/campus/*`. The coordinator may expose stream attributes for shared lifecycle code, but controlled trace replay is only activated when `SimulationEngine` injects `_student_traces`.

Expose:

```python
self.routing_rng = random_streams.routing
self.service_rng = random_streams.service
self.eat_rng = random_streams.eat
```

Keep `StudentRouter(..., rng=self.routing_rng)`.

- [ ] **Step 4: Generate and inject trace in `SimulationEngine`**

In `SimulationEngine.__init__()`:

```python
self._streams = build_random_streams(rng_seed)
self._student_traces = build_single_canteen_traces(config, self._streams)
```

Remove global:

```python
random.seed(rng_seed)
```

In `_to_single_canteen_config()`:

```python
"_student_traces": self._student_traces,
```

- [ ] **Step 5: Drive `ArrivalGenerator` from trace**

When `_student_traces` exists:

```python
last_arrival = 0.0
for trace in traces:
    yield self.env.timeout(trace.arrival_at - last_arrival)
    last_arrival = trace.arrival_at
    student = self._spawn_student(trace)
    self.env.process(student_lifecycle(...))
```

`_spawn_student(trace)` must set:

```python
student.trace = trace
student.patience_threshold = trace.to_patience_seconds(router.config)
```

- [ ] **Step 6: Run focused backend tests**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_random_streams.py backend/tests/test_student_trace.py backend/tests/test_engine_facade.py backend/tests/test_arrival_generator.py -q
```

Expected: PASS.

---

### Task 5: Expose Seed Through `/api/config`

**Files:**
- Modify: `backend/api/routes.py`
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Write API tests**

Add tests:

```python
def finish_single(client, config):
    assert client.post("/api/config", json=config).status_code == 200
    assert client.post("/api/simulation/start").status_code == 200
    return client.post("/api/simulation/finish").get_json()


def test_config_forwards_optional_rng_seed(monkeypatch, client):
    captured = {}

    class CapturingEngine:
        def __init__(self, config, config_id=None, rng_seed=None):
            captured["rng_seed"] = rng_seed

    monkeypatch.setattr("api.routes.SimulationEngine", CapturingEngine)

    response = client.post("/api/config", json=dict(CONFIG, rng_seed=20260513))
    assert response.status_code == 200
    assert captured["rng_seed"] == 20260513


def test_config_rejects_non_integer_rng_seed(client):
    response = client.post("/api/config", json=dict(CONFIG, rng_seed="bad-seed"))

    assert response.status_code == 400
    assert "rng_seed" in response.get_json()["error"]


def test_same_seed_api_runs_are_reproducible(client):
    config = dict(CONFIG, rng_seed=20260513)

    a = finish_single(client, config)
    client.post("/api/simulation/reset")
    b = finish_single(client, config)

    assert a["total_arrived"] == b["total_arrived"]
    assert a["total_served"] == b["total_served"]
    assert a["avg_waiting_time"] == b["avg_waiting_time"]
```

- [ ] **Step 2: Run red tests**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_api.py -q
```

Expected: FAIL before `/api/config` parses and forwards `rng_seed`. The old implementation ignores unknown fields, so a plain “accepts optional rng_seed” test is not a valid red test.

- [ ] **Step 3: Implement optional seed parsing**

In `submit_config()`:

```python
rng_seed = payload.get("rng_seed")
if rng_seed is not None:
    try:
        rng_seed = int(rng_seed)
    except (TypeError, ValueError):
        return jsonify({"error": "rng_seed 必须是整数"}), 400
```

Then:

```python
_session["engine"] = SimulationEngine(config, config_id=config_id, rng_seed=rng_seed)
```

- [ ] **Step 4: Run API tests**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_api.py -q
```

Expected: PASS.

---

### Task 6: Make Frontend Scenario Comparison Controlled

**Files:**
- Modify: `frontend/static/js/main.js`
- Modify: `frontend/static/js/analysis_charts.js`
- Modify: `frontend/templates/index.html`
- Test: `backend/tests/test_frontend_main_js_contract.py`
- Test: `backend/tests/test_frontend_analysis_charts_contract.py`

- [ ] **Step 1: Write frontend contract tests**

Add assertions:

```python
def test_main_js_reruns_baseline_and_adjusted_with_same_seed():
    source = MAIN_JS.read_text()

    assert "runSingleScenarioWithSeed" in source
    assert "rng_seed" in source
    assert "const baselineResult = await runSingleScenarioWithSeed(baselineConfig, seed)" in source
    assert "const adjustedResult = await runSingleScenarioWithSeed(suggestion.config, seed)" in source
    assert "renderScenarioComparison(baselineResult, adjustedResult" in source
    assert "renderScenarioComparison(baselineStats, adjustedStats" not in source
```

Add HTML/content assertion:

```python
def test_scenario_panel_labels_controlled_comparison():
    html = INDEX_HTML.read_text()

    assert "scenario-seed" in html
```

- [ ] **Step 2: Run red tests**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_main_js_contract.py backend/tests/test_frontend_analysis_charts_contract.py -q
```

Expected: FAIL before frontend is changed.

- [ ] **Step 3: Implement a reusable frontend runner**

In `main.js`:

```javascript
function buildScenarioSeed() {
    return Date.now() % 1000000000;
}

async function runSingleScenarioWithSeed(config, seed) {
    await apiPost('/simulation/reset');
    const configRes = await apiPost('/config', { ...config, rng_seed: seed });
    if (!configRes.ok) throw new Error(configRes.data.error || '配置失败');
    const startRes = await apiPost('/simulation/start');
    if (!startRes.ok) throw new Error(startRes.data.error || '启动失败');
    const finishRes = await apiPost('/simulation/finish');
    if (!finishRes.ok) throw new Error(finishRes.data.error || '结算失败');
    return finishRes.data;
}
```

Then in `runSuggestedScenario()`:

```javascript
const seed = buildScenarioSeed();
const baselineResult = await runSingleScenarioWithSeed(baselineConfig, seed);
const adjustedResult = await runSingleScenarioWithSeed(suggestion.config, seed);
renderScenarioComparison(baselineResult, adjustedResult, `${suggestion.summary}，受控 seed=${seed}`);
showStatistics(adjustedResult);
```

Important: do not compare the previous uncontrolled `state.lastStatistics` against the adjusted run.

- [ ] **Step 4: Update UI text**

Use concise wording:

```html
<span id="scenario-seed">受控对比：等待运行</span>
```

Do not add long explanatory paragraphs inside the app.

- [ ] **Step 5: Run frontend contract tests**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_main_js_contract.py backend/tests/test_frontend_analysis_charts_contract.py -q
```

Expected: PASS.

---

### Task 7: Verification And Evidence

**Files:**
- No production changes unless failures are found.

- [ ] **Step 1: Syntax checks**

Run:

```bash
node --check frontend/static/js/main.js
node --check frontend/static/js/analysis_charts.js
```

Expected: both exit 0.

- [ ] **Step 2: Backend focused tests**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_random_streams.py backend/tests/test_student_trace.py backend/tests/test_engine_facade.py backend/tests/test_api.py backend/tests/test_campus_api.py backend/tests/test_frontend_main_js_contract.py backend/tests/test_frontend_analysis_charts_contract.py -q
```

Expected: PASS.

- [ ] **Step 3: Full regression**

Run:

```bash
git diff --check
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q
```

Expected: `git diff --check` has no whitespace errors; pytest PASS.

- [ ] **Step 4: Manual API sanity check**

Start app:

```bash
PYTHONPATH=backend ./.venv/bin/python backend/app.py
```

Use browser/API flow:

```text
/api/config with rng_seed=20260513
/api/simulation/start
/api/simulation/finish
/api/simulation/reset
repeat same config and seed
```

Expected: repeated same-seed run has identical `total_arrived`, `total_served`, and `avg_waiting_time`.

- [ ] **Step 5: Browser scenario check**

In the app:

```text
single-canteen config -> start -> finish -> analysis -> run suggested scenario
```

Expected:

- scenario panel says controlled comparison and displays seed.
- baseline and adjusted `total_arrived` are equal in API results for the same seed.
- no console errors.

- [ ] **Step 6: Commit only relevant files**

Run:

```bash
git status --short
git diff --stat
git add backend/simulation/random_streams.py backend/simulation/student_trace.py backend/simulation/queue_sim.py backend/simulation/dining_sim.py backend/simulation/student.py backend/simulation/arrival_generator.py backend/simulation/coordinator.py backend/simulation/engine.py backend/api/routes.py frontend/static/js/main.js frontend/static/js/analysis_charts.js frontend/templates/index.html backend/tests/test_random_streams.py backend/tests/test_student_trace.py backend/tests/test_engine_facade.py backend/tests/test_api.py backend/tests/test_frontend_main_js_contract.py backend/tests/test_frontend_analysis_charts_contract.py
git commit -m "feat(simulation): add controlled random trace comparison"
```

Expected: commit excludes unrelated `docs/phase2/...` and old untracked plan.

---

## Stretch If Time Allows

Only after Tasks 1-7 pass:

- Add a 5-seed batch comparison helper in frontend or backend.
- Report mean delta for average wait, peak queue, and seat utilization.
- Keep this as “多次受控平均”，do not block the main controlled single-seed deliverable on confidence intervals.

## Final Acceptance Checklist

- Same seed + same config gives identical final statistics.
- Same seed + capacity-only change gives identical `total_arrived`.
- Same seed + service/eat mean change gives identical `total_arrived`.
- `/api/campus/*` regression tests still pass, proving campus mode and pending-data boundaries were not changed by trace replay.
- Scenario UI compares controlled baseline against controlled adjusted result, not old page state.
- Existing Phase 2 API callers still work without `rng_seed`.
- Full backend test suite passes.
- `node --check` passes for modified JS files.
