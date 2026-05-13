"""Pre-generated student inputs for controlled single-canteen comparisons."""
from dataclasses import dataclass


@dataclass(frozen=True)
class StudentTrace:
    arrival_at: float
    patience_z: float
    service_z: float
    eat_z: float

    def to_patience_seconds(self, router_config) -> float:
        raw = (
            router_config.patience_mean_seconds
            + self.patience_z * router_config.patience_std_seconds
        )
        return max(router_config.patience_min_seconds, raw)


def build_single_canteen_traces(config: dict, streams) -> list[StudentTrace]:
    rate_per_sec = float(config["arrival_rate"]) / 60.0
    if rate_per_sec <= 0:
        raise ValueError("arrival_rate must be positive")

    stop_after = float(config["total_time"]) * 60.0
    arrival_at = 0.0
    traces: list[StudentTrace] = []
    while True:
        arrival_at += streams.arrival.expovariate(rate_per_sec)
        if arrival_at >= stop_after:
            break
        traces.append(
            StudentTrace(
                arrival_at=arrival_at,
                patience_z=streams.routing.normalvariate(0.0, 1.0),
                service_z=streams.service.normalvariate(0.0, 1.0),
                eat_z=streams.eat.normalvariate(0.0, 1.0),
            )
        )
    return traces
