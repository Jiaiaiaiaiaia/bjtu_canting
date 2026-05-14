# 3D Digital Twin Canteen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved 3D-first canteen digital-twin experience while preserving Phase 2 single-canteen API compatibility and proving that runtime window interventions change real SimPy state.

**Architecture:** Keep Flask + SimPy + plain JavaScript. First close the backend intervention hard gates: physical window instantiation, SimPy-safe queue reallocation, and intervention persistence. Only after those gates pass, upgrade the frontend so Three.js is the main campus/canteen experience with 2D as fallback.

**Tech Stack:** Python 3.12+, Flask, SimPy, SQLite, pytest, plain JavaScript ES modules, Three.js, ECharts, browser E2E checks.

**Spec reference:** `docs/superpowers/specs/2026-05-14-3d-digital-twin-canteen-design.md`

---

## Review Hard Constraints

These constraints came from spec review and are mandatory for implementation:

1. **Queue migration must cancel/requeue SimPy requests, not only move Python lists.** Current `student_lifecycle()` joins `window.waiting_students` and then waits on `window.resource.request()`, so a closing-window migration must wake the waiting process, cancel its pending request if not triggered, remove it from the old window list, and re-enter window selection.
2. **Intervention history must have an explicit persistence path.** Add `interventions_json` to `campus_snapshot` and include interventions in `_compact_snapshot()`, `_flush_campus_snapshots()`, and campus history APIs. Do not hide interventions inside unrelated fields.
3. **"Increase open windows" means opening pre-instantiated physical windows.** Build all `physical_count` windows at `Canteen` initialization. `active_count` only marks the initial `is_open=True` subset. Do not dynamically create new Window objects during a running simulation.
4. **Implementation order follows backend consistency first.** Complete backend intervention semantics and persistence before wiring the 3D UI.
5. **Do not stage unrelated files.** Existing `docs/phase2/*` modifications and the old untracked `docs/superpowers/plans/2026-05-12-threejs-canteen-v7-plan.md` are not part of this implementation plan unless the user explicitly asks.

---

## File Map

### Backend Simulation

- Modify `backend/simulation/canteen.py`
  - Add `Window.is_open`, `Window.closing`, `Window.intervention_event`, and helpers for open/close/requeue signaling.
  - Instantiate `physical_count` windows, with `active_count` determining initial open state.
  - Add canteen-level helpers for counting open windows, closing/opening a window, and finding open candidate windows.
- Modify `backend/simulation/student.py`
  - Extend the queue wait `yield` to include a window requeue/intervention event.
  - Cancel pending SimPy requests and re-loop when a queued student is moved from a closing window.
- Modify `backend/simulation/coordinator.py`
  - Add a `toggle_window()` or equivalent campus-level intervention method.
  - Record interventions in coordinator/session state for snapshots.

### Backend API and Persistence

- Modify `backend/api/campus_routes.py`
  - Add `POST /api/campus/canteens/<canteen_id>/floors/<floor_id>/windows/<window_id>/toggle`.
  - Add interventions to compact snapshots and history responses.
- Modify `backend/api/db_migrate.py`
  - Add `interventions_json` to `campus_snapshot`.
- Modify tests:
  - `backend/tests/test_window_intervention.py` (new)
  - `backend/tests/test_student_window_intervention.py` (new)
  - `backend/tests/test_campus_intervention_api.py` (new)
  - `backend/tests/test_db_migration.py`
  - `backend/tests/test_campus_api.py`

### Frontend 3D

- Modify `frontend/templates/index.html`
  - Make the Three.js stage the campus-mode simulation main surface.
  - Keep fallback controls available but not as the primary path.
- Modify `frontend/static/js/three/scene3d.js`
  - Keep it as the public 3D entrypoint.
- Create:
  - `frontend/static/js/three/campus_scene.js`
  - `frontend/static/js/three/canteen_scene.js`
  - `frontend/static/js/three/state_adapter.js`
  - `frontend/static/js/three/intervention_ui.js`
- Modify `frontend/static/js/main.js`
  - Route campus snapshots to the 3D state adapter and intervention UI.
  - Keep existing Phase 2 single-canteen flow intact.
- Modify `frontend/static/css/style.css`
  - Support the 3D-first layout: left object panel, full 3D stage, right KPI/intervention panel.
- Modify frontend contract tests:
  - `backend/tests/test_frontend_three_js_contract.py`
  - `backend/tests/test_frontend_main_js_contract.py`
  - Add `backend/tests/test_frontend_intervention_ui_contract.py`

### Evidence and Docs

- Update `docs/phase3/browser_e2e_check.md`
- Add/refresh screenshots and JSON evidence under `docs/phase3/screenshots/`
- Update `docs/phase3/demo_script.md`

---

## Task 0: Baseline and Guardrails

**Files:**
- Verify only, no code edits.

- [ ] **Step 1: Confirm worktree state**

Run:

```bash
git status --short
```

Expected: unrelated `docs/phase2/*` modifications may exist; do not stage them.

- [ ] **Step 2: Run backend baseline**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q
```

Expected: current backend suite passes before feature edits.

- [ ] **Step 3: Run current frontend syntax checks**

Run:

```bash
node --check frontend/static/js/main.js
node --check frontend/static/js/campus.js
node --check frontend/static/js/campus_map.js
node --check frontend/static/js/floor_tabs.js
node --input-type=module --check < frontend/static/js/three/scene3d.js
```

Expected: all checks pass before feature edits.

---

## Task 1: Physical Window Model and Initial Open State

**Files:**
- Modify: `backend/simulation/canteen.py`
- Test: `backend/tests/test_window_intervention.py`

- [ ] **Step 1: Write failing tests for physical vs open window semantics**

Create `backend/tests/test_window_intervention.py`:

```python
import simpy
import pytest
from simulation.canteen import Canteen


def make_def(active=2, physical=4):
    return {
        "id": "demo",
        "display_name": "Demo",
        "campus_position": {"x": 0, "y": 0},
        "avg_eat_time_minutes": 15,
        "avg_serve_time_seconds": 30,
        "arrival_weight": 1.0,
        "floors": [{
            "floor_id": 1,
            "windows": {
                "physical_count": physical,
                "active_count": active,
                "avg_serve_time_seconds": 30,
            },
            "seats": {"count": 20},
        }],
    }


def test_physical_windows_are_instantiated_but_only_active_are_open():
    c = Canteen(simpy.Environment(), make_def(active=2, physical=4))
    assert len(c.windows) == 4
    assert c.physical_window_count == 4
    assert c.active_window_count == 2
    assert [w.is_open for w in c.windows] == [True, True, False, False]


def test_shortest_window_ignores_closed_windows():
    c = Canteen(simpy.Environment(), make_def(active=1, physical=3))
    c.windows[0].is_open = False
    c.windows[1].is_open = True
    assert c.shortest_window().id == 1


def test_cannot_close_last_open_window():
    c = Canteen(simpy.Environment(), make_def(active=1, physical=2))
    with pytest.raises(ValueError, match="last open window"):
        c.close_window(floor_id=1, window_id=0)
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_window_intervention.py -q
```

Expected: FAIL because `is_open`, `close_window`, and physical-window instantiation do not exist yet.

- [ ] **Step 3: Implement minimal Window open-state model**

In `backend/simulation/canteen.py`:

- Add `is_open: bool = True` and `closing: bool = False` to `Window`.
- Instantiate `physical_count` windows instead of only `active_count`.
- Set `is_open = idx < active_count`.
- Make `active_window_count` dynamic or update it inside open/close helpers.
- Make `shortest_window()` choose only open windows.
- Add `open_window(floor_id, window_id)` and `close_window(floor_id, window_id)` helpers.

- [ ] **Step 4: Run focused tests**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_window_intervention.py backend/tests/test_simpy_canteen.py backend/tests/test_multi_floor.py -q
```

Expected: all pass. If legacy tests assumed `len(windows) == active_count`, update them to assert open-count separately from physical-count.

- [ ] **Step 5: Commit**

```bash
git add backend/simulation/canteen.py backend/tests/test_window_intervention.py backend/tests/test_simpy_canteen.py backend/tests/test_multi_floor.py
git commit -m "feat(simulation): model physical and open canteen windows"
```

---

## Task 2: SimPy-Safe Queue Reallocation on Window Close

**Files:**
- Modify: `backend/simulation/canteen.py`
- Modify: `backend/simulation/student.py`
- Test: `backend/tests/test_student_window_intervention.py`

- [ ] **Step 1: Write failing tests for queued-student reallocation**

Create `backend/tests/test_student_window_intervention.py`. The tests should construct a small campus/canteen setup and verify:

```python
def test_closing_window_wakes_waiting_student_and_cancels_old_request():
    # Arrange: one student waiting on window 0 while window 1 is open.
    # Act: close window 0 while the request is still pending.
    # Assert: student is removed from window 0 waiting_students,
    # old SimPy request is no longer in window 0.resource.queue,
    # and student re-enters queueing on an open window.
    ...


def test_closing_serving_window_does_not_interrupt_current_service():
    # Arrange: window 0 has a current service request already triggered.
    # Act: close window 0.
    # Assert: current service completes and total_served increments;
    # after service, window 0 becomes closed and takes no new students.
    ...
```

Use helper functions from existing `backend/tests/test_student_lifecycle.py` where possible instead of duplicating large fixtures.

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_student_window_intervention.py -q
```

Expected: FAIL because the current student lifecycle waits only on `req | timeout`.

- [ ] **Step 3: Add window requeue signaling**

In `Window`, add a SimPy event used to wake queued students when the window is closing:

```python
def reset_requeue_event(self, env):
    self.requeue_event = env.event()

def signal_requeue(self, env, reason):
    if not self.requeue_event.triggered:
        self.requeue_event.succeed({"reason": reason, "window_id": self.id})
    self.reset_requeue_event(env)
```

Initialize the event when the window is created.

- [ ] **Step 4: Update `student_lifecycle()` wait branch**

Change the queue wait from:

```python
result = yield req | env.timeout(student.patience_threshold)
```

to include the requeue event:

```python
patience_timeout = env.timeout(student.patience_threshold)
result = yield req | patience_timeout | window.requeue_event
```

If `window.requeue_event` wins and `req` is not triggered:

- cancel the request with `req.cancel()`;
- call `window.leave_queue(student)`;
- add the configured requeue cost to wait time or yield `env.timeout(requeue_cost_seconds)`;
- keep `student.state = "queueing"`;
- loop back to choose a new open window.

If `req` is already triggered, treat the student as serving and do not interrupt.

- [ ] **Step 5: Run focused lifecycle tests**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_student_window_intervention.py backend/tests/test_student_lifecycle.py backend/tests/test_coordinator.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/simulation/canteen.py backend/simulation/student.py backend/tests/test_student_window_intervention.py
git commit -m "feat(simulation): requeue students when windows close"
```

---

## Task 3: Campus-Level Window Intervention API

**Files:**
- Modify: `backend/simulation/coordinator.py`
- Modify: `backend/api/campus_routes.py`
- Test: `backend/tests/test_campus_intervention_api.py`

- [ ] **Step 1: Write failing API tests**

Create `backend/tests/test_campus_intervention_api.py`:

```python
def test_toggle_window_close_updates_snapshot(client):
    # configure and start campus mode
    # POST /api/campus/canteens/minghu_xueyi/floors/1/windows/0/toggle {"open": false}
    # assert response ok, intervention returned, window state closed/closing in snapshot
    ...


def test_toggle_window_rejects_last_open_window(client):
    # configure a one-open-window canteen
    # assert 400 and no state mutation
    ...


def test_toggle_window_open_reactivates_physical_window(client):
    # close or start with inactive physical window
    # POST {"open": true}
    # assert it is included in shortest-window candidates
    ...
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_campus_intervention_api.py -q
```

Expected: FAIL because the route and coordinator method do not exist.

- [ ] **Step 3: Implement coordinator method**

Add `CampusCoordinator.toggle_window(canteen_id, floor_id, window_id, open)` that:

- validates canteen/floor/window exists;
- delegates to `Canteen.open_window()` or `Canteen.close_window()`;
- records an intervention dict with current time, ids, action, status, and migrated count if available;
- returns the intervention plus current snapshot.

- [ ] **Step 4: Implement Flask route**

Add route in `backend/api/campus_routes.py`:

```python
@campus_bp.post('/canteens/<canteen_id>/floors/<int:floor_id>/windows/<int:window_id>/toggle')
def toggle_campus_window(canteen_id, floor_id, window_id):
    ...
```

Use `_ensure_campus_initialized()` and return JSON with `mode`, `intervention`, and `snapshot`.

- [ ] **Step 5: Run focused API tests**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_campus_intervention_api.py backend/tests/test_campus_api.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/simulation/coordinator.py backend/api/campus_routes.py backend/tests/test_campus_intervention_api.py
git commit -m "feat(api): add campus window intervention endpoint"
```

---

## Task 4: Persist Interventions in Campus History

**Files:**
- Modify: `backend/api/db_migrate.py`
- Modify: `backend/api/campus_routes.py`
- Test: `backend/tests/test_db_migration.py`
- Test: `backend/tests/test_campus_api.py`

- [ ] **Step 1: Write failing migration/history tests**

Add tests:

```python
def test_migration_adds_interventions_json_to_campus_snapshot(tmp_path):
    ...


def test_campus_history_includes_interventions_after_toggle(client):
    # configure/start campus, toggle a window, step/finish or flush snapshots,
    # fetch /api/campus/history, assert at least one item contains interventions
    ...
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_db_migration.py backend/tests/test_campus_api.py -q
```

Expected: FAIL because `interventions_json` is missing.

- [ ] **Step 3: Add explicit persistence column**

In `backend/api/db_migrate.py`:

- create `interventions_json TEXT` in new `campus_snapshot` tables;
- add idempotent ALTER for existing tables when column is absent.

In `backend/api/campus_routes.py`:

- `_compact_snapshot()` includes `interventions`;
- `_flush_campus_snapshots()` writes `interventions_json`;
- `_load_campus_history_rows()` parses `interventions_json`;
- `/api/campus/history/configs` can include a count or latest intervention summary if useful, but keep this optional.

- [ ] **Step 4: Run persistence tests**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_db_migration.py backend/tests/test_campus_api.py backend/tests/test_campus_intervention_api.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/api/db_migrate.py backend/api/campus_routes.py backend/tests/test_db_migration.py backend/tests/test_campus_api.py
git commit -m "feat(api): persist campus window interventions"
```

---

## Task 5: Backend Full Regression Gate

**Files:**
- Verify only unless tests reveal regressions.

- [ ] **Step 1: Run full backend regression**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q
```

Expected: all tests pass. Do not start frontend 3D implementation until this passes.

- [ ] **Step 2: Record backend gate result**

Update `docs/phase3/browser_e2e_check.md` or create a short implementation evidence section only after actual implementation. Record command, pass count, and date.

- [ ] **Step 3: Commit evidence if updated**

```bash
git add docs/phase3/browser_e2e_check.md
git commit -m "docs: record backend intervention regression evidence"
```

Skip this commit if no doc evidence was updated in this task.

---

## Task 6: Split Three.js Modules Without Changing Behavior

**Files:**
- Modify: `frontend/static/js/three/scene3d.js`
- Create: `frontend/static/js/three/state_adapter.js`
- Create: `frontend/static/js/three/campus_scene.js`
- Create: `frontend/static/js/three/canteen_scene.js`
- Test: `backend/tests/test_frontend_three_js_contract.py`

- [ ] **Step 1: Write failing module-boundary contract tests**

Update `backend/tests/test_frontend_three_js_contract.py` to assert:

- `scene3d.js` imports `state_adapter.js`, `campus_scene.js`, and `canteen_scene.js`;
- `window.CanteenApp3D` still exposes `init`, `render`, `dispose`;
- fallback handling still exists;
- `visibleCanteens` and `pendingCanteens` are still supported.

- [ ] **Step 2: Run contract test and verify it fails**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py -q
```

Expected: FAIL because the modules do not exist.

- [ ] **Step 3: Extract modules**

Move pure helper responsibilities out of `scene3d.js`:

- state normalization and marker entries -> `state_adapter.js`;
- campus meshes and in-transit dots -> `campus_scene.js`;
- canteen floors/windows/seats/students -> `canteen_scene.js`.

Keep the public global shape unchanged:

```javascript
window.CanteenApp3D = { init, render, dispose };
```

- [ ] **Step 4: Run JS checks**

Run:

```bash
node --input-type=module --check < frontend/static/js/three/scene3d.js
node --input-type=module --check < frontend/static/js/three/state_adapter.js
node --input-type=module --check < frontend/static/js/three/campus_scene.js
node --input-type=module --check < frontend/static/js/three/canteen_scene.js
```

Expected: all pass.

- [ ] **Step 5: Run frontend contract tests**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/static/js/three/scene3d.js frontend/static/js/three/state_adapter.js frontend/static/js/three/campus_scene.js frontend/static/js/three/canteen_scene.js backend/tests/test_frontend_three_js_contract.py
git commit -m "refactor(frontend): split threejs scene modules"
```

---

## Task 7: Make 3D the Campus-Mode Main Screen

**Files:**
- Modify: `frontend/templates/index.html`
- Modify: `frontend/static/js/main.js`
- Modify: `frontend/static/css/style.css`
- Test: `backend/tests/test_frontend_main_js_contract.py`
- Test: `backend/tests/test_frontend_three_js_contract.py`

- [ ] **Step 1: Write failing contracts for 3D-first campus mode**

Tests should assert:

- campus-mode simulation page includes a primary `#three-stage`;
- 2D/SVG controls are not presented as the main campus mode toggle;
- `applyViewState()` defaults campus mode to 3D;
- single-canteen mode still uses the existing canvas path.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_main_js_contract.py backend/tests/test_frontend_three_js_contract.py -q
```

Expected: FAIL because campus mode still treats 3D as a selectable render mode.

- [ ] **Step 3: Implement 3D-first layout**

Update page structure to:

- left object/canteen panel;
- full central 3D stage;
- right KPI/intervention panel;
- fallback/debug affordance for 2D, not primary path.

Do not remove Phase 2 single-canteen canvas.

- [ ] **Step 4: Run JS checks**

```bash
node --check frontend/static/js/main.js
node --input-type=module --check < frontend/static/js/three/scene3d.js
```

Expected: pass.

- [ ] **Step 5: Run focused frontend contracts**

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_main_js_contract.py backend/tests/test_frontend_three_js_contract.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/templates/index.html frontend/static/js/main.js frontend/static/css/style.css backend/tests/test_frontend_main_js_contract.py backend/tests/test_frontend_three_js_contract.py
git commit -m "feat(frontend): make threejs campus view primary"
```

---

## Task 8: Build Realistic Campus and Canteen 3D Scenes

**Files:**
- Modify: `frontend/static/js/three/campus_scene.js`
- Modify: `frontend/static/js/three/canteen_scene.js`
- Modify: `frontend/static/js/three/state_adapter.js`
- Test: `backend/tests/test_frontend_three_js_contract.py`

- [ ] **Step 1: Add contract assertions for scene content**

Tests should assert source contains stable hooks or data-driven code paths for:

- pending 学活 marker;
- Minghu/Xueyi and Xuesi canteen IDs;
- floor-based canteen rendering;
- window status rendering;
- in-transit student rendering.

- [ ] **Step 2: Run test and verify it fails**

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py -q
```

Expected: FAIL until scene hooks exist.

- [ ] **Step 3: Implement campus scene**

Use data-driven marker entries from runtime snapshot and `visibleCanteens`. Render:

- campus base;
- simplified 明湖 water body;
- main paths;
- runtime canteen buildings;
- pending 学活 building with locked/pending style;
- in-transit student dots/paths.

- [ ] **Step 4: Implement canteen interior scene**

Render floors from `canteen.floors`:

- floor slabs;
- windows by floor and `is_open`/`closing`/serving state;
- seats by occupied/empty state;
- queue/student dots by snapshot state;
- floor focus/cutaway mode if scope allows in this task.

- [ ] **Step 5: Run JS and contract checks**

```bash
node --input-type=module --check < frontend/static/js/three/campus_scene.js
node --input-type=module --check < frontend/static/js/three/canteen_scene.js
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/static/js/three/campus_scene.js frontend/static/js/three/canteen_scene.js frontend/static/js/three/state_adapter.js backend/tests/test_frontend_three_js_contract.py
git commit -m "feat(frontend): render campus and canteen digital twin scenes"
```

---

## Task 9: Add 3D Window Intervention UI

**Files:**
- Create: `frontend/static/js/three/intervention_ui.js`
- Modify: `frontend/static/js/main.js`
- Modify: `frontend/templates/index.html`
- Modify: `frontend/static/css/style.css`
- Test: `backend/tests/test_frontend_intervention_ui_contract.py`

- [ ] **Step 1: Write failing frontend intervention contract tests**

Create `backend/tests/test_frontend_intervention_ui_contract.py` asserting:

- intervention UI module exists;
- it calls `/api/campus/canteens/.../windows/.../toggle`;
- UI exposes open/closing/closed labels;
- it handles rejected last-window closure;
- it records/uses returned intervention payload.

- [ ] **Step 2: Run test and verify it fails**

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_intervention_ui_contract.py -q
```

Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement intervention UI module**

`intervention_ui.js` should:

- render active canteen/floor window controls;
- disable last-open-window closure client-side;
- POST toggle requests;
- update state from response snapshot;
- show recent intervention events.

- [ ] **Step 4: Wire into `main.js` and 3D render loop**

When campus snapshot updates:

- update the intervention panel;
- pass returned snapshot into `CanteenApp3D.render()`;
- keep single-canteen mode untouched.

- [ ] **Step 5: Run JS and focused tests**

```bash
node --check frontend/static/js/main.js
node --input-type=module --check < frontend/static/js/three/intervention_ui.js
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_intervention_ui_contract.py backend/tests/test_frontend_main_js_contract.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/static/js/three/intervention_ui.js frontend/static/js/main.js frontend/templates/index.html frontend/static/css/style.css backend/tests/test_frontend_intervention_ui_contract.py
git commit -m "feat(frontend): add realtime window intervention controls"
```

---

## Task 10: Browser E2E Evidence and No-Fake-Animation Proof

**Files:**
- Update: `docs/phase3/browser_e2e_check.md`
- Update/Create: `docs/phase3/screenshots/*.png`
- Update/Create: `docs/phase3/screenshots/three-result.json`
- Update: `docs/phase3/demo_script.md`

- [ ] **Step 1: Start Flask app**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python backend/app.py
```

Expected: app available at `http://127.0.0.1:5001/`.

- [ ] **Step 2: Browser flow evidence**

Using a real browser automation check, record:

- default campus mode opens 3D main screen;
- campus 3D canvas nonblank;
- Minghu/Xueyi and Xuesi are clickable;
- 学活 pending marker is visible and locked;
- entering a canteen shows floor/window/seat/student rendering;
- closing a window changes backend snapshot and UI state;
- console errors are zero.

- [ ] **Step 3: Save machine-readable evidence**

Save JSON evidence under `docs/phase3/screenshots/three-result.json` with at least:

```json
{
  "consoleErrors": 0,
  "canvasNonblankPixels": 12345,
  "intervention": {
    "beforeOpenWindows": 13,
    "afterOpenWindows": 12,
    "historyContainsIntervention": true,
    "queueDistributionChanged": true
  }
}
```

- [ ] **Step 4: Run full verification**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q
node --check frontend/static/js/main.js
node --input-type=module --check < frontend/static/js/three/scene3d.js
node --input-type=module --check < frontend/static/js/three/state_adapter.js
node --input-type=module --check < frontend/static/js/three/campus_scene.js
node --input-type=module --check < frontend/static/js/three/canteen_scene.js
node --input-type=module --check < frontend/static/js/three/intervention_ui.js
```

Expected: all pass.

- [ ] **Step 5: Update demo script**

Update `docs/phase3/demo_script.md` so the demonstration sequence is:

1. open 3D campus digital twin;
2. show people flowing to canteens;
3. click Minghu/Xueyi;
4. show floor/window/seat state;
5. close a window during run;
6. show intervention event and queue/KPI change;
7. finish simulation and show evidence-backed statistics.

- [ ] **Step 6: Commit evidence**

```bash
git add docs/phase3/browser_e2e_check.md docs/phase3/demo_script.md docs/phase3/screenshots
git commit -m "docs: record 3d intervention browser evidence"
```

---

## Final Gate

Before declaring the implementation complete, the final state must satisfy:

- [ ] Backend full regression passes.
- [ ] Frontend JS syntax checks pass.
- [ ] Campus-mode default path is 3D-first.
- [ ] Window closure cancels/requeues pending SimPy requests.
- [ ] Window opening can reactivate pre-instantiated physical windows.
- [ ] Interventions are persisted and visible through campus history.
- [ ] Browser evidence proves canvas nonblank and console errors zero.
- [ ] JSON evidence proves window intervention changed backend snapshot/history.
- [ ] Phase 2 single-canteen API shape is unchanged.
