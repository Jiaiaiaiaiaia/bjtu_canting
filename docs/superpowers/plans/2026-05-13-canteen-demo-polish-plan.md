# Canteen Demo Polish And 3D Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current Canteen simulation into a teacher-facing demo with credible data boundaries, a clean campus-mode entry, verified browser flow, and a first integrated 3D view.

**Architecture:** Keep Phase 2 single-canteen APIs (`/api/config`, `/api/simulation/*`) stable. Add campus preset loading and frontend preset UX on top of the existing `/api/campus/*` path, then integrate the standalone Three.js V7 prototype as an optional 3D render mode with 2D Canvas/SVG fallback. 学活食堂 stays explicitly pending until the user supplies real data; do not invent or silently "complete" its preset.

**Tech Stack:** Python 3.12, Flask, SimPy, SQLite, pytest, plain JavaScript, ECharts, Three.js ES modules, in-app browser verification.

---

## Non-Negotiable Constraints

- Do not change or fake 学活食堂 field data in `backend/simulation/presets/xuehuo.json`.
- Default campus simulation must not route students into 学活 while its data is pending; 学活 may be shown only as a visible pending point/metadata until real data is supplied.
- Preserve Phase 2 single-canteen response shapes for the existing frontend.
- Keep campus/multi-canteen behavior on `/api/campus/*`; do not overload `/api/simulation/*`.
- Keep `outputs/` deleted and ignored; it belongs to the separate Design Culture PPT work.
- For every frontend/API change, run backend regression and a browser flow check.

## File Structure

- `backend/simulation/presets/loader.py` loads `_campus.json` and canteen preset JSON files into a runtime campus config plus visible pending metadata.
- `backend/api/campus_routes.py` exposes the preset payload to the frontend without changing existing campus run endpoints.
- `frontend/templates/index.html` gets a teacher-friendly campus preset panel and an optional 2D/3D render toggle.
- `frontend/static/js/main.js` owns mode dispatch and render-mode state, then routes snapshots to 2D or 3D renderers.
- `frontend/static/js/three/` contains the integrated Three.js renderer, adapted from the current V7 brainstorm prototype.
- `docs/phase3/browser_e2e_check.md` records manual browser verification evidence.
- `README.md` and phase docs describe the current SimPy/campus/3D shape accurately.

---

### Task 0: Cleanup Guardrail

**Files:**
- Modify: `.gitignore`
- Modify: `task_plan.md`
- Modify: `progress.md`
- Verify: `AGENTS.md`
- Verify: `CLAUDE.md`
- Verify: `agent.md`

- [ ] **Step 1: Confirm `outputs/` is gone**

Run:

```bash
test ! -d outputs
```

Expected: command exits 0.

- [ ] **Step 2: Add `outputs/` to `.gitignore`**

Add:

```gitignore
# External generated deliverables
outputs/
```

Do not remove the existing `.superpowers/` ignore rule.

- [ ] **Step 3: Update root planning files**

Add a short progress note:

```markdown
## 2026-05-13

- User approved deleting `outputs/`; directory removed.
- Started the Canteen demo polish plan.
- Constraint: 学活 preset remains pending until user supplies real data.
```

- [ ] **Step 4: Verify collaboration guardrail files**

Read `AGENTS.md`, `CLAUDE.md`, and `agent.md`. Confirm they all describe the same broad collaboration boundary:

- Canteen is the 食堂/餐厅就餐仿真 project.
- Design Culture / `模块一` PPT artifacts are external.
- Phase 2 single-canteen APIs remain compatible.
- Campus/multi-canteen work uses separate campus APIs/data.

If they are aligned, include all three in the cleanup/guardrail commit. If they are not aligned, stop and update the mismatch first rather than committing only one file.

- [ ] **Step 5: Verify workspace status**

Run:

```bash
git status --short
```

Expected: no `outputs/` entry; `.gitignore`, root planning files, and guardrail files may be modified/untracked.

- [ ] **Step 6: Commit cleanup**

```bash
git add .gitignore AGENTS.md CLAUDE.md agent.md task_plan.md progress.md
git commit -m "chore: ignore external outputs and record demo polish plan"
```

---

### Task 1: Campus Preset Loader With Runtime/Pending Contract

**Files:**
- Create: `backend/simulation/presets/loader.py`
- Test: `backend/tests/test_campus_preset_loader.py`
- Modify: `backend/api/campus_routes.py`
- Test: `backend/tests/test_campus_api.py`

- [ ] **Step 1: Write failing loader tests**

Create `backend/tests/test_campus_preset_loader.py`:

```python
from simulation.presets.loader import load_default_campus_preset


def test_default_campus_runtime_excludes_pending_xuehuo():
    preset = load_default_campus_preset()
    runtime_ids = [c["id"] for c in preset["config"]["canteens"]]
    assert runtime_ids == ["minghu_xueyi", "xuesi"]


def test_visible_canteen_metadata_keeps_xuehuo_as_pending_point():
    preset = load_default_campus_preset()
    visible_ids = [c["id"] for c in preset["visible_canteens"]]
    assert visible_ids == [
        "minghu_xueyi",
        "xuehuo",
        "xuesi",
    ]
    xuehuo = next(c for c in preset["visible_canteens"] if c["id"] == "xuehuo")
    assert xuehuo["runtime_included"] is False
    assert xuehuo["data_status"] == "missing"
    assert xuehuo["pending_data"] is True


def test_field_collected_canteens_keep_todo_but_are_labeled_review_pending():
    preset = load_default_campus_preset()
    by_id = {c["id"]: c for c in preset["visible_canteens"]}
    assert by_id["minghu_xueyi"]["_TODO_field_research_pending"] is True
    assert by_id["minghu_xueyi"]["data_status"] == "field_collected_pending_review"
    assert by_id["minghu_xueyi"]["runtime_included"] is True
    assert by_id["xuesi"]["_TODO_field_research_pending"] is True
    assert by_id["xuesi"]["data_status"] == "field_collected_pending_review"
    assert by_id["xuesi"]["runtime_included"] is True


def test_pending_canteens_are_not_routable():
    preset = load_default_campus_preset()
    assert preset["pending_canteens"] == ["xuehuo"]
    assert all(
        c["id"] != "xuehuo"
        for c in preset["config"]["canteens"]
    )
```

- [ ] **Step 2: Run tests and see import failure**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_campus_preset_loader.py -q
```

Expected: failure because `simulation.presets.loader` does not exist.

- [ ] **Step 3: Implement loader**

Create `backend/simulation/presets/loader.py`:

```python
"""Campus preset loader for teacher-facing demo configs."""
from __future__ import annotations

import copy
import json
from pathlib import Path


PRESET_DIR = Path(__file__).resolve().parent
CANTEEN_FILES = ("minghu_xueyi.json", "xuehuo.json", "xuesi.json")
FIELD_STATUS = {
    "minghu_xueyi": {
        "data_status": "field_collected_pending_review",
        "runtime_included": True,
        "evidence_doc": "docs/phase3/canteen_field_research.md",
    },
    "xuesi": {
        "data_status": "field_collected_pending_review",
        "runtime_included": True,
        "evidence_doc": "docs/phase3/canteen_field_research.md",
    },
    "xuehuo": {
        "data_status": "missing",
        "runtime_included": False,
        "evidence_doc": "docs/phase3/canteen_field_research.md",
    },
}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _annotate_canteen(item: dict) -> dict:
    item = copy.deepcopy(item)
    status = FIELD_STATUS[item["id"]]
    item["pending_data"] = bool(item.get("_TODO_field_research_pending"))
    item.update(status)
    return item


def load_default_campus_preset() -> dict:
    campus = _read_json(PRESET_DIR / "_campus.json")
    visible_canteens = []
    for name in CANTEEN_FILES:
        visible_canteens.append(_annotate_canteen(_read_json(PRESET_DIR / name)))

    runtime_canteens = [
        c for c in visible_canteens if c["runtime_included"]
    ]

    return {
        "config": {
            "campus": campus,
            "canteens": runtime_canteens,
            "router": {
                "information_mode": "local_estimate",
                "patience_mean_seconds": 180,
                "patience_std_seconds": 60,
                "patience_min_seconds": 30,
                "switch_improvement_ratio": 1.3,
                "max_switches_per_student": 2,
                "rng_seed": 42,
            },
        },
        "visible_canteens": visible_canteens,
        "pending_canteens": [
            c["id"] for c in visible_canteens if not c["runtime_included"]
        ],
    }
```

Contract: `config.canteens` is the only list posted to `/api/campus/config`, so pending 学活 does not affect routing, queueing, statistics, or final totals. `visible_canteens` is metadata for UI notes or placeholder map/3D markers only.

- [ ] **Step 4: Run loader tests**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_campus_preset_loader.py -q
```

Expected: `4 passed`.

- [ ] **Step 5: Add API endpoint test**

Extend `backend/tests/test_campus_api.py` with:

```python
def test_campus_default_preset_endpoint(client):
    resp = client.get("/api/campus/presets/default")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["mode"] == "campus"
    assert data["pending_canteens"] == ["xuehuo"]
    assert [c["id"] for c in data["config"]["canteens"]] == ["minghu_xueyi", "xuesi"]
    visible = [c["id"] for c in data["visible_canteens"]]
    assert visible == ["minghu_xueyi", "xuehuo", "xuesi"]
```

- [ ] **Step 6: Implement endpoint**

In `backend/api/campus_routes.py`, import the loader and add:

```python
from simulation.presets.loader import load_default_campus_preset


@campus_bp.get("/presets/default")
def default_campus_preset():
    preset = load_default_campus_preset()
    return jsonify({
        "mode": "campus",
        "config": preset["config"],
        "visible_canteens": preset["visible_canteens"],
        "pending_canteens": preset["pending_canteens"],
    })
```

- [ ] **Step 7: Run focused API tests**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_campus_api.py backend/tests/test_campus_preset_loader.py -q
```

Expected: all selected tests pass.

- [ ] **Step 8: Commit**

```bash
git add backend/simulation/presets/loader.py backend/tests/test_campus_preset_loader.py backend/tests/test_campus_api.py backend/api/campus_routes.py
git commit -m "feat(campus): expose default preset with pending data contract"
```

---

### Task 2: Teacher-Friendly Campus Mode Entry

**Files:**
- Modify: `frontend/templates/index.html`
- Modify: `frontend/static/js/main.js`
- Modify: `frontend/static/css/style.css`
- Test: `backend/tests/test_frontend_a16_ui_contract.py`
- Test: `backend/tests/test_frontend_main_js_contract.py`

- [ ] **Step 1: Add frontend contract expectations**

Update existing frontend contract tests to assert:

```python
assert 'id="campus-preset-panel"' in INDEX_HTML
assert 'data-campus-preset="default"' in INDEX_HTML
assert 'loadDefaultCampusPreset' in MAIN_JS
assert '/campus/presets/default' in MAIN_JS
assert 'pending_canteens' in MAIN_JS
assert 'campusConfigDirty' in MAIN_JS
assert 'getCampusConfigForSubmit' in MAIN_JS
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_a16_ui_contract.py backend/tests/test_frontend_main_js_contract.py -q
```

Expected: fail on missing preset UI/function names.

- [ ] **Step 3: Replace campus textarea as the primary UI**

In `frontend/templates/index.html`, keep an advanced JSON textarea for fallback, but make the default campus UI a preset panel:

```html
<div id="campus-preset-panel" hidden class="campus-preset-panel">
  <button type="button" class="campus-preset-card active" data-campus-preset="default">
    <strong>北交大午餐高峰预设</strong>
    <span>明湖/学一与学四使用已采集数据；学活保留待补标记。</span>
  </button>
  <div id="pending-data-note" class="pending-data-note"></div>
</div>
```

Keep `#campus-config-json` available under a collapsed/advanced block.

- [ ] **Step 4: Add preset loading state**

In `frontend/static/js/main.js`, add:

```javascript
let campusPresetPayload = null;
let campusConfigDirty = false;

if (campusConfigJson) {
    campusConfigJson.addEventListener('input', () => {
        campusConfigDirty = true;
        campusPresetPayload = null;
    });
}

async function loadDefaultCampusPreset() {
    const res = await fetch(`${API_BASE}/campus/presets/default`);
    if (!res.ok) throw new Error('校园预设加载失败');
    const data = await res.json();
    campusPresetPayload = data.config;
    if (campusConfigJson) {
        campusConfigJson.value = JSON.stringify(data.config, null, 2);
        campusConfigDirty = false;
    }
    renderPendingDataNote(data.pending_canteens || []);
    return data.config;
}

function renderPendingDataNote(pending) {
    const node = document.getElementById('pending-data-note');
    if (!node) return;
    node.textContent = pending.length
        ? `待补数据：${pending.join(', ')}。演示中不伪造该食堂容量。`
        : '全部食堂数据已回填。';
}

async function getCampusConfigForSubmit() {
    if (campusConfigDirty) {
        return readCampusConfig();
    }
    if (campusPresetPayload) {
        return campusPresetPayload;
    }
    return await loadDefaultCampusPreset();
}
```

- [ ] **Step 5: Use preset on campus submit**

In `configForm.submit`, for campus mode:

```javascript
const payload = nextMode === 'campus'
    ? await getCampusConfigForSubmit()
    : readSingleConfig();
```

Add a contract/harness test in `backend/tests/test_frontend_main_js_contract.py` if the current test style allows execution: after dispatching an `input` event on `#campus-config-json`, `getCampusConfigForSubmit()` should call `readCampusConfig()` rather than reuse the cached preset. If the current test file only performs static checks, assert the dirty flag, input listener, and function name are present.

- [ ] **Step 6: Style the preset panel**

Add compact card styles to `frontend/static/css/style.css`. Keep cards under 8px radius unless existing surrounding card uses 12px.

- [ ] **Step 7: Run frontend static checks**

Run:

```bash
node --check frontend/static/js/main.js
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_a16_ui_contract.py backend/tests/test_frontend_main_js_contract.py -q
```

Expected: JS syntax OK and tests pass.

- [ ] **Step 8: Commit**

```bash
git add frontend/templates/index.html frontend/static/js/main.js frontend/static/css/style.css backend/tests/test_frontend_a16_ui_contract.py backend/tests/test_frontend_main_js_contract.py
git commit -m "feat(frontend): campus preset entry for teacher demo"
```

---

### Task 3: Browser E2E Evidence

**Files:**
- Create: `docs/phase3/browser_e2e_check.md`
- Create: `docs/phase3/screenshots/`
- Modify: `docs/phase3/integration_bug_log.md`

- [ ] **Step 1: Start local Flask app**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python backend/app.py
```

Expected: app serves `http://127.0.0.1:5001/`.

- [ ] **Step 2: Verify single-canteen browser flow**

In the browser:

```text
参数配置 -> 开始仿真 -> 仿真运行 -> 结束仿真 -> 数据分析 -> 历史记录
```

Expected:

- Console error count is `0`.
- 2D canvas nonblank check passes (`non_background_pixels > 0` or equivalent screenshot/pixel assertion).
- `total_arrived == total_served` after finish.
- History row appears and detail chart opens.
- Save screenshot to `docs/phase3/screenshots/single-flow-analysis.png`.

- [ ] **Step 3: Verify campus preset browser flow**

In the browser:

```text
参数配置 -> 校园联合模式 -> 北交大午餐高峰预设 -> 开始仿真 -> 校园地图 -> 食堂详情 -> 楼层 Tab -> 结束仿真 -> 数据分析
```

Expected:

- 学活 is visible as pending, not falsely completed.
- Three canteen markers render.
- In-transit dots render when there are walking students.
- Minghu/Xuesi floor tabs work.
- Statistics render after finish.
- Final `campus_totals.total_arrived == campus_totals.total_served`.
- Save screenshots to:
  - `docs/phase3/screenshots/campus-map.png`
  - `docs/phase3/screenshots/campus-canteen-floor.png`
  - `docs/phase3/screenshots/campus-analysis.png`

- [ ] **Step 4: Record evidence**

Create `docs/phase3/browser_e2e_check.md`:

```markdown
# Browser E2E Check

Date: 2026-05-13
App: http://127.0.0.1:5001/

## Single-Canteen Flow

- Result:
- Console errors:
- 2D canvas nonblank:
- Final totals:
- Screenshots:

## Campus Preset Flow

- Result:
- Pending canteens:
- Floor tabs:
- Console errors:
- 2D canvas/map nonblank:
- Final totals:
- Screenshots:

## Verification Artifacts

- `docs/phase3/screenshots/single-flow-analysis.png`
- `docs/phase3/screenshots/campus-map.png`
- `docs/phase3/screenshots/campus-canteen-floor.png`
- `docs/phase3/screenshots/campus-analysis.png`

## Open Issues

- None / list concrete issue ids.
```

- [ ] **Step 5: Update bug log**

In `docs/phase3/integration_bug_log.md`, replace the old limitation about missing browser clicks with a new dated section that points to `browser_e2e_check.md`.

- [ ] **Step 6: Commit**

```bash
git add docs/phase3/browser_e2e_check.md docs/phase3/integration_bug_log.md
git commit -m "test(e2e): record browser verification for demo flows"
```

---

### Task 4: Integrate V7 Three.js As Optional 3D View

**Files:**
- Create: `frontend/static/js/three/vendor/three.module.js`
- Create: `frontend/static/js/three/vendor/OrbitControls.js`
- Create: `frontend/static/js/three/scene3d.js`
- Modify: `frontend/templates/index.html`
- Modify: `frontend/static/js/main.js`
- Modify: `frontend/static/css/style.css`
- Test: `backend/tests/test_frontend_a16_ui_contract.py`

- [ ] **Step 1: Copy local Three.js vendor files**

Use the existing downloaded files:

```bash
mkdir -p frontend/static/js/three/vendor
cp .superpowers/brainstorm/96186-1778598663/vendor/three.module.js frontend/static/js/three/vendor/three.module.js
cp .superpowers/brainstorm/96186-1778598663/vendor/OrbitControls.js frontend/static/js/three/vendor/OrbitControls.js
```

Expected: no network dependency.

- [ ] **Step 2: Add 3D DOM shell**

In `frontend/templates/index.html`, add a render switch and 3D stage next to the current Canvas/SVG area:

```html
<div id="render-switcher" class="render-switcher">
  <button type="button" data-render="2d" class="active">2D</button>
  <button type="button" data-render="3d">3D</button>
</div>
<div id="three-stage" class="three-stage" hidden></div>
```

- [ ] **Step 3: Add importmap and module script**

V7 uses ES modules and `OrbitControls.js` imports from bare specifier `three`, so the browser needs an importmap before `scene3d.js` loads:

```html
<script type="importmap">
{
  "imports": {
    "three": "{{ url_for('static', filename='js/three/vendor/three.module.js') }}",
    "three/addons/controls/OrbitControls.js": "{{ url_for('static', filename='js/three/vendor/OrbitControls.js') }}"
  }
}
</script>
<script type="module" src="{{ url_for('static', filename='js/three/scene3d.js') }}"></script>
```

Place the importmap before the module script. Do not load `scene3d.js` as a classic script.

- [ ] **Step 4: Add frontend contract assertions**

In `backend/tests/test_frontend_a16_ui_contract.py`, assert:

```python
assert 'id="render-switcher"' in INDEX_HTML
assert 'id="three-stage"' in INDEX_HTML
assert 'type="importmap"' in INDEX_HTML
assert '"three"' in INDEX_HTML
assert 'OrbitControls.js' in INDEX_HTML
assert 'type="module"' in INDEX_HTML
assert 'scene3d.js' in INDEX_HTML
```

- [ ] **Step 5: Implement `scene3d.js`**

Create a small adapter, not a full rewrite. Public API:

```javascript
window.CanteenApp3D = {
    init(container),
    render(snapshot, appState),
    dispose(),
};
```

Minimum behavior:

- Campus view: render canteen buildings from `snapshot.canteens[*].campus_position`.
- Canteen view: render active canteen floors from `snapshot.canteens[id].floors`.
- Student agents: render visible queue/serving/waiting dots from `students`.
- 学活 pending: render as translucent placeholder only from `visible_canteens` metadata; it must not appear in routing/statistics unless the user later supplies real data.
- Use OrbitControls; keep 2D fallback available.

Use the V7 prototype in `.superpowers/brainstorm/96186-1778598663/canteen-three-real-model-v7.html` as the visual reference, but replace hardcoded data with live snapshots wherever possible.

- [ ] **Step 6: Wire render mode in `main.js`**

Add:

```javascript
state.renderMode = '2d';
```

In `dispatchStep()`:

```javascript
if (state.renderMode === '3d' && window.CanteenApp3D) {
    window.CanteenApp3D.render(data, state);
} else {
    // existing 2D path
}
```

Keep 2D as default.

- [ ] **Step 7: Style 3D stage**

Add stable dimensions:

```css
.three-stage {
    width: 100%;
    min-height: 560px;
    aspect-ratio: 16 / 9;
    background: #07111d;
    border: 1px solid var(--c-border-dark);
    border-radius: var(--radius-sm);
    overflow: hidden;
}
```

- [ ] **Step 8: Static verification**

Run:

```bash
node --check frontend/static/js/main.js
node --input-type=module --check < frontend/static/js/three/scene3d.js
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_a16_ui_contract.py -q
```

Expected: all pass.

- [ ] **Step 9: Browser verification**

Open `http://127.0.0.1:5001/`:

- Switch to campus mode.
- Start simulation.
- Switch 2D -> 3D.
- Confirm the WebGL canvas is nonblank via screenshot/pixel check.
- Switch campus map -> canteen detail.
- Confirm floor stack appears for Minghu/Xuesi.
- Confirm 学活 appears only as pending placeholder metadata, not as a runtime canteen with queue/statistics.
- Confirm switching back to 2D still works.

- [ ] **Step 10: Commit**

```bash
git add frontend/static/js/three/ frontend/templates/index.html frontend/static/js/main.js frontend/static/css/style.css backend/tests/test_frontend_a16_ui_contract.py
git commit -m "feat(frontend): add optional Three.js 3D demo view"
```

---

### Task 5: Documentation And Demo Script

**Files:**
- Modify: `README.md`
- Create: `docs/phase3/demo_script.md`
- Modify: `task_plan.md`
- Modify: `findings.md`
- Modify: `progress.md`

- [ ] **Step 1: Update README technical shape**

README should mention:

- Single-canteen mode remains compatible.
- Campus mode uses SimPy `CampusCoordinator`.
- 学活 data is pending by design.
- Browser URL and regression command.
- 2D/3D view switch if Task 4 is complete.

- [ ] **Step 2: Write demo script**

Create `docs/phase3/demo_script.md`:

```markdown
# Demo Script

## 1. Single-Canteen Baseline

Show Phase 2 compatibility: config, start, finish, statistics, history.

## 2. Campus Joint Simulation

Use BJTU lunch preset. Explain Minghu/Xuesi are field-backed; 学活 remains pending and is not overclaimed.

## 3. 2D/3D Visualization

Show campus overview, canteen drilldown, floor tabs, and optional 3D.

## 4. Evidence

Mention pytest count and browser E2E check.
```

- [ ] **Step 3: Update root planning files**

Mark the demo polish plan phases and note remaining data gaps.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/phase3/demo_script.md task_plan.md findings.md progress.md
git commit -m "docs: update demo script and current system shape"
```

---

### Task 6: Final Regression And Handoff

**Files:**
- Verify only unless a failure is found.

- [ ] **Step 1: Run backend regression**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q
```

Expected: all tests pass; current baseline before this plan was `138 passed`.

- [ ] **Step 2: Run JS syntax checks**

Run:

```bash
node --check frontend/static/js/main.js
node --check frontend/static/js/campus.js
node --check frontend/static/js/campus_map.js
node --check frontend/static/js/floor_tabs.js
node --input-type=module --check < frontend/static/js/three/scene3d.js
```

Expected: no output and exit code 0.

- [ ] **Step 3: Run browser flow**

Repeat the browser E2E checklist and update `docs/phase3/browser_e2e_check.md`.

- [ ] **Step 4: Confirm no external generated clutter**

Run:

```bash
git status --short
git diff --stat
test ! -d outputs
```

Expected: no `outputs/`; only intended tracked changes remain. Review the status/stat output before staging anything, especially because this workspace may already contain unrelated Phase 2 doc edits and guardrail files.

- [ ] **Step 5: Final commit with explicit path list**

```bash
git add \
  .gitignore \
  AGENTS.md CLAUDE.md agent.md \
  backend/api/campus_routes.py \
  backend/simulation/presets/loader.py \
  backend/tests/test_campus_api.py \
  backend/tests/test_campus_preset_loader.py \
  backend/tests/test_frontend_a16_ui_contract.py \
  backend/tests/test_frontend_main_js_contract.py \
  frontend/templates/index.html \
  frontend/static/css/style.css \
  frontend/static/js/main.js \
  frontend/static/js/three/ \
  docs/phase3/browser_e2e_check.md \
  docs/phase3/screenshots/ \
  docs/phase3/integration_bug_log.md \
  docs/phase3/demo_script.md \
  README.md \
  task_plan.md findings.md progress.md \
  docs/superpowers/plans/2026-05-13-canteen-demo-polish-plan.md
git commit -m "chore: finalize canteen demo polish and verification"
```

---

## Execution Notes

- Execute tasks in order. Task 4 depends on Task 2/3 only for a polished demo path, not for backend correctness.
- If time is tight, finish Tasks 0-3 first; those close the strongest teacher-facing risks.
- Do not treat 学活 pending data as a failure in this plan. The correct behavior is transparent labeling and no fake capacity claims.
