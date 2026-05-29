"""前端 campus.js 食堂下钻层契约测试。"""
import json
import subprocess
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CAMPUS_JS = REPO_ROOT / 'frontend' / 'static' / 'js' / 'campus.js'
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


def test_campus_js_script_is_loaded_after_main_js():
    html = INDEX_HTML.read_text(encoding='utf-8')
    main_marker = "filename='js/main.js'"
    campus_marker = "filename='js/campus.js'"
    assert main_marker in html
    assert campus_marker in html
    assert html.index(main_marker) < html.index(campus_marker)


def test_campus_js_refresh_filters_active_floor_and_updates_overview():
    assert CAMPUS_JS.exists()
    snapshot = {
        'current_time': 12,
        'mode': 'campus',
        'canteen_order': ['minghu_xueyi', 'xuehuo'],
        'campus_totals': {
            'total_arrived': 10,
            'total_served': 7,
            'total_in_transit': 2,
            'total_switches': 1,
            'avg_waiting_time': 3.25,
        },
        'canteens': {
            'minghu_xueyi': {
                'id': 'minghu_xueyi',
                'display_name': '明湖学一',
                'current_time': 12,
                'total_arrived': 6,
                'total_served': 4,
                'total_in_queue': 3,
                'total_eating': 1,
                'empty_seats': 20,
                'avg_waiting_time': 0,
                'waiting_queue_length': 9,
                'windows': [{'id': 1, 'floor_id': 1}, {'id': 2, 'floor_id': 2}],
                'seats': [{'id': 1, 'floor_id': 1}, {'id': 2, 'floor_id': 2}],
                'students': [{'id': 1, 'floor_id': 1}, {'id': 2, 'floor_id': 2}],
                'floors': [
                    {
                        'floor_id': 1,
                        'windows': [{'id': 1, 'floor_id': 1}],
                        'seats': [{'id': 1, 'floor_id': 1}],
                        'students': [{'id': 1, 'floor_id': 1}],
                    },
                    {
                        'floor_id': 2,
                        'windows': [{'id': 2, 'floor_id': 2}],
                        'seats': [{'id': 2, 'floor_id': 2}],
                        'students': [{'id': 2, 'floor_id': 2}],
                    },
                ],
            },
            'xuehuo': {'display_name': '学活'},
        },
    }
    script = textwrap.dedent(f"""
        const fs = require('fs');
        const vm = require('vm');
        const nodes = {{}};
        function makeNode(id) {{
          return nodes[id] = {{
            id,
            value: '',
            textContent: '',
            children: [],
            _innerHTML: '',
            set innerHTML(value) {{ this._innerHTML = value; this.children = []; }},
            get innerHTML() {{ return this._innerHTML; }},
            appendChild(child) {{ this.children.push(child); }},
            addEventListener(name, handler) {{ this.handler = handler; }},
          }};
        }}
        makeNode('active-canteen-select');
        for (const id of ['campus-total-arrived', 'campus-total-served',
                          'campus-in-transit', 'campus-total-switches',
                          'campus-avg-waiting']) {{
          makeNode(id);
        }}
        global.window = {{
          CanteenApp: {{
            state: {{
              mode: 'campus',
              view: 'canteen',
              activeCanteenId: null,
              activeFloorId: 2,
              lastData: null,
            }},
            drawCanteen(data) {{ global.drawn = data; }},
            updateInfoPanel(data) {{ global.info = data; }},
            renderFloorTabs(data) {{ global.tabsFor = data.id; }},
          }},
        }};
        global.document = {{
          getElementById(id) {{ return nodes[id] || null; }},
          createElement(tag) {{ return makeNode(tag + '-' + Math.random()); }},
        }};
        vm.runInThisContext(fs.readFileSync({json.dumps(str(CAMPUS_JS))}, 'utf8'));
        window.CanteenApp.refreshCampusView({json.dumps(snapshot, ensure_ascii=False)});
        console.log(JSON.stringify({{
          active: window.CanteenApp.state.activeCanteenId,
          optionCount: nodes['active-canteen-select'].children.length,
          drawnWindows: global.drawn.windows.map(w => w.id),
          waitingQueueLength: global.drawn.waiting_queue_length,
          arrived: nodes['campus-total-arrived'].textContent,
          avgWaiting: nodes['campus-avg-waiting'].textContent,
          tabsFor: global.tabsFor,
        }}));
    """)
    result = run_node(script)

    assert result == {
        'active': 'minghu_xueyi',
        'optionCount': 2,
        'drawnWindows': [2],
        'waitingQueueLength': 9,
        'arrived': '10',
        'avgWaiting': '3.3 s',
        'tabsFor': 'minghu_xueyi',
    }


def test_campus_js_loads_before_future_campus_dom_exists():
    assert CAMPUS_JS.exists()
    snapshot = {
        'mode': 'campus',
        'canteen_order': ['minghu_xueyi'],
        'campus_totals': {},
        'canteens': {'minghu_xueyi': {'display_name': '明湖学一'}},
    }
    script = textwrap.dedent(f"""
        const fs = require('fs');
        const vm = require('vm');
        global.window = {{
          CanteenApp: {{
            state: {{ view: 'canteen', activeCanteenId: null, activeFloorId: null }},
            drawCanteen() {{}},
            updateInfoPanel() {{}},
          }},
        }};
        global.document = {{
          getElementById() {{ return null; }},
          createElement() {{ return {{ appendChild() {{}} }}; }},
        }};
        vm.runInThisContext(fs.readFileSync({json.dumps(str(CAMPUS_JS))}, 'utf8'));
        window.CanteenApp.refreshCampusView({json.dumps(snapshot, ensure_ascii=False)});
        console.log(JSON.stringify({{
          active: window.CanteenApp.state.activeCanteenId,
          hasRefresh: typeof window.CanteenApp.refreshCampusView,
          hasFilter: typeof window.CanteenApp.filterByFloor,
        }}));
    """)
    result = run_node(script)

    assert result == {
        'active': 'minghu_xueyi',
        'hasRefresh': 'function',
        'hasFilter': 'function',
    }


def test_canteen_select_change_resets_active_floor():
    assert CAMPUS_JS.exists()
    script = textwrap.dedent(f"""
        const fs = require('fs');
        const vm = require('vm');
        const select = {{
          value: '',
          children: [],
          set innerHTML(value) {{ this.children = []; }},
          appendChild(child) {{ this.children.push(child); }},
          addEventListener(name, handler) {{ this.handler = handler; }},
        }};
        global.window = {{
          CanteenApp: {{
            state: {{
              view: 'canteen',
              activeCanteenId: 'minghu_xueyi',
              activeFloorId: 2,
              lastData: null,
            }},
            drawCanteen() {{}},
            updateInfoPanel() {{}},
          }},
        }};
        global.document = {{
          getElementById(id) {{ return id === 'active-canteen-select' ? select : null; }},
          createElement() {{ return {{ value: '', textContent: '' }}; }},
        }};
        vm.runInThisContext(fs.readFileSync({json.dumps(str(CAMPUS_JS))}, 'utf8'));
        window.CanteenApp.fillCanteenSelect(
          ['minghu_xueyi', 'xuehuo'],
          {{ minghu_xueyi: {{ display_name: '明湖学一' }}, xuehuo: {{ display_name: '学活' }} }}
        );
        select.value = 'xuehuo';
        select.handler({{ target: select }});
        console.log(JSON.stringify({{
          active: window.CanteenApp.state.activeCanteenId,
          floor: window.CanteenApp.state.activeFloorId,
        }}));
    """)
    result = run_node(script)

    assert result == {'active': 'xuehuo', 'floor': None}
