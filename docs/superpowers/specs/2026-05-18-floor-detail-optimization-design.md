# Floor Detail Optimization Design

Date: 2026-05-18
Scope: Minghu single-canteen 3D — per-floor visual **detail** polish only
Status: User approved the direction (window style A "realistic stall"; table-layout cleanup before→after) in the brainstorming visual companion on 2026-05-18.

## Position in the User's 6-Item Sequence

The user requested six optimizations to run **one at a time** ("一个一个来"):

1. **Per-floor layout detail** ← this spec
2. Color palette research/optimization
3. Whole-building 3D presence
4. Floor flicker full fix
5. Multi-angle view per floor
6. Analysis panel

This spec covers **only item 1**. Items 2–6 each get their own spec → plan → implementation cycle later and are explicitly out of scope here.

## Goal

On the layout base the user has already built, make each floor read as a believable cafeteria floor by fixing the three things the user called out as "ugly":

- service **windows** currently render as flat stacked light boxes with a floating menu label — no structure, identical on every floor;
- **table placement** inside the existing blocks looks scattered, unevenly spaced, edge-stuck, and bleeds into the queue zone;
- **crowd flow** (students + paths) is not readable as a believable entrance→window→queue→pickup→seat sequence.

No backend simulation state, public API, snapshot shape, statistics, floor skeleton, camera presets, palette system, flicker material strategy, or analysis panel changes.

## Fact Baseline (current worktree)

- `frontend/static/js/three/state_adapter.js` defines `MINGHU_FLOOR_LAYOUTS` with three distinct profiles: `1: basicMealWideAisle`, `2: featureFoodCourt`, `3: restaurantDiningRoom`, each with `windowBays`, `tableBlocks`, `queueBufferDepth`, `rearNotchDepth`, and a furniture-derived `footprint` (`source: "furnitureDerivedFootprint"`).
- `canteen_scene.js` mirrors these profiles and renders windows in `_addServiceStall` (front + `left` side branch), chairs in `_addChair` (variant set: standard / open-back / round-stool / bench), student avatars in `_studentAvatar` (capsule body + sphere head + status ring), and floor identity cues in `_addFloorIdentityCues`.
- The user has accepted the **1F layout as the reference base** and wants 2F/3F brought to the same quality while each floor keeps its own character (1F basic fast-food, 2F denser central-island/mixed dining, 3F wall booths + small-group long tables).
- An earlier `2026-05-18-1f-layout-sample-design.md` / `2026-05-18-1f-layout-sample.md` pair covers **only the 1F sample**. This spec is a **superset** (all three floors + window structure + crowd flow) and **supersedes** that pair. The implementation plan derived from this spec must reconcile, not double-apply, the 1F changes; the 1F sample plan must not be executed independently after this spec is approved.

## Approved Direction

### A. Windows as realistic stalls (replaces the flat box stack in `_addServiceStall`)

Window selection in the brainstorming companion: **A — realistic stall**. Each window becomes a four-part stall instead of a flat counter:

1. **Signboard band** at the top (per-floor themed material/color).
2. **Open-kitchen glass** in the middle — low opacity, high roughness, no strong specular highlight, no emissive glow.
3. **Base counter** below.
4. **Tray rail + thin status strip** at the front edge.

Per-floor theme is **material/color-temperature only**, emissive intensity ≈ 0:

- 1F: brushed-steel cool tone.
- 2F: warm wood + brass.
- 3F: dark wood + warm (non-emissive) tone.

The menu label attaches to the signboard band instead of floating in the air.

The `left`-side window branch keeps the same four-part structure in a smaller footprint.

### B. Table-layout cleanup (regularize within existing `tableBlocks`)

Skeleton, block semantics, and per-floor character are unchanged. Only positions/spacing are regularized:

- Within each block: even row/column alignment using the block's own `cols` and uniform `dx`/`dz`; eliminate the current z-stagger and edge-stuck placement.
- Between blocks: a fixed clearance lane; one continuous main aisle along `mainAisleWidth`; a fixed buffer between the queue zone (`queueBufferDepth`) and the first table row.
- Per-floor character is expressed by block composition, kept clearly different floor-to-floor:
  - 1F: orderly four-person square table groups.
  - 2F: large central island + side table banks.
  - 3F: wall-booth run + central small-group square cluster + small-group long-table run + window-side booths.
- All seats/tables stay inside the furniture-derived `footprint` (re-verify block parameters do not overflow bounds).
- Chairs reuse the existing `_addChair` variants so seating variety is preserved.

### C. Crowd-flow readability (students + paths)

- Moving students orient toward their direction of travel; per-student variation continues to use `stableStudentClothingColor` plus the existing anti-overlap jitter, so trajectories are not identical.
- Paths follow reachable circulation polylines: entrance → window → queue → pickup → seat, without cutting through tables or walls. Cross-floor movement continues to render on the stair core (existing `floor_switching` rendering is preserved, not replaced).
- Queueing renders as ordered lanes inside the queue buffer in front of the service band, reusing the existing `WINDOW_QUEUE_LANES` constants.
- Rendering remains pure interpolation of backend snapshot data via `state_adapter`. No statistics are invented; the `state_adapter` output contract is unchanged.

## Implementation Boundary

Allowed changes:

- Rewrite the window stall geometry/materials in `frontend/static/js/three/canteen_scene.js` (`_addServiceStall` and any helper it needs).
- Regularize table/chair placement: adjust `tableBlocks` parameters and the block-positioning helpers in `state_adapter.js` and the mirrored profile/positioning in `canteen_scene.js`.
- Adjust student orientation and path/queue polyline rendering in `canteen_scene.js`.
- Add or adjust per-floor visual cues (`_addFloorIdentityCues`) and small layout markers, keeping required token names.
- Add/adjust focused frontend contract tests in `backend/tests/test_frontend_three_js_contract.py` for any token or structural change, with deliberate, stated test edits when a contract token is intentionally renamed.

Disallowed in this step:

- Any change to backend presets, snapshot shape, statistics, routing, simulation behavior, `/api/config`, or `/api/simulation/*` / `/api/campus/*` response shapes.
- Changing the floor skeleton/footprint derivation strategy, profile `key`s, backend window/seat counts, or rendering fewer/more/relabeled windows than the backend snapshot provides (no fake or hidden "added windows").
- Changing the color-palette system beyond the per-floor stall/table material tones this layout needs (full palette work is item 2).
- Changing camera/view presets, floor-flicker material strategy, whole-building shell, or analysis-panel UI (items 3–6).
- Restoring campus-map or multi-canteen product behavior.

## Contracts and Invariants to Preserve

- `scene3d.js` facade unchanged: `window.CanteenApp3D.init/render/dispose`, `visibleCanteens`, `pendingCanteens`.
- `state_adapter` per-floor `footprint` keeps `source: "furnitureDerivedFootprint"` plus bounds/dimensions/outline; tables/queues/windows/paths stay inside computed bounds.
- Window meshes keep `userData { floorId, kind: 'window', windowId }` and the intervention hooks (`_activeWindowInterventionEffect`, `_tagWindowInterventionBody`, `_addWindowInterventionPulse`) so the ops panel and `is_open`/`closing`/`is_serving` states still render.
- Window labels keep the `alwaysReadableWindowLabel` flag and `WINDOW_LABEL_RENDER_ORDER`-based `renderOrder`.
- Existing `test_frontend_three_js_contract.py` 1F tokens remain satisfied (kept as-is or migrated with a deliberate, documented test update; no silent weakening). Forbidden tokens (`f1-added-window`, `f1-fake-window`, `addedWindowCount`, `fabricatedWindow`) never appear.
- **Cue tokens live inside the helper being rewritten.** `f1-snake-queue-guide`, `f1-pickup-return-lane`, `f1-main-aisle-cue`, `f1-condiment-station`, `f1-tray-return-point` are emitted by `_addFloorIdentityCues` (canteen_scene.js ~1811+), and section B regularization will move those meshes. The plan must explicitly re-emit these exact cue tokens from the new layout code (or migrate each with a stated `test_frontend_three_js_contract.py` edit). They cannot be silently dropped while rewriting the helper.
- The adapter uses split bay ids `f1-front-service-band-left/center/right`; the contract test only requires the substring `f1-front-service-band`. Preserving any one split id keeps the test green — a planner must not "consolidate" these away without re-checking the test.
- All six 1F backend windows continue to render as real open windows in the front service band; opened/closed windows from interventions appear in the same band, never scattered into the dining area.
- Phase 2 single-canteen API behavior is untouched by construction (renderer-only change).

## Verification Plan

1. `node --check frontend/static/js/three/state_adapter.js`
2. `node --check frontend/static/js/three/canteen_scene.js`
3. `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py -q`
4. Full regression: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q` (must stay green; any intentional contract test edit stated in the commit message).
5. Browser check on each floor focus: window shows the four-part stall with per-floor material; tables are aligned in even rows with a readable main aisle and queue buffer; students orient along travel and queue in lanes; no console errors; no bloom/glare.

**Section C acceptance signal (path readability).** Because "paths do not cut through tables/walls" has no existing test, the plan must add one focused contract assertion in `test_frontend_three_js_contract.py`: drive `StateAdapter` with a snapshot containing a moving student and assert every generated path waypoint stays inside `floor.footprint` bounds and does not fall inside any `tableBlocks` axis-aligned footprint (within a small clearance). This is the machine-checkable counterpart to the manual browser observation; section A (window tokens/userData) and section B (footprint/table tokens) already have token/footprint coverage.

## Risks

- **Double-apply with the 1F sample plan.** Mitigation: this spec supersedes `2026-05-18-1f-layout-sample-*`; the new implementation plan integrates the 1F changes once and the old 1F-only plan is not executed separately.
- **Contract-token churn.** Regularizing tables/cues may move token-bearing meshes. Mitigation: preserve token names where possible; when a token is intentionally renamed, edit `test_frontend_three_js_contract.py` deliberately and state it in the commit message (no silent test weakening).
- **Footprint overflow** after spacing changes. Mitigation: re-verify block parameters against `footprint` bounds in the contract test and browser check.

## Out of Scope (separate later specs)

Item 2 (color palette), item 3 (whole-building 3D presence), item 4 (floor flicker full fix), item 5 (multi-angle per floor), item 6 (analysis panel). Touching their code areas in this step is out of scope except where unavoidable shared-helper fallout is required by item 1, which must then be minimal and stated.
