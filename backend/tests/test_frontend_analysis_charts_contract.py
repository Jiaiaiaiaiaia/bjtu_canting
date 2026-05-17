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


def test_analysis_page_has_intervention_effect_panel():
    for snippet in (
        'id="intervention-effect-panel"',
        'id="intervention-effect-summary"',
        'id="intervention-effect-list"',
        '干预效果',
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


def test_analysis_page_styles_intervention_effect_panel():
    for snippet in (
        '.intervention-effect-panel',
        '.intervention-effect-list',
        '.intervention-effect-card',
        '.intervention-effect-card.improved',
        '.intervention-effect-card.worse',
        '.intervention-effect-card.rejected',
    ):
        assert snippet in STYLE_CSS


def test_analysis_page_has_scenario_comparison_panel():
    for snippet in (
        'id="scenario-panel"',
        'id="scenario-run-btn"',
        'id="scenario-status"',
        'id="scenario-seed"',
        'id="scenario-comparison"',
        'id="scenario-adjustment"',
        'id="scenario-baseline-wait"',
        'id="scenario-adjusted-wait"',
        'id="scenario-delta-wait"',
        'id="scenario-baseline-peak"',
        'id="scenario-adjusted-peak"',
        'id="scenario-delta-peak"',
        'id="scenario-baseline-seat"',
        'id="scenario-adjusted-seat"',
        'id="scenario-delta-seat"',
    ):
        assert snippet in INDEX_HTML


def test_analysis_page_styles_scenario_comparison():
    for snippet in (
        '.scenario-panel',
        '.scenario-header',
        '.scenario-comparison',
        '.scenario-row',
        '.scenario-delta',
        '.scenario-adjustment',
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


def test_analysis_charts_builds_intervention_effect_from_statistics():
    for snippet in (
        'function buildInterventionEffects(stats)',
        'function renderInterventionEffects(stats, deps)',
        'stats.intervention_analysis',
        'intervention-effect-summary',
        'intervention-effect-list',
        'renderInterventionEffects(stats, deps);',
        'buildInterventionEffects,',
        'renderInterventionEffects,',
    ):
        assert snippet in ANALYSIS_CHARTS_JS


def test_analysis_charts_builds_scenario_helpers_from_existing_statistics():
    for snippet in (
        'function buildSuggestedSingleConfig(config, stats)',
        'function buildScenarioComparison(baselineStats, adjustedStats)',
        'function renderScenarioComparison(baselineStats, adjustedStats, summary, deps)',
        'window_count',
        'seat_count',
        'avg_serve_time',
        'avg_eat_time',
        'scenario-baseline-wait',
        'scenario-adjusted-wait',
        'buildSuggestedSingleConfig,',
        'buildScenarioComparison,',
        'renderScenarioComparison,',
    ):
        assert snippet in ANALYSIS_CHARTS_JS


def test_analysis_page_replaces_low_signal_chart_grid_with_evidence_panels():
    for snippet in (
        'class="analysis-evidence-grid"',
        'id="timeline-insight"',
        'id="timeline-badge"',
        'id="window-balance-summary"',
        'id="window-balance-badge"',
        'id="seat-trend-summary"',
        'id="service-concentration-summary"',
    ):
        assert snippet in INDEX_HTML

    assert '<h3>窗口服务占比</h3>' not in INDEX_HTML
    assert '<h3>各窗口服务人数</h3>' not in INDEX_HTML
    assert '<h3>拥堵时间线</h3>' in INDEX_HTML
    assert '<h3>窗口负载排名</h3>' in INDEX_HTML


def test_analysis_page_styles_evidence_panels():
    for snippet in (
        '.analysis-evidence-grid',
        '.analysis-evidence-card',
        '.analysis-card-main',
        '.analysis-card-header',
        '.analysis-card-summary',
        '.analysis-badge',
        '.analysis-timeline-chart',
        '.analysis-rank-chart',
        '.analysis-compact-chart',
    ):
        assert snippet in STYLE_CSS


def test_window_service_distribution_avoids_misleading_utilization_pie():
    assert '<h3>窗口利用率</h3>' not in INDEX_HTML
    assert "type: 'pie'" not in ANALYSIS_CHARTS_JS
    assert 'function buildWindowServiceShare(windowSeries, limit = 6)' in ANALYSIS_CHARTS_JS
    assert 'buildWindowServiceShare,' in ANALYSIS_CHARTS_JS


def test_analysis_charts_builds_story_helpers_from_existing_statistics():
    for snippet in (
        'function buildTimelineInsight(stats)',
        'function buildWindowLoadInsight(windowSeries)',
        'function buildSeatTrendInsight(stats)',
        'function renderAnalysisNarrative(stats, windowSeries, deps)',
        'buildTimelineInsight,',
        'buildWindowLoadInsight,',
        'buildSeatTrendInsight,',
        'renderAnalysisNarrative,',
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


def build_intervention_effects(stats):
    script = f"""
global.window = {{ CanteenApp: {{}} }};
{ANALYSIS_CHARTS_JS}
const effects = window.CanteenApp.AnalysisCharts.buildInterventionEffects({json.dumps(stats)});
console.log(JSON.stringify(effects));
"""
    completed = subprocess.run(
        ['node', '-e', script],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def build_suggested_config(config, stats):
    script = f"""
global.window = {{ CanteenApp: {{}} }};
{ANALYSIS_CHARTS_JS}
const suggestion = window.CanteenApp.AnalysisCharts.buildSuggestedSingleConfig(
  {json.dumps(config)},
  {json.dumps(stats)}
);
console.log(JSON.stringify(suggestion));
"""
    completed = subprocess.run(
        ['node', '-e', script],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def build_scenario_comparison(baseline, adjusted):
    script = f"""
global.window = {{ CanteenApp: {{}} }};
{ANALYSIS_CHARTS_JS}
const comparison = window.CanteenApp.AnalysisCharts.buildScenarioComparison(
  {json.dumps(baseline)},
  {json.dumps(adjusted)}
);
console.log(JSON.stringify(comparison));
"""
    completed = subprocess.run(
        ['node', '-e', script],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def build_window_service_share(window_served, limit):
    script = f"""
global.window = {{ CanteenApp: {{}} }};
{ANALYSIS_CHARTS_JS}
const windowSeries = window.CanteenApp.AnalysisCharts.normalizeWindowServed(
  {json.dumps(window_served)}
);
const share = window.CanteenApp.AnalysisCharts.buildWindowServiceShare(
  windowSeries,
  {limit}
);
console.log(JSON.stringify(share));
"""
    completed = subprocess.run(
        ['node', '-e', script],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def build_timeline_insight(stats):
    script = f"""
global.window = {{ CanteenApp: {{}} }};
{ANALYSIS_CHARTS_JS}
const insight = window.CanteenApp.AnalysisCharts.buildTimelineInsight({json.dumps(stats)});
console.log(JSON.stringify(insight));
"""
    completed = subprocess.run(
        ['node', '-e', script],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def build_window_load_insight(window_served):
    script = f"""
global.window = {{ CanteenApp: {{}} }};
{ANALYSIS_CHARTS_JS}
const windowSeries = window.CanteenApp.AnalysisCharts.normalizeWindowServed(
  {json.dumps(window_served)}
);
const insight = window.CanteenApp.AnalysisCharts.buildWindowLoadInsight(windowSeries);
console.log(JSON.stringify(insight));
"""
    completed = subprocess.run(
        ['node', '-e', script],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def build_seat_trend_insight(stats):
    script = f"""
global.window = {{ CanteenApp: {{}} }};
{ANALYSIS_CHARTS_JS}
const insight = window.CanteenApp.AnalysisCharts.buildSeatTrendInsight({json.dumps(stats)});
console.log(JSON.stringify(insight));
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
    assert '跨食堂' not in seat_pressure['summary']


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


def test_intervention_effects_summarize_deduped_backend_events():
    effects = build_intervention_effects({
        'intervention_analysis': {
            'summary': '已记录 3 次窗口干预，2 次生效，1 次拒绝。',
            'events': [
                {
                    'time': 120,
                    'floor_id': 2,
                    'window_id': 6,
                    'action': 'open',
                    'status': 'applied',
                    'verdict': 'improved',
                    'open_window_delta': 1,
                    'avg_queue_delta': -8.5,
                    'summary': '增开窗口后平均排队下降 8.5 人。',
                },
                {
                    'time': 180,
                    'floor_id': 1,
                    'window_id': 0,
                    'action': 'close',
                    'status': 'rejected',
                    'verdict': 'rejected',
                    'open_window_delta': 0,
                    'avg_queue_delta': 0,
                    'summary': '关窗被拒绝：cannot close last open window。',
                },
                {
                    'time': 240,
                    'floor_id': 3,
                    'window_id': 35,
                    'action': 'add',
                    'status': 'applied',
                    'verdict': 'neutral',
                    'open_window_delta': 1,
                    'avg_queue_delta': 0,
                    'summary': '添加窗口后开放窗口 +1，平均排队基本持平。',
                },
            ],
        },
    })

    assert effects['summary'].startswith('已记录 3 次窗口干预')
    assert effects['items'][0]['title'] == '2F 窗6 增开窗口'
    assert effects['items'][0]['tone'] == 'improved'
    assert '平均排队下降' in effects['items'][0]['impact']
    assert effects['items'][1]['tone'] == 'rejected'
    assert effects['items'][2]['title'] == '3F 窗35 添加窗口'


def test_suggested_single_config_adjusts_dominant_pressure_only():
    base_config = {
        'window_count': 4,
        'seat_count': 100,
        'avg_serve_time': 30,
        'avg_eat_time': 15,
        'arrival_rate': 5,
        'total_time': 60,
    }

    queue_suggestion = build_suggested_config(base_config, {
        'total_arrived': 100,
        'total_served': 100,
        'peak_queue_length': 35,
        'avg_waiting_time': 140,
        'seat_utilization': 50,
    })
    assert queue_suggestion['config']['window_count'] > base_config['window_count']
    assert queue_suggestion['config']['seat_count'] == base_config['seat_count']
    assert '窗口' in queue_suggestion['summary']

    seat_suggestion = build_suggested_config(base_config, {
        'total_arrived': 80,
        'total_served': 80,
        'peak_queue_length': 2,
        'avg_waiting_time': 15,
        'seat_utilization': 91,
    })
    assert seat_suggestion['config']['seat_count'] > base_config['seat_count']
    assert seat_suggestion['config']['window_count'] == base_config['window_count']
    assert '座位' in seat_suggestion['summary']

    low_suggestion = build_suggested_config(base_config, {
        'total_arrived': 30,
        'total_served': 30,
        'peak_queue_length': 1,
        'avg_waiting_time': 8,
        'seat_utilization': 34,
    })
    assert low_suggestion['config'] is None


def test_scenario_comparison_reports_metric_deltas():
    comparison = build_scenario_comparison(
        {
            'avg_waiting_time': 120,
            'peak_queue_length': 30,
            'seat_utilization': 90,
        },
        {
            'avg_waiting_time': 75,
            'peak_queue_length': 12,
            'seat_utilization': 64,
        },
    )
    by_key = {item['key']: item for item in comparison}
    assert by_key['wait']['delta'] == '-45.0 s'
    assert by_key['peak']['delta'] == '-18'
    assert by_key['seat']['delta'] == '-26.0%'
    assert by_key['wait']['tone'] == 'improved'


def test_window_service_share_sorts_and_groups_small_windows():
    share = build_window_service_share([20, 5, 0, 11, 9, 8], 3)

    assert [item['name'] for item in share] == ['窗口 1', '窗口 4', '窗口 5', '其余窗口']
    assert [item['rawValue'] for item in share] == [20, 11, 9, 13]
    assert [item['value'] for item in share] == [37.7, 20.8, 17.0, 24.5]


def test_story_helpers_summarize_timeline_window_balance_and_seat_trend():
    timeline = build_timeline_insight({
        'total_arrived': 100,
        'peak_queue_length': 35,
        'avg_waiting_time': 95,
        'queue_timeline': {'x': [0, 5, 10], 'y': [0, 35, 6]},
        'seat_util_timeline': {'x': [0, 5, 10], 'y': [20, 91, 62]},
    })
    assert timeline['badge'] == '高峰 5 分'
    assert '峰值排队 35 人' in timeline['summary']
    assert '座位最高 91.0%' in timeline['summary']

    load = build_window_load_insight([50, 45, 10, 5, 0])
    assert load['badge'] == '负载不均'
    assert load['top'][0]['name'] == '窗口 1'
    assert load['bottom'][0]['name'] == '窗口 5'
    assert '窗口 1' in load['summary']

    seat = build_seat_trend_insight({
        'seat_utilization': 88,
        'seat_util_timeline': {'x': [0, 5, 10], 'y': [10, 88, 74]},
    })
    assert seat['badge'] == '座位紧张'
    assert '最高 88.0%' in seat['summary']
