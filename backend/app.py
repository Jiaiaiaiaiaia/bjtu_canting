from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sqlite3
import json
import os

app = Flask(__name__, template_folder='../frontend/templates', static_folder='../frontend/static')
CORS(app)

# 数据库初始化
def init_db():
    conn = sqlite3.connect('simulation.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS simulation_config (
                    id INTEGER PRIMARY KEY,
                    window_count INTEGER NOT NULL,
                    seat_count INTEGER NOT NULL,
                    avg_serve_time REAL NOT NULL,
                    avg_eat_time REAL NOT NULL,
                    arrival_rate REAL NOT NULL,
                    total_time INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS simulation_snapshot (
                    id INTEGER PRIMARY KEY,
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
    conn.close()

init_db()

# 全局变量存储仿真状态
simulation_state = {
    'is_running': False,
    'current_time': 0,
    'config': None,
    'windows': [],
    'seats': [],
    'students': [],
    'event_queue': [],
    'total_arrived': 0,
    'total_served': 0
}

# 导入仿真模块
from simulation.simulation_engine import SimulationEngine
sim_engine = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/config', methods=['POST'])
def set_config():
    global simulation_state, sim_engine
    config = request.json
    
    # 验证参数
    required_fields = ['window_count', 'seat_count', 'avg_serve_time', 'avg_eat_time', 'arrival_rate', 'total_time']
    for field in required_fields:
        if field not in config:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # 保存配置到数据库
    conn = sqlite3.connect('simulation.db')
    c = conn.cursor()
    c.execute('''INSERT INTO simulation_config 
                (window_count, seat_count, avg_serve_time, avg_eat_time, arrival_rate, total_time)
                VALUES (?, ?, ?, ?, ?, ?)''', 
                (config['window_count'], config['seat_count'], config['avg_serve_time'], 
                 config['avg_eat_time'], config['arrival_rate'], config['total_time']))
    config_id = c.lastrowid
    conn.commit()
    conn.close()
    
    # 初始化仿真引擎
    simulation_state['config'] = config
    simulation_state['config_id'] = config_id
    sim_engine = SimulationEngine(config)
    
    return jsonify({'message': 'Configuration saved successfully', 'config_id': config_id})

@app.route('/api/simulation/start', methods=['POST'])
def start_simulation():
    global simulation_state, sim_engine
    if not sim_engine:
        return jsonify({'error': 'Simulation not configured'}), 400
    
    simulation_state['is_running'] = True
    sim_engine.start()
    
    return jsonify({'message': 'Simulation started', 'status': 'running'})

@app.route('/api/simulation/step', methods=['GET'])
def step_simulation():
    global simulation_state, sim_engine
    if not sim_engine or not simulation_state['is_running']:
        return jsonify({'error': 'Simulation not running'}), 400
    
    # 执行一步仿真
    state = sim_engine.step()
    if state['is_ended']:
        simulation_state['is_running'] = False
    
    return jsonify(state)

@app.route('/api/simulation/status', methods=['GET'])
def get_simulation_status():
    global simulation_state
    return jsonify({
        'is_running': simulation_state['is_running'],
        'current_time': simulation_state.get('current_time', 0)
    })

@app.route('/api/simulation/pause', methods=['POST'])
def pause_simulation():
    global simulation_state
    simulation_state['is_running'] = False
    return jsonify({'message': 'Simulation paused'})

@app.route('/api/simulation/reset', methods=['POST'])
def reset_simulation():
    global simulation_state, sim_engine
    simulation_state = {
        'is_running': False,
        'current_time': 0,
        'config': None,
        'windows': [],
        'seats': [],
        'students': [],
        'event_queue': [],
        'total_arrived': 0,
        'total_served': 0
    }
    sim_engine = None
    return jsonify({'message': 'Simulation reset'})

@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    global sim_engine
    if not sim_engine:
        return jsonify({'error': 'No simulation data available'}), 400
    
    stats = sim_engine.get_statistics()
    return jsonify(stats)

@app.route('/api/history', methods=['GET'])
def get_history():
    conn = sqlite3.connect('simulation.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM simulation_snapshot ORDER BY current_time')
    snapshots = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(snapshots)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
