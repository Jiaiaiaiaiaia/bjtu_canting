# Canteen Project Context

This repository is the Beijing Jiaotong University canteen / restaurant dining simulation project.

Read this file before doing any work in this repository. Treat it as the project-context guardrail for future sessions.

Also keep `agent.md` and `CLAUDE.md` in sync when changing broad collaboration rules.

## Project Identity

- The main project is an interactive canteen simulation system, not a presentation project.
- Core product: a Flask + plain JavaScript web app that simulates student arrivals, queueing, meal service, seat usage, statistics, history, and later multi-canteen campus routing.
- Domain wording: use "食堂仿真", "餐厅模拟", or "就餐仿真系统". If someone casually calls it a game, interpret that as the interactive simulation demo, not a separate game codebase.

## Out-of-Scope Context

- Any `outputs/` content about `模块一`, `设计文化概论`, or cultural-design PPT decks belongs to a separate Design Culture course project.
- Do not use those PPT artifacts to judge the status, requirements, or deliverables of this Canteen simulation project.
- If old planning files mention the Design Culture PPT, treat that section as external context unless the user explicitly asks about that other project.

## Current Technical Shape

- Phase 2 single-canteen mode is the compatibility baseline exposed through `/api/config` and `/api/simulation/*`.
- The integration-stage backend has started a SimPy-based refactor: `SimulationEngine` is now a single-canteen compatibility facade over `CampusCoordinator`.
- Preserve Phase 2 API response shapes for the existing frontend unless the user explicitly approves a breaking change.
- Campus / multi-canteen work should use separate campus APIs and data files; do not overload the existing single-canteen routes.

## Before Editing

- Check `git status --short` first. The worktree may already contain user or prior-agent edits.
- Read the relevant plan/spec before changing behavior:
  - `docs/superpowers/specs/2026-04-28-3d-immersive-multi-canteen-design.md`
  - `docs/superpowers/plans/2026-04-28-3d-immersive-multi-canteen-plan.md`
  - `task_plan.md`, `progress.md`, and `findings.md` if present, but ignore their Design Culture PPT section for Canteen status.
- For bug fixes, add or update focused tests before changing production code.

## Verification

- Backend regression command:
  - `PYTHONPATH=backend ./.venv/bin/python -m pytest backend/tests -q`
- For API/frontend changes, also start the Flask app and manually check the browser flow: config -> start -> step/run -> finish -> statistics/history.
