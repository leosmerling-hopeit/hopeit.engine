SAMSA_CONSUME_NODES="http://localhost:9200" && nohup hopeit_server run --port=9020 --config-files=engine/config/dev-noauth.json,plugins/streams/samsa/config/1x0.json &
SAMSA_CONSUME_NODES="http://localhost:9201" && nohup hopeit_server run --port=9021 --config-files=engine/config/dev-noauth.json,plugins/streams/samsa/config/1x0.json &
SAMSA_CONSUME_NODES="http://localhost:9202" && nohup hopeit_server run --port=9022 --config-files=engine/config/dev-noauth.json,plugins/streams/samsa/config/1x0.json &
