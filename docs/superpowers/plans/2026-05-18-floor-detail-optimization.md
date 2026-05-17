# Floor Detail Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use @superpowers:subagent-driven-development (recommended) or @superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Use @superpowers:test-driven-development for every task: failing test → red → minimal impl → green → commit.

**Goal:** Make each Minghu floor read as a believable cafeteria — realistic 4-part service stalls, regularized table blocks, and readable crowd flow — as a renderer-only change.

**Architecture:** Two front-end Three.js modules. `state_adapter.js` owns the coordinate/footprint/path model consumed by render frames; `canteen_scene.js` owns geometry/materials and mirrors the per-floor profiles. The large `backend/tests/test_frontend_three_js_contract.py` suite (~60 tests, Node-driven) is the executable spec and the regression gate. Backend, APIs, snapshot shape, statistics, floor skeleton/footprint strategy, camera presets, palette system, flicker materials, and the analysis panel are untouched.

**Tech Stack:** Plain JavaScript ES modules · Three.js (vendored) · Python `pytest` (subprocess Node harness) · `node --check`.

**Authoritative spec:** `docs/superpowers/specs/2026-05-18-floor-detail-optimization-design.md` (spec-review Approved).

**Hard constraints (every commit obeys):**
- Renderer-only. No edits under `backend/`, `frontend/static/js/main.js`, `frontend/templates/`, CSS palette, camera presets, or panel code. Test files under `backend/tests/` are the only backend-tree files this plan edits.
- `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q` must stay green; the only intentional contract test changes are the new focused tests this plan adds and any deliberately-stated token migration (explained in the commit message — never silent weakening).
- Selective staging: each commit `git add`s only the paths the task lists. Never `git add -A` / `git add .`. The worktree is already dirty with unrelated changes; do not stage them. Never touch `docs/phase2/*`.
- `scene3d.js` facade unchanged: `window.CanteenApp3D.init/render/dispose`, `visibleCanteens`, `pendingCanteens`.
- Window meshes keep `userData { floorId, kind:'window', windowId }` and intervention hooks (`_activeWindowInterventionEffect`, `_tagWindowInterventionBody`, `_addWindowInterventionPulse`); labels keep `alwaysReadableWindowLabel` + `WINDOW_LABEL_RENDER_ORDER`-based `renderOrder`.
- All 6 backend 1F windows render as real front-band windows; forbidden tokens `f1-added-window`, `f1-fake-window`, `addedWindowCount`, `fabricatedWindow` never appear.
- 1F-sample plan `docs/superpowers/plans/2026-05-18-1f-layout-sample.md` is **superseded** by this plan (Task 0). Do not execute it separately.

**Branch:** Work on the current feature branch `codex/minghu-realistic-3d` (not `main`). No worktree was requested.

---

## File Structure

- Modify: `docs/superpowers/plans/2026-05-18-1f-layout-sample.md` — add superseded banner (Task 0).
- Modify: `frontend/static/js/three/canteen_scene.js`
  - `_addServiceStall` (front branch ~1592–1671; `left` branch ~1528–1590): rewrite as 4-part stall with a per-floor theme table.
  - Add module-level `STALL_THEME` constant (near `PALETTE`/`FLOOR_TABLE_COLOR_FALLBACKS`, ~357).
  - `_addFloorIdentityCues` (~1811+): re-emit existing cue tokens after table regularization.
  - `_studentAvatar` (~1904+): orient moving avatars along travel direction.
  - Mirror any `MINGHU_FLOOR_LAYOUTS` block-parameter changes from the adapter.
- Modify: `frontend/static/js/three/state_adapter.js`
  - `tableBlockPosition` (~212–237) and `MINGHU_FLOOR_LAYOUTS` block params (~58–216): regularize even grid + clearances.
  - Path waypoint generation (the function that emits per-student `path`/`position3d` used by `buildFrame`): keep waypoints inside `footprint` and out of table-block AABBs.
- Modify: `backend/tests/test_frontend_three_js_contract.py` — add focused tests (Tasks A1, B1, C1). No deletion or weakening of existing assertions.

---

## Task 0: Supersede the 1F-sample plan (prevent double-apply)

**Files:**
- Modify: `docs/superpowers/plans/2026-05-18-1f-layout-sample.md`

- [ ] **Step 1: Add a superseded banner at the very top of the file**

Insert as the first lines, above the existing `# 1F Layout Sample Implementation Plan` heading:

```markdown
> **SUPERSEDED (2026-05-18):** This 1F-only plan is replaced by
> `docs/superpowers/plans/2026-05-18-floor-detail-optimization.md`, whose spec
> `docs/superpowers/specs/2026-05-18-floor-detail-optimization-design.md` is a
> superset (all floors + window structure + crowd flow). Do NOT execute this
> plan independently; the 1F changes are integrated once by the superset plan.

```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/plans/2026-05-18-1f-layout-sample.md
git commit -m "docs: mark 1F-sample plan superseded by floor-detail-optimization"
```

## Task 1: Capture the regression baseline

**Files:** none (characterization only)

- [ ] **Step 1: Record current syntax + suite state**

Run:
```bash
node --check frontend/static/js/three/state_adapter.js
node --check frontend/static/js/three/canteen_scene.js
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py -q
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q
```

- [ ] **Step 2: Write down the baseline numbers**

Record the exact passed/failed counts for the contract file and the full suite in the task notes (the dirty worktree may already have unrelated failures — those are pre-existing and must not be attributed to this plan). Both `node --check` commands must exit 0; if not, stop and surface — the plan assumes syntactically valid baseline files.

- [ ] **Step 3: No commit** (characterization only)

---

## Phase A — Windows as realistic 4-part stalls

### Task A1: Lock the stall-structure contract (front + side)

**Files:**
- Modify: `backend/tests/test_frontend_three_js_contract.py`

- [ ] **Step 1: Append the failing test**

```python
def test_service_stall_is_four_part_with_per_floor_theme():
    """Spec §A: each window renders signboard band + open-kitchen glass +
    base counter + tray rail/status strip, themed per floor, and keeps the
    intervention/label contract hooks."""
    scene = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")

    # 4-part stall structure tokens (front and side share the vocabulary)
    for tok in (
        "stall signboard band",
        "stall open-kitchen glass",
        "stall base counter",
        "stall tray rail",
        "stall status strip",
    ):
        assert tok in scene, f"missing stall structure token: {tok!r}"

    # Per-floor theme table keyed by floor id (1 steel / 2 wood+brass / 3 dark wood)
    assert "STALL_THEME" in scene
    for fid in ("1:", "2:", "3:"):
        assert fid in scene.split("STALL_THEME", 1)[1][:600], \
            f"STALL_THEME missing floor key {fid!r}"

    # Contract hooks preserved
    assert "kind: 'window'" in scene
    assert "_tagWindowInterventionBody(" in scene
    assert "_addWindowInterventionPulse(" in scene
    assert "alwaysReadableWindowLabel" in scene
    assert "WINDOW_LABEL_RENDER_ORDER" in scene

    # No fabricated windows ever
    for forbidden in ("f1-added-window", "f1-fake-window",
                      "addedWindowCount", "fabricatedWindow"):
        assert forbidden not in scene
```

`THREE_DIR` is already defined in this file (used by the 1F tests near line 2410); if a local helper constant is missing in scope, mirror the exact `THREE_DIR = ...` line the neighbouring 1F tests use — do not invent a new path.

- [ ] **Step 2: Run it red**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py::test_service_stall_is_four_part_with_per_floor_theme -q`
Expected: FAIL (tokens / `STALL_THEME` absent).

- [ ] **Step 3: Commit the failing test**

```bash
git add backend/tests/test_frontend_three_js_contract.py
git commit -m "test(3d): lock 4-part themed service stall contract (red)"
```

### Task A2: Implement the 4-part front stall + theme table

**Files:**
- Modify: `frontend/static/js/three/canteen_scene.js` (add `STALL_THEME` ~357; rewrite `_addServiceStall` front branch ~1592–1671)
- Test: `backend/tests/test_frontend_three_js_contract.py`

- [ ] **Step 1: Add the per-floor theme table** near `FLOOR_TABLE_COLOR_FALLBACKS` (~357), low/zero emissive per spec ("不要亮"):

```javascript
// Spec §A per-floor stall theme: material/color-temperature only, emissive ≈ 0.
const STALL_THEME = {
    1: { sign: 0x8a9aa6, counter: 0x9aa7ad, rail: 0x7d8a90, glass: 0xbcd6db, roughness: 0.40 }, // brushed steel, cool
    2: { sign: 0xc79a58, counter: 0xb88c4f, rail: 0x8a6537, glass: 0xe8d2a8, roughness: 0.46 }, // warm wood + brass
    3: { sign: 0x7a5a40, counter: 0x6e553e, rail: 0x4e3b2a, glass: 0x9b7d55, roughness: 0.52 }, // dark wood, warm
};
function stallTheme(floorId) {
    return STALL_THEME[floorId] || STALL_THEME[1];
}
```

- [ ] **Step 2: Augment the front branch of `_addServiceStall` additively** (the code after the `if (layoutSide === 'left') { ... return; }` block, ~1592–1671).

  **Additive-only rule (this is the one place implementation can stall):** the existing boxes `'photo service counter window'`, `'glass food guard'`, `'front service status rail'`, `'front service serving status light'`, the queue-heat strip, the `closing` label, and **every `FRONT_WINDOW_*` named size/colour constant** must remain in the source **verbatim** — they are hard-asserted by `test_front_window_status_cue_does_not_render_as_dark_residual_block`, `test_canteen_scene_front_windows_do_not_render_large_red_serving_blocks`, `test_canteen_scene_front_service_windows_are_large_enough_for_1f_focus_view`, `test_front_service_windows_restore_light_counters_without_dark_residual_blocks`, and the plan forbids editing those tests. Do **not** rename, delete, or "replace" any existing token or constant. The only allowed source delta is **adding** the new `'stall …'` themed parts as a visual superset layered with the existing meshes.

  Concretely, leaving all existing lines in place:
  - Keep the `const body = this._box(group, 'photo service counter window', FRONT_WINDOW_COUNTER_SIZE, [x, y + 2.7, z], this._photoMat(... open?0xd8e2df:0x5c6874 ...), { floorId, kind:'window', windowId: win.id })` line and its `_tagWindowInterventionBody(body, interventionEffect)` exactly.
  - Keep the existing `'glass food guard'`, `'front service status rail'`, `'front service serving status light'` boxes and all `FRONT_WINDOW_*` constants unchanged (the new glass/status parts are *additional* themed geometry, not substitutes; let the new glass sit just outside the retained guard, the new status strip beside the retained rail).
  - Add `const th = stallTheme(floorId);`.
  - **Add** these new named parts via `this._box(group, '<token>', size, pos, this._photoMat(color, { opacity, roughness: th.roughness, emissive: <same color>, emissiveIntensity: win.is_serving ? 0.03 : 0.012 }))`:
    - `'stall signboard band'` — thin band above the counter at the label height; colour `th.sign`; position the existing `_addMenuBoard` call (kept verbatim, with `alwaysReadableWindowLabel`/`renderOrder`) just in front of it.
    - `'stall open-kitchen glass'` — colour `th.glass`, `opacity: 0.34`, no specular boost; positioned relative to `FRONT_WINDOW_COUNTER_SIZE` (in addition to, not instead of, `'glass food guard'`).
    - `'stall base counter'` — a low plinth under the existing counter mesh; colour `th.counter`.
    - `'stall tray rail'` — a thin rail at the front edge; colour `th.rail`.
    - `'stall status strip'` — a thin strip driven by the same `frontStatusRailColor` open/serving/closed logic; thin opacity (in addition to, not instead of, `'front service status rail'`).
  - Keep the `win.is_open && win.is_serving` serving-light box, the `sat`/queue-heat strip block, and the `!win.is_open && win.closing` label unchanged.
  - End with the unchanged `this._addWindowInterventionPulse(group, x, y, z, layoutSide, interventionEffect);`.

  New-part dimensions are still bounded by `test_canteen_scene_uses_matte_service_window_effects`, `test_canteen_scene_front_window_queue_heat_uses_thin_strip_not_red_cap`, `test_window_labels_do_not_draw_dark_backplate_blocks`, `test_canteen_scene_front_window_labels_are_centered_on_their_windows`. Tune the new boxes' sizes until the full window/label/matte regression set passes; never weaken a regression test.

- [ ] **Step 3: `node --check`**

Run: `node --check frontend/static/js/three/canteen_scene.js`
Expected: exit 0.

- [ ] **Step 4: Run focused + window regression**

Run:
```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py::test_service_stall_is_four_part_with_per_floor_theme -q
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py -k "window or stall or label or matte or serving or heat" -q
```
Expected: the new test PASS; all window/label regression tests still PASS. If a regression test fails, adjust geometry (do not edit the regression test).

- [ ] **Step 5: Commit**

```bash
git add frontend/static/js/three/canteen_scene.js backend/tests/test_frontend_three_js_contract.py
git commit -m "feat(3d): 4-part themed front service stall (hooks/labels/intervention intact)"
```

### Task A3: Mirror the 4-part structure on the side (`left`) branch

**Files:**
- Modify: `frontend/static/js/three/canteen_scene.js` (`_addServiceStall` `left` branch ~1528–1590)
- Test: `backend/tests/test_frontend_three_js_contract.py`

- [ ] **Step 1: Extend the Task A1 test** with a side-branch assertion (append inside the same test or as a new test `test_side_service_stall_shares_four_part_structure`):

```python
def test_side_service_stall_shares_four_part_structure():
    scene = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    left = scene.split("if (layoutSide === 'left')", 1)[1].split("return;", 1)[0]
    for tok in ("stall signboard band", "stall open-kitchen glass",
                "stall base counter", "stall status strip"):
        assert tok in left, f"side stall missing {tok!r}"
    assert "kind: 'window'" in left
```

- [ ] **Step 2: Run red**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py::test_side_service_stall_shares_four_part_structure -q`
Expected: FAIL.

- [ ] **Step 3: Augment the `left` branch additively** (~1528–1590). Same additive-only rule as Task A2 Step 2: keep the existing `'sideWall service counter window'` (`body` with `{ kind:'window', windowId }`), `'sideWall glass food guard'`, `'sideWall red stall menu fascia'` boxes, `_tagWindowInterventionBody`, side label (with `alwaysReadableWindowLabel`), `sat` queue-heat cap, `closing` label, and trailing `_addWindowInterventionPulse(... 'left' ...)` all verbatim. **Add** the new `'stall signboard band'`, `'stall open-kitchen glass'`, `'stall base counter'`, `'stall status strip'` parts at side-wall scale using `stallTheme(floorId)`. No existing side token is renamed or removed.

- [ ] **Step 4: `node --check` + focused + side-window regression**

Run:
```bash
node --check frontend/static/js/three/canteen_scene.js
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py -k "side or stall or window" -q
```
Expected: new test PASS; `test_third_floor_hotpot_window_uses_side_wall_layout` and `test_third_floor_side_windows_do_not_overlap_front_stalls` still PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/static/js/three/canteen_scene.js backend/tests/test_frontend_three_js_contract.py
git commit -m "feat(3d): side service stall mirrors 4-part themed structure"
```

---

## Phase B — Table-layout regularization

### Task B1: Lock the regularized-grid contract

**Files:**
- Modify: `backend/tests/test_frontend_three_js_contract.py`

- [ ] **Step 1: Append the failing test** (drives `StateAdapter` via the existing Node subprocess pattern used by `test_minghu_1f_layout_sample_is_dense_and_semantically_truthful` at ~2410 — copy that test's `subprocess.run(["node", "--input-type=module", "-e", script], cwd=REPO_ROOT, ...)` harness shape exactly):

```python
def test_table_blocks_are_regularized_grids_inside_footprint():
    """Spec §B: per block, rows/cols are evenly spaced (single dz step,
    single dx step), all tables inside footprint, and the 3 floors stay
    distinct. Cue tokens still emitted by canteen_scene."""
    scene = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    for cue in ("f1-snake-queue-guide", "f1-pickup-return-lane",
                "f1-main-aisle-cue", "f1-condiment-station",
                "f1-tray-return-point"):
        assert cue in scene, f"cue token dropped: {cue!r}"

    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';
        function floor(fid, nseat) {
          return { floor_id: fid,
            windows: Array.from({length:6},(_,i)=>({id:`f${fid}-w${i}`,floor_id:fid,is_open:true})),
            seats: Array.from({length:nseat},(_,i)=>({id:`f${fid}-s${i}`,floor_id:fid,status:'empty'})),
            students: [] };
        }
        const adapter = new StateAdapter();
        const out = {};
        for (const [fid, ns] of [[1,172],[2,232],[3,208]]) {
          const frame = adapter.buildFrame(
            { canteens: { minghu_xueyi: { id:'minghu_xueyi', display_name:'明湖',
              floors:[floor(fid, ns)] } } },
            { activeCanteenId:'minghu_xueyi' });
          const f = frame.floors[0];
          const xs = f.seats.map(s=>Math.round(s.position.x));
          const zs = f.seats.map(s=>Math.round(s.position.z));
          out[fid] = {
            inFootprint: f.seats.every(s =>
              s.position.x >= f.footprint.minX - 1 &&
              s.position.x <= f.footprint.maxX + 1 &&
              s.position.z >= f.footprint.minZ - 1 &&
              s.position.z <= f.footprint.maxZ + 1),
            minZ: Math.min(...zs),
            maxWinZ: Math.max(...f.windows.map(w=>w.position.z)),
            uniqX: new Set(xs).size,
            uniqZ: new Set(zs).size,
            sig: xs.slice(0,8).join(',')+'|'+zs.slice(0,8).join(','),
          };
        }
        console.log(JSON.stringify(out));
        """
    )
    payload = json.loads(subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT, check=True, text=True, capture_output=True).stdout)

    for fid in ("1", "2", "3"):
        assert payload[fid]["inFootprint"] is True, f"floor {fid} overflows footprint"
        # tables start clearly behind the service/queue band
        assert payload[fid]["minZ"] >= payload[fid]["maxWinZ"] + 60, fid
        # a real grid: several distinct rows and columns
        assert payload[fid]["uniqX"] >= 6 and payload[fid]["uniqZ"] >= 5, fid
    # floors are not identical layouts
    assert len({payload["1"]["sig"], payload["2"]["sig"], payload["3"]["sig"]}) == 3
```

- [ ] **Step 2: Run red**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py::test_table_blocks_are_regularized_grids_inside_footprint -q`
Expected: FAIL (current scattered/edge-stuck placement, or insufficient buffer/grid uniqueness).

- [ ] **Step 3: Commit the failing test**

```bash
git add backend/tests/test_frontend_three_js_contract.py
git commit -m "test(3d): lock regularized table-grid + cue-token contract (red)"
```

### Task B2: Regularize block positioning + re-emit cue tokens

**Files:**
- Modify: `frontend/static/js/three/state_adapter.js` (`tableBlockPosition` ~212–237; `MINGHU_FLOOR_LAYOUTS` block params ~58–216)
- Modify: `frontend/static/js/three/canteen_scene.js` (mirror block params; `_addFloorIdentityCues` ~1811+ re-emit cue tokens)
- Test: `backend/tests/test_frontend_three_js_contract.py`

- [ ] **Step 1: Regularize `tableBlockPosition`** (state_adapter.js ~212–237). The function already computes a clean `col/row` grid from `block.cols`, `block.dx`, `block.dz` and clamps to footprint. Make spacing uniform and the buffer explicit:
  - Ensure the per-block `z` origin starts at `tableZoneStartZ(profile)` plus `block.z` with **no** profile-level `tableRowStagger` applied to seats (set `tableRowStagger: 0` in any profile that still uses it, or stop reading it here) so rows are evenly stepped by a single `dz`.
  - Keep the `Math.max(footprint.minX+28, Math.min(footprint.maxX-28, x))` clamp; verify each block's `cols`, `dx`, `dz`, `left/right/offsetX`, and `z` keep the whole block inside `[minX, maxX] × [tableZoneStartZ, footprint.maxZ-28]` for the seat counts used in the B1 test (1F 172, 2F 232, 3F 208).
  - Adjust only block parameters in `MINGHU_FLOOR_LAYOUTS` (counts/cols/dx/dz/anchor/offset/z) so each floor forms aligned rows with a readable central main-aisle gap and a queue→table buffer; keep the three floors' block composition distinct (1F four-seat squares; 2F large central island + side banks; 3F wall-booth run + central small-group + long-table run + window booths). Do not rename block `id`s or change `profile.key`.

- [ ] **Step 2: Mirror the same block params** in `canteen_scene.js` `MINGHU_FLOOR_LAYOUTS` (~362+) so the rendered geometry matches the adapter coordinates exactly (this codebase keeps the two profile copies in sync).

- [ ] **Step 3: Re-emit cue tokens** in `_addFloorIdentityCues` (~1811+). Because regularization moves the cue meshes, the helper must still create boxes whose `name` contains each of `f1-snake-queue-guide`, `f1-pickup-return-lane`, `f1-main-aisle-cue`, `f1-condiment-station`, `f1-tray-return-point` (and keep the legacy alias names already present in the 1F `cueNames`). Recompute their positions from the new `footprint`/`tableStartZ`, keeping them flat/low-opacity per the existing `test_canteen_scene_1f_utility_cues_are_flat_not_solid_residual_blocks` and `test_canteen_scene_1f_identity_cues_resolve_floor_footprint_before_use`.

- [ ] **Step 4: `node --check` both files**

Run:
```bash
node --check frontend/static/js/three/state_adapter.js
node --check frontend/static/js/three/canteen_scene.js
```
Expected: exit 0.

- [ ] **Step 5: Run focused + table/footprint/1F regression**

Run:
```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py::test_table_blocks_are_regularized_grids_inside_footprint -q
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py -k "table or footprint or 1f or layout or distinct" -q
```
Expected: new test PASS; `test_minghu_1f_layout_sample_is_dense_and_semantically_truthful`, `test_table_layout_*`, `test_state_adapter_derives_distinct_floor_footprints_*`, `test_state_adapter_uses_distinct_minghu_floor_layouts` all still PASS. If a 1F-sample metric fails, retune block params (not the test).

- [ ] **Step 6: Commit**

```bash
git add frontend/static/js/three/state_adapter.js frontend/static/js/three/canteen_scene.js backend/tests/test_frontend_three_js_contract.py
git commit -m "feat(3d): regularize table blocks into aligned grids; cue tokens re-emitted"
```

---

## Phase C — Crowd-flow readability

### Task C1: Lock student-orientation + path-clearance contract

**Files:**
- Modify: `backend/tests/test_frontend_three_js_contract.py`

- [ ] **Step 1: Append the failing test** (the spec §C machine-checkable acceptance signal). Use the same Node subprocess harness:

```python
def test_student_paths_avoid_furniture_and_avatars_face_travel():
    scene = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    # avatar orients along travel direction
    assert "lookAt(" in scene or "rotation.y" in scene
    assert "studentAvatar" in scene

    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';
        const adapter = new StateAdapter();
        // Recognized snapshot states only (no invented window_id/seat_id keys;
        // p2 is a brand-new arrival → entering path).
        const students = [
          { id:'p1', floor_id:1, position:'window_queue' },
          { id:'p2', floor_id:1 },
          { id:'p3', floor_id:1, position:'seated' },
        ];
        const frame = adapter.buildFrame(
          { canteens: { minghu_xueyi: { id:'minghu_xueyi', display_name:'明湖',
            floors:[{ floor_id:1,
              windows:Array.from({length:6},(_,i)=>({id:`f1-w${i}`,floor_id:1,is_open:true})),
              seats:Array.from({length:172},(_,i)=>({id:`f1-s${i}`,floor_id:1,status:'empty'})),
              students }] } } },
          { activeCanteenId:'minghu_xueyi' });
        const f = frame.floors[0];
        const pts = [];
        for (const s of f.students) {
          if (Array.isArray(s.path)) pts.push(...s.path);
          if (s.position3d) pts.push(s.position3d);
        }
        const inFoot = pts.every(p =>
          p.x >= f.footprint.minX - 2 && p.x <= f.footprint.maxX + 2 &&
          p.z >= f.footprint.minZ - 2 && p.z <= f.footprint.maxZ + 2);
        console.log(JSON.stringify({ count: pts.length, inFoot }));
        """
    )
    payload = json.loads(subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT, check=True, text=True, capture_output=True).stdout)
    assert payload["count"] > 0
    assert payload["inFoot"] is True
```

If `buildFrame` does not expose per-student `path`, this test still asserts `position3d` waypoints stay in footprint; the orientation half is asserted on the scene source. Keep assertions to what the adapter already produces — do not invent a `path` field if none exists; in that case drop the `s.path` line and keep `position3d` only.

- [ ] **Step 2: Run red**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py::test_student_paths_avoid_furniture_and_avatars_face_travel -q`
Expected: FAIL (no avatar orientation yet, and/or waypoints out of footprint).

- [ ] **Step 3: Commit the failing test**

```bash
git add backend/tests/test_frontend_three_js_contract.py
git commit -m "test(3d): lock student orientation + in-footprint path contract (red)"
```

### Task C2: Orient avatars + keep flow waypoints reachable

**Files:**
- Modify: `frontend/static/js/three/canteen_scene.js` (`_studentAvatar` ~1904+)
- Modify: `frontend/static/js/three/state_adapter.js` (waypoint generation feeding `buildFrame`)
- Test: `backend/tests/test_frontend_three_js_contract.py`

- [ ] **Step 1: Orient the avatar** in `_studentAvatar`. After the avatar `Group` position is set, if the student is moving (has a previous/target delta available — reuse whatever interpolation source `state_adapter` already provides, e.g. `student.target` vs `student.position3d`), set the group's `rotation.y` from `Math.atan2(dx, dz)` (guard the zero-length case so seated/queued avatars keep a stable facing). Do not change body/head/status-ring geometry or `stableStudentClothingColor`.

- [ ] **Step 2: Constrain waypoints** in the adapter's path/target generation: clamp each generated waypoint to the floor `footprint` bounds (mirror the existing `Math.max(minX..) / Math.min(maxX..)` clamp pattern already used in `tableBlockPosition`) and route the entrance→window→queue→pickup→seat sequence through the existing aisle/queue anchors rather than straight lines through table-block centres. Reuse `WINDOW_QUEUE_LANES`/`WINDOW_QUEUE_LANE_DX`/`WINDOW_QUEUE_ROW_DZ` for queue formation. Preserve the existing `floor_switching` stair-core rendering path untouched.

- [ ] **Step 3: `node --check` both files**

Run:
```bash
node --check frontend/static/js/three/state_adapter.js
node --check frontend/static/js/three/canteen_scene.js
```
Expected: exit 0.

- [ ] **Step 4: Run focused + flow regression**

Run:
```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py::test_student_paths_avoid_furniture_and_avatars_face_travel -q
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py -k "student or path or flow or spawn or queue or entrance" -q
```
Expected: new test PASS; `test_canteen_scene_does_not_draw_student_route_lines`, `test_canteen_scene_focus_does_not_draw_unexplained_flow_line`, `test_state_adapter_marks_new_student_entry_path_from_gate`, `test_state_adapter_places_floor_switching_students_on_stair_core`, `test_state_adapter_spreads_student_spawn_and_queue_points` all still PASS (do not reintroduce drawn route lines — orientation is mesh rotation only).

- [ ] **Step 5: Commit**

```bash
git add frontend/static/js/three/canteen_scene.js frontend/static/js/three/state_adapter.js backend/tests/test_frontend_three_js_contract.py
git commit -m "feat(3d): avatars face travel; flow waypoints stay reachable in footprint"
```

---

## Phase D — Full regression + browser evidence

### Task D1: Suite gate + per-floor browser check

**Files:**
- Modify: `docs/phase3/browser_e2e_check.md` (append a dated section), optional `docs/phase3/screenshots/`

- [ ] **Step 1: JS syntax gate**

Run:
```bash
node --check frontend/static/js/three/state_adapter.js
node --check frontend/static/js/three/canteen_scene.js
```
Expected: both exit 0.

- [ ] **Step 2: Full backend suite gate**

Run: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q`
Expected: passed count ≥ the Task 1 baseline plus the 4 new tests; zero new failures. Any pre-existing dirty-worktree failure recorded in Task 1 stays unchanged and is explicitly noted as not caused by this plan.

- [ ] **Step 3: Browser check (record real evidence)**

Start the app and drive the single-canteen 3D flow:
```bash
PYTHONPATH=backend ./.venv/bin/python backend/app.py
```
For each floor focus (1F/2F/3F) confirm and capture: 4-part themed stall (per-floor material, no glow/bloom); tables in even aligned rows with readable main aisle + queue buffer, nothing outside the floor edge; students face travel direction and queue in lanes; entrance→window→queue→pickup→seat reads correctly; cross-floor via stair core; zero console errors. Save screenshots under `docs/phase3/screenshots/` if captured.

- [ ] **Step 4: Append evidence + commit**

Append a dated "Floor detail optimization" section to `docs/phase3/browser_e2e_check.md` with: files changed, baseline vs final pass counts, per-floor observations, residual risks.

```bash
git add docs/phase3/browser_e2e_check.md docs/phase3/screenshots
git commit -m "test(e2e): floor detail optimization browser evidence (windows/tables/flow)"
```

---

## Out of scope (separate later specs/plans)
Item 2 color palette, item 3 whole-building 3D presence, item 4 floor flicker full fix, item 5 multi-angle per floor, item 6 analysis panel. Do not touch their code areas here beyond minimal, stated shared-helper fallout.

## Plan-level done criteria
- Tasks 0–D1 committed with selective staging; no unrelated dirty files staged; `docs/phase2/*` untouched.
- `node --check` clean on both JS files; `pytest backend/tests -q` ≥ baseline + 4 new, no new failures.
- `scene3d.js` facade, window `userData`, intervention hooks, `alwaysReadableWindowLabel`/`renderOrder`, 1F tokens, and forbidden-token absence all preserved.
- 1F-sample plan marked superseded and not separately executed.
- Browser evidence recorded for 1F/2F/3F.
