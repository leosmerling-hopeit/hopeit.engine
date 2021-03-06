from unittest.mock import MagicMock

from hopeit.server import web
from hopeit.server.web import parse_args


def test_port_path():
    args = ['--port=8080', '--path=/tmp/test', '--config-files=engine.json,test.json']
    result = parse_args(args)
    assert result == (None, 8080, '/tmp/test', False, ['engine.json', 'test.json'], None)


def test_stream_start():
    args = ['--start-streams', '--config-files=test.json']
    result = parse_args(args)
    assert result == (None, 8020, None, True, ['test.json'], None)


def test_port_only():
    args = ['--port=8020', '--config-files=test.json']
    result = parse_args(args)
    assert result == (None, 8020, None, False, ['test.json'], None)


def test_path_only():
    args = ['--path=/tmp/test', '--config-files=test.json']
    result = parse_args(args)
    assert result == (None, None, '/tmp/test', False, ['test.json'], None)


def test_rest_config_only():
    args = ['--config-files=test.json']
    result = parse_args(args)
    assert result == (None, 8020, None, False, ['test.json'], None)


def test_rest_config_with_host():
    args = ['--host=127.0.0.1', '--config-files=test.json']
    result = parse_args(args)
    assert result == ('127.0.0.1', 8020, None, False, ['test.json'], None)


def test_config_with_api_file():
    args = ['--config-files=test.json', '--api-file=openapi.json']
    result = parse_args(args)
    assert result == (None, 8020, None, False, ['test.json'], 'openapi.json')


class MockLoop:
    def run_until_complete(self, mock):
        return mock

    @staticmethod
    def get_event_loop():
        return MockLoop()


def test_main(monkeypatch):
    _load_engine_config = MagicMock()
    _load_api_file = MagicMock()
    _enable_swagger = MagicMock()
    _register_server_config = MagicMock()
    _register_apps = MagicMock()
    _load_app_config = MagicMock()
    _run_app = MagicMock()
    _create_scheduler = MagicMock()
    _start_server = MagicMock()
    _start_app = MagicMock()

    monkeypatch.setattr(web.asyncio, 'get_event_loop', MockLoop.get_event_loop)
    monkeypatch.setattr(web, '_load_engine_config', _load_engine_config)
    monkeypatch.setattr(web.api, 'load_api_file', _load_api_file)
    monkeypatch.setattr(web.api, 'register_server_config', _register_server_config)
    monkeypatch.setattr(web.api, 'register_apps', _register_apps)
    monkeypatch.setattr(web.api, 'enable_swagger', _enable_swagger)
    monkeypatch.setattr(web, '_load_app_config', _load_app_config)
    monkeypatch.setattr(web.web, 'run_app', _run_app)
    monkeypatch.setattr(web, 'start_server', _start_server)
    monkeypatch.setattr(web, 'start_app', _start_app)
    monkeypatch.setattr(web.aiojobs, 'create_scheduler', _create_scheduler)

    web.main(host='test', port=1234, path='//test', start_streams=True,
             config_files=['test_server_file.json', 'test_app_file.json', 'test_app_file2.json'],
             api_file='test_api_file.json')

    assert _load_engine_config.call_args[0] == ('test_server_file.json',)
    assert _start_server.call_count == 1
    assert _load_api_file.call_args[0] == ('test_api_file.json',)
    assert _register_server_config.call_count == 1
    assert _load_app_config.call_args_list[0][0] == ('test_app_file.json',)
    assert _load_app_config.call_args_list[1][0] == ('test_app_file2.json',)
    assert _start_app.call_count == 2
    assert _register_apps.call_count == 1
    assert _enable_swagger.call_count == 1
    assert _run_app.call_args[0] == (web.web_server,)
    assert _run_app.call_args[1] == {'host': 'test', 'path': '//test', 'port': 1234}
