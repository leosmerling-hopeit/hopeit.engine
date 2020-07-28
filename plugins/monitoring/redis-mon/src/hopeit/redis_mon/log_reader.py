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
from hopeit.redis_mon import redis, connect_redis, LogEventData, LogBatch, get_str


logger, extra = app_extra_logger()

__steps__ = ['process_log_data']


lock = asyncio.Lock()


class LogFileHandler(FileSystemEventHandler):

    def __init__(self, path: str, context: EventContext):
        self.path = path
        self.context = context
        self.batch = []
        self.open_files = {}
        self.last_access = {}
        self.loop = asyncio.get_event_loop()

    def on_modified(self, event):
        try:
            if self.context.app_key.replace('.', '_') in event.src_path:
                return
            asyncio.run_coroutine_threadsafe(self._on_event(event), self.loop)
        except Exception as e:
            logger.error(self.context, e)

    async def _on_event(self, event):
        try:
            await lock.acquire()
            await self._open_file(event)
            line = await self._read_line(event)
            while line:
                await self._emit(line)
                line = await self._read_line(event)
        except Exception as e:
            logger.error(self.context, e)
        finally:
            lock.release()
            await asyncio.sleep(1)

    async def _open_file(self, event):
        src_path = event.src_path
        self.last_access[src_path] = datetime.now().timestamp()
        if self.open_files.get(src_path) is None:
            checkpoint = await get_str(f'{self.context.app_key}.{src_path}.checkpoint')
            logger.info(self.context, "Opening log file...", extra=extra(src_path=src_path, checkpoint=checkpoint))
            self.open_files[src_path] = open(src_path, 'r')
            if checkpoint:
                line = self.open_files[src_path].readline()
                while line and (line[:24] < checkpoint):
                    line = self.open_files[src_path].readline()

    def close_inactive_files(self):
        exp = datetime.now().timestamp()
        for key, last_ts in list(self.last_access.items()):
            if (last_ts + 300.0) < exp:
                try:
                    logger.info(self.context, "Closing inactive file...", extra=extra(src_path=key))
                    self.open_files[key].close()
                except Exception as e:
                    logger.error(self.context, e)
                del self.open_files[key]
                del self.last_access[key]

    async def _read_line(self, event):
        src_path = event.src_path
        line = self.open_files[src_path].readline()
        if line:
            key = f'{self.context.app_key}.{src_path}'
            await redis().set(f'{key}.checkpoint', line[:24])
            await redis().expire(f'{key}.checkpoint', 3600)
        return line

    async def _emit(self, line: str):
        assert lock.locked()
        self.batch.append(line)

    async def get_and_reset_batch(self):
        try:
            await lock.acquire()
            results = self.batch
            self.batch = []
            return results
        finally:
            lock.release()
            await asyncio.sleep(1)


async def __init_event__(context: EventContext):
    await connect_redis(logger, context)


async def __service__(context: EventContext) -> Spawn[LogBatch]:
    await connect_redis(logger, context)
    path = context.env['log_reader']['path']
    event_handler = LogFileHandler(path, context)
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    try:
        while True:
            await asyncio.sleep(1)
            yield LogBatch(data=await event_handler.get_and_reset_batch())
            event_handler.close_inactive_files()
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
        app_info_components = app_info.split(' ')
        if len(app_info_components) == 5:
            app_name, app_version, event_name, host_name, pid = app_info_components
            extra_items = _parse_extras(extras)
            req_id = extra_items.get('track.request_id')
            await _process_counters(req_id, event_name, msg, context)
            await _process_duration(req_id, event_name, msg, extra_items, context)
            await _process_counters(req_id, '*', msg, context)
            await _process_duration(req_id, '*', msg, extra_items, context)
            await _process_counters('*', event_name, msg, context)
            await _process_duration('*', event_name, msg, extra_items, context)
    except Exception as e:
        logger.error(context, e)


async def _process_counters(req_id: str, event_name: str, msg: str, context: EventContext):
    msg = msg.strip(' ')
    if req_id and (msg in {'START', 'DONE', 'FAILED'}):
        key = f'{context.app_key}.{req_id}.{event_name}.{msg}.count'
        await _update(redis().incr, key)


async def _process_duration(req_id: str, event_name: str, msg: str, extra_items: Dict[str, str], context: EventContext):
    duration = extra_items.get('metrics.duration')
    if duration and req_id and (msg == 'DONE'):
        key = f'{context.app_key}.{req_id}.{event_name}.duration'
        await _update(redis().incr, f'{key}.count')
        await _update(redis().incrbyfloat, f'{key}.sum', float(duration))
        await _update(redis().set, f'{key}.last', float(duration))


async def _update(func, key: str, *args, expiration: int = 3600):
    try:
        await func(key, *args)
        if expiration:
            await redis().expire(key, expiration)
    except Exception as e:
        logger.error(context, e)


async def process_log_data(payload: LogBatch, context: EventContext):
    assert redis(), "Redis not connected"
    try:
        await lock.acquire()
        for entry in payload.data:
            await _process_log_entry(entry, context)
    finally:
        lock.release()
        await asyncio.sleep(1)
