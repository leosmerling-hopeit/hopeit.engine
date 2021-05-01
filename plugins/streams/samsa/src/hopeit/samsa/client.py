import asyncio
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict
import uuid
from datetime import datetime

import aiohttp

from hopeit.app.context import EventContext
from hopeit.dataobjects import dataobject
from hopeit.dataobjects.jsonify import Json
from hopeit.samsa import Batch, Message, Stats
from hopeit.server.serialization import deserialize, serialize


async def push(batch: Batch, context: EventContext, stream_name: str) -> Dict[str, Dict[str, int]]:
    nodes = context.env['samsa']['push_nodes'].split(',')

    partitions = defaultdict(list)
    for item in batch.items:
        node_index = hash(item.key) % len(nodes)
        partitions[nodes[node_index]].append(item)

    node_res = await asyncio.gather(*[
        _post_push(url=url, stream_name=stream_name, batch=Batch(items=items))
        for url, items in partitions.items()
    ])

    return {
        url: res for (url, _), res in zip(partitions.items(), node_res)
    }


async def consume(context: EventContext, stream_name: str, consumer_group: str, batch_size: int):
    nodes = context.env['samsa']['consume_nodes'].split(',')
    partitions = await asyncio.gather(*[
        _get_consume(url=url, stream_name=stream_name, consumer_group=consumer_group, batch_size=batch_size)
        for url in nodes
    ])
    return Batch(items=[
        item for partition in partitions for item in partition.items
    ])


async def stats(context: EventContext) -> Dict[str, Stats]:
    nodes = context.env['samsa']['push_nodes'].split(',')
    all_stats = {
        url: node_stats
        for url, node_stats in zip(
            nodes,
            await asyncio.gather(*[
                _get_stats(url)
                for url in nodes
            ])
        )
    }
    return all_stats


async def _post_push(url: str, stream_name: str, batch: Batch) -> Dict[str, int]:
    async with aiohttp.ClientSession() as client:
        async with client.post(f"{url}/api/samsa/1x0/push", data=Json.to_json(batch), params={"stream_name": stream_name}) as res:
            return await res.json()


async def _get_consume(url: str, stream_name: str, consumer_group: str, batch_size) -> Batch:
    async with aiohttp.ClientSession() as client:
        async with client.get(f"{url}/api/samsa/1x0/consume", 
                               params={
                                   "stream_name": stream_name, 
                                   "consumer_group": consumer_group, 
                                   "batch_size": batch_size
                                }) as res:
            body = await res.json()
            return Batch.from_dict(body)


async def _get_stats(url: str):
    async with aiohttp.ClientSession() as client:
        async with client.get(f"{url}/api/samsa/1x0/stats") as res:
            body = await res.json()
            return body


@dataobject
@dataclass
class MyMessage:
    number: int
    text: str


async def test_push():
    from hopeit.testing.apps import config, create_test_context
    from hopeit.server.serialization import serialize, Serialization, Compression

    app_config = config("plugins/streams/samsa/config/1x0.json")
    context = create_test_context(app_config, "push")
    batch = Batch(
        items=[
            Message.encode(
                key=str(uuid.uuid4()), 
                payload=serialize(MyMessage(number=i, text=f"message {i}"), Serialization.PICKLE5, Compression.LZ4)
            )
            for i in range(10)
        ]
    )
    res = await push(batch, context, stream_name="test_stream")
    print("PUSH ------------------------------------------------------")
    print(context.env['samsa']['push_nodes'], res)
    print("-----------------------------------------------------------")
    print(await stats(context))
    print("-----------------------------------------------------------")


async def test_consume(consumer_group: str):
    from hopeit.testing.apps import config, create_test_context
    from hopeit.server.serialization import deserialize, Serialization, Compression

    app_config = config("plugins/streams/samsa/config/1x0.json")
    context = create_test_context(app_config, "consume")
    data = await consume(context, stream_name="test_stream", consumer_group=consumer_group, batch_size=10)
    print("CONSUME ---------------------------------------------------")
    print(context.env['samsa']['consume_nodes'], data)
    for item in data.items:
        msg = deserialize(item.payload, Serialization.PICKLE5, Compression.LZ4, MyMessage)
        print(item.key, msg)
    print("-----------------------------------------------------------")
    print(await stats(context))
    print("-----------------------------------------------------------")


if __name__ == "__main__":
    import sys
    args = sys.argv
    print("client.py", args)
    if args[1] == "push":
        asyncio.run(test_push())
    elif args[1] == "consume":
        asyncio.run(test_consume(args[2]))
