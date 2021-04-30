#!/bin/bash
i = "0"
while [[ $i -le 10 ]]
do
    curl -i "localhost:8020/api/samsa/1x0/consume?stream_name=test_stream&consumer_group=$1&batch_size=10"
    ((i++))
    sleep 0.01
done
