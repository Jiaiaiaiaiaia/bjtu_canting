"""Campus 联合仿真 API —— 新增 /api/campus/* Blueprint。"""
import json
import random
import sqlite3

import simpy
from flask import Blueprint, jsonify, request

import api.routes as single_routes
from simulation.coordinator import CampusCoordinator


campus_bp = Blueprint('campus_api', __name__, url_prefix='/api/campus')

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


def _ensure_campus_initialized():
    coordinator = _session().get('coordinator')
    if coordinator is None:
        return None, (jsonify({'error': '请先提交校园联合配置'}), 400)
    return coordinator, None


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
    steps = 0
    while coordinator.env.peek() != float('inf') and steps < max_steps:
        coordinator.env.step()
        steps += 1
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
    return jsonify(_snapshot('statistics'))
