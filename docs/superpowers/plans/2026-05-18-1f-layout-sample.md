> **SUPERSEDED (2026-05-18):** This 1F-only plan is replaced by
> `docs/superpowers/plans/2026-05-18-floor-detail-optimization.md`, whose spec
> `docs/superpowers/specs/2026-05-18-floor-detail-optimization-design.md` is a
> superset (all floors + window structure + crowd flow). Do NOT execute this
> plan independently; the 1F changes are integrated once by the superset plan.

# 1F Layout Sample Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reshape Minghu 1F into the approved "full but not chaotic" cafeteria layout sample while preserving backend truth: 6 real open 1F windows, no fabricated added windows, no backend/API changes.

**Architecture:** This is a frontend Three.js layout-profile change. `state_adapter.js` owns the coordinate/footprint model used by runtime frames; `canteen_scene.js` must mirror the 1F profile and add 1F-only visual cues. Backend snapshots, statistics, 2F/3F layout profiles, camera presets, floor-flicker material strategy, and analysis panels stay out of scope.

**Tech Stack:** Plain JavaScript ES modules, Three.js, Python pytest contract tests, Node `--check`.

---

## File Structure

- Modify: `backend/tests/test_frontend_three_js_contract.py`
  - Add focused contract coverage for the 1F sample: semantic 6-window rendering, denser two-zone profile tokens, and no fake "added window" production tokens.
- Modify: `frontend/static/js/three/state_adapter.js`
  - Incrementally reshape only `MINGHU_FLOOR_LAYOUTS[1]`.
  - Keep 6 backend windows distributed across the front service band.
  - Increase 1F density with left four-person island, central dining island, right long-table zone, rear booth/fill zone, and enough queue/circulation spacing.
- Modify: `frontend/static/js/three/canteen_scene.js`
  - Mirror the 1F layout profile.
  - Replace/extend 1F identity cues so the focused 1F view shows queue lane, pickup/return lane, main aisle, condiment point, and tray-return point.

Do not touch backend preset files, backend simulation code, `main.js`, 2F/3F profiles except shared helper fallout, CSS palette work, camera/view work, or analysis-panel code in this plan.

## Task 1: Lock 1F Layout Contract Before Editing Production JS

**Files:**
- Modify: `backend/tests/test_frontend_three_js_contract.py`

- [ ] **Step 1: Write the failing test**

Append a focused contract test:

```python
def test_minghu_1f_layout_sample_is_dense_and_semantically_truthful():
    adapter = (THREE_DIR / "state_adapter.js").read_text(encoding="utf-8")
    scene = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")

    required_tokens = (
        "f1-front-service-band",
        "f1-left-four-seat-island",
        "f1-central-dining-island",
        "f1-right-long-table-zone",
        "f1-rear-booth-fill",
        "f1-snake-queue-guide",
        "f1-pickup-return-lane",
        "f1-main-aisle-cue",
        "f1-condiment-station",
        "f1-tray-return-point",
    )
    for tok in required_tokens:
        assert tok in adapter or tok in scene, f"missing 1F layout token: {tok!r}"

    forbidden_tokens = (
        "f1-added-window",
        "f1-fake-window",
        "addedWindowCount",
        "fabricatedWindow",
    )
    for tok in forbidden_tokens:
        assert tok not in adapter
        assert tok not in scene

    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const floor = {
          floor_id: 1,
          windows: Array.from({ length: 6 }, (_, id) => ({
            id: `f1-w${id}`,
            floor_id: 1,
            is_open: true,
            queue_length: id % 2
          })),
          seats: Array.from({ length: 172 }, (_, id) => ({
            id: `f1-s${id}`,
            floor_id: 1,
            status: 'empty'
          })),
          students: []
        };
        const frame = new StateAdapter().buildFrame({
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              display_name: '明湖',
              floors: [floor]
            }
          }
        }, { activeCanteenId: 'minghu_xueyi' });

        const f = frame.floors[0];
        const windowXs = f.windows.map(w => Math.round(w.position.x)).sort((a, b) => a - b);
        const tableCenters = [];
        for (let tableIdx = 0; tableIdx < 42; tableIdx += 1) {
          const seats = f.seats.filter((_, idx) => Math.floor(idx / 4) % 42 === tableIdx);
          tableCenters.push({
            x: Math.round(seats.reduce((sum, seat) => sum + seat.position.x, 0) / seats.length),
            z: Math.round(seats.reduce((sum, seat) => sum + seat.position.z, 0) / seats.length),
          });
        }
        const uniqueX = [...new Set(tableCenters.map(pos => pos.x))].sort((a, b) => a - b);
        const uniqueZ = [...new Set(tableCenters.map(pos => pos.z))].sort((a, b) => a - b);
        console.log(JSON.stringify({
          windowCount: f.windows.length,
          allWindowsOpen: f.windows.every(w => w.is_open === true),
          windowSides: [...new Set(f.windows.map(w => w.position.side))],
          windowSpan: Math.max(...windowXs) - Math.min(...windowXs),
          visualTableCount: tableCenters.length,
          uniqueXCount: uniqueX.length,
          uniqueZCount: uniqueZ.length,
          tableCoverageRatio:
            ((Math.max(...uniqueX) - Math.min(...uniqueX)) *
             (Math.max(...uniqueZ) - Math.min(...uniqueZ))) /
            (f.footprint.width * f.footprint.depth),
          minTableZ: Math.min(...tableCenters.map(pos => pos.z)),
          maxWindowZ: Math.max(...f.windows.map(w => w.position.z)),
          footprint: f.footprint
        }));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)

    assert payload["windowCount"] == 6
    assert payload["allWindowsOpen"] is True
    assert payload["windowSides"] == ["front"]
    assert payload["windowSpan"] >= 220
    assert payload["visualTableCount"] == 42
    assert payload["uniqueXCount"] >= 8
    assert payload["uniqueZCount"] >= 6
    assert payload["tableCoverageRatio"] >= 0.48
    assert payload["minTableZ"] >= payload["maxWindowZ"] + 70
    assert payload["footprint"]["source"] == "furnitureDerivedFootprint"
    assert payload["footprint"]["width"] / payload["footprint"]["depth"] <= 1.85
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py::test_minghu_1f_layout_sample_is_dense_and_semantically_truthful -q
```

Expected: FAIL on missing 1F tokens and/or current layout metrics.

- [ ] **Step 3: Commit is not required here**

Do not commit in the current dirty worktree unless the user explicitly asks. Keep this as a local staged/unstaged test change for the next task.

## Task 2: Reshape the 1F StateAdapter Profile

**Files:**
- Modify: `frontend/static/js/three/state_adapter.js`
- Test: `backend/tests/test_frontend_three_js_contract.py`

- [ ] **Step 1: Edit only `MINGHU_FLOOR_LAYOUTS[1]` in `state_adapter.js`**

Replace the current 1F profile with an incremental reshape. Keep the key `basicMealWideAisle`, but add the new layout token names:

```javascript
    1: {
        key: 'basicMealWideAisle',
        windowBays: [
            { id: 'f1-front-service-band-left', side: 'front', weight: 2,
              xStartRatio: 0.15, xEndRatio: 0.32, z: 16,
              bayStaggerZ: [0], minWindowGap: 30 },
            { id: 'f1-front-service-band-center', side: 'front', weight: 2,
              xStartRatio: 0.39, xEndRatio: 0.56, z: 16,
              bayStaggerZ: [0], minWindowGap: 30 },
            { id: 'f1-front-service-band-right', side: 'front', weight: 2,
              xStartRatio: 0.63, xEndRatio: 0.82, z: 16,
              bayStaggerZ: [0], minWindowGap: 30 },
        ],
        windowRows: 1,
        windowZ: [16],
        windowX0: 42,
        windowSpan: 268,
        windowRowOffset: 0,
        minWindowGap: 34,
        tableShiftX: 0,
        tableZ0: 96,
        tableRowStagger: 0,
        visibleTableCount: 42,
        mainAisleWidth: 72,
        queueBufferDepth: 98,
        tableBlocks: [
            { id: 'f1-left-four-seat-island', type: 'square', tableColor: 0xc79a58, count: 16, cols: 4,
              anchor: 'left', left: 54, z: 0, dx: 38, dz: 26 },
            { id: 'f1-central-dining-island', type: 'square', tableColor: 0xd0a45e, count: 8, cols: 4,
              anchor: 'center', offsetX: -28, z: 70, dx: 42, dz: 28 },
            { id: 'f1-right-long-table-zone', type: 'long', tableColor: 0x9a6b3e, count: 12, cols: 3,
              anchor: 'right', right: 62, z: 10, dx: 48, dz: 30 },
            { id: 'f1-rear-booth-fill', type: 'booth', tableColor: 0xb9804a, count: 6, cols: 3,
              anchor: 'right', right: 72, z: 106, dx: 46, dz: 32 },
        ],
        widthBias: 12,
        depthBias: 14,
        rearNotchDepth: 30,
        cueNames: [
            'f1-snake-queue-guide',
            'f1-pickup-return-lane',
            'f1-main-aisle-cue',
            'f1-condiment-station',
            'f1-tray-return-point',
        ],
    },
```

The exact numbers may be adjusted if the contract metrics fail, but preserve the intent: all six backend windows remain front-side real windows, and tables remain behind the service/queue zone.

- [ ] **Step 2: Run focused test**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py::test_minghu_1f_layout_sample_is_dense_and_semantically_truthful -q
```

Expected: still FAIL because `canteen_scene.js` has not mirrored the new profile/cues yet, but the Node metrics for `StateAdapter` should be closer. If the Node metrics fail, tune `tableZ0`, `tableBlocks`, `widthBias`, or `depthBias` before touching scene rendering.

- [ ] **Step 3: Syntax check**

Run:

```bash
node --check frontend/static/js/three/state_adapter.js
```

Expected: no syntax errors.

## Task 3: Mirror 1F Profile and Add 1F Visual Cues in CanteenScene

**Files:**
- Modify: `frontend/static/js/three/canteen_scene.js`
- Test: `backend/tests/test_frontend_three_js_contract.py`

- [ ] **Step 1: Mirror `MINGHU_FLOOR_LAYOUTS[1]`**

Update the 1F profile in `canteen_scene.js` to match the state adapter's 1F `tableBlocks`, `tableZ0`, `visibleTableCount`, `queueBufferDepth`, and 1F cue tokens. The scene profile can omit adapter-only `weight/xStartRatio` details if unused by rendering, but all table-block IDs and cue IDs must match.

- [ ] **Step 2: Replace the 1F identity cues**

In `_addFloorIdentityCues`, keep the `if (profile.key === 'basicMealWideAisle')` branch but replace the sparse cues with denser 1F-specific markers:

```javascript
        if (profile.key === 'basicMealWideAisle') {
            this._box(group, 'f1-snake-queue-guide', [footprint.width - 78, 0.9, 22],
                [footprint.centerX, baseY + 3.9, serviceMaxZ + 28],
                this._photoMat(0x84cc16, { opacity: 0.32, roughness: 0.30 })
            );
            this._box(group, 'f1-pickup-return-lane', [footprint.width - 86, 0.8, 12],
                [footprint.centerX, baseY + 3.8, tableStartZ - 18],
                this._photoMat(0xe7bd63, { opacity: 0.34, roughness: 0.28 })
            );
            this._box(group, 'f1-main-aisle-cue', [18, 0.8, Math.max(58, footprint.maxZ - tableStartZ - 20)],
                [footprint.centerX + 16, baseY + 3.75, tableStartZ + 44],
                this._photoMat(0x93c5fd, { opacity: 0.28, roughness: 0.30 })
            );
            this._box(group, 'f1-condiment-station', [28, 4.2, 9],
                [footprint.minX + 74, baseY + 6.4, tableStartZ - 22],
                this._photoMat(0xfde68a, { roughness: 0.38 })
            );
            this._box(group, 'f1-tray-return-point', [32, 4.6, 10],
                [footprint.maxX - 74, baseY + 6.6, tableStartZ - 22],
                this._photoMat(0xfde68a, { roughness: 0.38 })
            );
            return;
        }
```

If these dimensions collide visually after browser check, tune dimensions and positions, but keep the token names.

- [ ] **Step 3: Run focused test**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py::test_minghu_1f_layout_sample_is_dense_and_semantically_truthful -q
```

Expected: PASS.

- [ ] **Step 4: Syntax check changed JS**

Run:

```bash
node --check frontend/static/js/three/state_adapter.js
node --check frontend/static/js/three/canteen_scene.js
```

Expected: both pass.

## Task 4: Regression and Browser Verification

**Files:**
- No additional planned production files.
- Optional evidence update only if the browser check is run and screenshots/results are captured.

- [ ] **Step 1: Run focused frontend contract bundle**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run full backend/frontend contract regression**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q
```

Expected: full suite passes. If failures appear outside touched frontend contract areas, classify whether they are pre-existing dirty-worktree failures or caused by this 1F layout change before editing anything else.

- [ ] **Step 3: Run browser visual check**

Start the Flask app if needed, then open the simulation in the in-app browser:

```bash
./.venv/bin/python backend/app.py
```

Use the existing single-canteen 3D flow:

- load config,
- start simulation,
- switch/focus 1F,
- verify the 1F has 6 visible backend windows in the front service band,
- verify the scene is denser than before,
- verify queue zone and seating do not overlap,
- verify the main aisle stays readable,
- check console errors.

If the Flask app uses a different project command in the current worktree, inspect `README.md`/existing scripts before launching.

- [ ] **Step 4: Record outcome**

Summarize:

- files changed,
- whether 1F displays 6 real open windows,
- verification commands and results,
- any residual visual risk.

Do not claim 2F/3F, palette, whole-building, flicker, per-floor multi-view, or analysis panel are improved by this task.
