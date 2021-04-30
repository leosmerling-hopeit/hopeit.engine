from typing import List
from collections import deque
from collections import defaultdict

from hopeit.app.context import EventContext

from hopeit.samsa import Batch, queues


__steps__ = ['push']


async def push(payload: Batch, context: EventContext, stream_name: str) -> int:
    global queues
    q = queues[stream_name]
    q.data.extendleft(payload.items)
    q.offset0 += 1
    return q.offset0
