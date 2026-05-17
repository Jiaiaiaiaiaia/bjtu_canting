"""前端 main.js 控制层契约测试。

A.12 只允许重构控制流与 state 形状；这些静态断言用于避免后续把
单食堂 Phase 2 路径和 campus 预留分派写散。
"""
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MAIN_JS = (REPO_ROOT / 'frontend' / 'static' / 'js' / 'main.js').read_text(encoding='utf-8')
INDEX_HTML = (REPO_ROOT / 'frontend' / 'templates' / 'index.html').read_text(encoding='utf-8')
CANVAS_RENDERER_JS = REPO_ROOT / 'frontend' / 'static' / 'js' / 'canvas_renderer.js'
ANALYSIS_CHARTS_JS = REPO_ROOT / 'frontend' / 'static' / 'js' / 'analysis_charts.js'


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
        'visibleCanteens: []',
        'pendingCanteens: []',
        'campusPresetScale: null',
        "renderMode: '3d'",
        'lastStatistics: null',
        'lastSingleConfig: null',
    ):
        assert snippet in MAIN_JS


def test_main_js_loads_campus_preset_without_hiding_manual_json_edits():
    for snippet in (
        'let campusPresetPayload = null;',
        'let campusConfigDirty = false;',
        "campusConfigJson.addEventListener('input'",
        'campusConfigDirty = true;',
        'campusPresetPayload = null;',
        'async function loadDefaultCampusPreset()',
        '/campus/presets/default',
        'applyCampusPresetMetadata(data);',
        'state.visibleCanteens = data.visible_canteens || [];',
        'state.pendingCanteens = data.pending_canteens || [];',
        'state.campusPresetScale = data.source_scale || null;',
        'campusConfigDirty = false;',
        'async function getCampusConfigForSubmit()',
        'if (campusConfigDirty) {',
        'state.visibleCanteens = [];',
        'return readCampusConfig();',
    ):
        assert snippet in MAIN_JS


def test_main_js_uses_coarser_campus_finish_tick_for_demo_runtime():
    assert "const finishPath = state.mode === 'campus'" in MAIN_JS
    assert "?display_tick_seconds=60" in MAIN_JS
    assert "fetch(`${API_BASE}${finishPath}`, { method: 'POST' })" in MAIN_JS


def test_main_js_dispatches_step_by_mode():
    assert 'async function dispatchStep()' in MAIN_JS
    assert "'/campus/step?display_tick_seconds=10'" in MAIN_JS
    assert "'/simulation/step'" in MAIN_JS
    assert 'const data = await dispatchStep();' in MAIN_JS


def test_main_js_keeps_single_canteen_draw_helpers_available():
    for helper in ('drawWindows', 'drawSeats', 'drawStudentDots'):
        assert f'function {helper}(' in MAIN_JS
        assert f'window.CanteenApp.{helper} = {helper};' in MAIN_JS


def test_frontend_loads_extracted_rendering_modules_before_main_js():
    assert CANVAS_RENDERER_JS.exists()
    assert ANALYSIS_CHARTS_JS.exists()
    assert "filename='js/canvas_renderer.js'" in INDEX_HTML
    assert "filename='js/analysis_charts.js'" in INDEX_HTML
    assert INDEX_HTML.index("filename='js/canvas_renderer.js'") < INDEX_HTML.index(
        "filename='js/main.js'"
    )
    assert INDEX_HTML.index("filename='js/analysis_charts.js'") < INDEX_HTML.index(
        "filename='js/main.js'"
    )


def test_main_js_keeps_compatibility_shell_for_extracted_modules():
    for snippet in (
        'function rendererDeps()',
        'window.CanteenApp.CanvasRenderer.drawCanteen(data, rendererDeps())',
        'window.CanteenApp.CanvasRenderer.drawWindows(windows, W, rendererDeps())',
        'window.CanteenApp.CanvasRenderer.drawSeats(seats, W, H, rendererDeps())',
        'window.CanteenApp.CanvasRenderer.drawStudentDots(data, windowBoxes, W, H, rendererDeps())',
        'function chartDeps()',
        'window.CanteenApp.AnalysisCharts.renderStatCards(s, chartDeps())',
        'window.CanteenApp.AnalysisCharts.renderCharts(stats, chartDeps())',
        'window.CanteenApp.AnalysisCharts.disposeCharts(chartDeps())',
    ):
        assert snippet in MAIN_JS


def test_main_js_runs_single_canteen_suggested_scenario_without_campus_api():
    for snippet in (
        "const scenarioRunBtn = document.getElementById('scenario-run-btn');",
        'async function runSuggestedScenario()',
        'async function runSingleScenarioWithSeed(config, seed)',
        'function buildScenarioSeed()',
        "if (state.mode !== 'single')",
        'window.CanteenApp.AnalysisCharts.buildSuggestedSingleConfig',
        "await apiPost('/simulation/reset')",
        "await apiPost('/config', { ...config, rng_seed: seed })",
        "await apiPost('/simulation/start')",
        "await apiPost('/simulation/finish')",
        'const baselineResult = await runSingleScenarioWithSeed(baselineConfig, seed)',
        'const adjustedResult = await runSingleScenarioWithSeed(suggestion.config, seed)',
        'renderScenarioComparison(baselineResult, adjustedResult',
        'function showStatistics(stats)',
        'state.lastStatistics = stats;',
    ):
        assert snippet in MAIN_JS

    assert 'renderScenarioComparison(baselineStats, adjustedStats, suggestion.summary)' not in MAIN_JS


def test_main_js_exposes_scenario_helpers_for_contract_testing():
    for snippet in (
        'window.CanteenApp.runSuggestedScenario = runSuggestedScenario;',
        'window.CanteenApp.showStatistics = showStatistics;',
    ):
        assert snippet in MAIN_JS


MAIN = REPO_ROOT / 'frontend' / 'static' / 'js' / 'main.js'


def test_preset_first_uses_single_canteen_and_3d_default():
    s = MAIN.read_text(encoding="utf-8")
    assert "async function loadSingleCanteenPreset()" in s
    assert "/api/campus/presets/single-canteen" in s
    assert "async function loadDefaultCampusPreset()" in s     # legacy retained
    assert "/campus/presets/default" in s                       # legacy retained
    assert "renderMode: '3d'" in s
    assert "state.renderMode = '3d';" in s
    assert "renderMode: '2d'" not in s
    assert "state.renderMode = '2d';" not in s
    assert "canvas_renderer" in s.lower() or "CanvasRenderer" in s
