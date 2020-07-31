import asyncio
import time
import logging
from copy import copy
from asyncio import Lock
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timezone

import aioredis
from watchdog.observers import Observer
from watchdog.events import LoggingEventHandler, FileSystemEventHandler

from hopeit.app.context import EventContext
from hopeit.app.events import Spawn
from hopeit.app.logger import app_extra_logger
from hopeit.server.names import auto_path 

from hopeit.redis_mon import connect_redis, LogReaderConfig, LogEventData, LogBatch, get_str

logger, extra = app_extra_logger()

__steps__ = ['process_log_data']

redis: Optional[aioredis.Redis] = None


class LogFileHandler(FileSystemEventHandler):

    def __init__(self, config: LogReaderConfig, context: EventContext):
        self.path = config.path
        self.prefix = config.path + config.prefix
        self.context = context
        self.batch = []
        self.open_files = {}
        self.last_access = {}
        self.loop = asyncio.get_event_loop()
        self.lock = asyncio.Lock()
        self.file_open_timeout = config.file_open_timeout_secs
        self.file_checkpoint_expire = config.file_checkpoint_expire_secs

    def on_moved(self, event):
        try:
            if event.src_path in self.open_files:
                self.last_access[event.src_path] = 0
                self.close_inactive_files()
        except Exception as e:
            logger.error(self.context, e)

    def on_deleted(self, event):
        try:
            if event.src_path in self.open_files:
                self.last_access[event.src_path] = 0
                self.close_inactive_files()
        except Exception as e:
            logger.error(self.context, e)

    def on_modified(self, event):
        try:
            if event.src_path.startswith(self.prefix):
                asyncio.run_coroutine_threadsafe(self._on_event(event), self.loop)
        except Exception as e:
            logger.error(self.context, e)

    def _add_line(self, lines: List[str], line: str):
        if ('| START |' in line) or ('| DONE |' in line) or ('| FAILED |' in line):
            lines.append(line)

    async def _on_event(self, event):
        try:
            src_path = event.src_path
            if await self._open_file(src_path):
                line = await self._read_line(src_path)
                if line:
                    lines = []
                    self._add_line(lines, line)
                    while line:
                        line = await self._read_line(src_path)
                        self._add_line(lines, line)
                    if len(lines) > 0:
                        await self._emit(lines)
                        await self._save_checkpoint(src_path, lines[-1])
        except Exception as e:
            logger.error(self.context, e)

    async def _save_checkpoint(self, src_path: str, line: str):
        key = f'{self.context.app_key}.{src_path}'
        await redis.set(f'{key}.checkpoint', line)
        await redis.expire(f'{key}.checkpoint', self.file_checkpoint_expire)

    async def _open_file(self, src_path: str) -> bool:
        try:
            await self.lock.acquire()
            self.last_access[src_path] = datetime.now().timestamp()
            if self.open_files.get(src_path) is None:
                checkpoint = await get_str(redis, f'{self.context.app_key}.{src_path}.checkpoint')
                logger.info(self.context, "Opening log file...", extra=extra(src_path=src_path, checkpoint=checkpoint))
                self.open_files[src_path] = open(src_path, 'r')
                if checkpoint:
                    line = self.open_files[src_path].readline()
                    if line and (line <= checkpoint):
                        logger.info(self.context, "Skipping to checkpoint...", extra=extra(src_path=src_path, checkpoint=checkpoint))
                        while line and (line[:24] < checkpoint[:24]):
                            line = self.open_files[src_path].readline()
                        pos = self.open_files[src_path].tell()
                        while line and (line[:24] <= checkpoint[:24]) and (line != checkpoint):
                            line = self.open_files[src_path].readline()
                        if line != checkpoint:
                            self.open_files[src_path].seek(pos)
                        logger.info(self.context, "Skip to checkpoint done.", extra=extra(src_path=src_path, checkpoint=checkpoint))
                    else:
                        self.open_files[src_path].seek(0)
            return True
        except Exception as e:
            logger.error(self.context, e)
            return False
        finally:
            self.lock.release()

    def close_inactive_files(self):
        exp = datetime.now().timestamp()
        for key, last_ts in list(self.last_access.items()):
            if (last_ts + self.file_open_timeout) < exp:
                try:
                    logger.info(self.context, "Closing inactive/deleted file...", extra=extra(src_path=key))
                    if key in self.open_files:
                        self.open_files[key].close()
                        del self.open_files[key]
                except Exception as e:
                    logger.error(self.context, e)
                del self.last_access[key]

    async def _read_line(self, src_path: str):
        return self.open_files[src_path].readline()

    async def _emit(self, lines: List[str]):
        try:
            await self.lock.acquire()
            self.batch.extend(lines)
        finally:
            self.lock.release()
      
    async def get_and_reset_batch(self):
     
        def _sort_batch(x):
            xs = x.split(' | ')[:5]
            try:
                xs[4] = ['START', '', 'DONE', 'FAILED'].index(xs[4])
            except ValueError:
                xs[4] = 1
            except IndexError:
                pass
            return tuple(xs)

        try:
            await self.lock.acquire()
            results = sorted(self.batch, key=_sort_batch)
            self.batch = []
            return results
        finally:
            self.lock.release()


async def __init_event__(context: EventContext):
    global redis
    redis = await connect_redis(redis, logger, context)


async def __service__(context: EventContext) -> Spawn[LogBatch]:
    global redis
    redis = await connect_redis(redis, logger, context)
    config = LogReaderConfig.from_dict(context.env['log_reader'])
    event_handler = LogFileHandler(config, context)
    observer = Observer()
    observer.schedule(event_handler, config.path, recursive=False)
    observer.start()
    try:
        while True:
            batch = await event_handler.get_and_reset_batch()
            if len(batch) == 0:
                await asyncio.sleep(config.batch_wait_interval_secs)
            else:
                for i in range(0, len(batch), config.batch_size):
                    yield LogBatch(data=batch[i: i + config.batch_size + 1])
                    await asyncio.sleep(config.batch_wait_interval_secs)
            event_handler.close_inactive_files()
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


def _parse_extras(extras: List[str]) -> Dict[str, str]:
    items = {}
    for entry in extras:
        entry = entry.strip('\n')
        if entry:
            xs = entry.split('=')
            if len(xs) == 2:
                k, v = entry.split('=')
                items[k] = v
    return items


async def _save_request_event_metrics(req_id: str, event: str, msg: str, exp: int, req_ts: str,
                                      ts: str, extra_items: Dict[str, str], context: EventContext):
    await _process_timestamps(req_id, event, msg, exp, req_ts, ts, context)
    await _process_counters(req_id, event, msg, exp, context)
    await _process_duration(req_id, event, msg, exp, extra_items, context)


async def _process_log_entry(entry: str, exp: int, agg_events: bool, agg_requests: bool,
                             context: EventContext):
    try:
        xs = entry.split(' | ')
        if len(xs) >= 4:
            ts, app_info, msg, extras = xs[0], xs[2], xs[3], xs[4:]
            app_info_components = app_info.split(' ')
            if msg in {'START', 'DONE', 'FAILED'} and (len(app_info_components) >= 3):
                app_name, app_version, event_name = app_info_components[:3]
                event = auto_path(app_name, app_version, event_name)
                extra_items = _parse_extras(extras)
                req_id = extra_items.get('track.request_id')
                req_ts = extra_items.get('track.request_ts')
                tasks = [
                    _save_request_event_metrics(req_id, event, msg, exp, req_ts, ts, extra_items, context)
                    ]
                if agg_requests:
                    tasks.append(
                        _save_request_event_metrics(req_id, '*', msg, exp, req_ts, ts, extra_items, context)
                    )
                if agg_events:
                    tasks.append(
                        _save_request_event_metrics('*', event, msg, exp, req_ts, ts, extra_items, context)
                    )
                await asyncio.gather(*tasks)
    except Exception as e:
        logger.error(context, e)


async def _process_timestamps(req_id: str, event_name: str, msg: str, exp: int, 
                              req_ts: str, ts: str, context: EventContext):
    try:
        key = f'{context.app_key}.{req_id}.{event_name}'
        if req_ts and req_id and (msg == 'START'):
            await _update(redis.set, f'{key}.request_ts.last', req_ts, exp=exp)
        now_ts = datetime.now(tz=timezone.utc).isoformat()
        await _update(redis.set, f'{key}.processed_ts.last', now_ts, exp=exp)
        await _update(redis.set, f'{key}.event_ts.last', ts, exp=exp)
    except Exception as e:
        logger.error(context, e)


async def _process_counters(req_id: str, event_name: str, msg: str, exp: int, context: EventContext):
    try:
        if req_id and (msg in {'START', 'DONE', 'FAILED'}):
            key = f'{context.app_key}.{req_id}.{event_name}.{msg}.count'
            await _update(redis.incr, key, exp=exp)
    except Exception as e:
        logger.error(context, e)


async def _process_duration(req_id: str, event_name: str, msg: str, exp: int, 
                            extra_items: Dict[str, str], context: EventContext):
    try:
        duration = extra_items.get('metrics.duration')
        if duration and req_id and (msg == 'DONE'):
            key = f'{context.app_key}.{req_id}.{event_name}.duration'
            await _update(redis.incr, f'{key}.count', exp=exp)
            await _update(redis.incrbyfloat, f'{key}.sum', float(duration), exp=exp)
            await _update(redis.set, f'{key}.last', float(duration), exp=exp)
    except Exception as e:
        logger.error(context, e)


async def _update(func, key: str, *args, exp: int):
    await func(key, *args)
    if exp:
        await redis.expire(key, exp)


async def process_log_data(payload: LogBatch, context: EventContext):
    assert redis, "Redis not connected"
    config = LogReaderConfig.from_dict(context.env['log_reader'])
    logger.info(context, "Processing batch of log entries...", extra=extra(batch_size=len(payload.data)))
    try:
        for entry in payload.data:
            await _process_log_entry(entry, 
                                     exp=config.metrics_expire_secs, 
                                     agg_events=config.aggregate_events, 
                                     agg_requests=config.aggregate_requests, 
                                     context=context)
    except Exception as e:
        logger.error(context, e)
    finally:
        await asyncio.sleep(config.batch_wait_interval_secs)
