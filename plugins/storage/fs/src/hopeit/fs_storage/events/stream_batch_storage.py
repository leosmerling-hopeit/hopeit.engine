import asyncio
import os
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import aiofiles
from hopeit.app.context import EventContext
from hopeit.app.events import Spawn
from hopeit.app.logger import app_extra_logger
from hopeit.dataobjects import DataObject, dataobject
from hopeit.dataobjects.payload import Payload
from hopeit.fs_storage import FileStorageSettings

logger, extra = app_extra_logger()

__steps__ = ['buffer_item', 'flush']


@dataclass
class Partition:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    items: List[DataObject] = field(default_factory=list)

buffer: Dict[str, Partition] = {}
buffer_lock: asyncio.Lock = asyncio.Lock()


@dataobject
@dataclass
class FlushSignal:
    partition_key: str


async def __service__(context: EventContext) -> Spawn[FlushSignal]:
    global buffer
    settings: FileStorageSettings = context.settings(datatype=FileStorageSettings)
    if settings.flush_seconds:
        while True:
            await asyncio.sleep(settings.flush_seconds)
            for partition_key in list(buffer.keys()):
                yield FlushSignal(partition_key=partition_key)
    else:
        if settings.flush_max_size == 0:
            logger.warning(
                context, 
                "Flushing partitions by size and time are disabled."
                "Specify either `flush_seconds` or `flush_max_size`"
                "to enable flushing the buffer periodically"
            )
        else:
            logger.info(context, "Flushing partitions by time disabled.")


async def buffer_item(payload: DataObject, context: EventContext) -> Optional[FlushSignal]:
    global buffer, buffer_lock
    settings: FileStorageSettings = context.settings(datatype=FileStorageSettings)
    ts = payload.event_ts() or datetime.now(tz=timezone.utc)
    partition_key = ts.strftime(
        (settings.partition_dateformat.strip('/') + '/') or "%Y/%m/%d/"
    )
    async with buffer_lock:
        partition = buffer.get(partition_key, Partition())
        buffer[partition_key] = partition
    async with partition.lock:
        partition.items.append(payload)
    if settings.flush_max_size and len(partition.items) >= settings.flush_max_size:
        return FlushSignal(partition_key=partition_key)
    return None


async def flush(signal: FlushSignal, context: EventContext):
    global buffer, buffer_lock
    logger.info(context, f"Flushing partition {signal.partition_key}...")
    partition = buffer[signal.partition_key]
    async with partition.lock:
        if len(partition.items):
            await _save_partition(signal.partition_key, partition.items, context)
        async with buffer_lock:
            del buffer[signal.partition_key]
    logger.info(context, f"Flush {signal.partition_key} done.")


async def _save_partition(partition_key: str, items: List[DataObject], context: EventContext):
    settings = context.settings(datatype=FileStorageSettings)
    path = Path(settings.path) / partition_key
    file = path / f"{uuid.uuid4()}.jsonlines"
    logger.info(context, f"Saving {file}...")
    os.makedirs(path.resolve(), exist_ok=True)
    async with aiofiles.open(file, 'w') as f:
        for item in items:
            await f.write(Payload.to_json(item) + "\n")
