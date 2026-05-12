"""前端 main.js 控制层契约测试。

A.12 只允许重构控制流与 state 形状；这些静态断言用于避免后续把
单食堂 Phase 2 路径和 campus 预留分派写散。
"""
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MAIN_JS = (REPO_ROOT / 'frontend' / 'static' / 'js' / 'main.js').read_text(encoding='utf-8')


def test_main_js_exposes_canteen_app_namespace():
    assert 'window.CanteenApp = window.CanteenApp || {};' in MAIN_JS
    assert 'window.CanteenApp.state = state;' in MAIN_JS
    assert 'window.CanteenApp.drawCanteen = drawCanteen;' in MAIN_JS
    assert 'window.CanteenApp.updateInfoPanel = updateInfoPanel;' in MAIN_JS
    assert 'window.CanteenApp.renderCharts = renderCharts;' in MAIN_JS
    assert 'window.CanteenApp.disposeCharts = disposeCharts;' in MAIN_JS


def test_main_js_state_has_campus_control_fields():
    for snippet in (
        "mode: 'single'",
        "view: 'canteen'",
        'activeCanteenId: null',
        'activeFloorId: null',
        'canteenOrder: []',
    ):
        assert snippet in MAIN_JS


def test_main_js_dispatches_step_by_mode():
    assert 'async function dispatchStep()' in MAIN_JS
    assert "'/campus/step?display_tick_seconds=10'" in MAIN_JS
    assert "'/simulation/step'" in MAIN_JS
    assert 'const data = await dispatchStep();' in MAIN_JS


def test_main_js_keeps_single_canteen_draw_helpers_available():
    for helper in ('drawWindows', 'drawSeats', 'drawStudentDots'):
        assert f'function {helper}(' in MAIN_JS
        assert f'window.CanteenApp.{helper} = {helper};' in MAIN_JS
