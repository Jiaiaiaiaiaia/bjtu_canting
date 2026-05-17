"""Single-canteen product UI guardrails."""
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = REPO_ROOT / "frontend" / "templates" / "index.html"
MAIN_JS = REPO_ROOT / "frontend" / "static" / "js" / "main.js"
CAMPUS_JS = REPO_ROOT / "frontend" / "static" / "js" / "campus.js"
STYLE_CSS = REPO_ROOT / "frontend" / "static" / "css" / "style.css"
CAMPUS_MAP_JS = REPO_ROOT / "frontend" / "static" / "js" / "campus_map.js"
README = REPO_ROOT / "README.md"


def test_campus_map_product_entry_is_removed_from_default_ui():
    html = INDEX_HTML.read_text(encoding="utf-8")

    for stale in (
        "校园地图",
        "校园联合模式",
        "北交大午餐高峰预设",
        "学四使用已采集数据",
        "学活保留待补标记",
        'id="campus-map-container"',
        'id="campus-map-svg"',
        'data-view="campus"',
        "filename='js/campus_map.js'",
    ):
        assert stale not in html

    assert 'id="three-stage"' in html
    assert 'data-render="2d"' in html
    assert 'data-render="3d"' in html


def test_default_entry_is_3d_single_canteen_not_legacy_single_mode():
    html = INDEX_HTML.read_text(encoding="utf-8")
    main_js = MAIN_JS.read_text(encoding="utf-8")

    assert 'id="simulation-mode-campus" name="simulation_mode" value="campus" checked' in html
    assert 'id="simulation-mode-single" name="simulation_mode" value="single" checked' not in html
    assert "const campusModeRadio = document.getElementById('simulation-mode-campus');" in main_js
    assert "if (campusModeRadio) campusModeRadio.checked = true;" in main_js


def test_frontend_no_longer_loads_or_calls_campus_map_module():
    assert not CAMPUS_MAP_JS.exists()

    main_js = MAIN_JS.read_text(encoding="utf-8")
    campus_js = CAMPUS_JS.read_text(encoding="utf-8")
    style_css = STYLE_CSS.read_text(encoding="utf-8")

    assert "campus-map-container" not in main_js
    assert "renderCampusMap" not in campus_js
    assert "canteen-marker" not in style_css


def test_readme_matches_single_canteen_3d_product_direction():
    readme = README.read_text(encoding="utf-8")

    for stale in (
        "校园联合模式",
        "多食堂",
        "校园地图",
        "campus_map.js",
        "3D 沙盘",
    ):
        assert stale not in readme

    assert "3D 单食堂" in readme
    assert "/api/campus/*" in readme
    assert "2D" in readme and "fallback" in readme
