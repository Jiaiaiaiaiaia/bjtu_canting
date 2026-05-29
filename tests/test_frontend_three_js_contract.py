"""Optional Three.js view contract tests."""
import json
from pathlib import Path
import subprocess
import textwrap


REPO_ROOT = Path(__file__).resolve().parents[1]
SCENE3D_JS = REPO_ROOT / 'frontend' / 'static' / 'js' / 'three' / 'scene3d.js'


def test_scene3d_exposes_canteen_app_3d_api():
    assert SCENE3D_JS.exists()
    source = SCENE3D_JS.read_text(encoding='utf-8')

    for snippet in (
        "import * as THREE from 'three'",
        "import { OrbitControls } from 'three/addons/controls/OrbitControls.js'",
        'window.CanteenApp3D = {',
        'init(container)',
        'render(snapshot, appState)',
        'dispose()',
        'visibleCanteens',
        'pendingCanteens',
    ):
        assert snippet in source


def test_scene3d_render_returns_to_fallback_when_webgl_is_unavailable():
    source = SCENE3D_JS.read_text(encoding='utf-8')

    for snippet in (
        'let webglAvailable = true;',
        'webglAvailable = false;',
        'if (!webglAvailable || !renderer || !contentGroup) {',
        "showFallback(document.getElementById('three-stage'));",
        "canteen:three-fallback",
        'return;',
    ):
        assert snippet in source


THREE_DIR = REPO_ROOT / 'frontend' / 'static' / 'js' / 'three'


def _three_source(module_name):
    return (THREE_DIR / module_name).read_text(encoding="utf-8")


def _optional_three_source(module_name):
    path = THREE_DIR / module_name
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _canteen_scene_contract_source():
    """Source tokens that define the canteen scene contract after module split."""
    return "\n".join((
        _three_source("canteen_scene.js"),
        _optional_three_source("canteen_layouts.js"),
        _optional_three_source("canteen_furniture.js"),
    ))


def _assert_any_token(source, tokens, message):
    assert any(tok in source for tok in tokens), message


def test_scene3d_modules_exist_and_facade_preserved():
    s = (THREE_DIR / "scene3d.js").read_text(encoding="utf-8")
    for snippet in ("window.CanteenApp3D = {", "init(container)",
                    "render(snapshot, appState)", "dispose()",
                    "visibleCanteens", "pendingCanteens"):
        assert snippet in s              # 既有契约不破
    for m in ("state_adapter.js", "canteen_scene.js", "intervention_ui.js"):
        assert (THREE_DIR / m).exists()


def test_scene_fx_module_contract():
    s = (THREE_DIR / "scene_fx.js").read_text(encoding="utf-8")
    assert "export class SceneFX" in s
    assert "three/addons/postprocessing/EffectComposer.js" in s
    assert "UnrealBloomPass" in s
    assert "ACESFilmicToneMapping" in s
    # 失败降级、不触发 .three-fallback
    assert "this.enabled = false" in s
    assert "renderer.render(" in s


def test_scene3d_fx_and_raf_decouple_contract():
    s = (THREE_DIR / "scene3d.js").read_text(encoding="utf-8")
    # 契约 token 仍在
    for tok in ("window.CanteenApp3D = {", "init(container)",
                "render(snapshot, appState)", "dispose()",
                "visibleCanteens", "pendingCanteens",
                "let webglAvailable = true;", "webglAvailable = false;",
                "if (!webglAvailable || !renderer || !contentGroup) {",
                "showFallback(document.getElementById('three-stage'));"):
        assert tok in s, f"missing contract token: {tok!r}"
    # scene_fx 接入（本任务只接 composer/灯光雾；不动 animate 的 update→tick）
    assert "import { SceneFX } from './scene_fx.js'" in s
    assert "sceneFX" in s


def test_canteen_scene_split_and_v7_geometry():
    s = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    import re
    assert "tick(" in s, "missing tick() (RAF advance entry)"
    assert "update(frame)" in s.replace(" ", "") or "update(frame)" in s
    assert "_rebuild(" in s

    # Indentation-robust: slice a class method body from its signature up to the
    # NEXT class-method declaration (4-space-indented `name(...) {`) or EOF.
    def method_body(src, name):
        m = re.search(r"\n\s*" + re.escape(name) + r"\s*\([^)]*\)\s*\{", src)
        if not m:
            return None
        start = m.end()
        nxt = re.search(r"\n {4}[A-Za-z_]\w*\s*\([^)]*\)\s*\{", src[start:])
        return src[start: start + (nxt.start() if nxt else len(src) - start)]

    tb = method_body(s, "tick")
    ub = method_body(s, "update")
    assert tb is not None and "_rebuild(" not in tb, "tick() must NOT _rebuild() (RAF path)"
    assert ub is not None and "_rebuild(" in ub, "update(frame) must _rebuild() on snapshot"
    for tok in ("plinth", "glass", "stairCore", "cutaway", "heatColor"):
        assert tok in s, f"missing V7 token: {tok!r}"
    s3 = (THREE_DIR / "scene3d.js").read_text(encoding="utf-8")
    ma = re.search(r"function animate\(\)\s*\{.*?\n\}", s3, re.S)
    assert ma, "scene3d animate() not found"
    assert "canteenScene.tick(" in ma.group(0), "animate() must call canteenScene.tick() after V4"
    assert "canteenScene.update(" not in ma.group(0), \
        "animate() must NOT call canteenScene.update() (per-RAF rebuild removed)"


def test_default_twin_view_prioritizes_building_over_empty_ground():
    s3 = (THREE_DIR / "scene3d.js").read_text(encoding="utf-8")
    cs = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")

    for tok in (
        "const STAGE_GROUND_WIDTH = 440;",
        "const STAGE_GROUND_DEPTH = 240;",
        "const STAGE_GRID_SIZE = 420;",
        "const STAGE_GRID_DIVISIONS = 12;",
        "new THREE.GridHelper(STAGE_GRID_SIZE, STAGE_GRID_DIVISIONS",
    ):
        assert tok in s3, f"3D stage should keep the ground grid compact: {tok!r}"

    for tok in (
        "const OVERVIEW_CAMERA_Z = 360;",
        "const OVERVIEW_CAMERA_X = 160;",
        "const OVERVIEW_CAMERA_Y_PADDING = 118;",
        "Math.max(OVERVIEW_CAMERA_Z, buildingFootprint.maxZ + 250)",
        "this._camTarget.look.set(buildingFootprint.centerX + buildingFootprint.width * OVERVIEW_LOOK_PANEL_CLEARANCE_X_RATIO, centerY, buildingFootprint.centerZ)",
    ):
        assert tok in cs, f"default overview camera should frame the building first: {tok!r}"


def test_stage_ground_is_subtle_reference_not_dominant_floor():
    s3 = (THREE_DIR / "scene3d.js").read_text(encoding="utf-8")

    for tok in (
        "const STAGE_FLOOR_OPACITY = 0.42;",
        "const STAGE_GRID_OPACITY = 0.0;",
        "floor.name = 'subtle stage floor';",
        "grid.name = 'subtle stage grid';",
        "grid.material.transparent = true;",
        "grid.material.opacity = STAGE_GRID_OPACITY;",
        "grid.visible = STAGE_GRID_OPACITY > 0;",
        "floor.material.depthWrite = false;",
        "floor.receiveShadow = false;",
        "floor.castShadow = false;",
    ):
        assert tok in s3, f"stage floor/grid should stay visually subdued: {tok!r}"


def test_canteen_floor_shape_is_visible_from_above():
    s = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    for tok in (
        "mesh.material.side = THREE.BackSide;",
        "mesh.material.needsUpdate = true;",
        "floor shape must be visible from above",
        "avoid transparent DoubleSide floor flicker",
    ):
        assert tok in s, f"floor shape should not be back-face culled: {tok!r}"
    assert "mesh.material.side = THREE.DoubleSide;" not in s


def test_canteen_floor_surfaces_do_not_hide_lower_levels():
    s = _canteen_scene_contract_source()
    for tok in (
        "const FLOOR_SLAB_COLORS = [0xf0f4ee, 0xe3ece8];",
        "const FLOOR_TILE_COLOR = 0xf4f7f1;",
        "const OVERVIEW_FLOOR_SLAB_OPACITY = 0.07;",
        "const FOCUS_FLOOR_SLAB_OPACITY = 1.0;",
        "const FLOOR_OUTLINE_OPACITY = 0.72;",
        "const FLOOR_TILE_OUTLINE_OPACITY = 0.42;",
        "_floorOutline(",
        "new THREE.LineLoop(",
        "floor outline should mark footprint without a second transparent sheet",
        "const slabBaseColor = FLOOR_SLAB_COLORS[floor.index % FLOOR_SLAB_COLORS.length];",
        "floor surface must not hide lower levels",
        "mesh.material.depthWrite = mesh.material.opacity >= 0.98;",
        "transparent floor surfaces should not receive shadow-map stripes",
        "mesh.receiveShadow = false;",
        "mesh.castShadow = false;",
    ):
        assert tok in s, f"floor surface should stay readable but transparent: {tok!r}"
    assert "const tile = this._floorShapeMesh(" not in s
    assert "FLOOR_TILE_OPACITY" not in s


def test_focused_canteen_floor_uses_stable_readable_light_surface():
    s = _canteen_scene_contract_source()
    for tok in (
        "const OVERVIEW_FLOOR_SLAB_OPACITY = 0.07;",
        "const FOCUS_FLOOR_SLAB_OPACITY = 1.0;",
        "_floorSlabOpacity(floor)",
        "floor surface opacity increases only for selected floor focus",
        "_floorSlabMaterial(color, opacity)",
        "new this.THREE.MeshBasicMaterial({",
        "transparent: opacity < 0.98",
        "depthWrite: opacity >= 0.98",
        "toneMapped: false",
        "mat.forceSinglePass = true;",
    ):
        assert tok in s, f"focused floor should use a stable readable light surface: {tok!r}"


def test_canteen_floor_slab_is_not_coplanar_with_site_plinth():
    s = _canteen_scene_contract_source()
    for tok in (
        "const SITE_PLINTH_CENTER_Y = -7;",
        "plinth.position.set(buildingFootprint.centerX, SITE_PLINTH_CENTER_Y, buildingFootprint.centerZ);",
        "const FLOOR_SLAB_RENDER_ORDER = -4;",
        "mesh.renderOrder = FLOOR_SLAB_RENDER_ORDER;",
    ):
        assert tok in s, f"floor slab should not z-fight with the site plinth: {tok!r}"


def test_state_adapter_places_students_by_backend_state():
    s = (THREE_DIR / "state_adapter.js").read_text(encoding="utf-8")
    for tok in (
        "attachUnassignedStudents",
        "placeStudentTarget",
        "windowById",
        "seatById",
        "queue_index",
        "position_detail",
        "window_queue",
        "being_served",
        "seated",
        "waiting_queue",
    ):
        assert tok in s, f"state adapter must use backend state token: {tok!r}"


def test_state_adapter_new_students_start_at_nearest_side_entrance():
    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const windows = Array.from({ length: 6 }, (_, idx) => ({
          id: idx === 0 ? 'low-window' : `w${idx}`,
          is_open: true,
          queue_length: 1
        }));
        const snapshot = {
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              display_name: '明湖学一',
              floors: [{
                floor_id: 1,
                windows,
                seats: [],
                students: [
                  {
                    id: 'lower-entry-student',
                    floor_id: 1,
                    position: 'window_queue',
                    position_detail: 'low-window',
                    queue_index: 0
                  },
                  {
                    id: 'upper-entry-student',
                    floor_id: 1,
                    position: 'waiting_queue',
                    position_detail: 15
                  }
                ]
              }]
            }
          }
        };

        const adapter = new StateAdapter();
        const first = adapter.buildFrame(snapshot, { activeCanteenId: 'minghu_xueyi' })
          .floors[0].students;
        const second = adapter.buildFrame(snapshot, { activeCanteenId: 'minghu_xueyi' })
          .floors[0].students;

        console.log(JSON.stringify({
          firstLower: first[0],
          firstUpper: first[1],
          secondLower: second[0],
          secondUpper: second[1]
        }));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)

    assert payload["firstLower"]["position3d"]["x"] < 0
    assert payload["firstUpper"]["position3d"]["x"] < 0
    assert payload["firstLower"]["position3d"]["z"] < payload["firstUpper"]["position3d"]["z"]
    assert payload["firstLower"]["entry3d"]["z"] == payload["firstLower"]["position3d"]["z"]
    assert payload["firstUpper"]["entry3d"]["z"] == payload["firstUpper"]["position3d"]["z"]
    assert payload["secondLower"]["position3d"]["x"] > payload["firstLower"]["position3d"]["x"]
    assert payload["secondUpper"]["position3d"]["x"] > payload["firstUpper"]["position3d"]["x"]


def test_state_adapter_spreads_student_spawn_and_queue_points():
    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const students = Array.from({ length: 18 }, (_, idx) => ({
          id: `student-${idx}`,
          floor_id: 1,
          position: 'window_queue',
          position_detail: 'w0',
          queue_index: idx
        }));
        const snapshot = {
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              floors: [{
                floor_id: 1,
                windows: [{ id: 'w0', is_open: true, queue_length: students.length }],
                seats: [],
                students
              }]
            }
          }
        };

        const floor = new StateAdapter()
          .buildFrame(snapshot, { activeCanteenId: 'minghu_xueyi' })
          .floors[0];
        const entries = floor.students.map(s => [
          Math.round(s.entry3d.x * 10) / 10,
          Math.round(s.entry3d.z * 10) / 10
        ]);
        const targets = floor.students.map(s => [
          Math.round(s.target.x * 10) / 10,
          Math.round(s.target.z * 10) / 10
        ]);
        const entryXs = entries.map(p => p[0]);
        const entryZs = entries.map(p => p[1]);
        const targetZs = targets.map(p => p[1]);
        console.log(JSON.stringify({
          uniqueEntries: new Set(entries.map(p => `${p[0]}:${p[1]}`)).size,
          entrySpreadX: Math.max(...entryXs) - Math.min(...entryXs),
          entrySpreadZ: Math.max(...entryZs) - Math.min(...entryZs),
          uniqueTargets: new Set(targets.map(p => `${p[0]}:${p[1]}`)).size,
          targetSpreadZ: Math.max(...targetZs) - Math.min(...targetZs)
        }));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)

    assert payload["uniqueEntries"] >= 10
    assert payload["entrySpreadX"] >= 5
    assert payload["entrySpreadZ"] >= 16
    assert payload["uniqueTargets"] >= 15
    assert payload["targetSpreadZ"] >= 24


def test_state_adapter_marks_new_student_entry_path_from_gate():
    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const baseSnapshot = {
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              floors: [{
                floor_id: 1,
                windows: [{ id: 'w0', is_open: true, queue_length: 1 }],
                seats: [],
                students: []
              }]
            }
          }
        };
        const nextSnapshot = structuredClone(baseSnapshot);
        nextSnapshot.canteens.minghu_xueyi.floors[0].students = [{
          id: 'new-student',
          floor_id: 1,
          position: 'window_queue',
          position_detail: 'w0',
          queue_index: 0
        }];

        const adapter = new StateAdapter();
        adapter.buildFrame(baseSnapshot, { activeCanteenId: 'minghu_xueyi' });
        const student = adapter.buildFrame(nextSnapshot, { activeCanteenId: 'minghu_xueyi' })
          .floors[0].students[0];
        console.log(JSON.stringify(student));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    student = json.loads(result.stdout)

    assert student["is_entering"] is True
    assert student["entry3d"]["x"] < 0
    assert student["position3d"] == student["entry3d"]
    assert student["target"]["x"] > student["entry3d"]["x"]


def test_state_adapter_places_floor_switching_students_on_stair_core():
    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const frame = new StateAdapter().buildFrame({
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              floors: [
                {
                  floor_id: 1,
                  windows: [{ id: 'w0', is_open: true, queue_length: 4 }],
                  seats: [],
                  students: [{
                    id: 'switching-student',
                    floor_id: 1,
                    position: 'floor_switching',
                    position_detail: 'stairs',
                    from_floor_id: 1,
                    target_floor_id: 2,
                    floor_switch_progress: 0.5
                  }]
                },
                {
                  floor_id: 2,
                  windows: [{ id: 'w1', is_open: true, queue_length: 0 }],
                  seats: [],
                  students: []
                }
              ]
            }
          }
        }, { activeCanteenId: 'minghu_xueyi' });

        const student = frame.floors[0].students[0];
        console.log(JSON.stringify({
          target: student.target,
          position3d: student.position3d,
          entry3d: student.entry3d,
          baseY0: frame.floors[0].baseY,
          baseY1: frame.floors[1].baseY
        }));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)

    assert payload["target"]["x"] < 0
    assert payload["target"]["y"] > payload["baseY0"] + 20
    assert payload["target"]["y"] < payload["baseY1"] + 20
    assert payload["position3d"] == payload["entry3d"]
    assert payload["position3d"]["y"] == payload["target"]["y"]


def test_state_adapter_uses_distinct_minghu_floor_layouts():
    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const makeFloor = (floorId) => ({
          floor_id: floorId,
          windows: Array.from({ length: 14 }, (_, idx) => ({
            id: `${floorId}-w${idx}`,
            is_open: true,
            queue_length: idx % 3
          })),
          seats: Array.from({ length: 96 }, (_, idx) => ({
            id: `${floorId}-s${idx}`,
            status: idx % 5 === 0 ? 'occupied' : 'empty'
          })),
          students: []
        });

        const adapter = new StateAdapter();
        const frame = adapter.buildFrame({
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              display_name: '明湖学一',
              floors: [makeFloor(1), makeFloor(2), makeFloor(3)]
            }
          }
        }, { activeCanteenId: 'minghu_xueyi' });

        const compact = frame.floors.map(floor => ({
          floorId: floor.floor_id,
          windows: floor.windows.map(w => [
            Math.round(w.position.x),
            Math.round(w.position.z)
          ]),
          seats: floor.seats.slice(0, 24).map(s => [
            Math.round(s.position.x),
            Math.round(s.position.z)
          ])
        }));
        console.log(JSON.stringify(compact));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    floors = json.loads(result.stdout)

    window_layouts = [floor["windows"] for floor in floors]
    seat_layouts = [floor["seats"] for floor in floors]
    assert len({json.dumps(layout) for layout in window_layouts}) == 3
    assert len({json.dumps(layout) for layout in seat_layouts}) == 3
    assert len({z for _, z in floors[0]["windows"]}) == 1
    assert len({z for _, z in floors[1]["windows"]}) > 1
    assert len({z for _, z in floors[2]["windows"]}) > 1


def test_canteen_scene_renders_students_as_3d_avatars():
    s = _canteen_scene_contract_source()
    for tok in (
        "_studentAvatar",
        "CapsuleGeometry",
        "SphereGeometry",
        "studentBody",
        "studentHead",
        "student.position === 'window_queue'",
        "student.position === 'seated'",
    ):
        assert tok in s, f"missing 3D avatar/state token: {tok!r}"


def test_canteen_scene_keeps_student_clothing_color_stable_across_states():
    s = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    for tok in (
        "stableStudentClothingColor",
        "STUDENT_CLOTHING_PALETTE",
        "studentStatusColor",
        "studentStatusRing",
    ):
        assert tok in s, f"missing stable clothing/status token: {tok!r}"

    for state_color_assignment in (
        "if (student.position === 'window_queue') color =",
        "if (student.position === 'waiting_queue') color =",
        "if (student.position === 'being_served') color =",
        "color = PALETTE.seatOccupied",
    ):
        assert state_color_assignment not in s


def test_canteen_scene_does_not_draw_student_route_lines():
    s = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    for tok in ("_studentEntryPath", "studentEntryPath", "kind: 'studentEntryPath'"):
        assert tok not in s, f"student routes should not be rendered: {tok!r}"
    assert "floor.students.forEach(student => {" in s
    assert "fg.add(this._studentAvatar(student, floor.floor_id));" in s


def test_state_adapter_keeps_moderate_crowds_for_3d_rendering():
    adapter = (THREE_DIR / "state_adapter.js").read_text(encoding="utf-8")
    assert ".slice(0, 80)" not in adapter

    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const students = Array.from({ length: 140 }, (_, id) => ({
          id: `student-${id}`,
          floor_id: 2,
          position: 'window_queue',
          position_detail: 'w0',
          queue_index: id
        }));
        const snapshot = {
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              floors: [{
                floor_id: 2,
                windows: [{ id: 'w0', is_open: true, queue_length: students.length }],
                seats: [],
                students
              }]
            }
          }
        };

        const frame = new StateAdapter()
          .buildFrame(snapshot, { activeCanteenId: 'minghu_xueyi' });
        console.log(JSON.stringify({
          studentCount: frame.floors[0].students.length,
          kpiStudents: frame.perFloorKpi[0].students,
          studentsInCanteen: frame.students_in_canteen
        }));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)
    assert payload == {
        "studentCount": 140,
        "kpiStudents": 140,
        "studentsInCanteen": 140,
    }


def test_state_adapter_caps_heavy_crowds_without_truncating_kpis():
    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const students = Array.from({ length: 500 }, (_, id) => ({
          id: `student-${id}`,
          floor_id: 2,
          position: 'window_queue',
          position_detail: 'w0',
          queue_index: id
        }));
        const snapshot = {
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              floors: [{
                floor_id: 2,
                windows: [{ id: 'w0', is_open: true, queue_length: students.length }],
                seats: [],
                students
              }]
            }
          }
        };

        const frame = new StateAdapter()
          .buildFrame(snapshot, { activeCanteenId: 'minghu_xueyi' });
        console.log(JSON.stringify({
          studentCount: frame.floors[0].students.length,
          kpiStudents: frame.perFloorKpi[0].students,
          studentsInCanteen: frame.students_in_canteen
        }));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)
    assert payload == {
        "studentCount": 96,
        "kpiStudents": 500,
        "studentsInCanteen": 500,
    }


def test_canteen_scene_marks_side_entrances_for_student_spawn():
    s = _canteen_scene_contract_source()
    for tok in (
        "_addEntranceMarker",
        "SIDE_ENTRANCE_X",
        "SIDE_ENTRANCE_MARKERS",
        "ENTRANCE_DOOR_DEPTH",
        "ENTRANCE_DOOR_HEIGHT",
        "ENTRANCE_GLASS_DEPTH",
        "ENTRANCE_CANOPY_DEPTH",
        "canteenEntranceLowerStair",
        "canteenEntranceUpperStair",
        "stairCoreEntranceLower",
        "stairCoreEntranceUpper",
        "side entrance, clear of front sightline",
        "entranceDoorFrame",
        "entranceGlassPanel",
        "entranceCanopy",
        "student spawn entrance marker",
    ):
        assert tok in s, f"missing entrance marker token: {tok!r}"
    for front_pos in ("BASE_D + 4.5", "BASE_D + 1.7", "BASE_D + 2.6", "BASE_D + 5.0"):
        assert front_pos not in s, "entrance markers must not sit on the front sightline"
    for cramped_door in ("[1.4, 10.5, 32]", "[0.8, 7.4, 20]", "[7.8, 2.0, 38]"):
        assert cramped_door not in s, f"entrance should read as a wider canteen doorway: {cramped_door!r}"
    for label in ("食堂入口", "入口A", "入口B"):
        assert label not in s, f"entrance should be modeled in 3D, not labeled as {label!r}"


def test_canteen_scene_has_visible_vertical_transport_core():
    s = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    for tok in (
        "_addElevatorCore",
        "elevator glass shaft",
        "elevator car",
        "elevator landing bridge",
        "elevator floor door",
        "stair step stack",
        "stair handrail",
    ):
        assert tok in s, f"vertical transport core should be visually explicit: {tok!r}"


def test_canteen_scene_uses_balanced_building_and_focus_camera_proportions():
    s = _canteen_scene_contract_source()
    adapter = (THREE_DIR / "state_adapter.js").read_text(encoding="utf-8")

    for tok in (
        "const FLOOR_V = 104",
        "FOOTPRINT_MAX_ASPECT_RATIO",
        "furnitureDerivedFootprint",
        "floor.footprint",
        "footprint.outline",
    ):
        assert tok in adapter, f"state adapter should derive floor footprint token: {tok!r}"
    for tok in (
        "_floorFootprint(",
        "_floorShapeMesh(",
        "new THREE.Shape(",
        "floor.footprint",
        "footprint.outline",
    ):
        assert tok in s, f"scene should render from frame footprint token: {tok!r}"

    assert "const SIDE_ENTRANCE_X = -10" in adapter
    assert "const SIDE_ENTRANCE_ZS = [28, 68]" in adapter
    assert "const BASE_W = 320" not in s
    assert "const BASE_D = 96" not in s
    assert "new THREE.BoxGeometry(BASE_W, 5, BASE_D)" not in s
    assert "const OVERVIEW_CAMERA_X = 160" in s
    assert "const FOCUS_CAMERA_X = 160" in s
    assert "camera.position.set(160, 246, 360)" in (THREE_DIR / "scene3d.js").read_text(encoding="utf-8")
    assert "FOCUS_CONTEXT_OFFSET" not in s
    assert "FOCUS_SLIDE" not in s
    assert "focus mode renders selected floor only" in s


def test_state_adapter_keeps_overview_floors_visibly_separated():
    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const makeFloor = floorId => ({
          floor_id: floorId,
          windows: Array.from({ length: 6 }, (_, id) => ({
            id: `f${floorId}-w${id}`,
            is_open: true,
            queue_length: 0
          })),
          seats: Array.from({ length: 48 }, (_, id) => ({
            id: `f${floorId}-s${id}`,
            status: 'empty'
          })),
          students: []
        });

        const frame = new StateAdapter().buildFrame({
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              floors: [makeFloor(1), makeFloor(2), makeFloor(3)]
            }
          }
        }, { activeCanteenId: 'minghu_xueyi' });

        console.log(JSON.stringify(frame.floors.map(floor => floor.baseY)));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    base_ys = json.loads(result.stdout)
    gaps = [base_ys[idx + 1] - base_ys[idx] for idx in range(len(base_ys) - 1)]

    assert gaps == [104, 104]


def test_canteen_scene_floor_focus_uses_side_to_top_to_full_floor_sequence():
    s = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")

    for tok in (
        "focusTransitionStage",
        "focusTransitionStartedAt",
        "FOCUS_SIDE_DURATION_MS",
        "FOCUS_TOP_DURATION_MS",
        "FOCUS_SIDE_CAMERA_Z",
        "FOCUS_TOP_CAMERA_Y_PADDING",
        "FOCUS_EXPANDED_CAMERA_Y_PADDING",
        "_currentFocusStage()",
        "_focusStageProgress(",
        "stage === 'side'",
        "stage === 'top'",
        "stage === 'expanded'",
        "whole selected floor readable",
    ):
        assert tok in s, f"floor focus must stage side -> top -> readable full-floor view: {tok!r}"
    assert "buildingFootprint.centerX" in s
    assert "Math.max(OVERVIEW_CAMERA_Z, buildingFootprint.maxZ + 250)" in s
    assert "this._camTarget.look.set(buildingFootprint.centerX + buildingFootprint.width * OVERVIEW_LOOK_PANEL_CLEARANCE_X_RATIO, centerY, buildingFootprint.centerZ)" in s
    assert "fg.visible = this.mode !== 'focus' || this.focusFloorId == null || floorId === this.focusFloorId" in s


def test_canteen_scene_focus_renders_only_selected_floor_group():
    s = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")

    for tok in (
        "focus mode renders selected floor only",
        "fg.visible = this.mode !== 'focus' || this.focusFloorId == null || floorId === this.focusFloorId",
        "fg.position.x = 0;",
        "this._floorSlide.set(floorId, 0);",
    ):
        assert tok in s, f"focus mode should hide non-selected floor groups: {tok!r}"

    for tok in (
        "FOCUS_CONTEXT_OFFSET",
        "FOCUS_EXPANDED_SPREAD_OFFSET",
        "targetSlide = dir * spread",
        "context-preserving focus",
    ):
        assert tok not in s, f"focus should no longer keep other floors visible: {tok!r}"


def test_canteen_scene_focus_hides_large_scene_labels_from_sightline():
    s = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    for tok in (
        "overview-only canteen title",
        "if (this.mode === 'overview') {",
        "sprite.scale.set(90 * scale, 22 * scale, 1)",
        "this._lastFrame && this._rebuild(this._lastFrame)",
    ):
        assert tok in s, f"missing focus sightline token: {tok!r}"
    for tok in (
        "const floorName = `${floor.floor_id}F`",
        "const labelText = `${floor.floor_id}",
        "FOCUS_LABEL_SCALE",
        "◀ 焦点",
    ):
        assert tok not in s, f"3D floor overlay text should stay out of the scene: {tok!r}"


def test_canteen_scene_does_not_draw_floor_window_or_seat_count_text():
    s = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    for tok in (
        "floor.windows.length}窗",
        "floor.seats.length}座",
        "labelText = `${floor.floor_id}",
        "const floorName = `${floor.floor_id}F`",
    ):
        assert tok not in s, f"3D floor overlay should not show window/seat count text: {tok!r}"


def test_canteen_scene_window_labels_stay_readable_and_sparse():
    s = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    for tok in (
        "WINDOW_LABEL_RENDER_ORDER",
        "WINDOW_LABEL_DENSITY_STEP",
        "alwaysReadableWindowLabel",
        "mat.depthTest = false",
        "mat.depthWrite = false",
        "sprite.renderOrder = options.renderOrder",
        "_shouldShowWindowLabel(floor, win, localIndex)",
        "win.is_serving || win.closing",
        "localIndex % WINDOW_LABEL_DENSITY_STEP === 0",
        "top-view labels must float above service counters",
    ):
        assert tok in s, f"window labels should be readable, sparse, and not occluded: {tok!r}"


def test_state_adapter_places_windows_in_loose_service_bays():
    adapter = (THREE_DIR / "state_adapter.js").read_text(encoding="utf-8")
    scene = _canteen_scene_contract_source()
    for tok in (
        "windowBays",
        "windowBayCounts",
        "bayStaggerZ",
        "windowBayPosition",
    ):
        assert tok in adapter, f"state adapter should support loose service window bays: {tok!r}"
    for tok in (
        "windowBays",
        "f2-left-snack-bay",
        "f3-specialty-side-bay",
    ):
        assert tok in adapter, f"state adapter should support loose service window bays: {tok!r}"
        assert tok in scene, f"scene profile should document matching service window bays: {tok!r}"

    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const makeFloor = (floorId, windowCount, seatCount) => ({
          floor_id: floorId,
          windows: Array.from({ length: windowCount }, (_, id) => ({
            id: `f${floorId}-w${id}`,
            floor_id: floorId,
            queue_length: 0,
            is_open: true
          })),
          seats: Array.from({ length: seatCount }, (_, id) => ({
            id: `f${floorId}-s${id}`,
            floor_id: floorId,
            status: 'empty'
          })),
          students: []
        });

        const frame = new StateAdapter().buildFrame({
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              floors: [
                makeFloor(1, 6, 172),
                makeFloor(2, 13, 272),
                makeFloor(3, 14, 290)
              ]
            }
          }
        }, { activeCanteenId: 'minghu_xueyi' });

        const summary = frame.floors.map(floor => {
          const fronts = floor.windows
            .filter(win => win.position.side === 'front')
            .map(win => win.position);
          const sortedFrontX = fronts.map(pos => Math.round(pos.x)).sort((a, b) => a - b);
          const xGaps = sortedFrontX.slice(1).map((x, idx) => x - sortedFrontX[idx]);
          const roundedFrontZ = [...new Set(fronts.map(pos => Math.round(pos.z)))];
          const sideCount = floor.windows
            .filter(win => win.position.side === 'left').length;
          const allInside = floor.windows.every(win => (
            win.position.x >= floor.footprint.minX + 8
            && win.position.x <= floor.footprint.maxX - 8
            && win.position.z >= floor.footprint.minZ + 8
            && win.position.z <= floor.footprint.maxZ - 8
          ));
          return {
            floorId: floor.floor_id,
            sideCount,
            frontZBandCount: roundedFrontZ.length,
            maxFrontXGap: xGaps.length ? Math.max(...xGaps) : 0,
            allInside
          };
        });
        console.log(JSON.stringify(summary));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    floors = {row["floorId"]: row for row in json.loads(result.stdout)}

    assert floors[1]["sideCount"] == 0
    assert floors[1]["frontZBandCount"] >= 1
    assert floors[1]["maxFrontXGap"] >= 44
    assert floors[2]["sideCount"] <= 1
    assert floors[2]["frontZBandCount"] <= 3
    assert floors[2]["maxFrontXGap"] >= 44
    assert floors[3]["sideCount"] <= 2
    assert floors[3]["frontZBandCount"] <= 3
    assert floors[3]["maxFrontXGap"] >= 44
    assert all(row["allInside"] for row in floors.values())


def test_state_adapter_keeps_window_bays_sparse_and_top_view_readable():
    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const makeFloor = (floorId, windowCount, seatCount) => ({
          floor_id: floorId,
          windows: Array.from({ length: windowCount }, (_, id) => ({
            id: `f${floorId}-w${id}`,
            floor_id: floorId,
            queue_length: 0,
            is_open: true
          })),
          seats: Array.from({ length: seatCount }, (_, id) => ({
            id: `f${floorId}-s${id}`,
            floor_id: floorId,
            status: 'empty'
          })),
          students: []
        });

        const frame = new StateAdapter().buildFrame({
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              floors: [
                makeFloor(1, 6, 172),
                makeFloor(2, 13, 232),
                makeFloor(3, 14, 208)
              ]
            }
          }
        }, { activeCanteenId: 'minghu_xueyi' });

        const summary = frame.floors.map(floor => {
          const footprint = floor.footprint;
          const front = floor.windows.filter(win => (win.position.side || 'front') === 'front');
          const side = floor.windows.filter(win => win.position.side === 'left');
          const zRows = [...new Set(front.map(win => Math.round(win.position.z)))].sort((a, b) => a - b);
          const ratios = front.map(win => (win.position.x - footprint.minX) / footprint.width);
          return {
            floorId: floor.floor_id,
            sideCount: side.length,
            sideMinZ: side.length ? Math.min(...side.map(win => win.position.z)) : null,
            frontZRows: zRows,
            minFrontRatio: Math.min(...ratios),
            maxFrontRatio: Math.max(...ratios)
          };
        });
        console.log(JSON.stringify(summary));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    floor1, floor2, floor3 = json.loads(result.stdout)

    assert floor1["frontZRows"] == [16]
    assert floor2["sideCount"] <= 1
    assert floor3["sideCount"] <= 2
    assert floor3["sideMinZ"] >= 24
    assert len(floor2["frontZRows"]) <= 3
    assert len(floor3["frontZRows"]) <= 3
    assert all(0.22 <= floor["minFrontRatio"] <= floor["maxFrontRatio"] <= 0.84
               for floor in (floor1, floor2, floor3))


def test_canteen_scene_focus_top_view_keeps_oblique_floor_angle():
    s = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    for tok in (
        "FOCUS_TOP_OBLIQUE_Z_PADDING",
        "FOCUS_EXPANDED_OBLIQUE_Z_PADDING",
        "tilted floor window labels remain readable",
        "Math.max(FOCUS_TOP_CAMERA_Z, fp.maxZ + FOCUS_TOP_OBLIQUE_Z_PADDING)",
        "Math.max(FOCUS_EXPANDED_CAMERA_Z, fp.maxZ + FOCUS_EXPANDED_OBLIQUE_Z_PADDING)",
    ):
        assert tok in s, f"focused floor view should stay oblique instead of pure top-down: {tok!r}"


def test_immersive_ui_syncs_floorstrip_to_scene_focus_state():
    ui = (THREE_DIR / "immersive_ui.js").read_text(encoding="utf-8")
    scene = (THREE_DIR / "scene3d.js").read_text(encoding="utf-8")

    for tok in (
        "const mode = sceneApi?.getMode?.() || 'overview'",
        "const activeFloorId = sceneApi?.getFocusFloorId?.()",
        "allFloorBtn.classList.toggle('active', mode !== 'focus')",
        "btn.classList.toggle('active', mode === 'focus'",
    ):
        assert tok in ui, f"floorstrip sync missing token: {tok!r}"
    for tok in (
        "getMode()",
        "getFocusFloorId()",
        "syncImmersiveUI()",
        "sceneApi?.focusFloor?.(data.floorId)",
    ):
        assert tok in scene, f"scene focus sync missing token: {tok!r}"


def test_immersive_ui_exposes_multi_angle_view_presets():
    ui = (THREE_DIR / "immersive_ui.js").read_text(encoding="utf-8")
    scene = (THREE_DIR / "scene3d.js").read_text(encoding="utf-8")
    canteen = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")

    for tok in (
        "const viewPresets = [",
        "{ id: 'overview', label: '总览', title: '整栋斜俯视角' }",
        "{ id: 'front', label: '正面', title: '正面剖面视角' }",
        "{ id: 'side', label: '侧面', title: '侧向观察视角' }",
        "{ id: 'top', label: '俯视', title: '俯视平面视角' }",
        "{ id: 'free', label: '自由', title: '自由旋转视角' }",
        "this._sceneApi?.setViewPreset?.(preset.id)",
    ):
        assert tok in ui, f"immersive UI should expose multi-angle preset: {tok!r}"

    for tok in (
        "setViewPreset(id)",
        "canteenScene?.setViewPreset?.(id)",
    ):
        assert tok in scene, f"scene API should wire multi-angle presets: {tok!r}"

    for tok in (
        "setViewPreset(preset)",
        "this.viewPreset = preset",
        "_viewPresetTargets(",
        "case 'front':",
        "case 'side':",
        "case 'top':",
        "case 'free':",
    ):
        assert tok in canteen, f"canteen scene should implement multi-angle camera preset: {tok!r}"


def test_canteen_scene_focus_does_not_draw_unexplained_flow_line():
    s = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    assert "_flowPath" not in s
    assert "TubeGeometry(curve" not in s
    assert "CatmullRomCurve3(pts)" not in s


def test_canteen_scene_uses_real_minghu_photo_features():
    s = _canteen_scene_contract_source()
    for tok in (
        "photoWindowWall",
        "mixedChairPalette",
        "_addPhotoReferenceShell",
        "_addPhotoTableClusters",
        "_addServiceStall",
        "_addCeilingPipes",
        "_addMenuBoard",
        "woodTableTop",
    ):
        assert tok in s, f"missing Minghu real-photo feature token: {tok!r}"


def test_canteen_scene_avoids_glittery_ceiling_lamps():
    s = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    assert "photo pendant lamp" not in s
    assert "ConeGeometry(3.6, 6, 24)" not in s
    assert "emissive: 0xf1eee4" not in s
    assert "subtle ceiling rail" in s


def test_canteen_scene_uses_matte_service_window_effects():
    s = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    assert "emissiveIntensity: 0.12" not in s
    assert "emissiveIntensity: win.is_open ? 0.20 : 0.04" not in s

    queue_cap_start = s.index("'queue heat cap'")
    queue_cap_end = s.index("if (!win.is_open", queue_cap_start)
    queue_cap_block = s[queue_cap_start:queue_cap_end]
    assert "emissive:" not in queue_cap_block
    assert "emissiveIntensity" not in queue_cap_block


def test_canteen_scene_adds_stable_floor_depth_cues_without_shimmering_grids():
    s = _canteen_scene_contract_source()

    for tok in (
        "const FLOOR_EDGE_BAND_HEIGHT = 4.8;",
        "const FLOOR_EDGE_BAND_THICKNESS = 2.4;",
        "_floorEdgeBands(",
        "_addWallDepthCues(",
        "furnitureDerivedFootprint floor edge band",
        "building corner column",
        "wall top cap beam",
        "new THREE.BoxGeometry(length, FLOOR_EDGE_BAND_HEIGHT, FLOOR_EDGE_BAND_THICKNESS)",
    ):
        assert tok in s, f"floor/building depth cue missing: {tok!r}"

    assert "FLOOR_TILE_LINE_OPACITY" not in s
    assert "_subtleFloorTileLines(" not in s
    assert "furnitureDerivedFootprint floor tile line grid" not in s
    assert "new THREE.LineSegments(geometry, material)" not in s
    assert "depthWrite: false" in s
    assert "mesh.receiveShadow = false;" in s


def test_canteen_scene_uses_open_axonometric_layered_building_model():
    s = _canteen_scene_contract_source()

    for tok in (
        "const OVERVIEW_THREE_QUARTER_X_RATIO = 0.28;",
        "const OVERVIEW_THREE_QUARTER_MIN_X = 110;",
        "const OVERVIEW_THREE_QUARTER_Y_PADDING = 0;",
        "const OVERVIEW_THREE_QUARTER_Z_PADDING = 0;",
        "const OVERVIEW_THREE_QUARTER_HEIGHT_RATIO = 0.72;",
        "const OVERVIEW_THREE_QUARTER_DEPTH_RATIO = 0.72;",
        "const OVERVIEW_LOOK_PANEL_CLEARANCE_X_RATIO = 0.08;",
        "const FLOOR_SLAB_COLORS = [0xf0f4ee, 0xe3ece8];",
        "const OPEN_BUILDING_FRAME_OPACITY = 0.76;",
        "const FLOOR_BACK_WALL_OPACITY = 0.075;",
        "const FLOOR_SIDE_WALL_OPACITY = 0.035;",
        "const INTERFLOOR_SHADOW_OPACITY = 0.34;",
        "_addOpenBuildingFrame(",
        "_addOpenFloorFrame(",
        "open axonometric building corner column",
        "open axonometric rear floor beam",
        "open axonometric side depth beam",
        "open floor front vertical post",
        "open floor front edge beam",
        "open floor interlevel shadow band",
        "buildingFootprint.centerX + Math.max(OVERVIEW_THREE_QUARTER_MIN_X, buildingFootprint.width * OVERVIEW_THREE_QUARTER_X_RATIO)",
        "topY + Math.max(OVERVIEW_CAMERA_Y_PADDING + OVERVIEW_THREE_QUARTER_Y_PADDING, buildingFootprint.width * OVERVIEW_THREE_QUARTER_HEIGHT_RATIO)",
        "Math.max(OVERVIEW_CAMERA_Z, buildingFootprint.maxZ + 250) + Math.max(OVERVIEW_THREE_QUARTER_Z_PADDING, buildingFootprint.depth * OVERVIEW_THREE_QUARTER_DEPTH_RATIO)",
        "this._camTarget.look.set(buildingFootprint.centerX + buildingFootprint.width * OVERVIEW_LOOK_PANEL_CLEARANCE_X_RATIO, centerY, buildingFootprint.centerZ)",
        "if (this.mode === 'overview') {",
        "this._addOpenBuildingFrame(this.group, buildingFootprint, frame.floors, FLOOR_H);",
        "this._addOpenFloorFrame(fg, footprint, baseY, floor.floor_id);",
    ):
        assert tok in s, f"open axonometric building cue missing: {tok!r}"
    _assert_any_token(
        s,
        (
            "this._mat(0xbdebf2, FLOOR_BACK_WALL_OPACITY)",
            "meshMat(this.THREE, 0xbdebf2, FLOOR_BACK_WALL_OPACITY)",
        ),
        "open axonometric building cue missing: rear wall material",
    )
    _assert_any_token(
        s,
        (
            "this._mat(0xbdebf2, FLOOR_SIDE_WALL_OPACITY)",
            "meshMat(this.THREE, 0xbdebf2, FLOOR_SIDE_WALL_OPACITY)",
        ),
        "open axonometric building cue missing: side wall material",
    )

    assert "this._camTarget.pos.set(\n                buildingFootprint.centerX,\n                topY + OVERVIEW_CAMERA_Y_PADDING" not in s
    for tok in (
        "ROOF_CAP_HEIGHT",
        "_addBuildingShell(",
        "building exterior back wall shell",
        "building exterior side wall shell",
        "building roof cap slab",
        "BUILDING_SHELL_WALL_OPACITY",
        "BUILDING_SIDE_SHELL_WALL_OPACITY",
    ):
        assert tok not in s, f"open layered building should not use exterior shell/roof: {tok!r}"


def test_canteen_scene_uses_front_floor_gradient_display():
    s = _canteen_scene_contract_source()

    for tok in (
        "const OVERVIEW_FLOOR_GRADIENT_Z_OFFSETS = [48, 12, -24];",
        "const OVERVIEW_FLOOR_GRADIENT_OPACITY = [1.0, 0.64, 0.38];",
        "const DEFAULT_OVERVIEW_VIEW_PRESET = 'front';",
        "floor gradient display: 1F pulled forward, upper floors fade back",
        "this.viewPreset = DEFAULT_OVERVIEW_VIEW_PRESET;",
        "_floorGradientDisplay(floor)",
        "_floorGradientOpacityScale(floor)",
        "_applyFloorGradientMaterial(",
        "fg.position.z = gradient.zOffset;",
        "this._applyFloorGradientMaterial(backWall.material, floor);",
        "this._applyFloorGradientMaterial(leftWall.material, floor);",
        "this._applyFloorGradientMaterial(rightWall.material, floor);",
    ):
        assert tok in s, f"front floor gradient display missing token: {tok!r}"

    ui = (THREE_DIR / "immersive_ui.js").read_text(encoding="utf-8")
    assert "this._viewPreset = 'front';" in ui


def test_canteen_scene_stair_demo_follows_front_floor_gradient_offsets():
    s = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")

    for tok in (
        "stair core follows front floor gradient display",
        "_floorGradientZOffset(floor)",
        "_floorGradientZOffsetForFloorId(floorId)",
        "_floorSwitchGradientDelta(student, floorId)",
        "p.z + this._floorSwitchGradientDelta(student, floorId)",
        "const lowerZOffset = floorZOffset(lowerFloor);",
        "const upperZOffset = floorZOffset(upperFloor);",
        "lowerZOffset + t * (upperZOffset - lowerZOffset)",
        "baseZ + lowerZOffset + t * (upperZOffset - lowerZOffset)",
    ):
        assert tok in s, f"stair demo should share the floor gradient offset: {tok!r}"


def test_3d_visuals_keep_low_glare_lighting_contract():
    scene = (THREE_DIR / "scene3d.js").read_text(encoding="utf-8")
    fx = (THREE_DIR / "scene_fx.js").read_text(encoding="utf-8")
    canteen = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    css = (REPO_ROOT / "frontend" / "static" / "css" / "style.css").read_text(
        encoding="utf-8"
    )

    immersive_stage = css[css.index("body.twin-immersive #three-stage"):]
    immersive_stage = immersive_stage[:immersive_stage.index("/* --- 3.")]
    assert "radial-gradient" not in immersive_stage
    assert "radial glow" not in css

    for tok in (
        "renderer.toneMappingExposure = 0.90;",
        "const LOW_GLARE_BLOOM_STRENGTH = 0.12;",
        "const LOW_GLARE_BLOOM_RADIUS = 0.18;",
        "const LOW_GLARE_BLOOM_THRESHOLD = 0.96;",
    ):
        assert tok in fx, f"low-glare postprocessing token missing: {tok!r}"

    for tok in (
        "scene.background = new THREE.Color(0x0b1521)",
        "scene.fog = new THREE.Fog(0x0b1521, 680, 2600)",
        "new THREE.HemisphereLight(0xe6f3ef, 0x22364a, 1.38)",
        "new THREE.DirectionalLight(0xf0eee5, 1.24)",
        "new THREE.PointLight(0x54cfc7, 0.32, 520)",
    ):
        assert tok in scene, f"scene lighting should stay subdued: {tok!r}"

    for too_bright in (
        "emissiveIntensity: 0.35",
        "emissiveIntensity: 0.22",
        "emissiveIntensity: 0.45",
        "emissiveIntensity: 0.55",
        "emissiveIntensity: isTracked ? 0.55 : 0.08",
        "emissiveIntensity: 0.18",
        "this._mat(0x52d6d1, 0.55, 0x52d6d1, 0.14)",
    ):
        assert too_bright not in canteen, f"3D marker should not use high glare token: {too_bright!r}"


def test_canteen_scene_declutters_window_labels_and_slows_focus_transition():
    s = _canteen_scene_contract_source()

    for tok in (
        "const FOCUS_SIDE_DURATION_MS = 1600;",
        "const FOCUS_TOP_DURATION_MS = 1800;",
        "const FOCUS_EXPANDED_DURATION_MS = 1800;",
        "const CAM_LERP = 0.045;",
    ):
        assert tok in s, f"focus transition should be slow enough to read: {tok!r}"

    for tok in (
        "WINDOW_LABEL_MAX_CHARS",
        "WINDOW_LABEL_WORLD_WIDTH",
        "compactWindowLabel(",
        "_shouldShowWindowLabel(floor, win, localIndex)",
        "WINDOW_LABEL_DENSITY_STEP",
        "showWindowLabel",
        "if (showWindowLabel) {",
    ):
        assert tok in s, f"window labels should be decluttered: {tok!r}"

    assert "_addServiceStall(fg, win, floor.floor_id, winIdx, this._shouldShowWindowLabel(floor, win, winIdx))" in s
    assert "this.mode !== 'focus' || this.focusFloorId !== floor.floor_id" in s

    overview_rebuild = s[s.index("frame.floors.forEach(floor =>"):]
    assert "_addServiceStall(fg, win, floor.floor_id, winIdx);" not in overview_rebuild


def test_canteen_scene_window_labels_fit_readable_food_names():
    s = _canteen_scene_contract_source()

    for tok in (
        "const WINDOW_LABEL_MAX_CHARS = 6;",
        "const WINDOW_LABEL_LINE_MAX_CHARS = 4;",
        "const WINDOW_LABEL_WORLD_WIDTH = 48;",
        "const WINDOW_LABEL_WORLD_HEIGHT = 16;",
        "function windowLabelLines(text)",
        "const lines = Array.isArray(text) ? text : [String(text || '')];",
        "ctx.fillText(line, 160, lineY);",
        "windowLabelLines(this._windowLabel(win, floorId, localIndex))",
        "30,",
        "6.4,",
    ):
        assert tok in s, f"window text should stay readable in focus views: {tok!r}"


def test_canteen_scene_focus_window_labels_do_not_intersect_3d_menu_boards():
    s = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    menu_start = s.index("_addMenuBoard(group, text")
    menu_end = s.index("_addCeilingPipes", menu_start)
    menu_block = s[menu_start:menu_end]

    assert "if (!labelOptions.alwaysReadableWindowLabel) {" in menu_block
    assert "muted photo menu board" in menu_block
    assert "alwaysReadableWindowLabel" in menu_block


def test_canteen_scene_background_wall_panels_do_not_overlap_front_service_labels():
    s = _canteen_scene_contract_source()

    for token in (
        "const PHOTO_WALL_SIGN_COLOR = 0x18384a;",
        "generic dark photo wall signs are omitted from the service-window sightline",
        "fixed background photo service wall is omitted from the service-window sightline",
    ):
        assert token in s, f"background service wall panels should not sit behind labels: {token}"

    assert "photo off-white service wall" not in s
    assert "muted photo wall sign panel" not in s
    assert "muted photo wall notice panel" not in s
    assert "this._photoMat(PHOTO_WALL_SIGN_COLOR" not in s
    assert "photo red wall sign panel" not in s
    assert "photo red wall notice panel" not in s


def test_canteen_scene_focus_camera_keeps_side_and_top_angles_clear():
    s = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")

    for tok in (
        "const FOCUS_SIDE_MIN_DISTANCE = 240;",
        "const FOCUS_SIDE_Z_OFFSET_RATIO = 0.18;",
        "const FOCUS_TOP_MIN_HEIGHT = 300;",
        "const FOCUS_EXPANDED_MIN_HEIGHT = 430;",
        "_focusCameraTargets(footprint, y)",
        "Math.max(FOCUS_TOP_MIN_HEIGHT, FOCUS_TOP_CAMERA_Y_PADDING, footprint.width * 0.78",
        "Math.max(FOCUS_EXPANDED_MIN_HEIGHT, FOCUS_EXPANDED_CAMERA_Y_PADDING",
        "footprint.depth * 1.95",
        "const { sidePos, sideLook, topPos, topLook, expandedPos, expandedLook } =",
    ):
        assert tok in s, f"focus camera should keep side/top angles readable: {tok!r}"


def test_canteen_scene_uses_floor_specific_layout_profiles():
    s = _canteen_scene_contract_source()
    state_adapter = (THREE_DIR / "state_adapter.js").read_text(encoding="utf-8")
    for tok in (
        "MINGHU_FLOOR_LAYOUTS",
        "basicMealWideAisle",
        "featureFoodCourt",
        "restaurantDiningRoom",
        "_floorLayoutProfile",
        "_tablePositionForProfile",
        "_addFloorIdentityCues",
        "basicMealWideAisle central clear aisle",
        "basicMealWideAisle self service rice line",
        "featureFoodCourt coffee island",
        "featureFoodCourt hotpot zone",
        "restaurantDiningRoom booth seating",
        "restaurantDiningRoom service aisle",
    ):
        assert tok in s, f"missing floor-specific scene layout token: {tok!r}"
        if tok in ("MINGHU_FLOOR_LAYOUTS", "basicMealWideAisle",
                   "featureFoodCourt", "restaurantDiningRoom"):
            assert tok in state_adapter, \
                f"state adapter must mirror floor layout profile token: {tok!r}"


def test_canteen_scene_uses_real_minghu_window_food_labels():
    s = _canteen_scene_contract_source()
    for tok in (
        "MINGHU_WINDOW_LABELS",
        "_windowLabel",
        "小份菜",
        "麻辣香锅",
        "西北刀削面",
        "煲仔饭",
        "旋转小火锅",
        "重庆面庄",
    ):
        assert tok in s, f"missing real Minghu window-label token: {tok!r}"
    for bad in ("清汤锅底 / 番茄锅底", "微机室"):
        assert bad not in s, f"photo wall sign must not be used as a canteen window name: {bad!r}"


def test_canteen_scene_preserves_mixed_chair_colors_when_seated():
    s = _canteen_scene_contract_source()
    assert "occupied ? PALETTE.seatOccupied : color" not in s
    assert "chairOccupancyMarker" in s
    assert "mixedChairPalette" in s


def test_table_layout_preserves_backend_seats_but_caps_visual_tables():
    scene = _canteen_scene_contract_source()
    adapter = (THREE_DIR / "state_adapter.js").read_text(encoding="utf-8")

    assert "visibleTableCountForProfile" in scene
    assert "visibleTableCountForProfile" in adapter
    assert "profile.visibleTableCount" in scene
    assert "profile.visibleTableCount" in adapter
    assert "furnitureDerivedFootprint" in adapter
    assert "floor.footprint" in adapter
    assert "_floorFootprint(" in scene
    assert ".slice(0, 96)" not in adapter

    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const seats = Array.from({ length: 272 }, (_, id) => ({
          id,
          floor_id: 2,
          status: 'empty'
        }));
        const snapshot = {
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              display_name: '明湖学一',
              floors: [{
                floor_id: 2,
                windows: [],
                seats,
                students: []
              }]
            }
          }
        };

        const frame = new StateAdapter()
          .buildFrame(snapshot, { activeCanteenId: 'minghu_xueyi' });
        const floor = frame.floors[0];
        const uniquePositions = new Set(
          floor.seats.map(seat => `${Math.round(seat.position.x)}:${Math.round(seat.position.z)}`)
        );
        const xs = floor.seats.map(seat => seat.position.x);
        const zs = floor.seats.map(seat => seat.position.z);
        console.log(JSON.stringify({
          seatCount: floor.seats.length,
          lastSeatId: floor.seats[floor.seats.length - 1].id,
          uniquePositionCount: uniquePositions.size,
          footprint: floor.footprint,
          bounds: {
            minX: Math.min(...xs),
            maxX: Math.max(...xs),
            minZ: Math.min(...zs),
            maxZ: Math.max(...zs)
          }
        }));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)

    assert payload["seatCount"] == 272
    assert payload["lastSeatId"] == 271
    assert 228 <= payload["uniquePositionCount"] <= 236
    assert payload["footprint"]["source"] == "furnitureDerivedFootprint"
    assert len(payload["footprint"]["outline"]) == 4
    assert payload["footprint"]["width"] / payload["footprint"]["depth"] <= 1.85
    assert payload["bounds"]["minX"] >= payload["footprint"]["minX"] + 16
    assert payload["bounds"]["maxX"] <= payload["footprint"]["maxX"] - 16
    assert payload["bounds"]["minZ"] >= payload["footprint"]["minZ"] + 16
    assert payload["bounds"]["maxZ"] <= payload["footprint"]["maxZ"] - 16


def test_table_layout_uses_fuller_representative_table_counts_per_floor():
    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const makeFloor = (floorId, seatCount) => ({
          floor_id: floorId,
          windows: [],
          seats: Array.from({ length: seatCount }, (_, id) => ({
            id: `f${floorId}-s${id}`,
            floor_id: floorId,
            status: 'empty'
          })),
          students: []
        });

        const frame = new StateAdapter().buildFrame({
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              floors: [
                makeFloor(1, 172),
                makeFloor(2, 272),
                makeFloor(3, 290)
              ]
            }
          }
        }, { activeCanteenId: 'minghu_xueyi' });

        const summary = frame.floors.map(floor => {
          const uniquePositions = new Set(
            floor.seats.map(seat => `${Math.round(seat.position.x)}:${Math.round(seat.position.z)}`)
          );
          return {
            floorId: floor.floor_id,
            seatCount: floor.seats.length,
            visualTableCount: uniquePositions.size / 4,
            footprint: floor.footprint
          };
        });
        console.log(JSON.stringify(summary));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    floors = {row["floorId"]: row for row in json.loads(result.stdout)}

    assert floors[1]["seatCount"] == 172
    assert floors[2]["seatCount"] == 272
    assert floors[3]["seatCount"] == 290
    assert floors[1]["visualTableCount"] == 43
    assert floors[2]["visualTableCount"] == 58
    assert floors[3]["visualTableCount"] == 52
    assert len({(row["footprint"]["width"], row["footprint"]["depth"])
                for row in floors.values()}) == 3
    assert all(row["footprint"]["width"] / row["footprint"]["depth"] <= 1.85
               for row in floors.values())


def test_table_layout_is_block_based_not_uniform_table_grid():
    adapter = (THREE_DIR / "state_adapter.js").read_text(encoding="utf-8")
    scene = _canteen_scene_contract_source()
    for tok in (
        "tableBlocks",
        "tableBlockPosition",
        "mainAisleWidth",
        "queueBufferDepth",
        "f1-left-square-island",
        "f2-foodcourt-center-island",
        "f3-wall-booth-run",
    ):
        assert tok in adapter, f"state adapter should use block-based table layout: {tok!r}"
        assert tok in scene, f"scene renderer should mirror block-based table layout: {tok!r}"

    assert "Math.floor(idx / 4) % visibleTableCount" not in scene

    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const makeFloor = (floorId, seatCount) => ({
          floor_id: floorId,
          windows: [],
          seats: Array.from({ length: seatCount }, (_, id) => ({
            id: `f${floorId}-s${id}`,
            floor_id: floorId,
            status: 'empty'
          })),
          students: []
        });

        const frame = new StateAdapter().buildFrame({
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              floors: [
                makeFloor(1, 172),
                makeFloor(2, 272),
                makeFloor(3, 290)
              ]
            }
          }
        }, { activeCanteenId: 'minghu_xueyi' });

        const summary = frame.floors.map(floor => {
          const centersByTable = [];
          const visualTables = new Map();
          floor.seats.forEach((seat, idx) => {
            const tableIdx = Math.floor(idx / 4) % (floor.floor_id === 1 ? 42 : floor.floor_id === 2 ? 58 : 52);
            if (!visualTables.has(tableIdx)) visualTables.set(tableIdx, []);
            visualTables.get(tableIdx).push(seat.position);
          });
          for (const positions of visualTables.values()) {
            centersByTable.push({
              x: Math.round(positions.reduce((sum, pos) => sum + pos.x, 0) / positions.length),
              z: Math.round(positions.reduce((sum, pos) => sum + pos.z, 0) / positions.length),
            });
          }
          const uniqueX = [...new Set(centersByTable.map(pos => pos.x))].sort((a, b) => a - b);
          const uniqueZ = [...new Set(centersByTable.map(pos => pos.z))].sort((a, b) => a - b);
          return {
            floorId: floor.floor_id,
            visualTableCount: centersByTable.length,
            uniqueXCount: uniqueX.length,
            uniqueZCount: uniqueZ.length,
            xSpan: Math.max(...uniqueX) - Math.min(...uniqueX),
            zSpan: Math.max(...uniqueZ) - Math.min(...uniqueZ),
            maxXGap: Math.max(...uniqueX.slice(1).map((x, idx) => x - uniqueX[idx])),
            maxZGap: Math.max(...uniqueZ.slice(1).map((z, idx) => z - uniqueZ[idx])),
          };
        });
        console.log(JSON.stringify(summary));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    floors = {row["floorId"]: row for row in json.loads(result.stdout)}

    assert floors[1]["visualTableCount"] == 42
    assert floors[2]["visualTableCount"] == 58
    assert floors[3]["visualTableCount"] == 52
    assert floors[1]["uniqueXCount"] >= 7
    assert floors[2]["uniqueXCount"] >= 8
    assert floors[3]["uniqueXCount"] >= 7
    assert floors[1]["maxXGap"] >= 58
    assert floors[2]["maxXGap"] >= 58
    assert floors[3]["maxZGap"] >= 28
    assert len({(floors[f]["xSpan"], floors[f]["zSpan"]) for f in floors}) == 3


def test_table_layout_uses_denser_perimeter_fill_without_losing_aisles():
    adapter = (THREE_DIR / "state_adapter.js").read_text(encoding="utf-8")
    scene = _canteen_scene_contract_source()
    for tok in (
        "f1-rear-fill-tables",
        "f2-rear-flex-fill",
        "f3-right-window-booth-run",
    ):
        assert tok in adapter, f"state adapter should fill large unused dining pockets: {tok!r}"
        assert tok in scene, f"scene renderer should mirror dense dining pockets: {tok!r}"

    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const expectedCounts = { 1: 43, 2: 58, 3: 52 };
        const makeFloor = (floorId, seatCount) => ({
          floor_id: floorId,
          windows: [],
          seats: Array.from({ length: seatCount }, (_, id) => ({
            id: `f${floorId}-s${id}`,
            floor_id: floorId,
            status: 'empty'
          })),
          students: []
        });

        const frame = new StateAdapter().buildFrame({
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              floors: [
                makeFloor(1, 172),
                makeFloor(2, 272),
                makeFloor(3, 290)
              ]
            }
          }
        }, { activeCanteenId: 'minghu_xueyi' });

        const summary = frame.floors.map(floor => {
          const tableCount = expectedCounts[floor.floor_id];
          const centers = [];
          for (let tableIdx = 0; tableIdx < tableCount; tableIdx += 1) {
            const seats = floor.seats.filter((_, idx) => Math.floor(idx / 4) % tableCount === tableIdx);
            centers.push({
              x: Math.round(seats.reduce((sum, seat) => sum + seat.position.x, 0) / seats.length),
              z: Math.round(seats.reduce((sum, seat) => sum + seat.position.z, 0) / seats.length),
            });
          }
          const uniqueX = [...new Set(centers.map(pos => pos.x))].sort((a, b) => a - b);
          const uniqueZ = [...new Set(centers.map(pos => pos.z))].sort((a, b) => a - b);
          const xSpan = Math.max(...uniqueX) - Math.min(...uniqueX);
          const zSpan = Math.max(...uniqueZ) - Math.min(...uniqueZ);
          return {
            floorId: floor.floor_id,
            visualTableCount: centers.length,
            footprintArea: floor.footprint.width * floor.footprint.depth,
            tableCoverageRatio: (xSpan * zSpan) / (floor.footprint.width * floor.footprint.depth),
            maxXGap: Math.max(...uniqueX.slice(1).map((x, idx) => x - uniqueX[idx])),
            maxZGap: Math.max(...uniqueZ.slice(1).map((z, idx) => z - uniqueZ[idx])),
          };
        });
        console.log(JSON.stringify(summary));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    floors = {row["floorId"]: row for row in json.loads(result.stdout)}

    assert floors[1]["visualTableCount"] == 43
    assert floors[2]["visualTableCount"] == 58
    assert floors[3]["visualTableCount"] == 52
    assert floors[1]["tableCoverageRatio"] >= 0.49
    assert floors[2]["tableCoverageRatio"] >= 0.43
    assert floors[3]["tableCoverageRatio"] >= 0.43
    assert floors[1]["maxXGap"] >= 52
    assert floors[2]["maxXGap"] >= 52
    assert floors[3]["maxXGap"] <= 110
    assert floors[3]["maxZGap"] >= 28


def test_table_layout_keeps_dining_islands_compact_instead_of_scattered():
    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const expectedCounts = { 1: 43, 2: 58, 3: 52 };
        const makeFloor = (floorId, seatCount, windowCount) => ({
          floor_id: floorId,
          windows: Array.from({ length: windowCount }, (_, id) => ({
            id: `f${floorId}-w${id}`,
            floor_id: floorId,
            is_open: true,
            queue_length: 0
          })),
          seats: Array.from({ length: seatCount }, (_, id) => ({
            id: `f${floorId}-s${id}`,
            floor_id: floorId,
            status: 'empty'
          })),
          students: []
        });

        const frame = new StateAdapter().buildFrame({
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              floors: [
                makeFloor(1, 172, 6),
                makeFloor(2, 272, 13),
                makeFloor(3, 290, 14)
              ]
            }
          }
        }, { activeCanteenId: 'minghu_xueyi' });

        const summary = frame.floors.map(floor => {
          const tableCount = expectedCounts[floor.floor_id];
          const centers = [];
          for (let tableIdx = 0; tableIdx < tableCount; tableIdx += 1) {
            const seats = floor.seats.filter(
              (_, idx) => Math.floor(idx / 4) % tableCount === tableIdx
            );
            centers.push({
              x: seats.reduce((sum, seat) => sum + seat.position.x, 0) / seats.length,
              z: seats.reduce((sum, seat) => sum + seat.position.z, 0) / seats.length,
            });
          }
          const xs = centers.map(pos => pos.x);
          const zs = centers.map(pos => pos.z);
          const uniqueX = [...new Set(xs.map(x => Math.round(x)))].sort((a, b) => a - b);
          const uniqueZ = [...new Set(zs.map(z => Math.round(z)))].sort((a, b) => a - b);
          return {
            floorId: floor.floor_id,
            xSpan: Math.max(...xs) - Math.min(...xs),
            zSpan: Math.max(...zs) - Math.min(...zs),
            maxXGap: Math.max(...uniqueX.slice(1).map((x, idx) => x - uniqueX[idx])),
            maxZGap: Math.max(...uniqueZ.slice(1).map((z, idx) => z - uniqueZ[idx])),
            rearGapRatio: (
              Math.max(...zs) - centers
                .filter(pos => pos.z < Math.max(...zs) - 1)
                .reduce((max, pos) => Math.max(max, pos.z), 0)
            ) / floor.footprint.depth,
          };
        });
        console.log(JSON.stringify(summary));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    floors = {row["floorId"]: row for row in json.loads(result.stdout)}

    assert floors[1]["xSpan"] <= 455
    assert floors[2]["xSpan"] <= 490
    assert floors[3]["xSpan"] <= 500
    assert floors[1]["maxXGap"] <= 80
    assert floors[2]["maxXGap"] <= 80
    assert floors[3]["maxXGap"] <= 70
    assert floors[3]["maxZGap"] <= 32
    assert floors[3]["rearGapRatio"] <= 0.08


def test_table_layout_uses_subtle_color_coding_for_table_zones():
    adapter = (THREE_DIR / "state_adapter.js").read_text(encoding="utf-8")
    scene = _canteen_scene_contract_source()

    for tok in (
        "tableColor",
        "_tableColorForProfile",
        "block?.tableColor",
        "f3-east-mid-square-infill",
    ):
        assert tok in adapter or tok in scene

    assert scene.count("tableColor") >= 8
    assert "const FLOOR_TABLE_COLOR_FALLBACKS" in scene


def test_table_layout_groups_tables_into_zones_with_clear_aisles():
    adapter = (THREE_DIR / "state_adapter.js").read_text(encoding="utf-8")
    scene = _canteen_scene_contract_source()
    for tok in (
        "TABLE_ZONE_AISLE_X",
        "TABLE_ROW_AISLE_Z",
        "tableZonePosition",
    ):
        assert tok in adapter, f"state adapter should expose zoned table layout token: {tok!r}"
        assert tok in scene, f"scene renderer should mirror zoned table layout token: {tok!r}"

    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const seats = Array.from({ length: 84 }, (_, id) => ({
          id,
          floor_id: 2,
          status: 'empty'
        }));
        const snapshot = {
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              display_name: '明湖学一',
              floors: [{
                floor_id: 2,
                windows: [],
                seats,
                students: []
              }]
            }
          }
        };

        const floor = new StateAdapter()
          .buildFrame(snapshot, { activeCanteenId: 'minghu_xueyi' })
          .floors[0];
        const centers = [];
        for (let i = 0; i < floor.seats.length; i += 4) {
          const group = floor.seats.slice(i, i + 4);
          centers.push({
            x: Math.round(group.reduce((sum, seat) => sum + seat.position.x, 0) / group.length),
            z: Math.round(group.reduce((sum, seat) => sum + seat.position.z, 0) / group.length),
          });
        }
        const uniqueXs = [...new Set(centers.map(center => center.x))].sort((a, b) => a - b);
        const uniqueZs = [...new Set(centers.map(center => center.z))].sort((a, b) => a - b);
        const xGaps = uniqueXs.slice(1).map((x, idx) => x - uniqueXs[idx]);
        const zGaps = uniqueZs.slice(1).map((z, idx) => z - uniqueZs[idx]);
        console.log(JSON.stringify({
          tableCount: centers.length,
          uniqueXs,
          uniqueZs,
          maxXGap: Math.max(...xGaps),
          maxZGap: Math.max(...zGaps),
        }));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)

    assert payload["tableCount"] == 21
    assert payload["maxXGap"] >= 52
    assert payload["maxZGap"] >= 24


def test_state_adapter_separates_service_windows_from_table_chair_zones():
    adapter = (THREE_DIR / "state_adapter.js").read_text(encoding="utf-8")
    scene = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    for tok in (
        "TABLE_WINDOW_GAP_Z",
        "serviceWindowMaxZ",
        "tableZoneStartZ",
    ):
        assert tok in adapter, f"state adapter should derive table zone after service windows: {tok!r}"
        assert tok in scene, f"scene table rendering should mirror service/window separation: {tok!r}"

    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const makeFloor = (floorId, windowCount, seatCount) => ({
          floor_id: floorId,
          windows: Array.from({ length: windowCount }, (_, id) => ({
            id: `f${floorId}-w${id}`,
            is_open: true,
            queue_length: 0
          })),
          seats: Array.from({ length: seatCount }, (_, id) => ({
            id: `f${floorId}-s${id}`,
            status: 'empty'
          })),
          students: []
        });

        const frame = new StateAdapter().buildFrame({
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              floors: [
                makeFloor(1, 6, 172),
                makeFloor(2, 13, 272),
                makeFloor(3, 14, 290)
              ]
            }
          }
        }, { activeCanteenId: 'minghu_xueyi' });

        const summary = frame.floors.map(floor => {
          const tableZs = floor.seats.map(seat => seat.position.z);
          const windowZs = floor.windows.map(win => win.position.z);
          const tableCells = new Set(floor.seats.map(seat =>
            `${Math.round(seat.position.x / 4)}:${Math.round(seat.position.z / 4)}`
          ));
          const windowCells = new Set(floor.windows.map(win =>
            `${Math.round(win.position.x / 4)}:${Math.round(win.position.z / 4)}`
          ));
          const overlap = [...windowCells].filter(cell => tableCells.has(cell));
          return {
            floorId: floor.floor_id,
            tableMinZ: Math.min(...tableZs),
            tableMaxZ: Math.max(...tableZs),
            windowMaxZ: Math.max(...windowZs),
            footprintMaxZ: floor.footprint.maxZ,
            overlap,
          };
        });
        console.log(JSON.stringify(summary));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    floors = json.loads(result.stdout)

    assert len(floors) == 3
    for floor in floors:
        assert floor["overlap"] == []
        assert floor["tableMinZ"] - floor["windowMaxZ"] >= 42
        assert floor["tableMaxZ"] <= floor["footprintMaxZ"] - 16


def test_state_adapter_reserves_peak_queue_buffer_before_table_zones():
    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const students = Array.from({ length: 36 }, (_, id) => ({
          id: `queue-student-${id}`,
          floor_id: 1,
          position: 'window_queue',
          position_detail: 'w0',
          queue_index: id
        }));
        const snapshot = {
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              floors: [{
                floor_id: 1,
                windows: [{ id: 'w0', is_open: true, queue_length: students.length }],
                seats: Array.from({ length: 172 }, (_, id) => ({
                  id: `s${id}`,
                  status: 'empty'
                })),
                students
              }]
            }
          }
        };

        const floor = new StateAdapter()
          .buildFrame(snapshot, { activeCanteenId: 'minghu_xueyi' })
          .floors[0];
        const tableMinZ = Math.min(...floor.seats.map(seat => seat.position.z));
        const queueZs = floor.students.map(student => student.target.z);
        const windowMaxZ = Math.max(...floor.windows.map(win => win.position.z));
        console.log(JSON.stringify({
          tableMinZ,
          queueMinZ: Math.min(...queueZs),
          queueMaxZ: Math.max(...queueZs),
          queueSpreadZ: Math.max(...queueZs) - Math.min(...queueZs),
          windowMaxZ,
        }));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)

    assert payload["tableMinZ"] - payload["windowMaxZ"] >= 72
    assert payload["queueMinZ"] > payload["windowMaxZ"]
    assert payload["queueSpreadZ"] >= 52
    assert payload["queueMaxZ"] <= payload["tableMinZ"] - 6


def test_state_adapter_derives_distinct_floor_footprints_from_tables_and_windows():
    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const makeFloor = (floorId, windowCount, seatCount) => ({
          floor_id: floorId,
          windows: Array.from({ length: windowCount }, (_, id) => ({
            id: `f${floorId}-w${id}`,
            is_open: true,
            queue_length: 0
          })),
          seats: Array.from({ length: seatCount }, (_, id) => ({
            id: `f${floorId}-s${id}`,
            status: 'empty'
          })),
          students: []
        });

        const frame = new StateAdapter().buildFrame({
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              floors: [
                makeFloor(1, 6, 172),
                makeFloor(2, 13, 272),
                makeFloor(3, 14, 290)
              ]
            }
          }
        }, { activeCanteenId: 'minghu_xueyi' });

        console.log(JSON.stringify(frame.floors.map(floor => floor.footprint)));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    footprints = json.loads(result.stdout)

    assert len(footprints) == 3
    assert all(fp["source"] == "furnitureDerivedFootprint" for fp in footprints)
    assert all(len(fp["outline"]) >= 4 for fp in footprints)
    assert all(fp["width"] / fp["depth"] <= 1.85 for fp in footprints)
    assert len({(fp["width"], fp["depth"]) for fp in footprints}) == 3
    assert footprints[1]["width"] >= footprints[0]["width"]
    assert footprints[2]["depth"] >= footprints[0]["depth"]


def test_state_adapter_emits_rectangular_floor_outlines_for_each_floor():
    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const makeFloor = (floorId, windowCount, seatCount) => ({
          floor_id: floorId,
          windows: Array.from({ length: windowCount }, (_, id) => ({
            id: `f${floorId}-w${id}`,
            floor_id: floorId,
            is_open: true,
            queue_length: 0
          })),
          seats: Array.from({ length: seatCount }, (_, id) => ({
            id: `f${floorId}-s${id}`,
            floor_id: floorId,
            status: 'empty'
          })),
          students: []
        });

        const frame = new StateAdapter().buildFrame({
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              floors: [
                makeFloor(1, 6, 172),
                makeFloor(2, 13, 272),
                makeFloor(3, 14, 290)
              ]
            }
          }
        }, { activeCanteenId: 'minghu_xueyi' });

        console.log(JSON.stringify(frame.floors.map(floor => ({
          floorId: floor.floor_id,
          outline: floor.footprint.outline,
          minX: floor.footprint.minX,
          maxX: floor.footprint.maxX,
          minZ: floor.footprint.minZ,
          maxZ: floor.footprint.maxZ
        }))));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    floors = json.loads(result.stdout)

    for floor in floors:
        assert floor["outline"] == [
            {"x": floor["minX"], "z": floor["minZ"]},
            {"x": floor["maxX"], "z": floor["minZ"]},
            {"x": floor["maxX"], "z": floor["maxZ"]},
            {"x": floor["minX"], "z": floor["maxZ"]},
        ]


def test_minghu_window_layouts_use_floor_specific_spacing():
    adapter = (THREE_DIR / "state_adapter.js").read_text(encoding="utf-8")
    for tok in ("windowX0", "windowSpan", "windowRowOffset", "minWindowGap"):
        assert tok in adapter, f"window profile should expose {tok!r}"

    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const makeWindows = n => Array.from({ length: n }, (_, id) => ({
          id: `w${id}`,
          floor_id: 1,
          is_open: true,
          queue_length: 0
        }));
        const makeSeats = n => Array.from({ length: n }, (_, id) => ({
          id: `s${id}`,
          floor_id: 1,
          status: 'empty'
        }));
        const snapshot = {
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              floors: [
                { floor_id: 1, windows: makeWindows(6), seats: makeSeats(172), students: [] },
                { floor_id: 2, windows: makeWindows(13), seats: makeSeats(232), students: [] },
                { floor_id: 3, windows: makeWindows(14), seats: makeSeats(208), students: [] }
              ]
            }
          }
        };

        const floors = new StateAdapter()
          .buildFrame(snapshot, { activeCanteenId: 'minghu_xueyi' })
          .floors;
        const summarize = floor => ({
          zRows: [...new Set(floor.windows.map(w => Math.round(w.position.z)))],
          xs: floor.windows.map(w => Math.round(w.position.x)),
          minSameRowGap: (() => {
            const gaps = floor.windows.reduce((acc, win, idx, arr) => {
            const sameRow = arr
              .filter(other => Math.round(other.position.z) === Math.round(win.position.z))
              .map(other => other.position.x)
              .sort((a, b) => a - b);
              sameRow.slice(1).forEach((x, i) => acc.push(x - sameRow[i]));
              return acc;
            }, []);
            return gaps.length ? Math.min(...gaps) : 999;
          })()
        });
        console.log(JSON.stringify(floors.map(summarize)));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    floor1, floor2, floor3 = json.loads(result.stdout)

    assert len(floor1["zRows"]) == 1
    assert 2 <= len(floor2["zRows"]) <= 3
    assert 2 <= len(floor3["zRows"]) <= 5
    assert floor2["minSameRowGap"] >= 28
    assert floor3["minSameRowGap"] >= 33.9
    assert floor2["xs"] != floor3["xs"]


def test_third_floor_hotpot_window_uses_side_wall_layout():
    adapter = (THREE_DIR / "state_adapter.js").read_text(encoding="utf-8")
    scene = _canteen_scene_contract_source()

    for tok in (
        "sideWindowCount",
        "sideWindowX",
        "sideWindowZ0",
        "sideWindowGap",
        "sideWall service counter window",
        "sideWall red stall menu fascia",
    ):
        assert tok in adapter + scene, f"missing side-window layout token: {tok!r}"
    assert "['旋转小火锅', '东北麻辣烫'" in scene

    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const windows = Array.from({ length: 14 }, (_, id) => ({
          id: `w${id}`,
          floor_id: 3,
          is_open: true,
          queue_length: 0
        }));
        const snapshot = {
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              floors: [{ floor_id: 3, windows, seats: [], students: [] }]
            }
          }
        };
        const floor = new StateAdapter()
          .buildFrame(snapshot, { activeCanteenId: 'minghu_xueyi' })
          .floors[0];
        console.log(JSON.stringify({
          footprint: floor.footprint,
          windows: floor.windows.map(w => ({
            x: Math.round(w.position.x),
            z: Math.round(w.position.z),
            side: w.position.side || 'front'
          }))
        }));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)
    windows = payload["windows"]

    assert windows[0]["side"] == "left"
    assert windows[1]["side"] == "left"
    assert windows[0]["x"] <= payload["footprint"]["minX"] + 24
    assert windows[1]["x"] <= payload["footprint"]["minX"] + 24
    assert windows[1]["z"] - windows[0]["z"] >= 24
    assert all(win["side"] == "front" for win in windows[2:])


def test_third_floor_side_windows_do_not_overlap_front_stalls():
    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const windows = Array.from({ length: 14 }, (_, id) => ({
          id,
          floor_id: 3,
          is_open: true,
          queue_length: 0
        }));
        const seats = Array.from({ length: 290 }, (_, id) => ({
          id,
          floor_id: 3,
          status: 'empty'
        }));
        const floor = new StateAdapter().buildFrame({
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              floors: [{ floor_id: 3, windows, seats, students: [] }]
            }
          }
        }, { activeCanteenId: 'minghu_xueyi' }).floors[0];

        const footprint = floor.footprint;
        const boxes = floor.windows.map(win => {
          const side = win.position.side || 'front';
          const halfW = side === 'left' ? 6 : 9;
          const halfD = side === 'left' ? 9 : 6;
          return {
            id: win.id,
            side,
            x: win.position.x,
            minX: win.position.x - halfW,
            maxX: win.position.x + halfW,
            minZ: win.position.z - halfD,
            maxZ: win.position.z + halfD
          };
        });
        const overlaps = [];
        for (let i = 0; i < boxes.length; i += 1) {
          for (let j = i + 1; j < boxes.length; j += 1) {
            const a = boxes[i];
            const b = boxes[j];
            const intersects = a.minX < b.maxX && a.maxX > b.minX
              && a.minZ < b.maxZ && a.maxZ > b.minZ;
            if (intersects) overlaps.push([a.id, b.id]);
          }
        }
        console.log(JSON.stringify({
          footprint,
          leftWindows: boxes.filter(box => box.side === 'left'),
          overlaps
        }));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)

    assert payload["overlaps"] == []
    assert all(
        win["x"] <= payload["footprint"]["minX"] + 24
        for win in payload["leftWindows"]
    )


def test_canteen_scene_uses_mixed_table_and_chair_geometries():
    s = _canteen_scene_contract_source()
    for tok in (
        "_tableVariantForProfile",
        "addSquareTableCluster",
        "addLongTableCluster",
        "addBoothTableCluster",
        "square four-seat table",
        "long communal table",
        "booth table",
        "booth bench seat",
        "chairVariant",
    ):
        assert tok in s, f"missing mixed table/chair geometry token: {tok!r}"


def test_canteen_scene_does_not_render_non_data_flashing_table_decorations():
    s = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    for tok in (
        "photo flower basket",
        "photo flower leaves",
        "idx % 5 === 0",
    ):
        assert tok not in s, f"table decoration is not backed by simulation data: {tok!r}"


def test_intervention_ui_hooks_preserved_after_restyle():
    s = (THREE_DIR / "intervention_ui.js").read_text(encoding="utf-8")
    for tok in ("three-ops-console", "ops-grid", "ops-win", "ops-log",
                "twin-congestion-legend",
                "/campus/canteens/", "/windows/", "/toggle"):
        assert tok in s, f"intervention hook lost: {tok!r}"
    # 玻璃观感类（CSS 由 style.css 提供，这里只需结构 className 仍可被样式命中）
    assert "ops-kpi" in s


def test_intervention_window_buttons_show_open_and_close_actions():
    s = (THREE_DIR / "intervention_ui.js").read_text(encoding="utf-8")
    assert "const windowsForDisplay = [...floor.windows].sort" in s
    assert "Number(a.is_open) - Number(b.is_open)" in s
    assert "ops-add-window" in s
    assert "添加窗口" in s
    assert "/floors/${floorId}/windows/add" in s
    assert "this._addWindow(floor.floor_id)" in s
    assert "const actionLabel = isOpen ? '关' : '开';" in s
    assert "const actionLabel = isOpen ? '关' : '增开';" not in s
    assert "btn.textContent = `${actionLabel}${win.id}`;" in s
    assert "const act = this._actionLabel(ev.action);" in s


def test_canteen_scene_animates_window_intervention_events():
    s = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    for tok in (
        "WINDOW_INTERVENTION_EFFECT_MS",
        "_syncWindowInterventionEffects(frame);",
        "_animateWindowInterventions();",
        "_windowInterventionEffects",
        "_seenInterventionKeys",
        "event.action === 'add' || event.action === 'open'",
        "_addWindowInterventionPulse(",
        "windowInterventionPulse",
        "windowInterventionBody",
    ):
        assert tok in s, f"window intervention animation hook missing: {tok!r}"


def test_3d_ops_console_exposes_finish_simulation_control():
    intervention = (THREE_DIR / "intervention_ui.js").read_text(encoding="utf-8")
    scene = (THREE_DIR / "scene3d.js").read_text(encoding="utf-8")
    main = (REPO_ROOT / "frontend" / "static" / "js" / "main.js").read_text(
        encoding="utf-8"
    )

    for tok in ("ops-run-controls", "ops-finish-btn", "结束仿真", "结算中..."):
        assert tok in intervention, f"3D finish control missing token: {tok!r}"
    assert "this.onFinish" in intervention
    assert "interventionUI.onFinish" in scene
    assert "lastAppState?.onFinishSimulation?.()" in scene
    assert "async function finishSimulation()" in main
    assert "onFinishSimulation: finishSimulation" in main


def test_immersive_ui_module_contract():
    s = (THREE_DIR / "immersive_ui.js").read_text(encoding="utf-8")
    assert "export class ImmersiveUI" in s
    for tok in ("twin-topbar", "twin-toolbar", "twin-floorstrip",
                "twin-status", "data-render", "data-page"):
        assert tok in s, f"immersive_ui missing {tok!r}"
    assert "mount(" in s and "dispose(" in s


def test_immersive_ui_places_minghu_brand_at_top_left():
    ui = (THREE_DIR / "immersive_ui.js").read_text(encoding="utf-8")
    css = (REPO_ROOT / "frontend" / "static" / "css" / "style.css").read_text(encoding="utf-8")

    for tok in (
        "this._brandEl = null;",
        "brand.textContent = '明湖食堂';",
        "brand.setAttribute('aria-label', '明湖食堂标识');",
        "this._brandEl.textContent = this._canteenBrandLabel(frame.displayName);",
        "_canteenBrandLabel(name)",
    ):
        assert tok in ui, f"immersive UI should keep Minghu brand in the top-left overlay: {tok!r}"

    for tok in (
        "body.twin-immersive .twin-topbar-brand",
        "margin-right: auto;",
        "letter-spacing: 0;",
    ):
        assert tok in css, f"top-left Minghu brand styling missing token: {tok!r}"


def test_index_loads_new_three_modules_and_scene3d_wires_immersive():
    html = (Path(__file__).resolve().parents[1] / "frontend/templates/index.html").read_text(encoding="utf-8")
    assert "js/three/scene_fx.js" in html
    assert "js/three/immersive_ui.js" in html
    import re
    s = (THREE_DIR / "scene3d.js").read_text(encoding="utf-8")
    assert "ImmersiveUI" in s and "immersiveUI" in s
    # frame 仅在 renderCanteen() 内由 stateAdapter.buildFrame() 产生 →
    # immersiveUI.update(frame, ...) 必须在 renderCanteen() 内调用，不能在 render()
    rc = re.search(r"function renderCanteen\([^)]*\)\s*\{.*?\n\}", s, re.S)
    assert rc and "immersiveUI.update(" in rc.group(0), \
        "immersiveUI.update(frame, sceneApi) must be inside renderCanteen() (frame scope)"


def test_minghu_1f_layout_sample_is_dense_and_semantically_truthful():
    adapter = (THREE_DIR / "state_adapter.js").read_text(encoding="utf-8")
    scene = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")

    required_tokens = (
        "f1-front-service-band",
        "f1-left-four-seat-island",
        "f1-lower-left-fill-tables",
        "f1-central-dining-island",
        "f1-right-long-table-zone",
        "f1-rear-booth-fill",
        "f1-snake-queue-guide",
        "f1-pickup-return-lane",
        "f1-main-aisle-cue",
        "f1-condiment-station",
        "f1-tray-return-point",
    )
    for tok in required_tokens:
        assert tok in adapter or tok in scene, f"missing 1F layout token: {tok!r}"

    forbidden_tokens = (
        "f1-added-window",
        "f1-fake-window",
        "addedWindowCount",
        "fabricatedWindow",
    )
    for tok in forbidden_tokens:
        assert tok not in adapter
        assert tok not in scene

    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const floor = {
          floor_id: 1,
          windows: Array.from({ length: 6 }, (_, id) => ({
            id: `f1-w${id}`,
            floor_id: 1,
            is_open: true,
            queue_length: id % 2
          })),
          seats: Array.from({ length: 172 }, (_, id) => ({
            id: `f1-s${id}`,
            floor_id: 1,
            status: 'empty'
          })),
          students: []
        };
        const frame = new StateAdapter().buildFrame({
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              display_name: '明湖',
              floors: [floor]
            }
          }
        }, { activeCanteenId: 'minghu_xueyi' });

        const f = frame.floors[0];
        const windowXs = f.windows.map(w => Math.round(w.position.x)).sort((a, b) => a - b);
        const tableCenters = [];
        for (let tableIdx = 0; tableIdx < 43; tableIdx += 1) {
          const seats = f.seats.filter((_, idx) => Math.floor(idx / 4) % 43 === tableIdx);
          tableCenters.push({
            x: Math.round(seats.reduce((sum, seat) => sum + seat.position.x, 0) / seats.length),
            z: Math.round(seats.reduce((sum, seat) => sum + seat.position.z, 0) / seats.length),
          });
        }
        const uniqueX = [...new Set(tableCenters.map(pos => pos.x))].sort((a, b) => a - b);
        const uniqueZ = [...new Set(tableCenters.map(pos => pos.z))].sort((a, b) => a - b);
        console.log(JSON.stringify({
          windowCount: f.windows.length,
          allWindowsOpen: f.windows.every(w => w.is_open === true),
          windowSides: [...new Set(f.windows.map(w => w.position.side))],
          windowSpan: Math.max(...windowXs) - Math.min(...windowXs),
          visualTableCount: tableCenters.length,
          uniqueXCount: uniqueX.length,
          uniqueZCount: uniqueZ.length,
          tableCoverageRatio:
            ((Math.max(...uniqueX) - Math.min(...uniqueX)) *
             (Math.max(...uniqueZ) - Math.min(...uniqueZ))) /
            (f.footprint.width * f.footprint.depth),
          minTableZ: Math.min(...tableCenters.map(pos => pos.z)),
          maxWindowZ: Math.max(...f.windows.map(w => w.position.z)),
          footprint: f.footprint
        }));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)

    assert payload["windowCount"] == 6
    assert payload["allWindowsOpen"] is True
    assert payload["windowSides"] == ["front"]
    assert payload["windowSpan"] >= 220
    assert payload["visualTableCount"] == 43
    assert payload["uniqueXCount"] >= 8
    assert payload["uniqueZCount"] >= 6
    assert payload["tableCoverageRatio"] >= 0.48
    assert payload["minTableZ"] >= payload["maxWindowZ"] + 70
    assert payload["footprint"]["source"] == "furnitureDerivedFootprint"
    assert payload["footprint"]["width"] / payload["footprint"]["depth"] <= 1.85


def test_canteen_scene_1f_identity_cues_resolve_floor_footprint_before_use():
    scene = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    start = scene.index("_addFloorIdentityCues(group, floor, baseY)")
    end = scene.index("if (profile.key === 'featureFoodCourt')", start)
    function_head = scene[start:end]

    assert "const footprint = this._floorFootprint(floor);" in function_head
    assert (
        function_head.index("const footprint = this._floorFootprint(floor);")
        < function_head.index("f1-snake-queue-guide")
    )


def test_canteen_scene_1f_utility_cues_are_flat_not_solid_residual_blocks():
    scene = _canteen_scene_contract_source()

    for tok in (
        "f1-condiment-station flat floor cue",
        "f1-tray-return-point flat floor cue",
        "first-floor utility cues should read as floor markings, not leftover blocks",
    ):
        assert tok in scene, f"1F utility cue should be flat/subtle: {tok!r}"

    for old_block in (
        "this._box(group, 'f1-condiment-station', [28, 4.2, 9]",
        "this._box(group, 'f1-tray-return-point', [32, 4.6, 10]",
    ):
        assert old_block not in scene, f"1F utility cue still renders as a residual block: {old_block!r}"


def test_minghu_1f_visual_tables_have_clear_non_overlapping_footprints():
    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const floor = {
          floor_id: 1,
          windows: Array.from({ length: 6 }, (_, id) => ({
            id: `f1-w${id}`,
            floor_id: 1,
            is_open: true,
            queue_length: 0
          })),
          seats: Array.from({ length: 172 }, (_, id) => ({
            id: `f1-s${id}`,
            floor_id: 1,
            status: 'empty'
          })),
          students: []
        };
        const frame = new StateAdapter().buildFrame({
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              display_name: '明湖',
              floors: [floor]
            }
          }
        }, { activeCanteenId: 'minghu_xueyi' });

        const f = frame.floors[0];
        const dimsForTable = tableIdx => {
          if (tableIdx >= 37) return { width: 30, depth: 22, zone: 'booth' };
          if (tableIdx >= 31) return { width: 34, depth: 21, zone: 'right-long' };
          if (tableIdx >= 17) return { width: 30, depth: 20, zone: 'center' };
          if (tableIdx >= 12) return { width: 30, depth: 20, zone: 'lower-left' };
          return { width: 30, depth: 20, zone: 'left' };
        };
        const tables = [];
        for (let tableIdx = 0; tableIdx < 43; tableIdx += 1) {
          const seats = f.seats.filter((_, idx) => Math.floor(idx / 4) % 43 === tableIdx);
          tables.push({
            tableIdx,
            x: seats.reduce((sum, seat) => sum + seat.position.x, 0) / seats.length,
            z: seats.reduce((sum, seat) => sum + seat.position.z, 0) / seats.length,
            ...dimsForTable(tableIdx),
          });
        }

        const overlaps = [];
        for (let i = 0; i < tables.length; i += 1) {
          for (let j = i + 1; j < tables.length; j += 1) {
            const a = tables[i];
            const b = tables[j];
            const overlapX = Math.abs(a.x - b.x) < (a.width + b.width) / 2 + 2;
            const overlapZ = Math.abs(a.z - b.z) < (a.depth + b.depth) / 2 + 2;
            if (overlapX && overlapZ) {
              overlaps.push({
                a: a.tableIdx,
                b: b.tableIdx,
                azone: a.zone,
                bzone: b.zone,
                dx: Math.round(Math.abs(a.x - b.x)),
                dz: Math.round(Math.abs(a.z - b.z)),
              });
            }
          }
        }

        console.log(JSON.stringify({ overlaps, tables }));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)

    assert payload["overlaps"] == []


def test_minghu_1f_tables_fill_lower_corners_without_crossing_floor_edge():
    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const floor = {
          floor_id: 1,
          windows: Array.from({ length: 6 }, (_, id) => ({
            id: `f1-w${id}`,
            floor_id: 1,
            is_open: true,
            queue_length: 0
          })),
          seats: Array.from({ length: 172 }, (_, id) => ({
            id: `f1-s${id}`,
            floor_id: 1,
            status: 'empty'
          })),
          students: []
        };
        const frame = new StateAdapter().buildFrame({
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              display_name: '明湖',
              floors: [floor]
            }
          }
        }, { activeCanteenId: 'minghu_xueyi' });

        const f = frame.floors[0];
        const visibleTableCount = Math.ceil(f.seats.length / 4);
        const tables = [];
        for (let tableIdx = 0; tableIdx < visibleTableCount; tableIdx += 1) {
          const seats = f.seats.filter((_, idx) => Math.floor(idx / 4) % visibleTableCount === tableIdx);
          tables.push({
            tableIdx,
            x: seats.reduce((sum, seat) => sum + seat.position.x, 0) / seats.length,
            z: seats.reduce((sum, seat) => sum + seat.position.z, 0) / seats.length,
          });
        }

        const rightFloorMaxZ = f.footprint.outline[2].z;
        const lowerLeft = tables.filter(table => (
          table.x < f.footprint.centerX - 90
          && table.z > f.footprint.centerZ + 45
        ));
        const lowerRight = tables.filter(table => (
          table.x > f.footprint.centerX + 90
          && table.z > f.footprint.centerZ + 70
          && table.z <= rightFloorMaxZ - 4
        ));
        const rightOvershoot = tables.filter(table => (
          table.x > f.footprint.centerX
          && table.z > rightFloorMaxZ - 4
        ));

        console.log(JSON.stringify({
          lowerLeft: lowerLeft.map(t => t.tableIdx),
          lowerRight: lowerRight.map(t => t.tableIdx),
          rightOvershoot: rightOvershoot.map(t => t.tableIdx),
          rightFloorMaxZ,
          tables,
        }));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)

    assert len(payload["lowerLeft"]) >= 5
    assert len(payload["lowerRight"]) >= 6
    assert payload["rightOvershoot"] == []


def test_minghu_1f_tables_balance_center_zone_and_right_rear_density():
    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const floor = {
          floor_id: 1,
          windows: Array.from({ length: 6 }, (_, id) => ({
            id: `f1-w${id}`,
            floor_id: 1,
            is_open: true,
            queue_length: 0
          })),
          seats: Array.from({ length: 172 }, (_, id) => ({
            id: `f1-s${id}`,
            floor_id: 1,
            status: 'empty'
          })),
          students: []
        };
        const frame = new StateAdapter().buildFrame({
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              display_name: '明湖',
              floors: [floor]
            }
          }
        }, { activeCanteenId: 'minghu_xueyi' });

        const f = frame.floors[0];
        const visibleTableCount = Math.ceil(f.seats.length / 4);
        const tables = [];
        for (let tableIdx = 0; tableIdx < visibleTableCount; tableIdx += 1) {
          const seats = f.seats.filter((_, idx) => Math.floor(idx / 4) % visibleTableCount === tableIdx);
          tables.push({
            tableIdx,
            x: seats.reduce((sum, seat) => sum + seat.position.x, 0) / seats.length,
            z: seats.reduce((sum, seat) => sum + seat.position.z, 0) / seats.length,
          });
        }

        const centerReadable = tables.filter(table => (
          table.x >= f.footprint.centerX - 70
          && table.x <= f.footprint.centerX + 80
          && table.z >= f.footprint.centerZ - 35
          && table.z <= f.footprint.centerZ + 70
        ));
        const rightRearDense = tables.filter(table => (
          table.x > f.footprint.centerX + 110
          && table.z > f.footprint.centerZ + 55
        ));

        console.log(JSON.stringify({
          centerReadable: centerReadable.map(t => t.tableIdx),
          rightRearDense: rightRearDense.map(t => t.tableIdx),
          tables,
        }));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)

    assert len(payload["centerReadable"]) >= 8
    assert len(payload["rightRearDense"]) <= 6


def test_minghu_2f_3f_tables_reduce_rear_strips_and_keep_center_weight():
    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const floorConfigs = [
          { floorId: 2, seatCount: 272, windowCount: 13, tableCount: 58 },
          { floorId: 3, seatCount: 290, windowCount: 14, tableCount: 52 },
        ];
        const frame = new StateAdapter().buildFrame({
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              display_name: '明湖',
              floors: floorConfigs.map(config => ({
                floor_id: config.floorId,
                windows: Array.from({ length: config.windowCount }, (_, id) => ({
                  id: `f${config.floorId}-w${id}`,
                  floor_id: config.floorId,
                  is_open: true,
                  queue_length: 0
                })),
                seats: Array.from({ length: config.seatCount }, (_, id) => ({
                  id: `f${config.floorId}-s${id}`,
                  floor_id: config.floorId,
                  status: 'empty'
                })),
                students: []
              }))
            }
          }
        }, { activeCanteenId: 'minghu_xueyi' });

        const summary = frame.floors.map(floor => {
          const config = floorConfigs.find(item => item.floorId === floor.floor_id);
          const tables = [];
          for (let tableIdx = 0; tableIdx < config.tableCount; tableIdx += 1) {
            const seats = floor.seats.filter((_, idx) => Math.floor(idx / 4) % config.tableCount === tableIdx);
            tables.push({
              tableIdx,
              x: seats.reduce((sum, seat) => sum + seat.position.x, 0) / seats.length,
              z: seats.reduce((sum, seat) => sum + seat.position.z, 0) / seats.length,
            });
          }
          const centerWeighted = tables.filter(table => (
            table.x >= floor.footprint.centerX - 95
            && table.x <= floor.footprint.centerX + 115
            && table.z >= floor.footprint.centerZ - 55
            && table.z <= floor.footprint.centerZ + 95
          ));
          const rearStrip = tables.filter(table => (
            table.z > floor.footprint.centerZ + 92
          ));

          return {
            floorId: floor.floor_id,
            centerWeighted: centerWeighted.map(t => t.tableIdx),
            rearStrip: rearStrip.map(t => t.tableIdx),
            footprint: floor.footprint,
            tables,
          };
        });
        console.log(JSON.stringify(summary));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    floors = {row["floorId"]: row for row in json.loads(result.stdout)}

    assert len(floors[2]["centerWeighted"]) >= 18
    assert len(floors[3]["centerWeighted"]) >= 16
    assert len(floors[2]["rearStrip"]) <= 8
    assert len(floors[3]["rearStrip"]) <= 8


def test_canteen_scene_front_service_windows_are_large_enough_for_1f_focus_view():
    scene = _canteen_scene_contract_source()

    for token in (
        "FRONT_WINDOW_COUNTER_SIZE",
        "FRONT_WINDOW_GLASS_GUARD_SIZE",
        "FRONT_WINDOW_STATUS_RAIL_SIZE",
        "FRONT_WINDOW_MENU_BOARD_WIDTH",
        "FRONT_WINDOW_MENU_BOARD_HEIGHT",
    ):
        assert token in scene, f"front service window should use named scale token: {token}"

    import re

    def const_array(name):
        match = re.search(rf"const {name} = \[([^\]]+)\];", scene)
        assert match, f"missing {name}"
        return [float(part.strip()) for part in match.group(1).split(",")]

    counter = const_array("FRONT_WINDOW_COUNTER_SIZE")
    guard = const_array("FRONT_WINDOW_GLASS_GUARD_SIZE")
    rail = const_array("FRONT_WINDOW_STATUS_RAIL_SIZE")

    assert counter[0] >= 24 and 3.8 <= counter[1] <= 4.8 and 5.8 <= counter[2] <= 7.2
    assert guard[0] >= 24 and guard[1] <= 3
    assert rail[0] <= 14 and rail[1] <= 1.2 and rail[2] <= 1.0
    assert "FRONT_WINDOW_MENU_BOARD_WIDTH = 42" in scene
    assert "FRONT_WINDOW_MENU_BOARD_HEIGHT = 8.8" in scene


def test_canteen_scene_front_windows_do_not_render_large_red_serving_blocks():
    scene = _canteen_scene_contract_source()

    for token in (
        "const FRONT_WINDOW_STATUS_RAIL_IDLE_COLOR = 0x6f8790;",
        "const FRONT_WINDOW_STATUS_RAIL_SERVING_COLOR = 0x5eead4;",
        "const FRONT_WINDOW_SERVING_LIGHT_COLOR = 0x5eead4;",
        "const FRONT_WINDOW_SERVING_LIGHT_SIZE = [9, 1.4, 1.0];",
        "front service status rail",
        "front service serving status light",
    ):
        assert token in scene, f"front serving state should use a small status cue: {token}"
    _assert_any_token(
        scene,
        ("this._photoMat(frontStatusRailColor", "photoMat(this.THREE, frontStatusRailColor"),
        "front serving state should use a small status cue: status rail material",
    )
    _assert_any_token(
        scene,
        (
            "this._photoMat(FRONT_WINDOW_SERVING_LIGHT_COLOR",
            "photoMat(this.THREE, FRONT_WINDOW_SERVING_LIGHT_COLOR",
        ),
        "front serving state should use a small status cue: serving light material",
    )

    assert "'red stall menu fascia'" not in scene


def test_front_window_status_cue_does_not_render_as_dark_residual_block():
    scene = _canteen_scene_contract_source()

    for token in (
        "const FRONT_WINDOW_STATUS_RAIL_SIZE = [12, 1.1, 0.8];",
        "front service status rail",
        "front window status cue should stay thin, not become a dark block under menu labels",
    ):
        assert token in scene, f"front window status cue should be a thin rail: {token}"

    for old_block in (
        "FRONT_WINDOW_FASCIA_SIZE",
        "'front service menu fascia'",
        "FRONT_WINDOW_FASCIA_IDLE_COLOR",
        "FRONT_WINDOW_FASCIA_SERVING_COLOR",
    ):
        assert old_block not in scene, f"front window still has residual block token: {old_block}"


def test_front_service_windows_restore_light_counters_without_dark_residual_blocks():
    scene = _canteen_scene_contract_source()

    for token in (
        "const FRONT_WINDOW_COUNTER_SIZE = [24, 4.2, 6.2];",
        "photo service counter window",
        "front service counters are visible but light, not the dark residual under window labels",
        "body.userData.photoCue = 'counter';",
    ):
        assert token in scene, f"front service counter should be restored: {token}"

    for old_block in (
        "FRONT_WINDOW_SILL_SIZE",
        "front service sill line",
        "front service windows should use flat sill lines, not gray cuboid counters",
    ):
        assert old_block not in scene, f"front service window should not stay flattened: {old_block}"


def test_window_labels_do_not_draw_dark_backplate_blocks():
    scene = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")

    for token in (
        "if (!options.alwaysReadableWindowLabel) {",
        "window labels should render as stroked text, not dark rectangular blocks",
        "ctx.strokeText(line, 160, lineY);",
    ):
        assert token in scene, f"window label backplate should be removed: {token}"

    label_start = scene.index("_label(text, x, y, z")
    label_end_candidates = [
        idx for idx in (
            scene.find("_photoMat(color", label_start),
            scene.find("_floorSlabOpacity", label_start),
        )
        if idx >= 0
    ]
    label_end = min(label_end_candidates)
    label_block = scene[label_start:label_end]
    assert "ctx.roundRect?.(4, 4, 312, bgHeight, 10);" in label_block
    assert (
        label_block.index("if (!options.alwaysReadableWindowLabel) {")
        < label_block.index("ctx.roundRect?.(4, 4, 312, bgHeight, 10);")
    )


def test_canteen_scene_front_window_queue_heat_uses_thin_strip_not_red_cap():
    scene = _canteen_scene_contract_source()

    for token in (
        "const FRONT_WINDOW_QUEUE_HEAT_STRIP_SIZE = [18, 0.9, 1.1];",
        "const FRONT_WINDOW_QUEUE_HEAT_STRIP_OPACITY = 0.50;",
        "const FRONT_WINDOW_QUEUE_HEAT_CLEAR_COLOR = 0x2dd4bf;",
        "const FRONT_WINDOW_QUEUE_HEAT_BUSY_COLOR = 0x9ed7c5;",
        "front service queue heat strip",
        "FRONT_WINDOW_QUEUE_HEAT_STRIP_SIZE",
        "FRONT_WINDOW_QUEUE_HEAT_STRIP_OPACITY",
        "frontQueueHeatColor",
    ):
        assert token in scene, f"front queue heat should be a restrained strip: {token}"

    assert "[FRONT_WINDOW_COUNTER_SIZE[0], 2.4, FRONT_WINDOW_COUNTER_SIZE[2]]" not in scene


def test_canteen_scene_served_students_do_not_create_red_window_blocks():
    scene = _canteen_scene_contract_source()

    assert "const STUDENT_SERVING_STATUS_COLOR = 0x5eead4;" in scene
    assert "if (student.position === 'being_served') return STUDENT_SERVING_STATUS_COLOR;" in scene
    assert "if (student.position === 'being_served') return PALETTE.windowOpen;" not in scene


def test_minghu_1f_front_windows_have_readable_even_spacing():
    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const floor = {
          floor_id: 1,
          windows: Array.from({ length: 6 }, (_, id) => ({
            id: `f1-w${id}`,
            floor_id: 1,
            is_open: true,
            queue_length: 0
          })),
          seats: Array.from({ length: 172 }, (_, id) => ({
            id: `f1-s${id}`,
            floor_id: 1,
            status: 'empty'
          })),
          students: []
        };
        const frame = new StateAdapter().buildFrame({
          canteens: {
            minghu_xueyi: {
              id: 'minghu_xueyi',
              display_name: '明湖',
              floors: [floor]
            }
          }
        }, { activeCanteenId: 'minghu_xueyi' });

        const xs = frame.floors[0].windows
          .map(win => win.position.x)
          .sort((a, b) => a - b);
        const gaps = xs.slice(1).map((x, idx) => x - xs[idx]);
        console.log(JSON.stringify({
          xs,
          gaps,
          minGap: Math.min(...gaps),
          maxGap: Math.max(...gaps),
        }));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)

    assert payload["minGap"] >= 54
    assert payload["maxGap"] - payload["minGap"] <= 14


def test_minghu_1f_added_windows_do_not_overlap_service_counters():
    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';

        const makeFloor = (windowCount) => ({
          floor_id: 1,
          windows: Array.from({ length: windowCount }, (_, id) => ({
            id: `f1-w${id}`,
            floor_id: 1,
            is_open: true,
            queue_length: 0
          })),
          seats: Array.from({ length: 172 }, (_, id) => ({
            id: `f1-s${id}`,
            floor_id: 1,
            status: 'empty'
          })),
          students: []
        });

        const rows = [7, 8, 10].map(windowCount => {
          const frame = new StateAdapter().buildFrame({
            canteens: {
              minghu_xueyi: {
                id: 'minghu_xueyi',
                display_name: '明湖',
                floors: [makeFloor(windowCount)]
              }
            }
          }, { activeCanteenId: 'minghu_xueyi' });
          const floor = frame.floors[0];
          const xs = floor.windows
            .filter(win => (win.position.side || 'front') === 'front')
            .map(win => win.position.x)
            .sort((a, b) => a - b);
          const gaps = xs.slice(1).map((x, idx) => x - xs[idx]);
          return {
            windowCount,
            xs,
            minGap: Math.min(...gaps),
            maxGap: Math.max(...gaps),
            allInside: floor.windows.every(win => (
              win.position.x >= floor.footprint.minX + 32
              && win.position.x <= floor.footprint.maxX - 32
            )),
          };
        });
        console.log(JSON.stringify(rows));
        """
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    rows = json.loads(result.stdout)

    assert all(row["allInside"] for row in rows)
    assert all(row["minGap"] >= 43.9 for row in rows)


def test_canteen_scene_front_window_labels_are_centered_on_their_windows():
    scene = _canteen_scene_contract_source()

    for token in (
        "const FRONT_WINDOW_LABEL_X_OFFSET = 0;",
        "const FRONT_WINDOW_LABEL_Y_OFFSET = 20.4;",
        "const FRONT_WINDOW_LABEL_Z_OFFSET = -13.2;",
        "x + FRONT_WINDOW_LABEL_X_OFFSET",
        "y + FRONT_WINDOW_LABEL_Y_OFFSET",
        "z + FRONT_WINDOW_LABEL_Z_OFFSET",
    ):
        assert token in scene, f"front window labels should align to window centers: {token}"

    assert "localIndex % 2 === 0 ? -6.5 : 6.5" not in scene


def test_canteen_scene_top_view_is_zoomed_for_readable_floor_detail():
    scene = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")

    for token in (
        "const VIEW_PRESET_TOP_HEIGHT = 380;",
        "const VIEW_PRESET_TOP_Z_OFFSET = 18;",
        "focusFloor ? footprint.width * 0.78 : topY + buildingFootprint.width * 0.68",
        "footprint.depth * 1.22",
    ):
        assert token in scene, f"top preset should frame the floor closer: {token}"


def test_canteen_scene_window_label_texture_uses_high_resolution_no_mipmap():
    scene = _canteen_scene_contract_source()

    for token in (
        "const LABEL_TEXTURE_SCALE = 3;",
        "const LABEL_CANVAS_WIDTH = 320;",
        "canvas.width = LABEL_CANVAS_WIDTH * LABEL_TEXTURE_SCALE;",
        "ctx.scale(LABEL_TEXTURE_SCALE, LABEL_TEXTURE_SCALE);",
        "texture.generateMipmaps = false;",
        "texture.minFilter = this.THREE.LinearFilter;",
        "texture.magFilter = this.THREE.LinearFilter;",
        "texture.needsUpdate = true;",
    ):
        assert token in scene, f"window labels should render from a sharp texture: {token}"


def test_canteen_scene_focus_floor_avoids_alpha_flicker_layers():
    scene = _canteen_scene_contract_source()

    for token in (
        "const FOCUS_FLOOR_SLAB_OPACITY = 1.0;",
        "transparent: opacity < 0.98",
        "depthWrite: opacity >= 0.98",
        "if (this.mode === 'overview') {",
        "this._addOpenBuildingFrame(this.group, buildingFootprint, frame.floors, FLOOR_H);",
    ):
        assert token in scene, f"focused floor should not retain flickering overview alpha layers: {token}"


def test_service_stall_is_four_part_with_per_floor_theme():
    """Spec §A: each window renders signboard band + open-kitchen glass +
    base counter + tray rail/status strip, themed per floor, and keeps the
    intervention/label contract hooks."""
    scene = _canteen_scene_contract_source()

    # 4-part stall structure tokens (front and side share the vocabulary)
    for tok in (
        "stall signboard band",
        "stall open-kitchen glass",
        "stall base counter",
        "stall tray rail",
        "stall status strip",
    ):
        assert tok in scene, f"missing stall structure token: {tok!r}"

    # Per-floor theme table keyed by floor id (1 steel / 2 wood+brass / 3 dark wood)
    assert "STALL_THEME" in scene
    theme_source = _optional_three_source("canteen_layouts.js") or scene
    for fid in ("1:", "2:", "3:"):
        assert fid in theme_source.split("STALL_THEME", 1)[1][:600], \
            f"STALL_THEME missing floor key {fid!r}"

    # Contract hooks preserved
    assert "kind: 'window'" in scene
    assert "_tagWindowInterventionBody(" in scene
    assert "_addWindowInterventionPulse(" in scene
    assert "alwaysReadableWindowLabel" in scene
    assert "WINDOW_LABEL_RENDER_ORDER" in scene

    # No fabricated windows ever
    for forbidden in ("f1-added-window", "f1-fake-window",
                      "addedWindowCount", "fabricatedWindow"):
        assert forbidden not in scene


def test_side_service_stall_shares_four_part_structure():
    scene = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    left = scene.split("if (layoutSide === 'left')", 1)[1].split("return;", 1)[0]
    for tok in ("stall signboard band", "stall open-kitchen glass",
                "stall base counter", "stall status strip"):
        assert tok in left, f"side stall missing {tok!r}"
    assert "kind: 'window'" in left


def test_table_blocks_are_regularized_grids_inside_footprint():
    """Spec §B: per block, rows/cols are evenly spaced (single dz step,
    single dx step), all tables inside footprint, and the 3 floors stay
    distinct. Cue tokens still emitted by canteen_scene."""
    scene = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    for cue in ("f1-snake-queue-guide", "f1-pickup-return-lane",
                "f1-main-aisle-cue", "f1-condiment-station",
                "f1-tray-return-point"):
        assert cue in scene, f"cue token dropped: {cue!r}"

    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';
        function floor(fid, nseat) {
          return { floor_id: fid,
            windows: Array.from({length:6},(_,i)=>({id:`f${fid}-w${i}`,floor_id:fid,is_open:true})),
            seats: Array.from({length:nseat},(_,i)=>({id:`f${fid}-s${i}`,floor_id:fid,status:'empty'})),
            students: [] };
        }
        const adapter = new StateAdapter();
        const out = {};
        for (const [fid, ns] of [[1,172],[2,232],[3,208]]) {
          const frame = adapter.buildFrame(
            { canteens: { minghu_xueyi: { id:'minghu_xueyi', display_name:'明湖',
              floors:[floor(fid, ns)] } } },
            { activeCanteenId:'minghu_xueyi' });
          const f = frame.floors[0];
          const xs = f.seats.map(s=>Math.round(s.position.x));
          const zs = f.seats.map(s=>Math.round(s.position.z));
          out[fid] = {
            inFootprint: f.seats.every(s =>
              s.position.x >= f.footprint.minX - 1 &&
              s.position.x <= f.footprint.maxX + 1 &&
              s.position.z >= f.footprint.minZ - 1 &&
              s.position.z <= f.footprint.maxZ + 1),
            minZ: Math.min(...zs),
            maxWinZ: Math.max(...f.windows.map(w=>w.position.z)),
            uniqX: new Set(xs).size,
            uniqZ: new Set(zs).size,
            sig: xs.slice(0,8).join(',')+'|'+zs.slice(0,8).join(','),
          };
        }
        console.log(JSON.stringify(out));
        """
    )
    payload = json.loads(subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT, check=True, text=True, capture_output=True).stdout)

    for fid in ("1", "2", "3"):
        assert payload[fid]["inFootprint"] is True, f"floor {fid} overflows footprint"
        # tables start clearly behind the service/queue band
        assert payload[fid]["minZ"] >= payload[fid]["maxWinZ"] + 60, fid
        # a real grid: several distinct rows and columns
        assert payload[fid]["uniqX"] >= 6 and payload[fid]["uniqZ"] >= 5, fid
    # floors are not identical layouts
    assert len({payload["1"]["sig"], payload["2"]["sig"], payload["3"]["sig"]}) == 3


def test_student_paths_avoid_furniture_and_avatars_face_travel():
    scene = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    assert "studentAvatar" in scene
    # avatar orients along travel direction — assert avatar-SCOPED so the red is
    # meaningful (unrelated rotation.y/lookAt elsewhere must not satisfy it).
    avatar_src = scene.split("_studentAvatar(", 1)[1][:4000]
    assert "atan2" in avatar_src, "avatar must derive facing via Math.atan2(dx,dz)"

    script = textwrap.dedent(
        """
        import { StateAdapter } from './frontend/static/js/three/state_adapter.js';
        const adapter = new StateAdapter();
        // Recognized snapshot states only (no invented window_id/seat_id keys;
        // p2 is a brand-new arrival → entering path).
        const students = [
          { id:'p1', floor_id:1, position:'window_queue' },
          { id:'p2', floor_id:1 },
          { id:'p3', floor_id:1, position:'seated' },
        ];
        const frame = adapter.buildFrame(
          { canteens: { minghu_xueyi: { id:'minghu_xueyi', display_name:'明湖',
            floors:[{ floor_id:1,
              windows:Array.from({length:6},(_,i)=>({id:`f1-w${i}`,floor_id:1,is_open:true})),
              seats:Array.from({length:172},(_,i)=>({id:`f1-s${i}`,floor_id:1,status:'empty'})),
              students }] } } },
          { activeCanteenId:'minghu_xueyi' });
        const f = frame.floors[0];
        // Spec §C real invariant: routing must produce REACHABLE in-hall
        // destinations (no cutting through/over walls), and any settled
        // interior student stays inside the slab. A brand-new arrival is
        // correctly spawned at the side gate just OUTSIDE the slab edge
        // (separately locked by test_state_adapter_marks_new_student_entry_path_from_gate
        // and test_state_adapter_new_students_start_at_nearest_side_entrance),
        // so the entering spawn point is intentionally NOT required in-footprint.
        const pts = [];
        for (const s of f.students) {
          if (s.target) pts.push(s.target);                       // routed reachable destination
          if (s.position3d && s.is_entering !== true) pts.push(s.position3d);
        }
        const inFoot = pts.every(p =>
          p.x >= f.footprint.minX - 2 && p.x <= f.footprint.maxX + 2 &&
          p.z >= f.footprint.minZ - 2 && p.z <= f.footprint.maxZ + 2);
        console.log(JSON.stringify({ count: pts.length, inFoot }));
        """
    )
    payload = json.loads(subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT, check=True, text=True, capture_output=True).stdout)
    assert payload["count"] > 0
    assert payload["inFoot"] is True


def test_canteen_layouts_js_exists_and_exports():
    """canteen_layouts.js must exist and export the layout contract surface."""
    path = THREE_DIR / "canteen_layouts.js"
    assert path.exists(), "canteen_layouts.js not found"
    s = path.read_text(encoding="utf-8")
    for symbol in (
        "export const PALETTE",
        "export const MINGHU_FLOOR_LAYOUTS",
        "export const MINGHU_WINDOW_LABELS",
        "export function defaultFootprint",
        "export function normalizedFootprint",
        "export function tableBlockPosition",
        "export function stallTheme",
        "export const STALL_THEME",
    ):
        assert symbol in s, f"missing export: {symbol!r}"


def test_canteen_furniture_js_exists_and_exports():
    """canteen_furniture.js must exist and export the primitive builders."""
    path = THREE_DIR / "canteen_furniture.js"
    assert path.exists(), "canteen_furniture.js not found"
    s = path.read_text(encoding="utf-8")
    for symbol in (
        "export function meshMat",
        "export function photoMat",
        "export function addBox",
        "export function addChair",
        "export function addSquareTableCluster",
        "export function addLongTableCluster",
        "export function addBoothTableCluster",
        "export function heatColor",
    ):
        assert symbol in s, f"missing export: {symbol!r}"


def test_canteen_scene_still_exports_canteen_scene_class():
    """Split modules must preserve CanteenScene and keep tick() rebuild-free."""
    s = (THREE_DIR / "canteen_scene.js").read_text(encoding="utf-8")
    assert "export class CanteenScene" in s
    tick_def = "    tick() {"
    assert tick_def in s, f"method definition {tick_def!r} not found"
    tick_start = s.index(tick_def)
    tick_end = s.index("\n    }", tick_start)
    tick_body = s[tick_start:tick_end]
    assert "_rebuild" not in tick_body, "tick() must not call _rebuild directly"
