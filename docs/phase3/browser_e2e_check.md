# Browser E2E Check

Date: 2026-05-13
App: `http://127.0.0.1:5001/`
Browser: Headless Chrome via CDP

## Single-Canteen Flow

- Result: passed.
- Console errors: 0.
- 2D canvas nonblank: passed, `110987` non-background pixels.
- Final totals: `total_arrived=72`, `total_served=72`.
- History: history row appeared and detail chart opened.
- Screenshot: `docs/phase3/screenshots/single-flow-analysis.png`.

## Campus Preset Flow

- Result: passed.
- Preset metadata: visible canteens were `minghu_xueyi`, `xuehuo`, `xuesi`; pending canteens were `xuehuo`.
- Runtime boundary: textarea/runtime config did not include `"id": "xuehuo"`.
- Campus map: 3 markers rendered; 1 pending marker; 2 runtime markers; transit dots rendered.
- Floor tabs: `xuesi` detail opened with `全楼层 / 1F / 2F`; `1F` was selectable.
- Console errors: 0.
- Final totals: `total_arrived=21`, `total_served=21`.
- Screenshots:
  - `docs/phase3/screenshots/campus-map.png`
  - `docs/phase3/screenshots/campus-canteen-floor.png`
  - `docs/phase3/screenshots/campus-analysis.png`

## Verification Artifacts

- `docs/phase3/screenshots/e2e-result.json`
- `docs/phase3/screenshots/single-flow-analysis.png`
- `docs/phase3/screenshots/campus-map.png`
- `docs/phase3/screenshots/campus-canteen-floor.png`
- `docs/phase3/screenshots/campus-analysis.png`

## Open Issues

- None for the checked single-canteen and campus preset flows.
