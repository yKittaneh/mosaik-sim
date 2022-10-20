#!/bin/sh

echo "running start.sh file"

java -cp app.jar org.example.TaskSimulator 180 &
java -jar server.jar 5567