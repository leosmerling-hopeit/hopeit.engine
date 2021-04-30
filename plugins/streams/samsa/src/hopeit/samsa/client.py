import asyncio
from collections import defaultdict
import uuid

import aiohttp

from hopeit.app.context import EventContext
from hopeit.dataobjects.jsonify import Json
from hopeit.samsa import Batch, Message


async def push(batch: Batch, context: EventContext, stream_name: str):
    nodes = context.env['samsa_nodes']
    node_keys = list(nodes.keys())

    partitions = defaultdict(list)
    for item in batch.items:
        node_index = hash(item.key) % len(nodes)
        partitions[node_keys[node_index]].append(item)

    await asyncio.gather(*[
        invoke_push(url=nodes[node_key], stream_name=stream_name, batch=Batch(items=items))
        for node_key, items in partitions.items()
    ])


async def invoke_push(url: str, stream_name: str, batch: Batch):
    async with aiohttp.ClientSession() as client:
        async with client.post(f"{url}/api/samsa/1x0/push", data=Json.to_json(batch), params={"stream_name": stream_name}) as res:
            print("push", url, res.status, await res.json())


async def test_push():
    from hopeit.testing.apps import config, create_test_context
    app_config = config("plugins/streams/samsa/config/1x0.json")
    context = create_test_context(app_config, "push")
    batch = Batch(
        items=[
            Message(key=str(uuid.uuid4()), payload=f"Message {i}")
            for i in range(10)
        ]
    )
    await push(batch, context, stream_name="test_stream")


if __name__ == "__main__":
    asyncio.run(test_push())
