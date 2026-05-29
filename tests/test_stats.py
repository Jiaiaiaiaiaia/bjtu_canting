"""A.5.1 CampusStats 单元测试（共 5 条）。"""
from canteen.simulation.stats import CampusStats
from canteen.simulation.student import Student


def make_student(*, wait_time=0.0, walk_time=0.0, switch_count=0) -> Student:
    """轻量学生 fixture。"""
    return Student(
        id=1, state="left",
        wait_time=wait_time,
        walk_time=walk_time,
        switch_count=switch_count,
    )


# 1. 空 stats avg_waiting_time 返回 0
def test_avg_waiting_time_empty_returns_zero():
    s = CampusStats()
    assert s.avg_waiting_time() == 0.0


# 2. record_wait 后 avg 正确
def test_record_wait_then_avg():
    s = CampusStats()
    s.record_wait(make_student(wait_time=120))
    s.record_wait(make_student(wait_time=180))
    assert s.avg_waiting_time() == 150.0


# 3. record_completion 后 avg_walk_time 正确
def test_avg_walk_time_after_completion():
    s = CampusStats()
    s.record_completion(make_student(walk_time=60))
    s.record_completion(make_student(walk_time=120))
    assert s.avg_walk_time() == 90.0


# 4. 没切换的学生 → switch_rate = 0
def test_switch_rate_zero_when_no_switches():
    s = CampusStats()
    s.record_completion(make_student(switch_count=0))
    s.record_completion(make_student(switch_count=0))
    assert s.switch_rate() == 0.0


# 5. 部分学生有切换 → switch_rate 正确（分母为已完成样本数）
def test_switch_rate_counts_at_least_one_switch():
    s = CampusStats()
    s.record_completion(make_student(switch_count=0))
    s.record_completion(make_student(switch_count=1))
    s.record_completion(make_student(switch_count=2))
    # 3 个学生中 2 个有切换 → 2/3
    assert abs(s.switch_rate() - 2/3) < 0.01
