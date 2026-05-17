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
