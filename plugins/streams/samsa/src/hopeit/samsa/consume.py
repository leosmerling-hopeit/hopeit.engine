from typing import List
from collections import deque
from collections import defaultdict

from hopeit.app.context import EventContext

from hopeit.samsa import Batch, queues


__steps__ = ['consume']


async def consume(payload: None, context: EventContext, stream_name: str, batch_size: int=1) -> Batch:
    global queues
    q = queues[stream_name]
    batch = Batch(items=[])
    while q and (len(batch.items) < int(batch_size)):
        batch.items.append(q.pop())
    return batch
