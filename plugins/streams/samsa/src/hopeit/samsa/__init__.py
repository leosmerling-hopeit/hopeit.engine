import asyncio
from typing import Any, Dict, List
from collections import defaultdict, deque

from hopeit.dataobjects import EventPayload, dataclass, dataobject


@dataobject
@dataclass
class Message:
    key: str
    payload: Any


@dataobject
@dataclass
class Batch:
    items: List[Message]


class Queue:
    def __init__(self):
        self.maxlen = 10000
        self.data = deque(iterable=[None] * self.maxlen, maxlen=self.maxlen)
        self.consumer_offsets: Dict[str, int] = defaultdict(int)
        self.offset0 = -1
        self.lock = asyncio.Lock()

    def __repr__(self):
        return (
            f"consumer_offsets={dict(self.consumer_offsets.items())} \n"
            f"offset0={self.offset0} \n"
        )

    async def push(self, items: List[Message]) -> int:
        async with self.lock:
            self.data.extendleft(items)
            self.offset0 += len(items)
            return self.offset0


queues: Dict[str, deque] = defaultdict(Queue)
