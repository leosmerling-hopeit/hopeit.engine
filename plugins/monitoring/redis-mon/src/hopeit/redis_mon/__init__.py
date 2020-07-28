from dataclasses import dataclass, field
from typing import List

from hopeit.dataobjects import dataobject


@dataobject
@dataclass
class LogBatch:
    data: List[str]


@dataobject
@dataclass
class LogEventData:
    data: list


@dataobject
@dataclass
class RequestStats:
    request_id: str
    total: int
    done: int
    failed: int
    duration_avg: float
    duration_last: float


async def get_int(redis, key: str) -> int:
    v = await redis.get(key)
    if v is None:
        return 0
    return int(v.decode())


async def get_float(redis, key: str) -> float:
    v = await redis.get(key)
    if v is None:
        return 0.
    return float(v.decode())
