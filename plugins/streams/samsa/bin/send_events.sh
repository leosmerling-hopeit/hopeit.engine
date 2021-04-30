#!/bin/bash

i = "0"

template='{"items": [{"key": "%s", "payload": "x"}]}'

while [[ $i -le 1000 ]]
do
    json_string=$(printf "$template" "$i")
    curl -i -d "$json_string" "localhost:8020/api/samsa/1x0/push?stream_name=test_stream"
    ((i++))
    # sleep 0.01
done
