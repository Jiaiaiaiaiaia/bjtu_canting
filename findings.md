# Findings

## 2026-05-12 3D Map-First UI Relaunch Findings

- User wants to pause deliverable-document writing and fix the rough page experience first; planning docs remain in scope.
- Current frontend is 2D/SVG/Canvas only. `frontend/static/js/campus_map.js` renders simple SVG rectangles for canteens and transit dots; `frontend/static/js/three/` does not exist.
- Existing 4/28 spec already defines a three-layer visual architecture: campus overview, canteen drilldown, and floor tabs, with Three.js planned for deployment stage.
- Existing 4/28 plan has B.2-B.7 tasks for Three.js scene, campus view, canteen view, student rendering, camera transitions, and 2D/3D fallback, but those tasks are still unchecked.
- Backend campus presets exist under `backend/simulation/presets/`, including `_campus.json`, `minghu_xueyi.json`, `xuehuo.json`, and `xuesi.json`.
- `_campus.json` still marks field research as pending and contains a `_TODO_field_research_pending` flag, so “same as the real school map” should be treated as a design/data update rather than already proven.
- Web check found official BJTU pages confirming the campus address as 北京市海淀区上园村3号 and an official visitor page with a “校园地图” entry. BJTU News also lists canteen relative locations such as 学一 in the west-campus northeast area and 学四 southeast of the ninth teaching building; BJTU logistics pages identify 明湖, 学活, and 学四 dining facilities.
- After user rejected arbitrary relative positioning, queried OpenStreetMap/Nominatim/Overpass for real BJTU main-campus coordinates. Nominatim result for 北京交通大学主校区 gives bbox approximately `lat 39.9468749-39.9541403`, `lon 116.3300560-116.3437379`. Overpass anchor coordinates used in V3 preview: 明湖 `39.9505925,116.3363837`; 学生一食堂 `39.9517937,116.3373089`; 学生活动中心 `39.9492244,116.3318648`; 学生第四食堂 `39.9483301,116.3382077`; 交大南门 `39.9478614,116.3353094`; 东门 `39.952596,116.3413042`; 九教 `39.9484986,116.3361803`; 八教 `39.9512953,116.3362731`.
- Created `.superpowers/brainstorm/41912-1778589923/bjtu-real-map-v3.html`, which uses OSM tile background plus projected coordinate anchors instead of hand-placed relative positions. Verified in browser that the V3 page loaded and clicking 学四 opens the correct detail panel.
- User then requested a better color palette and fully 3D direction, followed by a detailed design brief for a canteen-internal digital-twin UI. The internal view should use a "main sand table + side/bottom dashboard" structure, micro-data tags for windows, seat heatmap/dot matrix, hover tooltips, a prominent return-to-map button, dark data-twin style, monospaced KPI numerals, and curved/non-straight flow routes.
- V5 internal-view prototype implements the requested route constraint with SVG cubic Bezier paths rather than straight route segments.

## 2026-05-13 Demo Polish And 3D Integration Findings

- `outputs/` belonged to the external Design Culture PPT work and is now ignored by `.gitignore`.
- The default campus preset now separates runtime config from visible metadata. Runtime includes 明湖/学一 and 学四; 学活 is visible as pending metadata only and does not affect routing, queueing, statistics, or final totals.
- `_campus.json` remains source-scale (`28000` students, `5400` seconds), while the API default preset returns demo-scale runtime values (`180` students, `300` seconds) plus `source_scale` metadata for honest explanation.
- The campus JSON textarea is no longer a source of embedded 学活 placeholder capacity. It is populated by the API preset, and manual edits set `campusConfigDirty` so submission uses the user's JSON explicitly.
- `frontend/static/js/campus_map.js` now renders pending visible canteens as non-clickable translucent markers. Runtime-only interactions still use `snapshot.canteens`.
- Browser E2E evidence is recorded in `docs/phase3/browser_e2e_check.md`: console errors 0; single-canteen final totals `72/72`; campus final totals `21/21`; campus map has 3 markers with 1 pending marker and 2 runtime markers.
- Three.js is integrated as an optional render mode under `frontend/static/js/three/`. It uses importmap/module loading, renders live campus/canteen snapshots, keeps 2D as default fallback, and passed a WebGL nonblank check with sampled nonblank pixels `50869`.

## 2026-05-11 Canteen Project Context Correction

- The Design Culture / `模块一` PPT work is a separate course project and should not be used as Canteen simulation status.
- Added `AGENTS.md` as the root project-context guardrail future sessions should read before work.

## 2026-05-11 A.9.1 SimulationEngine Review Findings

- Verified issue #1 exists: current `SimulationEngine.step()` advanced one SimPy micro-event at a time; the first call after `start()` returned `current_time=0` with no visible state change.
- Verified issue #2 exists: `engine.students` and `engine.event_queue` were populated with `None` placeholders after `start()`.
- Verified issue #3 exists: `CampusCoordinator` docstrings said single-canteen mode did not use the class, but `SimulationEngine` now wraps a one-canteen `CampusCoordinator`.
- Verified issue #4 exists as a test-organization issue: the facade-specific coordinator assertion had been added to `backend/tests/test_engine.py`; it now belongs in `backend/tests/test_engine_facade.py`.
- Verified issue #5 exists for the EmptySchedule branch: when the SimPy queue is empty, `step()` returned an end state without appending the corresponding compact snapshot to `history`.
- Issue #6 is commit-message bookkeeping only; no history rewrite should be done.
- Issue #7 is legacy metric naming behavior and not changed in this fix.

## 2026-05-10 Module 1 PPT Findings

- New task: create a four-slide Module 1 deck using `/Users/sissi/Downloads/设计文化概论.pptx` as the visual template.
- User-specified core slides: `理论底色` divider; research question; three innovation modes; sales/tension handoff slide.
- User specifically requires real photos for Palace Museum/National Museum and product examples; generated lookalike imagery is not acceptable for those case products.
- Template inspection found 24 source slides. Best mapped sources: slide 3 for chapter divider, slide 16 for research-question/image layout, slide 11 for three columns, and slide 21 for the final framework/tension layout.
- Template visual grammar: beige paper texture, white inner canvas, brick-red labels, small red clover marker, oversized chapter fan/roundel, clouds, swallows, and muted ink body text.
- Verified the National Museum official 2026-02-28 page for the 3,000,000 phoenix-crown fridge-magnet milestone and the 2025-03 / 2025-07 / 2026-02 sales nodes.
- Downloaded real source images for Taihe Dian, phoenix-crown fridge magnet, Palace Museum cat ornament, and Qianli Jiangshan hairpin. The Palace Museum cat and Qianli hairpin images are real product-listing images but not from the museum's own official domain.

## Initial Inventory

- Actual deliverable directory contains 11 visible user files plus `.DS_Store`.
- Several DOCX names still include placeholders `[学号]_[姓名]`.
- Two source archives appear to be missing a student ID segment after `软件综合实训_`.

## Current Inventory After User Updates

- Current deliverable directory still contains 11 visible deliverables plus `.DS_Store`, matching the expected count for 3 members: 2 team documents + 3 source archives + 3 unit test reports + 3 development reports.
- Current personal DOCX file names include student IDs and names; no placeholder text remains in current DOCX bodies based on text extraction.
- Current team documents have copy suffixes in the file name: `03小组_小组开发任务划分说明(6).docx` and `03小组_开发阶段小组沟通交流记录(4).docx`.
- Current backend source archive has copy suffix: `软件综合实训_24281153_朱思思_后端模块源代码(2).rar`.
- Requirement/name specification indicates formal documents should be submitted as PDF if followed strictly; current documents are DOCX.

## DOCX Content And Render Findings

- All 8 current DOCX files rendered successfully through LibreOffice.
- Team task division document has a generated table of contents and content covers member roles, IDs, modules, task breakdown, dependencies, API list, schedule, collaboration, and quality measures.
- Team communication record contains multiple communication tables and appears complete for repeated meeting records.
- Personal unit test reports cover test overview/objectives/environment/cases/results/issues/conclusion.
- Personal development reports cover issues/solutions, personal tasks/completion, learning gains, collaboration reflection, and next-stage plan.
- Some pages, especially tables in individual reports, are dense but still readable in the rendered preview.

## Archive Findings

- All three `.rar` files are readable and contain code files.
- All three archives store files under `tmp/canteen_pack/...`; naming specification says project folders should be named like `SRC_[学号]`.
- Frontend archive has code files but no detected README/source-code explanation document.
- Backend archive has code/tests but no detected README/source-code explanation document.
- Configuration/analysis archive has README/source-code explanation material.

## Fix Results

- Rebuilt frontend archive as `软件综合实训_24281139_宋嘉桐_前端模块源代码.rar`; top-level folder is `SRC_24281139`.
- Rebuilt backend archive as `软件综合实训_24281153_朱思思_后端模块源代码.rar`; top-level folder is `SRC_24281153`.
- Rebuilt configuration/analysis archive as `软件综合实训_24281131_贾文霞_配置与分析模块源代码.rar`; top-level folder is `SRC_24281131`.
- Added `SOURCE_CODE_DESCRIPTION.md` to all three source archives. The content is based on actual source files from `/Users/sissi/PycharmProjects/Canteen`.
- Renamed team documents to remove `(6)` and `(4)` suffixes.
- Removed hidden `.DS_Store` from the deliverable folder.

## 2026-05-01 Focused Zhu Sisi Re-check

- Checked `软件综合实训_24281153_朱思思_单元测试报告.docx`, `软件综合实训_24281153_朱思思_开发阶段实训报告.docx`, and `软件综合实训_24281153_朱思思_后端模块源代码.rar`.
- Both DOCX files have complete identity fields and no obvious placeholder strings such as `[学号]`, `[姓名]`, TODO, or `待补充`.
- Both DOCX files rendered successfully after running LibreOffice outside the sandbox.
- Unit test report content is coherent and matches the archive test count: 39 tests.
- Unit test report TOC page numbers are stale: e.g. 4.1 renders on page 4 but TOC lists page 3; sections 5 and 6 render on page 7 but TOC lists page 8.
- Unit test report has long-table pagination artifacts: continuation rows appear at the top of pages 5, 6, and 7 without repeated headers; page 8 has a repeated blue header row with missing header text.
- Development report has a blank rendered page 2 between cover and TOC.
- Development report TOC page numbers are stale by at least one page because body section 1 renders on page 4 while TOC lists page 3.
- Development report table in section 2 splits awkwardly across pages 4-5, leaving the last row continuation at the top of page 5.
- Development report stage date is `2026年4月5日 —— 2026年5月3日`; if submitted on 2026-05-01, the end date is two days in the future.
- Backend archive has correct `SRC_24281153` top-level folder and includes code, tests, requirements, and source-code description files.
- `python3 -m pytest tests/ -q` passed inside the extracted backend archive: 39 passed.
- Backend archive `requirements.txt` lacks `pytest`, although the archive includes tests and the report/description tells users to run pytest.
- Backend archive root route `/` fails with `TemplateNotFound: index.html` because `app.py` references `frontend/templates/index.html` but the backend-only archive does not include that frontend template.
- Backend archive includes duplicate source-code descriptions: `SOURCE_CODE_DESCRIPTION.md` and `源代码说明.md` have the same content; this is harmless but redundant.
