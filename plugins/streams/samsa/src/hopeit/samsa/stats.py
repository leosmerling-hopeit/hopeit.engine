from datetime import datetime, timezone
import os
import socket
from typing import List

from hopeit.app.context import EventContext
from hopeit.app.logger import app_extra_logger
from hopeit.streams import StreamManager

from hopeit.samsa import Stats, get_all_streams

logger, extra = app_extra_logger()

__steps__ = ['stats']


def _host() -> str:
    ts = datetime.now().astimezone(tz=timezone.utc).isoformat()
    host = socket.gethostname()
    pid = os.getpid()
    return f"{ts}.{host}.{pid}"


_host = _host()


async def stats(payload: None, context: EventContext) -> Stats:
    return Stats(
        host=_host,
        streams={
            stream_name: q.stats()
            for stream_name, q in get_all_streams()
        }
    )
