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
