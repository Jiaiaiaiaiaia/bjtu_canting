"""时变到达日程：baseline + 午高峰爬升 + 离散下课脉冲。

不变量：∫₀ᵀ λ(t) dt == total_arrivals（仅时间再分布，不改总量）。
常量场景走 is_constant 旁路，调用方据此用旧 expovariate 路径，
保证与今日行为在仿真语义层完全一致（不额外抽 acceptance）。
trace/实时生成器共用本类同一实例 + 同一 thinning + 同一 streams.arrival。
"""
from dataclasses import dataclass, field


@dataclass
class ArrivalSchedule:
    total_arrivals: float
    horizon_seconds: float
    baseline: float = 1.0
    ramp: tuple = None          # (start_s, end_s, height) 三角爬升；None=无
    pulses: list = field(default_factory=list)  # [(center_s, height, half_width_s)]
    _k: float = field(default=1.0, init=False)
    is_constant: bool = field(default=False, init=False)

    def __post_init__(self):
        self.is_constant = (self.ramp is None and not self.pulses)
        if self.is_constant:
            self._k = 1.0
            self._const = self.total_arrivals / self.horizon_seconds
            return
        raw = sum(self._shape(t) for t in self._grid())
        self._k = self.total_arrivals / raw if raw > 0 else 0.0

    @classmethod
    def constant(cls, rate_per_sec: float, horizon_seconds: float = 1.0):
        obj = cls(total_arrivals=rate_per_sec * horizon_seconds,
                  horizon_seconds=horizon_seconds)
        return obj

    def _grid(self):
        n = max(1, int(self.horizon_seconds))
        return range(n)

    def _shape(self, t: float) -> float:
        v = self.baseline
        if self.ramp:
            a, b, h = self.ramp
            if a <= t <= b:
                mid = (a + b) / 2.0
                v += h * (1.0 - abs(t - mid) / max(1e-9, (b - a) / 2.0))
        for c, h, w in self.pulses:
            if abs(t - c) <= w:
                v += h * (1.0 - abs(t - c) / max(1e-9, w))
        return max(0.0, v)

    def lambda_at(self, t: float) -> float:
        if self.is_constant:
            return self._const
        return self._k * self._shape(t)

    def lambda_max(self) -> float:
        if self.is_constant:
            return self._const
        return max(self.lambda_at(t) for t in self._grid())

    def sample_arrivals(self, rng) -> list:
        """非齐次泊松 thinning（Lewis–Shedler）。返回到达时刻列表。
        常量场景：调用方应改走旧 expovariate 路径，不应调用本方法。"""
        out, t = [], 0.0
        lmax = self.lambda_max()
        if lmax <= 0:
            return out
        while True:
            t += rng.expovariate(lmax)
            if t >= self.horizon_seconds:
                return out
            if rng.random() <= self.lambda_at(t) / lmax:
                out.append(t)
