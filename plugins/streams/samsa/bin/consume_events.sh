export SAMSA_CONSUME_NODES="http://localhost:9020,http://localhost:9021" \
    && nohup python plugins/streams/samsa/src/hopeit/samsa/client.py consume $1 &
export SAMSA_CONSUME_NODES="http://localhost:9022" \
    && nohup python plugins/streams/samsa/src/hopeit/samsa/client.py consume $1 &
