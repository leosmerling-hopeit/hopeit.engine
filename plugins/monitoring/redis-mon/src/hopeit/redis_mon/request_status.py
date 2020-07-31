from typing import Optional, List

import aioredis
from hopeit.app.api import event_api
from hopeit.app.context import EventContext
from hopeit.app.logger import app_extra_logger

from hopeit.redis_mon import RequestStats, LogReaderConfig, get_int, get_float, get_opt_ts, get_float_list, connect_redis

logger, extra = app_extra_logger()

__steps__ = ['query_status']

__api__ = event_api(
    query_args=[
        ('request_id', str, "track.request_id, '*' to aggregated all requests stats"),
        ('event', str, "optional 'app_name.app_version.event_name' string, default '*' all events aggregated"),
    ],
    responses={
        200: (RequestStats, "Stats about request processed events")
    }
)

redis: Optional[aioredis.Redis] = None

async def __init_event__(context: EventContext):
    global redis
    redis = await connect_redis(redis, logger, context)


def _calc_percentile(samples: List[float], percentile: float) -> float:
    count = len(samples)
    if count == 0:
        return 0.0
    pidx = count - int(count * percentile / 100)
    return samples[pidx]


async def query_status(payload: None, context: EventContext, 
                       request_id: str, event: str = '*') -> RequestStats:
    assert redis, "Redis not connected"
    try:
        config = LogReaderConfig.from_dict(context.env['log_reader'])
        prefix = f'{context.app_key}.{request_id}.{event}'
        samples = sorted(await get_float_list(redis, f'{prefix}.duration.samples', config.pct_samples), 
                         reverse=True)
        return RequestStats(
            request_id=request_id,
            request_ts=await get_opt_ts(redis, f'{prefix}.request_ts.last'),
            last_event_ts=await get_opt_ts(redis, f'{prefix}.event_ts.last', '%Y-%m-%d %H:%M:%S,%f'),
            processed_ts=await get_opt_ts(redis, f'{prefix}.processed_ts.last'),
            event=event,
            started=await get_int(redis, f'{prefix}.START.count'),
            done=await get_int(redis, f'{prefix}.DONE.count'),
            failed=await get_int(redis, f'{prefix}.FAILED.count'),
            duration_count=await get_int(redis, f'{prefix}.duration.count'),
            duration_sum=await get_float(redis, f'{prefix}.duration.sum'),
            duration_last=await get_float(redis, f'{prefix}.duration.last'),
            duration_p90=_calc_percentile(samples, 90.),
            duration_p99=_calc_percentile(samples, 99.),
            duration_p999=_calc_percentile(samples, 99.9)
        )
    except Exception as e:
        logger.error(context, e)
