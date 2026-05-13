"""Independent random streams for controlled simulation experiments."""
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class RandomStreams:
    arrival: random.Random
    routing: random.Random
    service: random.Random
    eat: random.Random


def build_random_streams(master_seed=None) -> RandomStreams:
    master = random.Random(master_seed)
    seeds = [master.randrange(1, 2**31 - 1) for _ in range(4)]
    return RandomStreams(
        arrival=random.Random(seeds[0]),
        routing=random.Random(seeds[1]),
        service=random.Random(seeds[2]),
        eat=random.Random(seeds[3]),
    )
