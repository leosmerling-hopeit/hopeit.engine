from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, timezone

import aioredis

from hopeit.dataobjects import dataobject
from hopeit.app.context import EventContext


async def connect_redis(redis, logger, context: EventContext):
    if redis is None:
        logger.info(context, "Connecting monitoring plugin to Redis...")
        return await aioredis.create_redis_pool('redis://localhost:6379')
    return redis


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
    request_ts: Optional[datetime]
    last_event_ts: Optional[datetime]
    processed_ts: Optional[datetime]
    event: str
    started: int
    done: int
    failed: int
    duration_count: int
    duration_sum: float
    duration_last: float
    pending: int = 0
    progress: float = 0.0
    success: float = 0.0
    error_rate: float = 0.0
    duration_avg: float = 0.0
    elapsed_secs: int = 0
    processed_lag: int = 0

    def __post_init__(self):
        self.pending = max(0, self.started - self.done - self.failed)
        if self.started > 0:
            self.progress = 100. * min(1.0, (self.done + self.failed) / self.started)
        if (self.done + self.failed) > 0:
            self.success = 100. * min(1.0, self.done / (self.done + self.failed))
            self.error_rate = 100. * min(1.0, self.failed / (self.done + self.failed))
        if self.duration_count > 0:
            self.duration_avg = self.duration_sum / self.duration_count
        if self.request_ts and self.processed_ts:
            self.elapsed_secs = (self.processed_ts - self.request_ts).seconds
        if self.processed_ts and self.last_event_ts:
            self.processed_lag = (self.processed_ts - self.last_event_ts).seconds


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


async def get_str(redis, key: str) -> str:
    v = await redis.get(key)
    if v is None:
        return ''
    return v.decode()


async def get_opt_ts(redis, key: str, format_str: str = 'ISO') -> Optional[datetime]:
    v = await redis.get(key)
    if v is None:
        return None
    if format_str == 'ISO':
        return datetime.fromisoformat(v.decode())
    else:
        return datetime.strptime(v.decode(), format_str).replace(tzinfo=timezone.utc)
