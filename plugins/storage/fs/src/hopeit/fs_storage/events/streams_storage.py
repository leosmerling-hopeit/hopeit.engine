from hopeit.app.context import EventContext
from hopeit.app.logger import app_extra_logger
from hopeit.streams.storage import StreamStorageBatch, StreamStorageOp

from hopeit.fs_storage import FileStorage, FileStorageSettings

logger, extra = app_extra_logger()

__steps__ = ['store']


async def store(batch: StreamStorageBatch, context: EventContext) -> StreamStorageOp:
    settings = context.settings(datatype=FileStorageSettings)
    logger.info(context, f"Saving batch...", extra=extra(
        path=settings.path,
        items=len(batch.items)
    ))
    for item in batch.items:
        FileStorage(path=settings.path).store(key=item.key, value=item.data)
