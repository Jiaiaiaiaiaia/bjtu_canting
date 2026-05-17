"""Campus 联合仿真 API —— 新增 /api/campus/* Blueprint。"""
import json
import random
import sqlite3

import simpy
from flask import Blueprint, jsonify, request

import api.routes as single_routes
from .campus_config_helpers import campus_config_summary, validate_campus_config
from .campus_history_store import (
    campus_history_for_analysis,
    campus_history_snapshots,
    flush_campus_snapshots,
    list_campus_history_configs as load_campus_history_configs,
    load_campus_history_rows,
)
from .campus_simulation_service import (
    add_window_intervention,
    pause_campus_session,
    reset_campus_session,
    start_campus_session,
    toggle_window_intervention,
)
from .campus_stats_helpers import build_campus_statistics
from simulation.coordinator import CampusCoordinator
from simulation.presets.loader import (
    load_default_campus_preset,
    load_single_canteen_preset,
)
from simulation.random_streams import build_random_streams


campus_bp = Blueprint('campus_api', __name__, url_prefix='/api/campus')

STEP_FLUSH_THRESHOLD = 50
FINISH_FLUSH_THRESHOLD = 500


def _session():
    """返回 routes.py 的共享 session，保证 monkeypatch 后仍读到同一个对象。"""
    return single_routes._session


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
        'interventions': state.get('interventions', []),
        'event_type': event_type,
    }


def _campus_buffer_count() -> int:
    return sum(1 for s in _session()['snapshot_buffer'] if 'campus_totals' in s)


def _flush_campus_snapshots():
    _session()['snapshot_buffer'] = flush_campus_snapshots(
        single_routes.DB_PATH,
        _session()['snapshot_buffer'],
    )


def _load_campus_history_rows(config_id: int | None = None) -> list[dict]:
    return load_campus_history_rows(single_routes.DB_PATH, config_id)


def _campus_history_snapshots() -> list[dict]:
    return campus_history_snapshots(
        single_routes.DB_PATH,
        _session()['config_id'],
        _session()['snapshot_buffer'],
    )


def _campus_history_for_analysis() -> list[dict]:
    return campus_history_for_analysis(
        single_routes.DB_PATH,
        _session()['config_id'],
        _session()['snapshot_buffer'],
    )


def _campus_statistics() -> dict:
    coordinator = _session()['coordinator']
    return build_campus_statistics(
        coordinator,
        _campus_history_snapshots(),
        _campus_history_for_analysis(),
    )


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
        'source_scale': preset['source_scale'],
        'demo_runtime': preset['demo_runtime'],
    })


@campus_bp.get('/presets/single-canteen')
def single_canteen_preset():
    preset = load_single_canteen_preset()
    return jsonify({
        'mode': 'campus',
        'config': preset['config'],
        'visible_canteens': preset['visible_canteens'],
        'pending_canteens': preset['pending_canteens'],
        'source_scale': preset['source_scale'],
        'demo_runtime': preset['demo_runtime'],
    })


@campus_bp.post('/config')
def submit_campus_config():
    if _session().get('mode') not in (None, 'campus'):
        return jsonify({'error': '切换模式前请先 reset 当前仿真'}), 400

    payload = request.get_json(silent=True) or {}
    error = validate_campus_config(payload)
    if error:
        return jsonify({'error': error}), 400

    summary = campus_config_summary(payload)
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

    rng_seed = payload['router'].get('rng_seed', 42)
    streams = build_random_streams(rng_seed)
    coordinator = CampusCoordinator(
        simpy.Environment(), payload, random.Random(rng_seed),
        random_streams=streams)
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
    return jsonify(start_campus_session(_session()))


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


@campus_bp.post('/canteens/<cid>/windows/<int:wid>/toggle')
def toggle_window(cid, wid):
    coordinator, error = _ensure_campus_initialized()
    if error is not None:
        return error
    open_ = bool((request.get_json(silent=True) or {}).get('open', True))
    state = toggle_window_intervention(
        coordinator,
        _session(),
        cid,
        wid,
        open_,
        _snapshot,
        _compact_snapshot,
        _flush_campus_snapshots,
    )
    return jsonify(state)


@campus_bp.post('/canteens/<cid>/floors/<int:floor_id>/windows/add')
def add_window(cid, floor_id):
    coordinator, error = _ensure_campus_initialized()
    if error is not None:
        return error
    state = add_window_intervention(
        coordinator,
        _session(),
        cid,
        floor_id,
        _snapshot,
        _compact_snapshot,
        _flush_campus_snapshots,
    )
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
    return jsonify(pause_campus_session(_session(), _flush_campus_snapshots))


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
    return jsonify(reset_campus_session(_session(), _flush_campus_snapshots))


@campus_bp.get('/statistics')
def campus_statistics():
    _, error = _ensure_campus_initialized()
    if error is not None:
        return error
    return jsonify(_campus_statistics())


@campus_bp.get('/history/configs')
def list_campus_history_configs():
    return jsonify(load_campus_history_configs(single_routes.DB_PATH))


@campus_bp.get('/history')
def get_campus_history():
    config_id = request.args.get('config_id', type=int)
    return jsonify(_load_campus_history_rows(config_id))
