import asyncio
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime
import random
import os

import aiohttp

from hopeit.app.context import EventContext
from hopeit.dataobjects import dataobject
from hopeit.dataobjects.jsonify import Json
from hopeit.samsa import Batch, Message, Stats, consume_in_process, get_all_streams, push_in_process
from hopeit.server.serialization import deserialize, serialize


class SamsaClient:

    def __init__(self, *, 
                 push_nodes: List[str], 
                 consume_nodes: List[str],
                 consumer_id: str):
        self.push_nodes = [*push_nodes]
        self.consume_nodes = [*consume_nodes]
        self.all_nodes = sorted(list(set([*push_nodes, *consume_nodes])))
        self.consumer_id = consumer_id
        random.seed(os.getpid())
        random.shuffle(self.consume_nodes)

    async def push(self, batch: Batch, stream_name: str, maxlen: int) -> Dict[str, Dict[str, int]]:
        partitions = defaultdict(list)
        for item in batch.items:
            node_index = hash(item.key) % len(self.push_nodes)
            partitions[self.push_nodes[node_index]].append(item)

        node_res = await asyncio.gather(*[
           self._invoke_push(
               url=url,
               stream_name=stream_name, 
               batch=Batch(items=items), 
               producer_id=self.consumer_id,
               maxlen=maxlen)
            for url, items in partitions.items()
        ])

        return {
            url: res for (url, _), res in zip(partitions.items(), node_res)
        }


    async def consume(self, stream_name: str, consumer_group: str, batch_size: int, timeout_ms: Optional[int]):
        return await self._invoke_consume(
            url=random.choice(self.consume_nodes),
            stream_name=stream_name,
            consumer_group=consumer_group,
            consumer_id=self.consumer_id,
            batch_size=batch_size,
            timeout_ms=timeout_ms
        )

    async def stats(self) -> Dict[str, Stats]:
        all_stats = {
            url: node_stats
            for url, node_stats in zip(
                self.all_nodes,
                await asyncio.gather(*[
                    self._invoke_stats(url)
                    for url in self.all_nodes
                ])
            )
        }
        return all_stats

    @staticmethod
    async def _invoke_push(url: str, stream_name: str, batch: Batch, 
                           producer_id: str, maxlen: int) -> Dict[str, int]:

        if url == "in-process":
            return await push_in_process(
                batch=batch,
                stream_name=stream_name,
                producer_id=producer_id,
                maxlen=maxlen
            )

        async with aiohttp.ClientSession() as client:
            async with client.post(
                f"{url}/api/samsa/1x0/push",
                data=Json.to_json(batch),
                params={
                    "stream_name": stream_name,
                    "producer_id": producer_id,
                    "maxlen": maxlen
                }
            ) as res:
                return await res.json()

    @staticmethod
    async def _invoke_consume(url: str, stream_name: str, 
                              consumer_group: str, consumer_id: str,
                              batch_size: int, timeout_ms: int) -> Batch:

        if url == "in-process":
            return await consume_in_process(
                stream_name=stream_name,
                consumer_group=consumer_group,
                consumer_id=consumer_id,
                batch_size=batch_size,
                timeout_ms=timeout_ms
            )

        async with aiohttp.ClientSession() as client:
            async with client.get(
                f"{url}/api/samsa/1x0/consume", 
                params={
                    "stream_name": stream_name,
                    "consumer_group": consumer_group,
                    "consumer_id": consumer_id,
                    "batch_size": batch_size,
                    "timeout_ms": timeout_ms
                }
            ) as res:
                return Batch.from_dict(await res.json())

    @staticmethod
    async def _invoke_stats(url: str) -> Stats:
        if url == "in-process":
            return Stats(streams={
                stream_name: q.stats()
                for stream_name, q in get_all_streams()}
            )
        
        async with aiohttp.ClientSession() as client:
            async with client.get(f"{url}/api/samsa/1x0/stats") as res:
                return Stats.from_dict(await res.json())

# TESTS
# @dataobject
# @dataclass
# class MyMessage:
#     number: int
#     text: str


# def create_test_client(context: EventContext) -> SamsaClient:
#     push_nodes = context.env['samsa']['push_nodes'].split(',')
#     consume_nodes = context.env['samsa']['consume_nodes'].split(',')
#     return SamsaClient(push_nodes=push_nodes, consume_nodes=consume_nodes)


# async def test_push():
#     from hopeit.testing.apps import config, create_test_context
#     from hopeit.server.serialization import serialize, Serialization, Compression

#     app_config = config("plugins/streams/samsa/config/1x0.json")
#     context = create_test_context(app_config, "push")
#     batch = Batch(
#         items=[
#             Message.encode(
#                 key=str(uuid.uuid4()), 
#                 payload=serialize(MyMessage(number=i, text=f"message {i}"), Serialization.PICKLE5, Compression.LZ4)
#             )
#             for i in range(10)
#         ]
#     )
#     client = create_test_client(context)
#     res = await client.push(batch, stream_name="test_stream")
#     print("PUSH ------------------------------------------------------")
#     print(context.env['samsa']['push_nodes'], res)
#     print("-----------------------------------------------------------")
#     print(await client.stats())
#     print("-----------------------------------------------------------")


# async def test_consume(consumer_group: str):
#     from hopeit.testing.apps import config, create_test_context
#     from hopeit.server.serialization import deserialize, Serialization, Compression

#     app_config = config("plugins/streams/samsa/config/1x0.json")
#     context = create_test_context(app_config, "consume")
#     client = create_test_client(context)
#     data = await client.consume(stream_name="test_stream", consumer_group=consumer_group, batch_size=10)
#     print("CONSUME ---------------------------------------------------")
#     print(context.env['samsa']['consume_nodes'], data)
#     for item in data.items:
#         msg = deserialize(item.payload, Serialization.PICKLE5, Compression.LZ4, MyMessage)
#         print(item.key, msg)
#     print("-----------------------------------------------------------")
#     print(await client.stats())
#     print("-----------------------------------------------------------")


# if __name__ == "__main__":
#     import sys
#     args = sys.argv
#     print("client.py", args)
#     if args[1] == "push":
#         asyncio.run(test_push())
#     elif args[1] == "consume":
#         asyncio.run(test_consume(args[2]))
