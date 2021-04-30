import asyncio
from typing import Any, Dict, List, Tuple
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


@dataobject
@dataclass
class ConsumerGroupStats:
    next_offset: int
    missed: int
    lag: int


@dataobject
@dataclass
class StreamStats:
    head_offset: int
    consumers: Dict[str, ConsumerGroupStats]


@dataobject
@dataclass
class Stats:
    streams: Dict[str, StreamStats]



class Queue:
    def __init__(self):
        self.maxlen = 10000
        self.data = deque(iterable=[None] * self.maxlen, maxlen=self.maxlen)
        self.consumer_offsets: Dict[str, int] = defaultdict(int)
        self.offset0 = -1
        self._lock = asyncio.Lock()

    def __repr__(self):
        return (
            f"consumer_offsets={dict(self.consumer_offsets.items())} \n"
            f"offset0={self.offset0} \n"
        )

    async def push(self, items: List[Message]) -> int:
        async with self._lock:
            self.data.extendleft(items)
            self.offset0 += len(items)
            return self.offset0

    async def consume(self, consumer_group: str, batch_size: int) -> Tuple[List[Message], int]:
        async with self._lock:
            items = []
            index = self.offset0 - self.consumer_offsets[consumer_group]
            missed = max(0, index - self.maxlen + 1)
            if missed > 0:
                index -= missed

            item = self.data[index]
            while (index >= 0) and (item is not None) and (len(items) < int(batch_size)):
                items.append(self.data[index])
                index -= 1
                item = self.data[index]

            self.consumer_offsets[consumer_group] = self.consumer_offsets[consumer_group] + len(items) + missed
            return items, missed

    def stats(self) -> StreamStats:
        return StreamStats(
            head_offset=self.offset0,
            consumers={
                consumer_group: ConsumerGroupStats(
                    next_offset=offset,
                    missed=max(0, self.offset0 - offset - self.maxlen + 1),
                    lag=self.offset0 - offset + 1
                ) for consumer_group, offset in self.consumer_offsets.items()
            }
        )


queues: Dict[str, deque] = defaultdict(Queue)
