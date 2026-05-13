"""Campus 联合仿真 API —— 新增 /api/campus/* Blueprint。"""
import json
import random
import sqlite3

import simpy
from flask import Blueprint, jsonify, request

import api.routes as single_routes
from simulation.coordinator import CampusCoordinator
from simulation.presets.loader import load_default_campus_preset


campus_bp = Blueprint('campus_api', __name__, url_prefix='/api/campus')

STEP_FLUSH_THRESHOLD = 50
FINISH_FLUSH_THRESHOLD = 500

REQUIRED_TOP_LEVEL = ('campus', 'canteens', 'router')
REQUIRED_CAMPUS_FIELDS = (
    'total_students', 'lunch_alpha', 'coverage', 'peak_window_minutes',
    'simulation_seconds', 'entrance_position', 'walking_speed_mps',
)


def _session():
    """返回 routes.py 的共享 session，保证 monkeypatch 后仍读到同一个对象。"""
    return single_routes._session


def _validate_campus_config(payload: dict) -> str | None:
    for field in REQUIRED_TOP_LEVEL:
        if field not in payload:
            return f'缺少参数：{field}'
    campus = payload['campus']
    for field in REQUIRED_CAMPUS_FIELDS:
        if field not in campus:
            return f'缺少 campus 参数：{field}'
    if not isinstance(payload['canteens'], list) or not payload['canteens']:
        return 'canteens 必须是非空列表'
    try:
        if float(campus['total_students']) <= 0:
            return '学生总数必须大于 0'
        if float(campus['lunch_alpha']) <= 0:
            return '午餐比例必须大于 0'
        if float(campus['coverage']) <= 0:
            return '覆盖率必须大于 0'
        if float(campus['peak_window_minutes']) <= 0:
            return '高峰窗口必须大于 0'
        if float(campus['simulation_seconds']) <= 0:
            return '仿真时长必须大于 0'
        if float(campus['walking_speed_mps']) <= 0:
            return '步行速度必须大于 0'
    except (TypeError, ValueError):
        return 'campus 参数类型错误'
    return None


def _campus_summary(payload: dict) -> dict:
    canteens = payload['canteens']
    total_windows = 0
    total_seats = 0
    serve_times = []
    eat_times = []
    for canteen in canteens:
        eat_times.append(float(canteen.get('avg_eat_time_minutes', 0) or 0))
        for floor in canteen.get('floors', []):
            windows = floor.get('windows', {})
            seats = floor.get('seats', {})
            active_count = int(windows.get('active_count', 0) or 0)
            total_windows += active_count
            total_seats += int(seats.get('count', 0) or 0)
            serve_time = windows.get(
                'avg_serve_time_seconds',
                canteen.get('avg_serve_time_seconds', 0),
            )
            serve_times.extend([float(serve_time or 0)] * active_count)

    campus = payload['campus']
    arrival_rate = (
        float(campus['total_students'])
        * float(campus['lunch_alpha'])
        * float(campus['coverage'])
        / float(campus['peak_window_minutes'])
    )
    return {
        'window_count': max(1, total_windows),
        'seat_count': max(1, total_seats),
        'avg_serve_time': sum(serve_times) / len(serve_times) if serve_times else 30.0,
        'avg_eat_time': sum(eat_times) / len(eat_times) if eat_times else 15.0,
        'arrival_rate': arrival_rate,
        'total_time': max(1, int(float(campus['simulation_seconds']) / 60)),
    }


def _snapshot(event_type: str | None = None) -> dict:
    coordinator = _session()['coordinator']
    state = coordinator.snapshot()
    state['is_running'] = _session()['is_running']
    state['is_ended'] = coordinator.env.peek() == float('inf')
    if event_type is not None:
        state['event_type'] = event_type
    return state


def _compact_snapshot(state: dict, event_type: str) -> dict:
    return {
        'config_id': _session()['config_id'],
        'current_time': state['current_time'],
        'campus_totals': state['campus_totals'],
        'canteens': state['canteens'],
        'in_transit': state['in_transit'],
        'event_type': event_type,
    }


def _campus_buffer_count() -> int:
    return sum(1 for s in _session()['snapshot_buffer'] if 'campus_totals' in s)


def _flush_campus_snapshots():
    buf = _session()['snapshot_buffer']
    if not buf:
        return
    campus_snapshots = [s for s in buf if 'campus_totals' in s]
    if not campus_snapshots:
        return
    with sqlite3.connect(single_routes.DB_PATH) as conn:
        conn.executemany(
            '''INSERT INTO campus_snapshot
               (config_id, current_time, campus_totals_json, canteens_json,
                in_transit_json, event_type)
               VALUES (?, ?, ?, ?, ?, ?)''',
            [
                (
                    s['config_id'],
                    s['current_time'],
                    json.dumps(s['campus_totals'], ensure_ascii=False),
                    json.dumps(s['canteens'], ensure_ascii=False),
                    json.dumps(s['in_transit'], ensure_ascii=False),
                    s['event_type'],
                )
                for s in campus_snapshots
            ],
        )
        conn.commit()
    _session()['snapshot_buffer'] = [s for s in buf if 'campus_totals' not in s]


def _load_campus_history_rows(config_id: int | None = None) -> list[dict]:
    query = '''SELECT s.id, s.config_id, s.current_time AS current_time,
                      s.campus_totals_json, s.canteens_json,
                      s.in_transit_json, s.event_type
               FROM campus_snapshot s'''
    params = ()
    if config_id is not None:
        query += ' WHERE s.config_id = ?'
        params = (config_id,)
    query += ' ORDER BY s.current_time'

    with sqlite3.connect(single_routes.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()

    history = []
    for row in rows:
        item = dict(row)
        item['campus_totals'] = json.loads(item.pop('campus_totals_json') or '{}')
        item['canteens'] = json.loads(item.pop('canteens_json') or '{}')
        item['in_transit'] = json.loads(item.pop('in_transit_json') or '[]')
        history.append(item)
    return history


def _campus_history_snapshots() -> list[dict]:
    config_id = _session()['config_id']
    snapshots = []
    with sqlite3.connect(single_routes.DB_PATH) as conn:
        rows = conn.execute(
            '''SELECT s.current_time, s.campus_totals_json
               FROM campus_snapshot s
               WHERE s.config_id = ?
               ORDER BY s.current_time''',
            (config_id,),
        ).fetchall()
    for current_time, totals_json in rows:
        snapshots.append({
            'current_time': current_time,
            'campus_totals': json.loads(totals_json or '{}'),
        })

    for item in _session()['snapshot_buffer']:
        if item.get('config_id') == config_id and 'campus_totals' in item:
            snapshots.append({
                'current_time': item['current_time'],
                'campus_totals': item['campus_totals'],
            })

    snapshots.sort(key=lambda s: s['current_time'])
    return snapshots


def _aggregate_campus_timeline(history: list[dict], field: str, normalize=None) -> dict:
    if not history:
        return {'x': [], 'y': []}
    effective_time = max(s['current_time'] for s in history)
    total_minutes = max(1, int(effective_time // 60) + 1)
    buckets = [None] * total_minutes
    for snap in history:
        minute = min(total_minutes - 1, int(snap['current_time'] // 60))
        value = snap['campus_totals'].get(field, 0)
        if normalize:
            value = value / normalize * 100
        buckets[minute] = value
    last = 0
    xs, ys = [], []
    for i, value in enumerate(buckets):
        if value is None:
            value = last
        else:
            last = value
        xs.append(i)
        ys.append(round(value, 2))
    return {'x': xs, 'y': ys}


def _campus_statistics() -> dict:
    coordinator = _session()['coordinator']
    snapshot = coordinator.snapshot()
    served = [s for s in coordinator.all_students if s.state == 'left']
    service_times = [s.service_time for s in served]
    eating_times = [s.eat_time for s in served]
    walk_times = [s.walk_time for s in served]

    total_seats = sum(len(c.seats) for c in coordinator.canteens.values())
    effective_time = max(1.0, coordinator.env.now)
    used_seat_time = sum(eating_times)
    seat_utilization = (
        used_seat_time / (total_seats * effective_time) * 100
        if total_seats > 0 else 0
    )

    history = _campus_history_snapshots()
    if not history:
        history = [{
            'current_time': snapshot['current_time'],
            'campus_totals': snapshot['campus_totals'],
        }]
    peak_queue_length = max(
        s['campus_totals'].get('total_in_queue', 0) for s in history
    )

    canteen_statistics = {}
    window_served = {}
    for cid, canteen in coordinator.canteens.items():
        canteen_snap = snapshot['canteens'][cid]
        served_by_window = [w.total_served for w in canteen.windows]
        window_served[cid] = served_by_window
        canteen_statistics[cid] = {
            'display_name': canteen.display_name,
            'total_arrived': canteen.total_arrived,
            'total_served': canteen.total_served,
            'total_in_queue': canteen_snap['total_in_queue'],
            'total_eating': canteen_snap['total_eating'],
            'empty_seats': canteen_snap['empty_seats'],
            'window_served': served_by_window,
            'seat_count': len(canteen.seats),
            'active_window_count': canteen.active_window_count,
        }

    return {
        'mode': 'campus',
        'total_arrived': coordinator.total_arrived,
        'total_served': coordinator.total_served,
        'total_switches': sum(s.switch_count for s in coordinator.all_students),
        'avg_waiting_time': coordinator.stats.avg_waiting_time(),
        'avg_service_time': (
            sum(service_times) / len(service_times) if service_times else 0
        ),
        'avg_eating_time': (
            sum(eating_times) / len(eating_times) if eating_times else 0
        ),
        'avg_walk_time': (
            sum(walk_times) / len(walk_times)
            if walk_times else coordinator.stats.avg_walk_time()
        ),
        'switch_rate': coordinator.stats.switch_rate(),
        'window_served': window_served,
        'seat_utilization': seat_utilization,
        'peak_queue_length': peak_queue_length,
        'queue_timeline': _aggregate_campus_timeline(history, 'total_in_queue'),
        'seat_util_timeline': _aggregate_campus_timeline(
            history, 'total_eating', normalize=total_seats
        ),
        'canteen_statistics': canteen_statistics,
    }


def _ensure_campus_initialized():
    coordinator = _session().get('coordinator')
    if coordinator is None:
        return None, (jsonify({'error': '请先提交校园联合配置'}), 400)
    return coordinator, None


def _advance_to_display_time(coordinator, target_time: float,
                             steps: int, max_steps: int) -> int:
    while coordinator.env.peek() <= target_time and steps < max_steps:
        coordinator.env.step()
        steps += 1
    if steps >= max_steps:
        return steps
    if coordinator.env.peek() != float('inf') and coordinator.env.now < target_time:
        coordinator.env.run(until=target_time)
    return steps


@campus_bp.get('/presets/default')
def default_campus_preset():
    preset = load_default_campus_preset()
    return jsonify({
        'mode': 'campus',
        'config': preset['config'],
        'visible_canteens': preset['visible_canteens'],
        'pending_canteens': preset['pending_canteens'],
    })


@campus_bp.post('/config')
def submit_campus_config():
    if _session().get('mode') not in (None, 'campus'):
        return jsonify({'error': '切换模式前请先 reset 当前仿真'}), 400

    payload = request.get_json(silent=True) or {}
    error = _validate_campus_config(payload)
    if error:
        return jsonify({'error': error}), 400

    summary = _campus_summary(payload)
    with sqlite3.connect(single_routes.DB_PATH) as conn:
        cur = conn.execute(
            '''INSERT INTO simulation_config
               (window_count, seat_count, avg_serve_time, avg_eat_time,
                arrival_rate, total_time, mode, campus_config_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                summary['window_count'],
                summary['seat_count'],
                summary['avg_serve_time'],
                summary['avg_eat_time'],
                summary['arrival_rate'],
                summary['total_time'],
                'campus',
                json.dumps(payload, ensure_ascii=False),
            ),
        )
        config_id = cur.lastrowid
        conn.commit()

    rng = random.Random(payload['router'].get('rng_seed', 42))
    coordinator = CampusCoordinator(simpy.Environment(), payload, rng)
    _session()['mode'] = 'campus'
    _session()['engine'] = None
    _session()['coordinator'] = coordinator
    _session()['config_id'] = config_id
    _session()['is_running'] = False
    _session()['snapshot_buffer'] = []

    return jsonify({
        'message': '校园联合配置已保存',
        'mode': 'campus',
        'config_id': config_id,
        'canteen_order': list(coordinator.canteens.keys()),
    })


@campus_bp.post('/start')
def start_campus_simulation():
    _, error = _ensure_campus_initialized()
    if error is not None:
        return error
    _session()['is_running'] = True
    return jsonify({'message': '校园联合仿真已启动', 'mode': 'campus', 'status': 'running'})


@campus_bp.get('/step')
def step_campus_simulation():
    coordinator, error = _ensure_campus_initialized()
    if error is not None:
        return error
    if not _session()['is_running']:
        return jsonify({'error': '校园联合仿真未运行'}), 400

    tick = request.args.get('display_tick_seconds', default=10.0, type=float)
    if tick is None or tick <= 0:
        return jsonify({'error': 'display_tick_seconds 必须大于 0'}), 400

    coordinator.advance(tick)
    state = _snapshot('step')
    _session()['snapshot_buffer'].append(_compact_snapshot(state, 'step'))
    if state['is_ended']:
        _session()['is_running'] = False
    if _campus_buffer_count() >= STEP_FLUSH_THRESHOLD or state['is_ended']:
        _flush_campus_snapshots()
    return jsonify(state)


@campus_bp.get('/status')
def campus_status():
    coordinator = _session().get('coordinator')
    if coordinator is None:
        return jsonify({
            'mode': _session().get('mode'),
            'is_running': False,
            'initialized': False,
        })
    return jsonify({
        'mode': 'campus',
        'is_running': _session()['is_running'],
        'initialized': True,
        'current_time': coordinator.env.now,
        'canteen_order': list(coordinator.canteens.keys()),
        'total_arrived': coordinator.total_arrived,
        'total_served': coordinator.total_served,
    })


@campus_bp.post('/pause')
def pause_campus_simulation():
    _session()['is_running'] = False
    _flush_campus_snapshots()
    return jsonify({'message': '校园联合仿真已暂停', 'mode': 'campus'})


@campus_bp.post('/finish')
def finish_campus_simulation():
    coordinator, error = _ensure_campus_initialized()
    if error is not None:
        return error

    max_steps = 2_000_000
    display_tick = request.args.get('display_tick_seconds', default=10.0, type=float)
    if display_tick is None or display_tick <= 0:
        return jsonify({'error': 'display_tick_seconds 必须大于 0'}), 400
    next_snapshot_time = coordinator.env.now + display_tick
    steps = 0
    while coordinator.env.peek() != float('inf') and steps < max_steps:
        steps = _advance_to_display_time(
            coordinator, next_snapshot_time, steps, max_steps
        )
        if coordinator.env.now >= next_snapshot_time:
            state = _snapshot('step')
            _session()['snapshot_buffer'].append(_compact_snapshot(state, 'step'))
            if _campus_buffer_count() >= FINISH_FLUSH_THRESHOLD:
                _flush_campus_snapshots()
            next_snapshot_time += display_tick
        else:
            break
    _session()['is_running'] = False

    state = _snapshot('finish')
    state['fast_forward_steps'] = steps
    _session()['snapshot_buffer'].append(_compact_snapshot(state, 'finish'))
    _flush_campus_snapshots()
    return jsonify(state)


@campus_bp.post('/reset')
def reset_campus_simulation():
    _flush_campus_snapshots()
    _session()['mode'] = None
    _session()['engine'] = None
    _session()['coordinator'] = None
    _session()['config_id'] = None
    _session()['is_running'] = False
    _session()['snapshot_buffer'] = []
    return jsonify({'message': '校园联合仿真已重置', 'mode': None})


@campus_bp.get('/statistics')
def campus_statistics():
    _, error = _ensure_campus_initialized()
    if error is not None:
        return error
    return jsonify(_campus_statistics())


@campus_bp.get('/history/configs')
def list_campus_history_configs():
    query = (
        '''SELECT c.id, c.window_count, c.seat_count, c.avg_serve_time,
                  c.avg_eat_time, c.arrival_rate, c.total_time, c.mode,
                  c.created_at, c.campus_config_json
           FROM simulation_config c
           WHERE c.mode = 'campus'
           ORDER BY c.created_at DESC'''
    )
    with sqlite3.connect(single_routes.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query).fetchall()

    configs = []
    for row in rows:
        item = dict(row)
        history = _load_campus_history_rows(item['id'])
        totals = [snap['campus_totals'] for snap in history]
        item['snapshot_count'] = len(history)
        item['total_arrived'] = (
            max((t.get('total_arrived', 0) for t in totals), default=None)
        )
        item['total_served'] = (
            max((t.get('total_served', 0) for t in totals), default=None)
        )
        if item.get('campus_config_json'):
            item['campus_config'] = json.loads(item.pop('campus_config_json'))
        configs.append(item)
    return jsonify(configs)


@campus_bp.get('/history')
def get_campus_history():
    config_id = request.args.get('config_id', type=int)
    return jsonify(_load_campus_history_rows(config_id))
