from hopeit.app.context import EventContext

from hopeit.samsa import Batch, queues


__steps__ = ['push']


async def push(payload: Batch, context: EventContext, stream_name: str) -> int:
    global queues
    q = queues[stream_name]
    res = await q.push(payload.items)
    return res
