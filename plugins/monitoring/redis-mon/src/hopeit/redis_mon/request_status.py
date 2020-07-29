from typing import Optional

import aioredis
from hopeit.app.api import event_api
from hopeit.app.context import EventContext
from hopeit.app.logger import app_extra_logger

from hopeit.redis_mon import RequestStats, get_int, get_float, get_opt_ts, connect_redis

logger, extra = app_extra_logger()

__steps__ = ['query_status']

__api__ = event_api(
    query_args=[
        ('request_id', str, 'track.request_id'),
        ('event_name', str, 'event_name'),
    ],
    responses={
        200: (RequestStats, "Stats about request processed events")
    }
)

redis: Optional[aioredis.Redis] = None

async def __init_event__(context: EventContext):
    global redis
    redis = await connect_redis(redis, logger, context)


async def query_status(payload: None, context: EventContext, 
                       request_id: str, event_name: str = '*') -> RequestStats:
    assert redis, "Redis not connected"
    try:
        prefix = f'{context.app_key}.{request_id}.{event_name}'
        return RequestStats(
            request_id=request_id,
            request_ts=await get_opt_ts(redis, f'{prefix}.request_ts.last'),
            last_event_ts=await get_opt_ts(redis, f'{prefix}.event_ts.last', '%Y-%m-%d %H:%M:%S,%f'),
            processed_ts=await get_opt_ts(redis, f'{prefix}.processed_ts.last'),
            event_name=event_name,
            started=await get_int(redis, f'{prefix}.START.count'),
            done=await get_int(redis, f'{prefix}.DONE.count'),
            failed=await get_int(redis, f'{prefix}.FAILED.count'),
            duration_count=await get_int(redis, f'{prefix}.duration.count'),
            duration_sum=await get_float(redis, f'{prefix}.duration.sum'),
            duration_last=await get_float(redis, f'{prefix}.duration.last')
        )
    except Exception as e:
        logger.error(context, e)
