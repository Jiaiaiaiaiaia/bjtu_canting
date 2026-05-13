# Canteen Planning Notes

Important context: this repository is the Beijing Jiaotong University canteen / restaurant dining simulation project. The Design Culture / `模块一` PPT work that appears in older notes belongs to a separate course project and must not be used to judge Canteen simulation status.

For future sessions, read `AGENTS.md` first.

---

# Canteen Demo Polish And 3D Integration

Goal: Turn the current Canteen simulation into a teacher-facing demo with credible data boundaries, a clean campus-mode entry, verified browser flow, and a first integrated 3D view.

## Phases

1. Complete - Delete external `outputs/` artifacts from this repo workspace.
2. Complete - Write and review the focused implementation plan.
3. Complete - Add cleanup guardrails and default campus preset loading while keeping 学活 pending.
4. Complete - Replace campus JSON-first UX with a teacher-friendly preset entry.
5. Complete - Run and record real browser E2E checks.
6. Complete - Integrate the V7 Three.js prototype as optional 3D view with 2D fallback.
7. Complete - Update README, demo script, and phase evidence docs.

## Notes

- User explicitly said 学活先不动，后面会补；do not fake or "complete" `xuehuo.json`.
- New plan path: `docs/superpowers/plans/2026-05-13-canteen-demo-polish-plan.md`.
- `outputs/` belonged to the external Design Culture PPT work and was deleted from the workspace.
- Plan review tightened the risky boundaries: no final `git add .`; default campus simulation excludes pending 学活 from runtime routing/statistics; frontend JSON edits must bypass cached presets; Three.js integration must use explicit importmap/module loading; browser E2E evidence must include screenshots, console-error count, canvas nonblank checks, and final served/arrived equality.
- Implementation note: default campus preset is demo-scale at runtime and keeps source-scale metadata. 学活 is visible as a pending marker through `visible_canteens`, but it is not in runtime `config.canteens`.
- Browser evidence is recorded in `docs/phase3/browser_e2e_check.md`; screenshots and JSON evidence are under `docs/phase3/screenshots/`.

---

# 3D Map-First Simulation UI Relaunch

Goal: Replan the Canteen simulation frontend so the runnable demo moves from the current rough 2D/SVG/Canvas experience toward a Three.js 3D campus and canteen simulation, while keeping Phase 2 single-canteen API compatibility and not working on deliverable documents yet.

## Phases

1. In progress - Audit existing frontend/backend state, prior 3D spec/plan, and real-map evidence.
2. Pending - Confirm visual direction and real-map fidelity level with the user.
3. Pending - Update the technical design/implementation plan for a 3D-first path.
4. Pending - Implement the first 3D vertical slice after design approval.
5. Pending - Verify backend regression and browser flow: config -> start -> step/run -> finish -> statistics/history.

## Notes

- User clarified that “文档” means deliverable documents; planning documents are still wanted.
- Current route should prioritize the visible page quality and 3D demo before any new phase deliverable writing.
- Preserve the existing single-canteen `/api/config` and `/api/simulation/*` response shapes.
- Current frontend files are still `index.html`, `style.css`, `main.js`, `campus.js`, `campus_map.js`, and `floor_tabs.js`; no `frontend/static/js/three/` implementation exists yet.
- Existing 4/28 plan already contains a Three.js Phase B, but it should be pulled forward or rewritten around a smaller 3D vertical slice.

---

# Deliverable Check Plan

Goal: Check the development-stage deliverables against the provided requirement workbook, task template, format requirements, and naming specification.

## Phases

1. Complete - Inventory actual deliverables and requirement sources.
2. Complete - Extract required deliverable list and naming/format rules.
3. Complete - Inspect DOCX contents and basic formatting signals.
4. Complete - Inspect archive/source packages.
5. Complete - Summarize issues and recommended fixes.
6. Complete - Rebuild source archives with `SRC_[学号]` roots and source-code descriptions.
7. Complete - Rename deliverable files cleanly and verify final folder.
8. Complete - Re-check the three user-specified Zhu Sisi deliverables for content, render, and archive issues.

## Notes

- User deliverable directory: `/Users/sissi/Downloads/03_software_training/development_stage_deliverables` (actual path uses Chinese characters).
- Source files are under `/Users/sissi/Downloads/03_software_training` (actual path uses Chinese characters).
- Current fixed deliverable directory is `/Users/sissi/Downloads/03_软件综合实训/开发阶段交付物`.

---

# External Project Note: Module 1 PPT Production Plan

Goal: Build a 4-slide Module 1 PPT based on `/Users/sissi/Downloads/设计文化概论.pptx`, following the user's detailed timing, narrative, visual-style, and real-photo requirements.

Status note for Canteen work: this section is external to the Canteen simulation project.

## Phases

1. In progress - Inspect the template deck and identify reusable source slides.
2. Pending - Verify source imagery/data and record provenance for real assets.
3. Pending - Create a template-following 4-slide PPTX for Module 1.
4. Pending - Render previews/contact sheet and fix layout defects.
5. Pending - Deliver final PPTX and list unresolved uncertainties.

## Notes

- Target structure: 1 section divider + 3 content slides.
- Target speaking time: 80-85 seconds, with slide count capped at 4.
- Must preserve template-style Chinese visual elements and avoid AI-generated product images.

---

# A.9.1 SimulationEngine Compatibility Fix Plan

Goal: Verify and fix the A.9.1 review issues in the Canteen simulation backend without changing the Phase 2 single-canteen API contract.

## Phases

1. Complete - Reproduce `step()` micro-event regression and `None` placeholder exposure.
2. Complete - Add focused facade regression tests outside the Phase 2 `test_engine.py` group.
3. Complete - Fix `SimulationEngine.step()` to advance to a visible Phase 2 semantic event.
4. Complete - Replace `students` / `event_queue` `None` placeholders with real object views.
5. Complete - Refresh stale coordinator / arrival-generator docstrings.
6. Complete - Add `AGENTS.md` project-context guardrail separating Canteen simulation from the external Design Culture PPT project.
7. Complete - Run full backend regression after edits.
