import asyncio
import time
import logging
from copy import copy
from asyncio import Lock
from typing import Dict, List, Tuple, Optional
from datetime import datetime

import aioredis

from hopeit.app.context import EventContext
from hopeit.app.events import Spawn, SHUFFLE
from hopeit.app.logger import app_extra_logger

from watchdog.observers import Observer
from watchdog.events import LoggingEventHandler, FileSystemEventHandler
from hopeit.redis_mon import LogEventData, LogBatch, get_int


logger, extra = app_extra_logger()

__steps__ = ['process_log_data']


redis: Optional[aioredis.Redis] = None
lock = asyncio.Lock()


async def _connect_redis(context: EventContext):
    global redis
    if redis is None:
        logger.info(context, "Connecting monitoring plugin...")
        redis = await aioredis.create_redis('redis://localhost:6379')


class LogFileHandler(FileSystemEventHandler):

    def __init__(self, path: str, context: EventContext):
        self.path = path
        self.context = context
        self.batch = []
        self.open_files = {}
        self.last_access = {}
        self.loop = asyncio.get_event_loop()

    def on_any_event(self, event):
        print("EVENT", event)
        try:
            if self.context.app_key.replace('.', '_') in event.src_path:
                return
            asyncio.run_coroutine_threadsafe(self._on_event(event), self.loop)
        except Exception as e:
            print(e)

    async def _on_event(self, event):
        try:
            await lock.acquire()
            await self._open_file(event)
            line = await self._read_line(event)
            while line:
                print(">>>>>>>>> ", line)
                await self._emit(line)
                line = await self._read_line(event)
        except Exceoption as e:
            print(e)
        finally:
            lock.release()
            await asyncio.sleep(1)

    async def _open_file(self, event):
        src_path = event.src_path
        self.last_access[src_path] = datetime.now().timestamp()
        if self.open_files.get(src_path) is None:
            skip_lines = await get_int(redis, f'{self.context.app_key}.{src_path}.lines')
            print("OPEN", src_path, skip_lines)
            self.open_files[src_path] = open(src_path, 'r')
            for _ in range(skip_lines):
                line = self.open_files[src_path].readline()
                if line is None:
                    break

    def close_unused_files(self):
        exp = datetime.now().timestamp()
        for key, last_ts in list(self.last_access.items()):
            print("LAST USED", key, last_ts)
            if (last_ts + 60.0) < exp:
                try:
                    print("CLOSING", key)
                    self.open_files[key].close()
                except Exception as e:
                    print(e)
                del self.open_files[key]
                del self.last_access[key]

    async def _read_line(self, event):
        src_path = event.src_path
        line = self.open_files[src_path].readline()
        if line is not None:
            key = f'{self.context.app_key}.{src_path}.lines'
            await redis.incr(key) #TODO: expire
            await redis.expire(key, 3600)
        return line

    async def _emit(self, line: str):
        assert lock.locked()
        self.batch.append(line)

    async def get_and_reset(self):
        try:
            await lock.acquire()
            results = self.batch
            self.batch = []
            return results
        finally:
            lock.release()
            await asyncio.sleep(1)


async def __init_event__(context: EventContext):
    await _connect_redis(context)


async def __service__(context: EventContext) -> Spawn[LogBatch]:
    await _connect_redis(context)
    path = context.env['log_reader']['path']
    event_handler = LogFileHandler(path, context)
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    try:
        while True:
            await asyncio.sleep(5)
            yield LogBatch(data=await event_handler.get_and_reset())
            event_handler.close_unused_files()
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


def _parse_extras(extras: List[str]) -> Dict[str, str]:
    items = {}
    for entry in extras:
        entry = entry.strip('\n')
        if entry:
            k, v = entry.split('=')
            items[k] = v
    return items


async def _process_log_entry(entry: str, context: EventContext):
    try:
        x = entry.split(' | ')
        ts, level, app_info, msg, extras = x[0], x[1], x[2], x[3], x[4:]
        app_name, app_version, event_name, host_name, pid = app_info.split(' ')
        extra_items = _parse_extras(extras)
        print("***********", app_name, app_version, msg, extra_items.get('track.request_id'))
        req_id = extra_items.get('track.request_id')
        await _process_counters(req_id, msg, context)
        await _process_duration(req_id, msg, extra_items, context)
    except Exception as e:
        print(e)


async def _process_counters(req_id: str, msg: str, context: EventContext):
    if req_id and (msg in {'START', 'DONE', 'FAILED'}):
        key = f'{context.app_key}.{req_id}.{msg}.count'
        res = await redis.incr(key)  # TODO: set TTL to 24h
        await redis.expire(key, 3600)
        print("========", key, res)


async def _process_duration(req_id: str, msg: str, extra_items: Dict[str, str], context: EventContext):
    duration = extra_items.get('metrics.duration')
    if duration and req_id and (msg == 'DONE'):
        key = f'{context.app_key}.{req_id}.duration'
        res = await redis.incr(f'{key}.count')
        res = await redis.incrbyfloat(f'{key}.sum', float(duration))
        res = await redis.set(f'{key}.last', float(duration))
        await redis.expire('{key}.count', 3600)
        await redis.expire('{key}.sum', 3600)
        await redis.expire('{key}.last', 3600)
        print("========", key, res)


async def process_log_data(payload: LogBatch, context: EventContext):
    assert redis, "No hay redis"
    print('==============================================================')
    try:
        await lock.acquire()
        for entry in payload.data:
            await _process_log_entry(entry, context)
    finally:
        lock.release()
        await asyncio.sleep(1)
    print('==============================================================')
