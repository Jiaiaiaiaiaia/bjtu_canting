# 1F Layout Sample Design

Date: 2026-05-18
Scope: Minghu single-canteen 3D 1F layout sample only
Status: User approved the visual direction from the browser sketch `normal-1f-denser-sketch-v2.html`

## Goal

Make the 1F 3D layout look like a believable, content-rich cafeteria floor without changing backend simulation state, public APIs, or 2F/3F behavior.

Fact correction before implementation planning: the current worktree 1F is not a blank or very simple baseline. `state_adapter.js` and `canteen_scene.js` already contain a 1F profile with two `windowBays` and four `tableBlocks`. The implementation should be written as an incremental reshape of that existing profile into the approved denser two-zone composition, not as a from-scratch layout.

This is the first item in the user's requested sequence:

1. Optimize each floor layout.
2. Optimize color palette.
3. Improve whole-building 3D presence.
4. Fully fix floor flicker.
5. Add multiple views for each floor.
6. Improve the analysis panel.

This spec covers only the first step, and only the 1F sample.

## Approved 1F Spatial Model

The approved direction is a denser but still readable cafeteria layout:

- A continuous service-window band at the front of the floor.
- All current backend-provided 1F windows placed inside the same service band, not isolated in the dining area.
- A snake-style waiting zone directly in front of the service band.
- A horizontal pickup/return circulation lane between queueing and seating.
- A clear main aisle from the left-side entrance/stair core into the dining zone.
- A denser seating area behind the circulation lane:
  - left-side four-person table island,
  - right-side long-table / booth zone,
  - small utility cues such as condiment and tray-return points.
- Entrance and stair core remain on the left side, outside the service queue and dining islands.

The layout should look more full than the earlier sparse diagram, but should not become visually chaotic or block the movement sequence.

## Implementation Boundary

This is a renderer/layout-profile change, not a backend behavior change.

Decision: render semantic truth first. The current 1F backend preset has 6
physical windows and all 6 are active, so the 1F runtime view must display 6
real open service windows. Do not render this as "4 real windows + 2 dashed
added windows" in production, because that would imply a state the backend does
not expose. The dashed "added-window" marks in the sketch are a design note for
where future backend-provided closed/opened/extra physical windows should sit
inside the service band. The renderer may not increase, hide, or relabel the
real window count, queue capacity, or statistics.

Allowed implementation changes:

- Update the 1F profile in `frontend/static/js/three/state_adapter.js`.
- Mirror the same 1F visual profile in `frontend/static/js/three/canteen_scene.js`.
- Add or adjust small 1F-only visual cues in `canteen_scene.js`, such as queue-lane markings, condiment/return blocks, and denser table islands.
- Add focused contract tests for the 1F profile tokens and the 1F footprint/table-block structure.

Disallowed in this step:

- Changing backend presets, snapshot shapes, statistics, routing, or simulation behavior.
- Changing 2F or 3F layout profiles except for shared helper fallout required by the 1F change.
- Changing color-palette strategy beyond colors already needed by the 1F layout cues.
- Changing camera/view presets, floor-flicker materials, whole-building shell, or analysis-panel UI.
- Restoring campus-map or multi-canteen product behavior.

## 1F Layout Profile Target

The 1F profile should move from the current relatively simple split-window/table-block plan to a clearer dining-hall plan:

- `windowBays`: front service band with all 6 existing backend windows spread across the band; any future added/openable positions remain service-band reservations unless the backend snapshot actually provides those windows.
- `queueBufferDepth`: enough depth for the snake waiting zone before seating begins.
- `tableBlocks`: denser but grouped seating:
  - a compact four-person table island on the left/back side,
  - a right-side long-table zone,
  - a small booth/fill zone near the rear or side.
- `rearNotchDepth` and footprint sizing should keep the floor from becoming a long skinny rectangle.
- Table and queue positions must remain inside the furniture-derived footprint.

The 1F result should make the following visible in single-floor focus:

- service band,
- queue zone,
- horizontal circulation lane,
- main aisle,
- left table island,
- right long-table / booth zone,
- entrance/stair relationship.

## Verification Plan

Focused verification should include:

- `node --check frontend/static/js/three/state_adapter.js`
- `node --check frontend/static/js/three/canteen_scene.js`
- focused frontend contract tests for 1F layout tokens
- `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests/test_frontend_three_js_contract.py -q`
- full backend/frontend contract regression when implementation is complete:
  `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q`

Browser verification should then show the 1F focus view and confirm:

- the floor is not sparse,
- windows and added-window slots are grouped as a service band,
- tables do not overlap the queue zone,
- the main aisle remains visually readable,
- the scene still has no console errors.
