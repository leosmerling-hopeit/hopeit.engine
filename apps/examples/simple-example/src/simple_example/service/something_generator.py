"""
Simple Example: Service Something Generator
--------------------------------------------------------------------
Creates and publish Something object every 10 seconds
"""

import asyncio
from datetime import datetime
import random
import os
from hopeit.app.context import EventContext
from hopeit.app.events import Spawn, service_running
from hopeit.app.logger import app_extra_logger

from model import Something, Status, StatusType, User, SomethingParams

__steps__ = ["create_something"]

logger, extra = app_extra_logger()


async def __service__(context: EventContext) -> Spawn[SomethingParams]:
    """
    Generate SomethingParams asynchronously in a loop until the service is stopped.
    """

    i = 1
    if not os.path.exists("/tmp/hopeit.initialized"):
        raise RuntimeError(
            "Missing /tmp/hopeit.initialized file. "
            "Service will not start until run setup_something."
        )
    os.remove("/tmp/hopeit.initialized")
    while service_running(context):
        logger.info(context, f"Generating something event {i}...")
        yield SomethingParams(id=f"id{i}", user=f"user{i}")
        i += 1
        await asyncio.sleep(random.random() * 10.0)
    logger.info(context, "Service seamlessly exit")


async def create_something(
    payload: SomethingParams, context: EventContext
) -> Something:
    """Create a Something object asynchronously."""
    logger.info(
        context,
        "Creating something...",
        extra=extra(payload_id=payload.id, user=payload.user),
    )
    result = Something(
        id=payload.id,
        user=User(id=payload.user, name=payload.user),
        status=Status(ts=datetime.now(), type=StatusType.NEW),
    )
    await asyncio.sleep(random.random() * 5.0)
    return result
