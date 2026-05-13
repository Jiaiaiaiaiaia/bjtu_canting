"""A.16 前端三层视图 HTML/CSS 框架契约测试。"""
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = (REPO_ROOT / 'frontend' / 'templates' / 'index.html').read_text(encoding='utf-8')
MAIN_JS = (REPO_ROOT / 'frontend' / 'static' / 'js' / 'main.js').read_text(encoding='utf-8')
STYLE_CSS = (REPO_ROOT / 'frontend' / 'static' / 'css' / 'style.css').read_text(encoding='utf-8')


def test_a16_html_adds_mode_forms_and_campus_controls():
    for snippet in (
        'rel="icon" href="data:,"',
        'name="simulation_mode"',
        'id="simulation-mode-single"',
        'id="simulation-mode-campus"',
        'value="single"',
        'value="campus"',
        'id="single-mode-form"',
        'id="campus-mode-form" hidden',
        'id="campus-preset-panel"',
        'data-campus-preset="default"',
        'id="pending-data-note"',
        'id="campus-config-json"',
        'placeholder="API 预设加载后会自动填入；手动模式请粘贴完整校园 JSON"',
        'id="view-switcher" hidden',
        'data-view="campus"',
        'data-view="canteen"',
        'id="campus-overview-panel" hidden',
        'id="campus-total-arrived"',
        'id="campus-total-served"',
        'id="campus-in-transit"',
        'id="campus-total-switches"',
        'id="campus-avg-waiting"',
        'id="canteen-switcher" hidden',
        'id="active-canteen-select"',
        'id="render-switcher"',
        'data-render="2d"',
        'data-render="3d"',
        'id="three-stage"',
        'type="importmap"',
        '"three"',
        'OrbitControls.js',
        'type="module"',
        'scene3d.js',
    ):
        assert snippet in INDEX_HTML


def test_a16_main_js_binds_mode_and_view_controls():
    for snippet in (
        "querySelectorAll('input[name=\"simulation_mode\"]')",
        "const DEFAULT_CAMPUS_CONFIG = campusConfigJson ? campusConfigJson.value : ''",
        'function selectedMode()',
        'function syncModeForms()',
        'function readCampusConfig()',
        'function loadDefaultCampusPreset()',
        'function applyCampusPresetMetadata(',
        'function renderPendingDataNote(',
        'function getCampusConfigForSubmit()',
        '/campus/presets/default',
        'pending_canteens',
        'campusConfigDirty',
        'visible_canteens',
        'source_scale',
        'display_tick_seconds=60',
        'function resetActiveSession()',
        'function applyViewState()',
        '/simulation/status',
        "apiPost('/campus/config'",
        "'campus-config-json'",
        "'view-switcher'",
        "'campus-map-container'",
        "'canteen-switcher'",
        "document.querySelector('.info-panel')",
        'campusOverviewPanel.hidden = !isCampusView',
        'infoPanel.hidden = isCampusView',
        "document.getElementById('simulation-mode-single')",
        "querySelectorAll('button[data-view]')",
        "querySelectorAll('button[data-render]')",
        'window.CanteenApp3D.init',
        'window.CanteenApp3D.render(data, state)',
    ):
        assert snippet in MAIN_JS


def test_a16_main_js_parses_payload_before_resetting_session():
    payload_snippet = (
        "const payload = nextMode === 'campus'\n"
        "            ? await getCampusConfigForSubmit()\n"
        "            : readSingleConfig();"
    )
    assert payload_snippet in MAIN_JS
    assert MAIN_JS.index(payload_snippet) < MAIN_JS.index('await resetActiveSession();')
    assert "await apiPost('/campus/config', payload)" in MAIN_JS


def test_a16_main_js_only_commits_mode_after_successful_start():
    reset_block = MAIN_JS.split(
        "resetBtn.addEventListener('click', () => {", 1
    )[1].split("});\n\nmodeRadios.forEach", 1)[0]
    radio_block = MAIN_JS.split(
        "modeRadios.forEach(radio => {", 1
    )[1].split("});\n\nsyncModeForms();", 1)[0]
    submit_block = MAIN_JS.split(
        "configForm.addEventListener('submit', async e => {", 1
    )[1].split("});\n\nfunction selectedMode()", 1)[0]

    assert 'state.mode =' not in reset_block
    assert 'applyViewState();' not in reset_block
    assert 'state.mode =' not in radio_block
    assert 'state.view =' not in radio_block
    assert 'applyViewState();' not in radio_block

    next_mode_snippet = "const nextMode = selectedMode();"
    payload_snippet = (
        "const payload = nextMode === 'campus'\n"
        "            ? await getCampusConfigForSubmit()\n"
        "            : readSingleConfig();"
    )
    assert next_mode_snippet in submit_block
    assert payload_snippet in submit_block
    assert "const apiBase = nextMode === 'campus' ? '/campus' : '/simulation';" in submit_block
    assert "state.mode = nextMode;" in submit_block
    assert submit_block.index(next_mode_snippet) < submit_block.index(payload_snippet)
    assert submit_block.index('state.mode = nextMode;') > submit_block.index(
        "const startRes = await apiPost(`${apiBase}/start`);"
    )


def test_a16_css_styles_new_campus_ui_shell():
    for snippet in (
        '.mode-selector',
        '.single-mode-form',
        '.campus-config-panel',
        '.campus-preset-panel',
        '.campus-preset-card',
        '.pending-data-note',
        '.view-switcher',
        '.campus-overview-panel',
        '.canteen-switcher',
        '.campus-map-container',
        '#campus-map-svg',
        '.floor-tabs',
        '.canteen-marker',
        '.render-switcher',
        '.three-stage',
    ):
        assert snippet in STYLE_CSS


def test_a16_html_does_not_embed_xuehuo_placeholder_runtime_json():
    textarea = INDEX_HTML.split('id="campus-config-json"', 1)[1].split('</textarea>', 1)[0]

    assert '"id": "xuehuo"' not in textarea
    assert 'placeholder single-floor layout' not in textarea
    assert '5 窗口 / 150 座' not in textarea
