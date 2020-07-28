from typing import Optional

import aioredis
from hopeit.app.api import event_api
from hopeit.app.context import EventContext
from hopeit.app.logger import app_extra_logger

from hopeit.redis_mon import RequestStats, get_int, get_float

logger, extra = app_extra_logger()

__steps__ = ['query_status']

__api__ = event_api(
    query_args=[('request_id', str, 'track.request_id')],
    responses={
        200: (RequestStats, "Stats about request processed events")
    }
)

redis: Optional[aioredis.Redis] = None

async def __init_event__(context: EventContext):
    global redis
    if redis is None:
        logger.info(context, "Connecting monitoring plugin...")
        redis = await aioredis.create_redis_pool('redis://localhost:6379')


async def query_status(payload: None, context: EventContext, request_id: str) -> RequestStats:
    assert redis, "No hay redis"
    try:
        prefix = f'{context.app_key}.{request_id}'
        duration_avg = 0.0
        duration_count = await get_int(redis, f'{prefix}.duration.count')
        if duration_count > 0:
            duration_avg = (await get_float(redis, f'{prefix}.duration.sum')) / duration_count
        return RequestStats(
            request_id=request_id,
            total=await get_int(redis, f'{prefix}.START.count'),
            done=await get_int(redis, f'{prefix}.DONE.count'),
            failed=await get_int(redis, f'{prefix}.FAILED.count'),
            duration_avg=duration_avg,
            duration_last=await get_float(redis, f'{prefix}.duration.last')
        )
    except Exception as e:
        print(e)
