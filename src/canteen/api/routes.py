"""REST API 路由 —— 对外暴露仿真控制与数据查询接口。"""
import json
import os
import sqlite3

from flask import Blueprint, jsonify, request

from canteen.simulation import SimulationEngine
from canteen.paths import DB_PATH
from .db_migrate import migrate


api_bp = Blueprint('api', __name__, url_prefix='/api')

# 单仿真会话：课程实训演示场景下仅需一个活跃引擎
_session = {
    'mode': None,
    'engine': None,
    'coordinator': None,
    'config_id': None,
    'is_running': False,
    'snapshot_buffer': [],
}

REQUIRED_FIELDS = (
    'window_count', 'seat_count', 'avg_serve_time',
    'avg_eat_time', 'arrival_rate', 'total_time',
)


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS simulation_config (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        window_count INTEGER NOT NULL,
                        seat_count INTEGER NOT NULL,
                        avg_serve_time REAL NOT NULL,
                        avg_eat_time REAL NOT NULL,
                        arrival_rate REAL NOT NULL,
                        total_time INTEGER NOT NULL,
                        mode TEXT DEFAULT 'single',
                        campus_config_json TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )''')
        c.execute('''CREATE TABLE IF NOT EXISTS simulation_snapshot (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        config_id INTEGER,
                        current_time REAL NOT NULL,
                        total_arrived INTEGER,
                        total_served INTEGER,
                        total_in_queue INTEGER,
                        total_eating INTEGER,
                        empty_seats INTEGER,
                        queue_details TEXT,
                        event_type TEXT,
                        FOREIGN KEY (config_id) REFERENCES simulation_config (id)
                    )''')
        conn.commit()
    migrate(DB_PATH)


def _validate_config(config):
    for field in REQUIRED_FIELDS:
        if field not in config:
            return f'缺少参数：{field}'
    try:
        if int(config['window_count']) <= 0:
            return '窗口数量必须大于 0'
        if int(config['seat_count']) <= 0:
            return '座位数必须大于 0'
        if float(config['avg_serve_time']) <= 0:
            return '打饭时长必须大于 0'
        if float(config['avg_eat_time']) <= 0:
            return '就餐时长必须大于 0'
        if float(config['arrival_rate']) <= 0:
            return '到达率必须大于 0'
        if int(config['total_time']) <= 0:
            return '仿真时长必须大于 0'
    except (TypeError, ValueError):
        return '参数类型错误'
    return None


def _flush_snapshots():
    """批量写入缓冲区快照到数据库。"""
    buf = _session['snapshot_buffer']
    if not buf:
        return
    single_snapshots = [s for s in buf if 'queue_details' in s]
    if not single_snapshots:
        return
    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany(
            '''INSERT INTO simulation_snapshot
               (config_id, current_time, total_arrived, total_served,
                total_in_queue, total_eating, empty_seats, queue_details, event_type)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            [(s['config_id'], s['current_time'], s['total_arrived'], s['total_served'],
              s['total_in_queue'], s['total_eating'], s['empty_seats'],
              json.dumps(s['queue_details'], ensure_ascii=False), s['event_type'])
             for s in single_snapshots]
        )
        conn.commit()
    _session['snapshot_buffer'] = [s for s in buf if 'queue_details' not in s]


@api_bp.post('/config')
def submit_config():
    if _session.get('mode') not in (None, 'single'):
        return jsonify({'error': '切换模式前请先 reset 当前仿真'}), 400

    payload = request.get_json(silent=True) or {}
    error = _validate_config(payload)
    if error:
        return jsonify({'error': error}), 400

    config = {
        'window_count': int(payload['window_count']),
        'seat_count': int(payload['seat_count']),
        'avg_serve_time': float(payload['avg_serve_time']),
        'avg_eat_time': float(payload['avg_eat_time']),
        'arrival_rate': float(payload['arrival_rate']),
        'total_time': int(payload['total_time']),
    }
    rng_seed = payload.get('rng_seed')
    if rng_seed is not None:
        try:
            rng_seed = int(rng_seed)
        except (TypeError, ValueError):
            return jsonify({'error': 'rng_seed 必须是整数'}), 400

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            '''INSERT INTO simulation_config
               (window_count, seat_count, avg_serve_time, avg_eat_time,
                arrival_rate, total_time, mode)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (config['window_count'], config['seat_count'], config['avg_serve_time'],
             config['avg_eat_time'], config['arrival_rate'], config['total_time'],
             'single')
        )
        config_id = cur.lastrowid
        conn.commit()

    _session['mode'] = 'single'
    _session['engine'] = SimulationEngine(config, config_id=config_id, rng_seed=rng_seed)
    _session['coordinator'] = None
    _session['config_id'] = config_id
    _session['is_running'] = False
    _session['snapshot_buffer'] = []
    return jsonify({
        'message': '配置已保存',
        'mode': 'single',
        'config_id': config_id,
        'config': config,
    })


@api_bp.post('/simulation/start')
def start_simulation():
    engine = _session['engine']
    if engine is None:
        return jsonify({'error': '请先提交仿真配置'}), 400
    if engine._is_started:
        # 防止重复 start 再次预生成到达事件，污染已有队列
        _session['is_running'] = True
        return jsonify({
            'message': '仿真已在运行',
            'mode': 'single',
            'status': 'running',
            'already_started': True,
        })
    engine.start()
    _session['is_running'] = True
    return jsonify({'message': '仿真已启动', 'mode': 'single', 'status': 'running'})


@api_bp.get('/simulation/step')
def step_simulation():
    engine = _session['engine']
    if engine is None:
        return jsonify({'error': '仿真尚未初始化'}), 400
    if not _session['is_running']:
        return jsonify({'error': '仿真未运行'}), 400

    state = engine.step()
    snapshot = engine.history[-1] if engine.history else None
    if snapshot is not None:
        _session['snapshot_buffer'].append(snapshot)
        if len(_session['snapshot_buffer']) >= 50 or state['is_ended']:
            _flush_snapshots()

    if state['is_ended']:
        _session['is_running'] = False
        _flush_snapshots()
    return jsonify(state)


@api_bp.get('/simulation/status')
def simulation_status():
    engine = _session['engine']
    if engine is None:
        return jsonify({
            'mode': _session.get('mode'),
            'is_running': False,
            'initialized': False,
        })
    return jsonify({
        'mode': 'single',
        'is_running': _session['is_running'],
        'initialized': True,
        'current_time': engine.current_time,
        'total_time': engine.total_time,
        'total_arrived': engine.total_arrived,
        'total_served': engine.total_served,
    })


@api_bp.post('/simulation/pause')
def pause_simulation():
    _session['is_running'] = False
    _flush_snapshots()
    return jsonify({'message': '仿真已暂停'})


@api_bp.post('/simulation/finish')
def finish_simulation():
    """一次性把剩余事件跑完并落库，返回最终统计。

    前端的"结束仿真"按钮应调用本接口，而不是 pause，以保证老师看到的是完整统计。
    """
    engine = _session['engine']
    if engine is None:
        return jsonify({'error': '仿真尚未初始化'}), 400
    if not engine._is_started:
        engine.start()

    # 最多跑 200 万次事件，避免异常情况下死循环
    MAX_STEPS = 2_000_000
    steps = 0
    while not engine._is_ended and steps < MAX_STEPS:
        state = engine.step()
        snapshot = engine.history[-1] if engine.history else None
        if snapshot is not None:
            _session['snapshot_buffer'].append(snapshot)
            # 大批量事件时分段落库，避免内存暴涨
            if len(_session['snapshot_buffer']) >= 500:
                _flush_snapshots()
        steps += 1
        if state['is_ended']:
            break

    _session['is_running'] = False
    _flush_snapshots()
    stats = engine.get_statistics()
    stats['fast_forward_steps'] = steps
    return jsonify(stats)


@api_bp.post('/simulation/reset')
def reset_simulation():
    _flush_snapshots()
    _session['mode'] = None
    _session['engine'] = None
    _session['coordinator'] = None
    _session['config_id'] = None
    _session['is_running'] = False
    _session['snapshot_buffer'] = []
    return jsonify({'message': '仿真已重置'})


@api_bp.get('/statistics')
def get_statistics():
    engine = _session['engine']
    if engine is None:
        return jsonify({'error': '暂无仿真数据'}), 400
    return jsonify(engine.get_statistics())


@api_bp.get('/history/configs')
def list_history_configs():
    """列出所有历史配置，并附带对应快照的汇总信息（最大 total_arrived/total_served）。"""
    query = (
        '''SELECT c.id, c.window_count, c.seat_count, c.avg_serve_time,
                  c.avg_eat_time, c.arrival_rate, c.total_time, c.created_at,
                  (SELECT MAX(total_arrived) FROM simulation_snapshot s WHERE s.config_id = c.id) AS total_arrived,
                  (SELECT MAX(total_served) FROM simulation_snapshot s WHERE s.config_id = c.id) AS total_served,
                  (SELECT COUNT(*) FROM simulation_snapshot s WHERE s.config_id = c.id) AS snapshot_count
           FROM simulation_config c
           ORDER BY c.created_at DESC'''
    )
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query).fetchall()
    return jsonify([dict(row) for row in rows])


@api_bp.get('/history')
def get_history():
    config_id = request.args.get('config_id', type=int)
    query = 'SELECT * FROM simulation_snapshot'
    params = ()
    if config_id is not None:
        query += ' WHERE config_id = ?'
        params = (config_id,)
    query += ' ORDER BY current_time'

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
    snapshots = []
    for row in rows:
        item = dict(row)
        if item.get('queue_details'):
            try:
                item['queue_details'] = json.loads(item['queue_details'])
            except (TypeError, ValueError):
                pass
        snapshots.append(item)
    return jsonify(snapshots)
