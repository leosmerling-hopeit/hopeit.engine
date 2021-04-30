from typing import List
from collections import deque
from collections import defaultdict

from hopeit.app.context import EventContext
from hopeit.app.logger import app_extra_logger

from hopeit.samsa import Batch, queues

logger, extra = app_extra_logger()

__steps__ = ['consume']


async def consume(payload: None, context: EventContext,
                  *, stream_name: str, consumer_group: str, batch_size: int=1) -> Batch:
    global queues
    q = queues[stream_name]
    batch = Batch(items=[])
    index = q.offset0 - q.consumer_offsets[consumer_group]
    missed = max(0, index - q.maxlen + 1)
    if missed > 0:
        index -= missed
        logger.warning(context, f"Consumer {consumer_group} missed {missed} messages")

    item = q.data[index]
    while index >= 0 and (item is not None) and (len(batch.items) < int(batch_size)):
        batch.items.append(q.data[index])
        index -= 1
        item = q.data[index]

    q.consumer_offsets[consumer_group] = q.consumer_offsets[consumer_group] + len(batch.items) + missed
    return batch
