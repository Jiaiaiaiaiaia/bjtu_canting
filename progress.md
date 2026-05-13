# Progress

## 2026-05-13

- Loaded applicable skills: `superpowers:writing-plans` and `planning-with-files`.
- User clarified that 学活食堂 should remain unchanged for now and will be filled later.
- User approved deleting `outputs/`; removed the `outputs/` directory from the workspace and verified it no longer exists.
- Created `docs/superpowers/plans/2026-05-13-canteen-demo-polish-plan.md` for the focused demo-polish route: cleanup guardrail, campus preset loading, teacher-friendly preset UI, browser E2E evidence, optional Three.js integration, and docs/demo script.
- Updated `task_plan.md` with the new Canteen demo polish plan and preserved the external Design Culture PPT boundary.
- Incorporated plan-review fixes before implementation: replaced the final broad stage command with explicit-path staging, added guardrail sync checks for `AGENTS.md` / `CLAUDE.md` / `agent.md`, made 学活 a visible-only pending point outside runtime simulation, preserved field-pending status for 明湖/学一 and 学四, added `campusConfigDirty` handling for manual JSON edits, required Three.js importmap/module loading, and made browser E2E evidence teacher-verifiable with screenshot paths, console-error count, canvas nonblank checks, and `total_arrived == total_served`.
- Implemented the default campus preset endpoint and loader. Runtime `config.canteens` includes 明湖/学一 and 学四 only; `visible_canteens` still exposes 学活 as pending metadata.
- Replaced the campus JSON-first entry with a teacher-facing preset card, dirty JSON fallback, and pending-data note. The static textarea no longer embeds 学活 placeholder capacity.
- Added demo-scale campus runtime values plus source-scale metadata so browser finish is suitable for live demonstration.
- Recorded real browser E2E evidence with Headless Chrome/CDP: console errors 0; single-canteen `72/72`; campus preset `21/21`; 3D WebGL canvas nonblank with sampled pixels `50869`.
- Integrated optional Three.js 3D view with importmap/module loading and 2D fallback.

## 2026-05-12

- Loaded applicable skills: `superpowers:using-superpowers`, `superpowers:brainstorming`, `superpowers:writing-plans`, and `planning-with-files`.
- Started the 3D map-first UI relaunch planning pass.
- Checked `git status --short`; there are existing modified deliverable docs plus untracked `AGENTS.md`, `CLAUDE.md`, `agent.md`, `task_plan.md`, `findings.md`, `progress.md`, and `outputs/`, so future edits must preserve unrelated work.
- Read the 4/28 3D immersive multi-canteen design and implementation plan; current Three.js work is planned but not implemented.
- Audited the current frontend and backend presets: frontend is still 2D/SVG/Canvas, backend has campus presets for 明湖学一 / 学活 / 学四.
- Recorded initial 3D relaunch plan and findings in `task_plan.md` and `findings.md`.
- Started the visual companion server at `http://localhost:64391` and created `.superpowers/brainstorm/41912-1778589923/bjtu-3d-map-v1.html`.
- Opened the preview in the in-app browser: a first 3D low-poly BJTU main-campus map prototype with 明湖、南门、主路、明湖学一、学活、学四 and student walking paths.
- Iterated to `.superpowers/brainstorm/41912-1778589923/bjtu-3d-map-v2.html` with cleaner UI and clickable canteens, then user rejected arbitrary relative placement.
- Queried OSM/Nominatim/Overpass to lock the map to real coordinates and created `.superpowers/brainstorm/41912-1778589923/bjtu-real-map-v3.html`.
- Refreshed the in-app browser to the V3 real-coordinate map and verified clickable canteen drilldown by opening 学四.
- Created `.superpowers/brainstorm/41912-1778589923/bjtu-real-3d-palette-v4.html` for a unified 3D palette that preserves real coordinates without the noisy OSM color tiles.
- Created `.superpowers/brainstorm/41912-1778589923/canteen-twin-interior-v5.html` for the canteen-internal digital-twin view: main sand table, side/bottom dashboards, stall queue tags, seat heatmap, tooltip, and curved non-straight flow routes.
- Added `.superpowers/brainstorm/41912-1778589923/CanteenTwinView.tsx` as the React + Tailwind structural code draft for the same internal view.

## 2026-05-11

- Corrected project context: Canteen is the restaurant / canteen simulation project; Design Culture PPT artifacts are external.
- Added `AGENTS.md` so future sessions read a stable project-context guardrail before acting.
- Added `backend/tests/test_engine_facade.py` for A.9.1 facade-specific regression coverage and moved the single-canteen coordinator assertion out of `backend/tests/test_engine.py`.
- Fixed `SimulationEngine.step()` so one API step advances through SimPy micro-events until a visible Phase 2 semantic event is reached.
- Replaced `students` / `event_queue` `None` placeholders with real object views and preplanned Student objects.
- Updated stale `CampusCoordinator` / `ArrivalGenerator` docstrings.
- Focused verification passed: `backend/tests/test_engine_facade.py` and `backend/tests/test_engine.py`.
- Full backend regression passed: `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q` reported `107 passed in 0.80s`.

## 2026-05-10

- Loaded applicable skills: `superpowers:using-superpowers`, `presentations`, `computer-use`, and `planning-with-files`.
- Started Module 1 PPT production based on `/Users/sissi/Downloads/设计文化概论.pptx`.
- Added the new PPT production phases to `task_plan.md` and recorded initial constraints in `findings.md`.
- Ran the presentation template inspection script; source deck has 24 slides and rendered previews/layout JSON under `outputs/manual-20260510-module1/presentations/module1-theory/template-inspect`.
- Created `profile-plan.txt`, `template-audit.txt`, `template-frame-map.json`, and `deviation-log.txt` for the template-following workflow.
- Generated the four-slide `template-starter.pptx` and verified its starter contact sheet.
- Downloaded and visually checked real imagery for slide 2 and slide 3 case photos; recorded source/provenance notes.

## 2026-04-30

- Loaded applicable skills: superpowers usage, spreadsheets, documents, planning-with-files.
- Listed actual development-stage deliverables.
- Started checking requirements and document contents.
- Extracted development-stage requirements from the workbook.
- Extracted format and naming requirements from the DOCX guidance files.
- Re-ran audits after the deliverable directory changed during the session.
- Rendered all current DOCX files successfully and visually inspected contact sheets.
- Inspected RAR contents with `bsdtar`.
- Rebuilt all three source archives from the actual project source code.
- Each rebuilt archive now has `SRC_[学号]` as the top-level folder and contains `SOURCE_CODE_DESCRIPTION.md`.
- Renamed team DOCX files to remove copy suffixes and replaced the backend archive name without `(2)`.
- Removed `.DS_Store` from the deliverable folder.
- Final verification listed 11 deliverable files and confirmed no `.DS_Store` remained.

## 2026-05-01

- Started a focused re-check of the three user-specified Zhu Sisi deliverables: unit test report, development-stage report, and backend source archive.
- Extracted DOCX text and checked for placeholder strings; none were found.
- Rendered both DOCX files through LibreOffice outside the sandbox and visually inspected page images.
- Extracted the backend source archive to `/private/tmp/canteen_zss_check/archive/SRC_24281153`.
- Ran archived backend tests with `python3 -m pytest tests/ -q`: 39 passed.
- Confirmed archive homepage route fails with `TemplateNotFound: index.html` because the backend archive does not include the frontend template referenced by `backend/app.py`.
- Completed the focused re-check and recorded issues in `findings.md`.
