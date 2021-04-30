#!/bin/bash

i = "0"

template='{"items": [{"key": "%s", "payload": "x"}]}'

while [[ $i -le 100 ]]
do
    python plugins/streams/samsa/src/hopeit/samsa/client.py
done
