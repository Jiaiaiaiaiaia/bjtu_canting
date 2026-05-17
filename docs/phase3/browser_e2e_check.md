# Browser E2E Check — V7 Immersive 3D Single-Canteen Digital Twin

Date: 2026-05-17
App: `http://127.0.0.1:5057/` (stable server `debug=False, use_reloader=False`; port 5057 because 5001 was already in use — no other server was killed)
Browser: Headless Chrome via CDP (SwiftShader WebGL 2.0)
Spec: `docs/superpowers/specs/2026-05-17-3d-twin-visual-redesign-design.md` §6
Evidence: `docs/phase3/screenshots/three-result.json` + `twin-*.png` (this run)

> **Supersedes prior evidence.** The earlier `docs/phase3/screenshots/*` / `three-result.json` / this file were 2026-05-13 demo-polish-era artifacts and do **not** describe the current build. They are overwritten here by the V7 immersive evidence. Driver `/tmp/e2e_twin_driver.mjs` is harness-only (not committed).

## Result: all spec §6 hard-acceptances PASS

| Scenario | Result | Key evidence |
|---|---|---|
| 1. Default immersive 3D | PASS | `renderMode=3d`, `body.twin-immersive=true`, white app chrome hidden, `#three-stage position:fixed` full-bleed, canvas non-blank ≈ **1,019,398 px** (rich V7 scene; old blocky build ≈290k), 1278×798 |
| 2. λ(t) peak (live frames) | PASS | tick=60 fast-forward; queue 0 → rises (t≈1110) → **peak 1169 @ t≈2380** → decays to 682; backend-frame driven, not faked, sim still running |
| 3. Drill to 2F | PASS | Clicked `.twin-floorstrip` **「2F」** → `sceneApi.focusFloor` → `focused_floor=2`, `reached_2F=true`, ops console filtered to `["2F"]` (focus mode), non-focus floors slid away |
| 4. Intervention causality | PASS | Toggled window 6 on focused 2F → `GET /api/campus/history` intervention rows **3→4**, `matches_toggled_window=true`, `immediately_visible=true`, ops log `t=3360s · 2F · 窗6 · 关窗 · 已生效` |
| 5. Narrow 390×780 | PASS | ops-console `[8,448,288,708]` + legend `[222,88,382,138]` → `controls_overlap_each_other=false`, `all_controls_within_viewport=true` — **the real pre-existing overlap defect is fixed** (V9 responsive @media) |
| 6. WebGL-unavailable fallback | PASS | `getContext('webgl*')→null` → `.three-fallback` shown, text “当前环境无法创建 WebGL 上下文，已保留 2D 视图。”, no WebGL canvas |
| Console errors (main flow) | PASS | **0** in the real 3D flow. The deliberate no-WebGL tab logs 1 expected `THREE.WebGLRenderer: Error creating WebGL context.` — isolated/expected, not counted against the gate. |

## Honest notes / limitations (recorded per spec)

- **Drill is driven by a deterministic DOM click** on the immersive `.twin-floorstrip` 「2F」 button (→ `sceneApi.focusFloor(2)` → `canteenScene.focusFloor`), the production-intended drill entry — not a synthetic canvas raycast. Headless synthetic-pointer raycast on the WebGL canvas proved unreliable in this Chrome (documented across earlier iterations); the floorstrip path is deterministic. The focus state machine (non-focus slide-away, FOCUS camera) is additionally covered by `test_frontend_three_js_contract.py` / the V4 `update()/tick()` split contract assertions.
- **"Bloom/composer failure does not trigger `.three-fallback`"** is guaranteed by `scene_fx.js` structure: every composer construct/run path is `try/catch` → `this.enabled=false` → `renderer.render(scene,camera)`; `.three-fallback` is reached ONLY via the independent `scene3d.js` `!webglAvailable` branch. Asserted by `test_scene_fx_module_contract` + the V3 contract test and verified by code path. A runtime postFX fault-injection is impractical to do reliably headless, so this boundary is evidenced by the contract + code path rather than a flaky injected-failure scenario — stated transparently.
- A stale `last_intervention_event` field in `three-result.json` reflects pre-existing `campus_snapshot` rows in the shared local DB from earlier runs; the **causal** assertion is "intervention rows strictly increased AND toggled window id present AND immediately visible", which holds independently of pre-existing rows (and the ops-log excerpt shows THIS run's toggle).

## Verification gates (also green)

- `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q` → all green (backend untouched; 212 baseline + new contract tests).
- `node --check` on `main.js`, `canvas_renderer.js`, all `three/*.js` (incl. `scene_fx.js`, `immersive_ui.js`) and vendored `postprocessing/*` + `shaders/*` → exit 0.
- `CanteenApp3D` facade tokens, no-WebGL fallback tokens, and `main.js` negative `'2d'` literal assertions all still hold (contract tests).

## Artifacts
- `docs/phase3/screenshots/three-result.json` — full metrics (this run)
- `docs/phase3/screenshots/twin-default-3d.png` — immersive default
- `docs/phase3/screenshots/twin-peak.png` — λ(t) peak
- `docs/phase3/screenshots/twin-focus-2f.png` — 2F focus drill
- `docs/phase3/screenshots/twin-intervention.png` — window intervention
- `docs/phase3/screenshots/twin-narrow.png` — 390×780 (no overlap)
- `docs/phase3/screenshots/twin-fallback.png` — WebGL fallback

## Open issues
- None for the checked V7 immersive single-canteen flow. (Headless canvas-raycast remains a harness limitation, documented above; product drill via floorstrip works deterministically.)

---

## 2026-05-18 — Item 1: Floor detail optimization (windows + tables + flow)

Scope: item 1 of the 6-item sequence (windows / tables / crowd-flow), renderer-only.
Plan `docs/superpowers/plans/2026-05-18-floor-detail-optimization.md`.

Commits (all intact in history):
- `364ce3e` A1 lock 4-part stall contract (red)
- `12ab4a7` A2 4-part themed front service stall (additive; hooks/labels/intervention intact) — spec + code-quality two-stage subagent review **passed**
- `b1e65da` B1 lock regularized table-grid + cue-token contract (red)
- `332ee3e` B2 floor-3 table-zone buffer satisfies the regularized-grid contract (minimal: f3 `tableZ0` 106→112 in both JS profiles; floors 1/2 already compliant; cue tokens preserved)
- `ab25bcc` C1 lock student-orientation + in-footprint path contract (red)
- `3e7d0a9` C2 avatars face travel (`atan2`); C1 corrected to assert the true §C invariant (routed targets reachable in-footprint; side-gate entrance spawn correctly outside the slab, still locked by the existing entry-path/nearest-entrance tests)

Machine verification at HEAD:
- `node --check` `state_adapter.js` and `canteen_scene.js`: exit 0.
- Item-1 test bundle `-k "service_stall or side_service_stall or table_blocks_are_regularized or student_paths_avoid or matte or window_labels or front_service or front_window or 1f_layout_sample"`: **19 passed, 0 failed**.
- The 4 new contract tests (A1 stall, A3 side stall, B1 regularized grid, C1 orientation/path) are green; window/label/matte and `test_minghu_1f_layout_sample_is_dense_and_semantically_truthful` regressions stay green.

Full-suite state (`pytest backend/tests -q`): 10 failed / 350 passed. **All 10 are concurrent non-item-1 work, none attributable to item 1:**
- 8 contract failures are the parallel item #3/#4 effort (building/camera/axonometric/floor-surface/alpha-flicker/scene-labels/brand): `test_default_twin_view_prioritizes_building_over_empty_ground`, `test_canteen_floor_surfaces_do_not_hide_lower_levels`, `test_focused_canteen_floor_uses_stable_readable_light_surface`, `test_canteen_scene_floor_focus_uses_side_to_top_to_full_floor_sequence`, `test_canteen_scene_focus_hides_large_scene_labels_from_sightline`, `test_canteen_scene_uses_open_axonometric_layered_building_model`, `test_immersive_ui_places_minghu_brand_at_top_left`, `test_canteen_scene_focus_floor_avoids_alpha_flicker_layers`.
- `test_readme_matches_single_canteen_3d_product_direction` — concurrent CLAUDE.md/README direction rewrite.
- `test_table_layout_preserves_backend_seats_but_caps_visual_tables` — broken by concurrent commit `8155747 "make all floors rectangular (rearNotchDepth=0 for 2F and 3F)"`, which landed after item-1 C2 and changed floor footprints.

Browser visual capture: **deferred, not faked.** The 3D scene (`canteen_scene.js`) is being concurrently rewritten by the parallel #3/#4 effort (continuous "Style B/C building", wall-height, rectangular-floor commits; the file is currently dirty with their in-progress work). A screenshot now would mix item 1 with their unfinished #3/#4 state and could not isolate item-1's stalls/tables/flow. Recommended: run the per-floor browser pass once #3/#4 settles (or with it paused). No screenshots were captured for this section to avoid misattributed evidence.
