import asyncio
from collections import defaultdict
from typing import Dict
import uuid

import aiohttp

from hopeit.app.context import EventContext
from hopeit.dataobjects.jsonify import Json
from hopeit.samsa import Batch, Message, Stats


async def push(batch: Batch, context: EventContext, stream_name: str):
    nodes = context.env['samsa_nodes']
    node_keys = list(nodes.keys())

    partitions = defaultdict(list)
    for item in batch.items:
        node_index = hash(item.key) % len(nodes)
        partitions[node_keys[node_index]].append(item)

    await asyncio.gather(*[
        post_push(url=nodes[node_key], stream_name=stream_name, batch=Batch(items=items))
        for node_key, items in partitions.items()
    ])

async def stats(context: EventContext) -> Dict[str, Stats]:
    nodes = context.env['samsa_nodes']
    node_items = list(nodes.items())
    all_stats = {
        node_key: node_stats
        for node_key, node_stats in zip([
            node_key for node_key, _ in node_items
        ], await asyncio.gather(*[
            get_stats(url)
            for _, url in node_items
        ]))
    }
    return all_stats


async def post_push(url: str, stream_name: str, batch: Batch):
    async with aiohttp.ClientSession() as client:
        async with client.post(f"{url}/api/samsa/1x0/push", data=Json.to_json(batch), params={"stream_name": stream_name}) as res:
            print("push", url, res.status, await res.json())


async def get_stats(url: str):
    async with aiohttp.ClientSession() as client:
        async with client.get(f"{url}/api/samsa/1x0/stats") as res:
            body = await res.json()
            print("stats", url, body)
            return body


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
    print(await stats(context))


if __name__ == "__main__":
    asyncio.run(test_push())
