"""REST API 路由集成测试 —— 用 Flask test_client 走完整流程。"""
import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    """每个测试一个独立的内存级 SQLite，且 _session 全新。"""
    db_path = tmp_path / 'test.db'
    import canteen.api.routes as routes
    monkeypatch.setattr(routes, 'DB_PATH', str(db_path))
    monkeypatch.setattr(routes, '_session', {
        'engine': None, 'config_id': None,
        'is_running': False, 'snapshot_buffer': [],
    })
    from canteen.app import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


CONFIG = {
    'window_count': 3, 'seat_count': 30, 'avg_serve_time': 15,
    'avg_eat_time': 5, 'arrival_rate': 20, 'total_time': 5,
}


def finish_single(client, config):
    assert client.post('/api/config', json=config).status_code == 200
    assert client.post('/api/simulation/start').status_code == 200
    return client.post('/api/simulation/finish').get_json()


class TestConfigEndpoint:
    def test_valid_config_accepted(self, client):
        r = client.post('/api/config', json=CONFIG)
        assert r.status_code == 200
        body = r.get_json()
        assert 'config_id' in body
        assert body['config']['window_count'] == 3

    def test_missing_field_rejected(self, client):
        bad = dict(CONFIG)
        del bad['window_count']
        r = client.post('/api/config', json=bad)
        assert r.status_code == 400
        assert '缺少参数' in r.get_json()['error']

    def test_negative_value_rejected(self, client):
        bad = dict(CONFIG)
        bad['arrival_rate'] = -1
        r = client.post('/api/config', json=bad)
        assert r.status_code == 400

    def test_config_forwards_optional_rng_seed(self, monkeypatch, client):
        captured = {}

        class CapturingEngine:
            def __init__(self, config, config_id=None, rng_seed=None):
                captured['rng_seed'] = rng_seed

        import canteen.api.routes as routes
        monkeypatch.setattr(routes, 'SimulationEngine', CapturingEngine)

        response = client.post('/api/config', json=dict(CONFIG, rng_seed=20260513))

        assert response.status_code == 200
        assert captured['rng_seed'] == 20260513

    def test_config_rejects_non_integer_rng_seed(self, client):
        response = client.post('/api/config', json=dict(CONFIG, rng_seed='bad-seed'))

        assert response.status_code == 400
        assert 'rng_seed' in response.get_json()['error']


class TestStartGuard:
    def test_first_start_runs(self, client):
        client.post('/api/config', json=CONFIG)
        r = client.post('/api/simulation/start').get_json()
        assert r['status'] == 'running'

    def test_repeated_start_does_not_pollute(self, client):
        client.post('/api/config', json=CONFIG)
        client.post('/api/simulation/start')
        r = client.post('/api/simulation/start').get_json()
        assert r.get('already_started') is True

    def test_start_without_config_400(self, client):
        r = client.post('/api/simulation/start')
        assert r.status_code == 400


class TestStep:
    def test_step_when_not_running_400(self, client):
        client.post('/api/config', json=CONFIG)
        # 还没 start 就 step
        r = client.get('/api/simulation/step')
        assert r.status_code == 400

    def test_step_returns_state(self, client):
        client.post('/api/config', json=CONFIG)
        client.post('/api/simulation/start')
        r = client.get('/api/simulation/step').get_json()
        assert 'current_time' in r
        assert 'windows' in r
        assert 'seats' in r
        assert 'students' in r


class TestFinish:
    def test_finish_returns_complete_stats(self, client):
        client.post('/api/config', json=CONFIG)
        client.post('/api/simulation/start')
        r = client.post('/api/simulation/finish').get_json()
        assert r['total_arrived'] == r['total_served']
        assert r['total_arrived'] > 0
        assert 0 <= r['seat_utilization'] <= 100
        assert 'fast_forward_steps' in r

    def test_finish_without_config_400(self, client):
        r = client.post('/api/simulation/finish')
        assert r.status_code == 400

    def test_same_seed_api_runs_are_reproducible(self, client):
        config = dict(CONFIG, rng_seed=20260513)

        a = finish_single(client, config)
        client.post('/api/simulation/reset')
        b = finish_single(client, config)

        assert a['total_arrived'] == b['total_arrived']
        assert a['total_served'] == b['total_served']
        assert a['avg_waiting_time'] == b['avg_waiting_time']


class TestHistory:
    def test_history_configs_endpoint(self, client):
        client.post('/api/config', json=CONFIG)
        client.post('/api/simulation/start')
        client.post('/api/simulation/finish')
        h = client.get('/api/history/configs').get_json()
        assert len(h) >= 1
        record = h[0]
        assert record['snapshot_count'] > 0
        assert record['total_arrived'] == record['total_served']

    def test_history_snapshots_endpoint(self, client):
        cfg_resp = client.post('/api/config', json=CONFIG).get_json()
        client.post('/api/simulation/start')
        client.post('/api/simulation/finish')
        snaps = client.get(f'/api/history?config_id={cfg_resp["config_id"]}').get_json()
        assert len(snaps) > 0
        assert snaps[0]['config_id'] == cfg_resp['config_id']
        # 时间应该单调递增
        times = [s['current_time'] for s in snaps]
        assert times == sorted(times)


class TestReset:
    def test_reset_clears_engine(self, client):
        client.post('/api/config', json=CONFIG)
        client.post('/api/simulation/start')
        client.post('/api/simulation/reset')
        s = client.get('/api/simulation/status').get_json()
        assert s['initialized'] is False
