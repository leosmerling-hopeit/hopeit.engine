from typing import List

from hopeit.app.context import EventContext
from hopeit.app.logger import app_extra_logger

from hopeit.samsa import Stats, queues

logger, extra = app_extra_logger()

__steps__ = ['stats']


async def stats(payload: None, context: EventContext) -> Stats:
    return Stats(streams={
        stream_name: q.stats()
        for stream_name, q in queues.items()}
    )
