#!/bin/sh

echo "running start.sh file"

# todo: maybe make start_sim run the spring jar (or modify this shell file) as many as there are nodes in the nodes config file, instead of it being hard coded like below
java -jar app.jar --nodeId=1

