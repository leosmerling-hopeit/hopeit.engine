from typing import List
from collections import deque
from collections import defaultdict

from hopeit.app.context import EventContext

from hopeit.samsa import Batch, queues


__steps__ = ['push']


async def push(payload: Batch, context: EventContext, stream_name: str) -> str:
    global queues
    queues[stream_name].extendleft(payload.items)
    return "OK"
