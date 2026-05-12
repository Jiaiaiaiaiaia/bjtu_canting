"""前端 floor_tabs.js 楼层 Tab 层契约测试。"""
import json
import subprocess
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FLOOR_TABS_JS = REPO_ROOT / 'frontend' / 'static' / 'js' / 'floor_tabs.js'
INDEX_HTML = REPO_ROOT / 'frontend' / 'templates' / 'index.html'


def run_node(script: str) -> dict:
    result = subprocess.run(
        ['node', '-e', script],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def test_floor_tabs_script_is_loaded_after_campus_js():
    html = INDEX_HTML.read_text(encoding='utf-8')
    assert 'id="floor-tabs"' in html
    campus_marker = "filename='js/campus.js'"
    tabs_marker = "filename='js/floor_tabs.js'"
    assert campus_marker in html
    assert tabs_marker in html
    assert html.index(campus_marker) < html.index(tabs_marker)


def test_floor_tabs_render_and_click_updates_active_floor():
    assert FLOOR_TABS_JS.exists()
    script = textwrap.dedent(f"""
        const fs = require('fs');
        const vm = require('vm');
        const container = {{
          children: [],
          set innerHTML(value) {{ this.children = []; }},
          appendChild(child) {{ this.children.push(child); return child; }},
          querySelector(selector) {{
            return this.children.find(child => child.dataset.floor === 'all') || null;
          }},
        }};
        function makeButton() {{
          return {{
            tag: 'button',
            dataset: {{}},
            textContent: '',
            events: {{}},
            classes: [],
            classList: {{
              add(name) {{ this.owner.classes.push(name); }},
              remove(name) {{ this.owner.classes = this.owner.classes.filter(x => x !== name); }},
            }},
            addEventListener(name, handler) {{ this.events[name] = handler; }},
          }};
        }}
        global.window = {{
          CanteenApp: {{
            state: {{
              activeFloorId: null,
              lastData: {{ mode: 'campus' }},
            }},
            refreshCampusView(snapshot) {{ global.refreshCalledWith = snapshot.mode; }},
          }},
        }};
        global.document = {{
          getElementById(id) {{ return id === 'floor-tabs' ? container : null; }},
          createElement(tag) {{
            const btn = makeButton();
            btn.classList.owner = btn;
            return btn;
          }},
          querySelectorAll(selector) {{
            return selector === '#floor-tabs button' ? container.children : [];
          }},
        }};
        vm.runInThisContext(fs.readFileSync({json.dumps(str(FLOOR_TABS_JS))}, 'utf8'));
        window.CanteenApp.renderFloorTabs({{
          id: 'minghu_xueyi',
          floors: [{{ floor_id: 1 }}, {{ floor_id: 2 }}],
        }});
        container.children[2].events.click();
        console.log(JSON.stringify({{
          labels: container.children.map(btn => btn.textContent),
          floors: container.children.map(btn => btn.dataset.floor),
          activeFloor: window.CanteenApp.state.activeFloorId,
          activeLabels: container.children.filter(btn => btn.classes.includes('active')).map(btn => btn.textContent),
          refreshCalledWith: global.refreshCalledWith,
        }}));
    """)
    result = run_node(script)

    assert result == {
        'labels': ['全楼层', '1F', '2F'],
        'floors': ['all', '1', '2'],
        'activeFloor': 2,
        'activeLabels': ['2F'],
        'refreshCalledWith': 'campus',
    }


def test_floor_tabs_single_floor_clears_tabs_and_filter():
    assert FLOOR_TABS_JS.exists()
    script = textwrap.dedent(f"""
        const fs = require('fs');
        const vm = require('vm');
        const container = {{
          children: [{{}}],
          set innerHTML(value) {{ this.children = []; }},
          appendChild(child) {{ this.children.push(child); }},
        }};
        global.window = {{
          CanteenApp: {{
            state: {{ activeFloorId: 2, lastData: null }},
          }},
        }};
        global.document = {{
          getElementById(id) {{ return id === 'floor-tabs' ? container : null; }},
          createElement() {{ return {{ dataset: {{}}, classList: {{ add() {{}}, remove() {{}} }}, addEventListener() {{}} }}; }},
          querySelectorAll() {{ return []; }},
        }};
        vm.runInThisContext(fs.readFileSync({json.dumps(str(FLOOR_TABS_JS))}, 'utf8'));
        window.CanteenApp.renderFloorTabs({{
          id: 'xuehuo',
          floors: [{{ floor_id: 1 }}],
        }});
        console.log(JSON.stringify({{
          childCount: container.children.length,
          activeFloor: window.CanteenApp.state.activeFloorId,
        }}));
    """)
    result = run_node(script)

    assert result == {'childCount': 0, 'activeFloor': None}
