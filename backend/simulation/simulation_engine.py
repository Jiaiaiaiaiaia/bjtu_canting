import random
import heapq
import json
import sqlite3

class Student:
    def __init__(self, id, arrival_time):
        self.id = id
        self.arrival_time = arrival_time
        self.start_service_time = None
        self.end_service_time = None
        self.start_eat_time = None
        self.end_eat_time = None
        self.window_id = None
        self.seat_id = None

class Window:
    def __init__(self, id, avg_serve_time):
        self.id = id
        self.queue = []
        self.avg_serve_time = avg_serve_time
        self.current_serving = None
        self.total_served = 0

class Seat:
    def __init__(self, id):
        self.id = id
        self.status = 'empty'  # empty or occupied
        self.student = None
        self.remaining_time = 0

class Event:
    def __init__(self, event_time, event_type, student=None, window=None, seat=None):
        self.event_time = event_time
        self.event_type = event_type  # arrival, service_end, eat_end
        self.student = student
        self.window = window
        self.seat = seat
    
    def __lt__(self, other):
        return self.event_time < other.event_time

class SimulationEngine:
    def __init__(self, config):
        self.config = config
        self.current_time = 0
        self.total_time = config['total_time'] * 60  # 转换为秒
        self.windows = [Window(i, config['avg_serve_time']) for i in range(config['window_count'])]
        self.seats = [Seat(i) for i in range(config['seat_count'])]
        self.students = []
        self.event_queue = []
        self.total_arrived = 0
        self.total_served = 0
        self.waiting_queue = []  # 等待座位的队列
        self.snapshots = []
        self.config_id = None
    
    def start(self):
        # 生成初始到达事件
        self.generate_arrival_events()
    
    def generate_arrival_events(self):
        # 基于泊松过程生成到达事件
        time = 0
        while time < self.total_time:
            # 泊松过程的时间间隔服从指数分布
            inter_arrival_time = random.expovariate(self.config['arrival_rate'] / 60)  # 转换为每秒到达率
            time += inter_arrival_time
            if time < self.total_time:
                student = Student(self.total_arrived + 1, time)
                self.total_arrived += 1
                self.students.append(student)
                event = Event(time, 'arrival', student=student)
                heapq.heappush(self.event_queue, event)
    
    def step(self):
        if not self.event_queue:
            return {'is_ended': True, 'message': 'No more events'}
        
        # 处理下一个事件
        event = heapq.heappop(self.event_queue)
        self.current_time = event.event_time
        
        if event.event_type == 'arrival':
            self.handle_arrival(event.student)
        elif event.event_type == 'service_end':
            self.handle_service_end(event.student, event.window)
        elif event.event_type == 'eat_end':
            self.handle_eat_end(event.student, event.seat)
        
        # 记录快照
        self.record_snapshot(event.event_type)
        
        # 检查是否结束
        is_ended = self.check_end_condition()
        
        # 收集所有学生的信息
        students = []
        for student in self.students:
            # 确定学生位置
            position = 'unknown'
            position_detail = None
            
            # 检查是否在窗口排队
            for window in self.windows:
                if student in window.queue:
                    position = 'window_queue'
                    position_detail = window.id
                    break
            
            # 检查是否在窗口被服务
            for window in self.windows:
                if window.current_serving == student:
                    position = 'being_served'
                    position_detail = window.id
                    break
            
            # 检查是否在等位队列
            if position == 'unknown' and student in self.waiting_queue:
                position = 'waiting_queue'
                position_detail = self.waiting_queue.index(student)
            
            # 检查是否在座位上
            if position == 'unknown' and student.seat_id is not None:
                position = 'seated'
                position_detail = student.seat_id
            
            # 检查是否已离开
            if position == 'unknown' and student.end_eat_time is not None:
                position = 'left'
                position_detail = None
            
            students.append({
                'id': student.id,
                'arrival_time': student.arrival_time,
                'start_service_time': student.start_service_time,
                'end_service_time': student.end_service_time,
                'start_eat_time': student.start_eat_time,
                'end_eat_time': student.end_eat_time,
                'window_id': student.window_id,
                'seat_id': student.seat_id,
                'position': position,
                'position_detail': position_detail
            })
        
        return {
            'is_ended': is_ended,
            'current_time': self.current_time,
            'windows': [{
                'id': w.id,
                'queue_length': len(w.queue),
                'is_serving': w.current_serving is not None,
                'total_served': w.total_served
            } for w in self.windows],
            'seats': [{
                'id': s.id,
                'status': s.status,
                'remaining_time': s.remaining_time,
                'student_id': s.student.id if s.student else None
            } for s in self.seats],
            'waiting_queue_length': len(self.waiting_queue),
            'total_arrived': self.total_arrived,
            'total_served': self.total_served,
            'students': students
        }
    
    def handle_arrival(self, student):
        # 分配到排队人数最少的窗口
        min_queue_window = min(self.windows, key=lambda w: len(w.queue) + (1 if w.current_serving else 0))
        student.window_id = min_queue_window.id
        
        if min_queue_window.current_serving is None:
            # 直接开始服务
            min_queue_window.current_serving = student
            student.start_service_time = self.current_time
            # 生成服务结束事件
            service_time = random.normalvariate(self.config['avg_serve_time'], self.config['avg_serve_time'] * 0.2)
            service_time = max(1, service_time)  # 确保服务时间为正
            end_time = self.current_time + service_time
            event = Event(end_time, 'service_end', student=student, window=min_queue_window)
            heapq.heappush(self.event_queue, event)
        else:
            # 加入队列
            min_queue_window.queue.append(student)
    
    def handle_service_end(self, student, window):
        window.current_serving = None
        window.total_served += 1
        student.end_service_time = self.current_time
        
        # 处理队列中的下一个学生
        if window.queue:
            next_student = window.queue.pop(0)
            window.current_serving = next_student
            next_student.start_service_time = self.current_time
            # 生成服务结束事件
            service_time = random.normalvariate(self.config['avg_serve_time'], self.config['avg_serve_time'] * 0.2)
            service_time = max(1, service_time)
            end_time = self.current_time + service_time
            event = Event(end_time, 'service_end', student=next_student, window=window)
            heapq.heappush(self.event_queue, event)
        
        # 寻找空闲座位（就近选择）
        empty_seats = [s for s in self.seats if s.status == 'empty']
        if empty_seats:
            # 计算每个空闲座位到窗口的距离（简化为座位ID与窗口ID的差异）
            # 这里使用简单的距离计算，实际可以根据食堂布局计算真实距离
            window_id = window.id
            nearest_seat = min(empty_seats, key=lambda s: abs(s.id - window_id * (len(self.seats) // len(self.windows))))
            
            # 分配座位
            nearest_seat.status = 'occupied'
            nearest_seat.student = student
            student.seat_id = nearest_seat.id
            student.start_eat_time = self.current_time
            # 生成就餐结束事件
            eat_time = random.normalvariate(self.config['avg_eat_time'] * 60, self.config['avg_eat_time'] * 60 * 0.2)  # 转换为秒
            eat_time = max(60, eat_time)  # 确保至少1分钟
            end_time = self.current_time + eat_time
            nearest_seat.remaining_time = eat_time
            event = Event(end_time, 'eat_end', student=student, seat=nearest_seat)
            heapq.heappush(self.event_queue, event)
        else:
            # 加入等位队列
            self.waiting_queue.append(student)
    
    def handle_eat_end(self, student, seat):
        seat.status = 'empty'
        seat.student = None
        seat.remaining_time = 0
        student.end_eat_time = self.current_time
        self.total_served += 1
        
        # 处理等位队列中的学生
        if self.waiting_queue:
            next_student = self.waiting_queue.pop(0)
            # 直接分配刚空出的座位（就近原则）
            seat.status = 'occupied'
            seat.student = next_student
            next_student.seat_id = seat.id
            next_student.start_eat_time = self.current_time
            # 生成就餐结束事件
            eat_time = random.normalvariate(self.config['avg_eat_time'] * 60, self.config['avg_eat_time'] * 60 * 0.2)
            eat_time = max(60, eat_time)
            end_time = self.current_time + eat_time
            seat.remaining_time = eat_time
            event = Event(end_time, 'eat_end', student=next_student, seat=seat)
            heapq.heappush(self.event_queue, event)
    
    def record_snapshot(self, event_type):
        # 记录仿真状态快照
        queue_details = json.dumps([{
            'window_id': w.id,
            'queue_length': len(w.queue),
            'total_served': w.total_served
        } for w in self.windows])
        
        total_in_queue = sum(len(w.queue) for w in self.windows) + len(self.waiting_queue)
        total_eating = sum(1 for s in self.seats if s.status == 'occupied')
        empty_seats = sum(1 for s in self.seats if s.status == 'empty')
        
        # 保存到数据库
        conn = sqlite3.connect('simulation.db')
        c = conn.cursor()
        c.execute('''INSERT INTO simulation_snapshot 
                    (config_id, current_time, total_arrived, total_served, 
                     total_in_queue, total_eating, empty_seats, queue_details, event_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                    (self.config_id or 1, self.current_time, self.total_arrived, self.total_served, 
                     total_in_queue, total_eating, empty_seats, queue_details, event_type))
        conn.commit()
        conn.close()
    
    def check_end_condition(self):
        # 检查仿真结束条件
        if self.current_time >= self.total_time:
            # 检查是否所有学生都已离开
            all_students_left = all(s.end_eat_time is not None for s in self.students)
            all_windows_empty = all(len(w.queue) == 0 and w.current_serving is None for w in self.windows)
            all_seats_empty = all(s.status == 'empty' for s in self.seats)
            waiting_queue_empty = len(self.waiting_queue) == 0
            
            return all_students_left and all_windows_empty and all_seats_empty and waiting_queue_empty
        return False
    
    def get_statistics(self):
        # 计算统计数据
        total_waiting_time = 0
        total_service_time = 0
        total_eating_time = 0
        served_students = [s for s in self.students if s.end_eat_time is not None]
        
        for student in served_students:
            if student.start_service_time:
                waiting_time = student.start_service_time - student.arrival_time
                total_waiting_time += waiting_time
            if student.end_service_time and student.start_service_time:
                service_time = student.end_service_time - student.start_service_time
                total_service_time += service_time
            if student.end_eat_time and student.start_eat_time:
                eating_time = student.end_eat_time - student.start_eat_time
                total_eating_time += eating_time
        
        avg_waiting_time = total_waiting_time / len(served_students) if served_students else 0
        avg_service_time = total_service_time / len(served_students) if served_students else 0
        avg_eating_time = total_eating_time / len(served_students) if served_students else 0
        
        # 窗口服务人数
        window_served = [w.total_served for w in self.windows]
        
        # 座位利用率
        total_possible_seat_time = self.config['seat_count'] * self.total_time
        actual_seat_time = sum(s.remaining_time for s in self.seats) + total_eating_time
        seat_utilization = actual_seat_time / total_possible_seat_time * 100 if total_possible_seat_time > 0 else 0
        
        return {
            'total_arrived': self.total_arrived,
            'total_served': self.total_served,
            'avg_waiting_time': avg_waiting_time,
            'avg_service_time': avg_service_time,
            'avg_eating_time': avg_eating_time,
            'window_served': window_served,
            'seat_utilization': seat_utilization,
            'peak_queue_length': max(sum(len(w.queue) for w in self.windows) + len(self.waiting_queue), 0)
        }
