"""数据分析页拥堵诊断面板契约测试。"""
import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = (REPO_ROOT / 'frontend' / 'templates' / 'index.html').read_text(encoding='utf-8')
STYLE_CSS = (REPO_ROOT / 'frontend' / 'static' / 'css' / 'style.css').read_text(encoding='utf-8')
ANALYSIS_CHARTS_JS = (
    REPO_ROOT / 'frontend' / 'static' / 'js' / 'analysis_charts.js'
).read_text(encoding='utf-8')


def test_analysis_page_has_congestion_diagnosis_panel():
    for snippet in (
        'id="diagnosis-panel"',
        'id="diagnosis-level"',
        'id="diagnosis-bottleneck"',
        'id="diagnosis-peak-time"',
        'id="diagnosis-action"',
        'id="diagnosis-summary"',
    ):
        assert snippet in INDEX_HTML


def test_analysis_page_styles_diagnosis_panel_as_first_class_section():
    for snippet in (
        '.diagnosis-panel',
        '.diagnosis-header',
        '.diagnosis-grid',
        '.diagnosis-level',
        '.diagnosis-summary',
    ):
        assert snippet in STYLE_CSS


def test_analysis_page_has_intervention_recommendation_panel():
    for snippet in (
        'id="intervention-panel"',
        'id="intervention-list"',
        'id="intervention-summary"',
    ):
        assert snippet in INDEX_HTML


def test_analysis_page_styles_intervention_recommendations():
    for snippet in (
        '.intervention-panel',
        '.intervention-list',
        '.intervention-card',
        '.intervention-tag',
        '.intervention-impact',
    ):
        assert snippet in STYLE_CSS


def test_analysis_charts_builds_diagnosis_from_existing_statistics():
    for snippet in (
        'function buildDiagnosis(stats)',
        'function renderDiagnosis(stats, deps)',
        'stats.peak_queue_length',
        'stats.avg_waiting_time',
        'stats.seat_utilization',
        'stats.queue_timeline',
        'renderDiagnosis(stats, deps);',
        'buildDiagnosis,',
        'renderDiagnosis,',
    ):
        assert snippet in ANALYSIS_CHARTS_JS


def test_analysis_charts_builds_interventions_from_existing_statistics():
    for snippet in (
        'function buildInterventions(stats)',
        'function renderInterventions(stats, deps)',
        'stats.peak_queue_length',
        'stats.avg_waiting_time',
        'stats.seat_utilization',
        'renderInterventions(stats, deps);',
        'buildInterventions,',
        'renderInterventions,',
    ):
        assert snippet in ANALYSIS_CHARTS_JS


def build_diagnosis(stats):
    script = f"""
global.window = {{ CanteenApp: {{}} }};
{ANALYSIS_CHARTS_JS}
const diagnosis = window.CanteenApp.AnalysisCharts.buildDiagnosis({json.dumps(stats)});
console.log(JSON.stringify(diagnosis));
"""
    completed = subprocess.run(
        ['node', '-e', script],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def build_interventions(stats):
    script = f"""
global.window = {{ CanteenApp: {{}} }};
{ANALYSIS_CHARTS_JS}
const interventions = window.CanteenApp.AnalysisCharts.buildInterventions({json.dumps(stats)});
console.log(JSON.stringify(interventions));
"""
    completed = subprocess.run(
        ['node', '-e', script],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_diagnosis_rules_classify_queue_and_seat_pressure():
    idle = build_diagnosis({})
    assert idle['level'] == '待仿真'
    assert idle['bottleneck'] == '暂无样本'

    queue_pressure = build_diagnosis({
        'total_arrived': 100,
        'total_served': 96,
        'peak_queue_length': 35,
        'avg_waiting_time': 140,
        'seat_utilization': 50,
        'queue_timeline': {'x': [0, 1, 2], 'y': [4, 35, 12]},
    })
    assert queue_pressure['level'] == '高拥堵'
    assert queue_pressure['bottleneck'] == '窗口排队压力'
    assert queue_pressure['peakTime'] == '1 分'
    assert '仍有 4 人未完成服务' in queue_pressure['summary']

    seat_pressure = build_diagnosis({
        'total_arrived': 60,
        'total_served': 60,
        'peak_queue_length': 2,
        'avg_waiting_time': 15,
        'seat_utilization': 91,
        'queue_timeline': {'x': [0, 1], 'y': [0, 2]},
        'switch_rate': 0.25,
    })
    assert seat_pressure['level'] == '高拥堵'
    assert seat_pressure['bottleneck'] == '座位周转压力'
    assert '跨食堂改派率 25.0%' in seat_pressure['summary']


def test_intervention_rules_recommend_action_for_dominant_pressure():
    idle = build_interventions({})
    assert idle[0]['title'] == '先完成一次仿真'

    queue_pressure = build_interventions({
        'total_arrived': 100,
        'total_served': 100,
        'peak_queue_length': 35,
        'avg_waiting_time': 140,
        'seat_utilization': 50,
    })
    assert queue_pressure[0]['title'] == '增开服务窗口'
    assert '平均等待' in queue_pressure[0]['impact']

    seat_pressure = build_interventions({
        'total_arrived': 80,
        'total_served': 80,
        'peak_queue_length': 2,
        'avg_waiting_time': 15,
        'seat_utilization': 91,
    })
    assert seat_pressure[0]['title'] == '增加座位供给'
    assert '座位利用率' in seat_pressure[0]['impact']

    low_pressure = build_interventions({
        'total_arrived': 30,
        'total_served': 30,
        'peak_queue_length': 1,
        'avg_waiting_time': 8,
        'seat_utilization': 34,
    })
    assert low_pressure[0]['title'] == '保持当前配置'
