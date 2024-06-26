from datetime import datetime
from hopeit.dataobjects import dataclass, dataobject


@dataobject(event_id="object_id", event_ts="object_ts")
@dataclass
class MyObject:
    object_id: str
    object_ts: datetime
    value: int
