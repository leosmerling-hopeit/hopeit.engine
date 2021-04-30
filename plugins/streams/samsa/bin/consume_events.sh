#!/bin/bash
nohup curl -i "localhost:9020/api/samsa/1x0/consume?stream_name=test_stream&consumer_group=$1&batch_size=10" &
nohup curl -i "localhost:9021/api/samsa/1x0/consume?stream_name=test_stream&consumer_group=$1&batch_size=10" &
nohup curl -i "localhost:9022/api/samsa/1x0/consume?stream_name=test_stream&consumer_group=$1&batch_size=10" &
