from hopeit.app.context import EventContext
from hopeit.app.logger import app_extra_logger

from hopeit.samsa import Batch, queues

logger, extra = app_extra_logger()

__steps__ = ['consume']


async def consume(payload: None, context: EventContext,
                  *, stream_name: str, consumer_group: str, batch_size: int=1) -> Batch:
    global queues
    q = queues[stream_name]
    items, missed = await q.consume(consumer_group, batch_size)
    if missed > 0:
        logger.warning(context, f"Consumer {consumer_group} missed {missed} messages")
    return Batch(items=items)
