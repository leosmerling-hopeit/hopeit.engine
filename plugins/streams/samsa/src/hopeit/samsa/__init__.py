from hopeit.dataobjects import EventPayload, dataclass, dataobject
from typing import Any, Dict, List
from functools import partial
from collections import defaultdict, deque


class Queue:
    def __init__(self):
        self.maxlen = 10000
        self.data = deque(iterable=[None] * self.maxlen, maxlen=self.maxlen)
        self.consumer_offsets: Dict[str, int] = defaultdict(int)
        self.offset0 = -1

    def __repr__(self):
        return (
            f"len(data)={len(self.data)} \n"
            f"items={self.data} \n"
            f"consumer_offsets={dict(self.consumer_offsets.items())} \n"
            f"offset0={self.offset0} \n"
        )


queues: Dict[str, deque] = defaultdict(Queue)


@dataobject
@dataclass
class Message:
    key: str
    payload: Any

@dataobject
@dataclass
class Batch:
    items: List[Message]
