"""前端 campus_map.js 校园 SVG 总览层契约测试。"""
import json
import subprocess
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CAMPUS_MAP_JS = REPO_ROOT / 'frontend' / 'static' / 'js' / 'campus_map.js'
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


def test_campus_map_script_is_loaded_after_campus_js():
    html = INDEX_HTML.read_text(encoding='utf-8')
    assert 'id="campus-map-container"' in html
    assert 'id="campus-map-svg"' in html
    campus_marker = "filename='js/campus.js'"
    map_marker = "filename='js/campus_map.js'"
    assert campus_marker in html
    assert map_marker in html
    assert html.index(campus_marker) < html.index(map_marker)


def test_campus_map_renders_markers_heat_and_transit_dots():
    assert CAMPUS_MAP_JS.exists()
    snapshot = {
        'mode': 'campus',
        'canteens': {
            'minghu_xueyi': {
                'display_name': '明湖学一',
                'campus_position': {'x': 100, 'y': 80},
                'windows': [{'queue_length': 25}],
                'waiting_queue_length': 25,
            },
            'xuehuo': {
                'display_name': '学活',
                'campus_position': {'x': 240, 'y': 180},
                'windows': [{'queue_length': 0}],
                'waiting_queue_length': 0,
            },
            'xuesi': {
                'display_name': '学四',
                'campus_position': {'x': 360, 'y': 120},
                'windows': [{'queue_length': 10}],
                'waiting_queue_length': 5,
            },
        },
        'in_transit': [
            {
                'from_canteen_id': None,
                'to_canteen_id': 'minghu_xueyi',
                'progress': 0.5,
            },
            {
                'from_canteen_id': 'xuehuo',
                'to_canteen_id': 'xuesi',
                'progress': 0.25,
            },
        ],
    }
    script = textwrap.dedent(f"""
        const fs = require('fs');
        const vm = require('vm');
        const nodes = {{}};
        function makeEl(tag) {{
          return {{
            tag,
            attrs: {{}},
            children: [],
            textContent: '',
            events: {{}},
            setAttribute(name, value) {{
              this.attrs[name] = String(value);
              if (name === 'id') nodes[value] = this;
            }},
            getAttribute(name) {{ return this.attrs[name]; }},
            appendChild(child) {{ this.children.push(child); return child; }},
            addEventListener(name, handler) {{ this.events[name] = handler; }},
          }};
        }}
        const svg = makeEl('svg');
        svg.setAttribute('id', 'campus-map-svg');
        nodes['campus-map-svg'] = svg;
        function findMarker(cid) {{
          return svg.children.find(el =>
            el.tag === 'g' &&
            el.attrs.class === 'canteen-marker' &&
            el.attrs['data-cid'] === cid
          );
        }}
        global.document = {{
          getElementById(id) {{ return nodes[id] || null; }},
          createElementNS(ns, tag) {{ return makeEl(tag); }},
          querySelector(selector) {{
            const match = selector.match(/data-cid="([^"]+)"/);
            if (!match) return null;
            const marker = findMarker(match[1]);
            return marker ? marker.children.find(el => el.tag === 'rect') : null;
          }},
        }};
        global.window = {{
          CanteenApp: {{
            state: {{
              view: 'campus',
              activeCanteenId: null,
              activeFloorId: 2,
              lastData: 'snapshot',
            }},
            refreshCampusView(snapshot) {{ global.refreshCalledWith = snapshot; }},
          }},
        }};
        vm.runInThisContext(fs.readFileSync({json.dumps(str(CAMPUS_MAP_JS))}, 'utf8'));
        window.CanteenApp.renderCampusMap({json.dumps(snapshot, ensure_ascii=False)});
        findMarker('xuehuo').events.click();
        const transitLayer = nodes['transit-layer'];
        console.log(JSON.stringify({{
          markerCount: svg.children.filter(el => el.attrs.class === 'canteen-marker').length,
          viewBox: svg.attrs.viewBox,
          hotColor: document.querySelector('.canteen-marker[data-cid="minghu_xueyi"] rect').attrs.fill,
          coldColor: document.querySelector('.canteen-marker[data-cid="xuehuo"] rect').attrs.fill,
          transitCount: transitLayer.children.length,
          firstTransit: {{
            cx: transitLayer.children[0].attrs.cx,
            cy: transitLayer.children[0].attrs.cy,
          }},
          clickedView: window.CanteenApp.state.view,
          clickedCanteen: window.CanteenApp.state.activeCanteenId,
          clickedFloor: window.CanteenApp.state.activeFloorId,
          refreshCalled: global.refreshCalledWith === 'snapshot',
        }}));
    """)
    result = run_node(script)

    assert result == {
        'markerCount': 3,
        'viewBox': '-50 -50 500 400',
        'hotColor': 'rgb(239, 60, 68)',
        'coldColor': 'rgb(239, 120, 68)',
        'transitCount': 2,
        'firstTransit': {'cx': '50', 'cy': '40'},
        'clickedView': 'canteen',
        'clickedCanteen': 'xuehuo',
        'clickedFloor': None,
        'refreshCalled': True,
    }
