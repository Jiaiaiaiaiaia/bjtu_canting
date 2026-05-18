# Project Requirements Record

Last updated: 2026-05-17

This file records user requirements that every agent must read before changing code, docs, config, tests, plans, or generated artifacts in this repository.

## Must Read Before Any Change

- Before modifying anything, read `AGENTS.md` and this file.
- Then check `git status --short` and inspect the relevant live files/specs before editing.
- If an older plan or spec conflicts with this file, treat that older document as stale until the user explicitly reconfirms it.
- Do not continue the old campus-map or multi-canteen product direction unless the user explicitly changes this record.

## Current Product Direction

- Only build one canteen.
- The main experience should be a 3D single-canteen simulation / digital-twin view.
- The 3D single-canteen view should support multi-angle display controls, including overview, front, side, top-down, and free-orbit views. This is a camera/display feature and must not change backend simulation state or statistics.
- When jumping into a single floor, the camera/transition should first view the canteen from the side, then change into a top-down view, and finally lay out the whole selected floor across the screen so the floor can be read clearly.
- Floor layouts should be different from each other; do not reuse the same floor plan for every level.
- Floor size, footprint, and proportions should not be arbitrary generic rectangles; choose a suitable scale and shape based on each floor's table/chair data, window placement, aisles, stairs, and usable circulation space.
- Floors need visible stairs between them.
- A student's initial floor should be truly randomized within the single canteen; do not weight the choice by visible queue pressure or service speed.
- Do not use visible/current queue pressure to trigger automatic floor switching. If a future behavior moves a student between floors, it must still go through the stairwell/stairs.
- Student trajectories should not all be identical; different students need individual variation in movement paths.
- A student's target dining window should also be chosen with true randomness among open options on the current floor, instead of every student deterministically going to the same best-looking or shortest-queue window.
- Student routes should be realistic: movement should follow the canteen layout, entrances, stairs, windows, seating areas, aisles, and obstacles instead of teleporting or cutting through walls/furniture.
- Student flow must follow the real dining sequence: go to a window to get food first, then move to a seat/table to sit and eat.
- Seating/stool types should not be monotonous; include varied canteen-appropriate seating forms while keeping them consistent with the real dining layout.
- Visual effects should not be too bright or distracting; avoid glare, overexposed highlights, bloom, or strong glowing elements that block the user's view of the canteen, students, routes, queues, or seats.
- The 3D stage floor and ground grid should be subdued spatial references only; they must not dominate the view or visually compete with the modeled canteen floors, furniture, students, queues, or paths.
- Canteen floor surfaces may use light colors for readability, but they must stay low-opacity and must not hide lower floors in the stacked 3D overview.
- Transparent canteen floor surfaces must avoid double-sided rendering because overlapping transparent front/back passes can flicker in Three.js.
- The stage ground grid should be hidden or effectively invisible in the 3D canteen view so it does not show through translucent canteen floors as moving stripes.
- Transparent canteen floor surfaces should not receive or cast shadows because shadow-map aliasing can create dark bands that read as flicker.
- In stacked overview, floor readability should come mainly from footprint outlines plus a very faint fill, not from multiple large translucent sheets.
- Delete the campus map first. In implementation terms, remove the campus-map product UI/entry before later visual work. Before deleting code, data, or tests, list the affected files and verify whether compatibility tests or backend snapshot paths still depend on them.
- Keep the existing 2D view. The 2D view remains a fallback, debug, and compatibility surface while 3D becomes the main experience.
- Preserve the Phase 2 single-canteen baseline unless the user explicitly approves a breaking change: `/api/config`, `/api/simulation/*`, and the existing single-canteen response shape.
- Campus and multi-canteen concepts are not the product narrative. If backend campus infrastructure is reused as a technical base for the single canteen, keep it out of the user-facing narrative and do not revive campus routing or campus-map behavior.

## Implementation Guardrails

- Do not restore, expand, or polish the multi-canteen campus-map workflow by default.
- Do not remove the 2D fallback while making 3D the default.
- Do not equate "delete campus map" with blindly deleting all backend support; inspect references and tests first, then make a small, reviewable deletion plan.
- Do not implement floor drill-down as a small tilted inset only; the selected floor needs a readable full-floor top-down layout after the side-view transition.
- Do not model every floor as a copied layout with only labels changed; window placement, seating areas, aisles, stairwell placement, or other floor details should differ enough to be visually and behaviorally meaningful.
- Do not force each floor into the same long rectangular box. Floor dimensions should be derived from the modeled furniture/layout data so tables, stools, queues, routes, and stairs fit with believable clearance.
- Implementation standard for 3D floors: `StateAdapter` should emit a per-floor `floor.footprint` with `source: "furnitureDerivedFootprint"`, dimensions, bounds, and outline derived from each floor's window count/placement, visible table groups, chair spacing, aisle clearance, and stair/entrance clearance. `CanteenScene` must consume that footprint instead of hard-coding one shared floor width/depth. Footprints should avoid long skinny rectangles and should keep furniture, queues, entrances, stairs, and routes inside the computed bounds.
- Treat floor choice and floor switching as movement inside one canteen, not as campus routing or multi-canteen behavior.
- Do not fake per-student variation only in the renderer; floor choice, window choice, and path differences should be backed by simulation state or reproducible random streams where behavior affects statistics.
- Do not draw unrealistic straight-line or decorative-only student routes; route generation/rendering should respect reachable paths in the modeled floor layout, and cross-floor movement must pass through the stairwell instead of jumping directly between floors.
- Do not let students sit down before completing the window/service step; direct entrance-to-seat behavior is invalid unless the user explicitly asks for a separate non-dining behavior.
- Do not place stools/seats as arbitrary decorations; seating variety should still follow believable canteen seating zones, table relationships, and aisle clearance.
- Do not use bright visual styling as decoration if it hurts readability. Lighting, heat maps, route highlights, and status indicators must stay legible and should not obscure the scene.
- Do not make the ground plane or grid read as the main canteen floor. Keep stage-floor opacity and grid opacity low, and keep the actual per-floor slabs/footprints visually readable under the canteen content.
- If the canteen floor uses light colors, keep it as a pale translucent material rather than a solid white sheet, so lower floors, furniture, queues, paths, and students remain visible.
- Do not render flat transparent floor surfaces as `DoubleSide`; choose the stable visible side or another single-pass approach so the floor does not shimmer or flicker during camera movement.
- Do not render a visible stage grid under translucent canteen floors; it can create moire-like striping that reads as floor flicker.
- Do not enable shadow receive/cast on flat translucent floor surfaces; use furniture, walls, and avatars for depth cues instead.
- Do not stack a separate translucent tile sheet on top of the floor slab; use a floor outline or edge cue for tile/footprint readability.
- For any future change touching campus, 3D, or 2D flow, explicitly check that it obeys: one canteen, 3D main experience, campus map removed first, and 2D retained.

## Implementation Records

- 2026-05-17: Floor and window choice is true random among eligible open choices, not weighted by open-window service capacity, current queue load, or visible congestion. A student first gets a random open floor, then chooses a random open window on that current floor. Queue visibility should not automatically trigger `floor_switching`; if floor switching is introduced by an explicit future behavior, backend snapshots must still expose `position: "floor_switching"`, `position_detail: "stairs"`, `from_floor_id`, `target_floor_id`, and `floor_switch_progress`, and the 3D adapter must render this state on the stair core instead of drawing a direct cross-floor line.
- 2026-05-17: Window intervention state must be visible in every backend snapshot consumed by the 3D UI. `Canteen.snapshot()` exposes each window's `is_open` and derived `closing` state in both top-level `windows[]` and nested `floors[].windows[]`; `closing` means the window is no longer open but still has queued or currently served students. The 3D operation panel must use these fields instead of assuming missing state means open.
- 2026-05-17: User-facing single-canteen display name is shortened to `明湖` while preserving the stable backend id `minghu_xueyi`. To address floor flicker, the 3D renderer must not draw tile-line grids over translucent canteen floor slabs, and the transparent stage floor must not receive or cast shadows or write depth.
- 2026-05-17: Single-floor focus must render only the selected floor. Non-selected floors should be hidden rather than slid aside or kept as contextual layers; returning to the overview restores all floor groups.
- 2026-05-18: Focused single-floor view must make the selected floor surface visibly readable with a stable light material, while the stacked overview must keep floor fill low-opacity so lower floors remain visible. The renderer should use a non-lighting-dependent single-pass material for the transparent floor slab, keep depth writing off, and keep the higher opacity only for the selected focused floor.
- 2026-05-18: The 3D overlay exposes multi-angle camera presets (`overview`, `front`, `side`, `top`, `free`) from the immersive toolbar. Preset changes are renderer-only and do not touch the backend snapshot, arrival flow, queueing logic, or statistics.

## Source

- User request on 2026-05-17: "只做一个食堂，3d 的，先删除校园地图，然后2d保留".
- User request on 2026-05-17: "跳转到单独楼层的时候要从侧面看，变成俯视，然后把整个楼层铺开画面".
- User request on 2026-05-17: "楼层之间需要有楼梯，小人如果发现某个楼层人很多会换楼层呢，小人到哪个楼层是随机的".
- User request on 2026-05-17: "每个小人的轨迹不要一样，还有小人到哪个窗口也随机的".
- User request on 2026-05-17: "按“开放窗口服务能力 / 当前队伍压力”加权，更空、更快的楼层概率更高，去掉视线真正的随机".
- User request on 2026-05-17: "小人的路线要真实".
- User request on 2026-05-17: "小人换楼层只可以通过楼梯间".
- User request on 2026-05-17: "楼层之间的布局不一样".
- User request on 2026-05-17: "凳子种类不要单一，要符合食堂布局" (interpreted from "凳子种类不要单一，不要符合食堂布局" because the literal wording conflicts with the prior realism requirements).
- User request on 2026-05-17: "小人要先去窗口打饭再就坐".
- User request on 2026-05-17: "每个楼层的尺寸不要长方形，根据桌椅数据选择合适的".
- User request on 2026-05-17: "不要有亮的影响视线".
- User request on 2026-05-17: "修复地板后记录，再要求.md 中".
- User request on 2026-05-17: "地板的颜色看不清下面的了" and "修复一下可以使用亮色".
- User request on 2026-05-17: "地板在闪烁".
- User request on 2026-05-17: "我希望只聚焦一层的时候其他层不要出现".
- User request on 2026-05-18: "可不可以多角度展示" and follow-up approval "可以".
