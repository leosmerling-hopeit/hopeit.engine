from hopeit.dataobjects import EventPayload, dataclass, dataobject
from typing import Any, Dict, List
from collections import defaultdict, deque


queues: Dict[str, deque] = defaultdict(deque)


@dataobject
@dataclass
class Message:
    id: int
    payload: Any

@dataobject
@dataclass
class Batch:
    items: List[Message]
