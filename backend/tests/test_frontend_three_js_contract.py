"""Optional Three.js view contract tests."""
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
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
        'return;',
    ):
        assert snippet in source


THREE_DIR = REPO_ROOT / 'frontend' / 'static' / 'js' / 'three'


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


def test_intervention_ui_hooks_preserved_after_restyle():
    s = (THREE_DIR / "intervention_ui.js").read_text(encoding="utf-8")
    for tok in ("three-ops-console", "ops-grid", "ops-win", "ops-log",
                "twin-congestion-legend",
                "/campus/canteens/", "/windows/", "/toggle"):
        assert tok in s, f"intervention hook lost: {tok!r}"
    # 玻璃观感类（CSS 由 style.css 提供，这里只需结构 className 仍可被样式命中）
    assert "ops-kpi" in s


def test_immersive_ui_module_contract():
    s = (THREE_DIR / "immersive_ui.js").read_text(encoding="utf-8")
    assert "export class ImmersiveUI" in s
    for tok in ("twin-topbar", "twin-toolbar", "twin-floorstrip",
                "twin-status", "data-render", "data-page"):
        assert tok in s, f"immersive_ui missing {tok!r}"
    assert "mount(" in s and "dispose(" in s
