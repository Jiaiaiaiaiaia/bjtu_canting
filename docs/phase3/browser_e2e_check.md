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
