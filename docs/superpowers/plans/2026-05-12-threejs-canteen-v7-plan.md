# Three.js Canteen V7 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new V7 visual prototype for the Beijing Jiaotong University canteen simulation with a real rotatable 3D campus/canteen scene instead of the current CSS 2.5D model.

**Architecture:** Keep the current backend and API untouched. Add a standalone browser prototype under `.superpowers/brainstorm/96186-1778598663/` that uses Three.js, local model data, and UI overlays. The scene has two modes: campus map and canteen interior, with real floor stacking for Minghu/Xueyi and Xuesi and a clearly marked placeholder for Xuehuo pending field data.

**Tech Stack:** Plain HTML/CSS/JavaScript, Three.js ES modules, OrbitControls, static local data from `docs/phase3/canteen_field_research.md`.

---

### Task 1: Local Three.js Dependency

**Files:**
- Create: `.superpowers/brainstorm/96186-1778598663/vendor/three.module.js`
- Create: `.superpowers/brainstorm/96186-1778598663/vendor/OrbitControls.js`

- [ ] **Step 1: Create the vendor directory**

Run:

```bash
mkdir -p .superpowers/brainstorm/96186-1778598663/vendor
```

- [ ] **Step 2: Download Three.js module files**

Run:

```bash
curl -L https://unpkg.com/three@0.164.1/build/three.module.js -o .superpowers/brainstorm/96186-1778598663/vendor/three.module.js
curl -L https://unpkg.com/three@0.164.1/examples/jsm/controls/OrbitControls.js -o .superpowers/brainstorm/96186-1778598663/vendor/OrbitControls.js
```

- [ ] **Step 3: Confirm files exist**

Run:

```bash
ls -lh .superpowers/brainstorm/96186-1778598663/vendor
```

Expected: both files are present and non-empty.

### Task 2: V7 Standalone Prototype

**Files:**
- Create: `.superpowers/brainstorm/96186-1778598663/canteen-three-real-model-v7.html`

- [ ] **Step 1: Create a standalone HTML shell**

Add a dark digital-twin layout with a full-bleed Three.js canvas, a left canteen selector, a right data panel, and top controls for campus/interior/floor/cutaway/heatmap.

- [ ] **Step 2: Define local canteen model data**

Use the field research values:
- Minghu/Xueyi: 3 floors, 6/13/14 windows, 172/272/290 seats, 734 total seats, 5 minute wait.
- Xuesi: 2 floors, 9/9 displayed windows from the 8-10 range, 150/150 seats, 300 total seats, 5 minute wait.
- Xuehuo: field data pending, no fake numeric capacity.

- [ ] **Step 3: Build the campus scene**

Create stylized but realistic map anchors: north-oriented campus base, curved roads, Minghu water body, and clickable canteen buildings.

- [ ] **Step 4: Build interior scenes**

Build stackable 3D floors with floor slabs, glass walls, vertical stair cores, service windows, queue rails, table groups, occupancy dots, and animated student agents. Use real floor counts and density mapping.

- [ ] **Step 5: Wire interactions**

Add canteen selection, campus/interior toggle, floor focus, cutaway mode, heatmap mode, hover labels, and return-to-campus behavior.

### Task 3: Verification

**Files:**
- Verify: `.superpowers/brainstorm/96186-1778598663/canteen-three-real-model-v7.html`

- [ ] **Step 1: Static checks**

Run:

```bash
rg -n "明湖|学活|学四|Three|OrbitControls|734|约18|待补" .superpowers/brainstorm/96186-1778598663/canteen-three-real-model-v7.html
```

- [ ] **Step 2: Browser rendering checks**

Serve the brainstorm directory locally, open V7, and check console errors, canvas nonblank pixels, desktop screenshot, and mobile screenshot.

- [ ] **Step 3: Interaction checks**

Verify switching canteens and entering interior updates metrics and visible floor stack.
