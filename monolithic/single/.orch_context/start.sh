#!/bin/sh

echo "running start.sh file"

java -jar /opt/activemq/bin/activemq.jar start &
java -cp app.jar org.example.TaskSimulator &
java -cp sim.jar org.example.NodeSimulator 0.0.0.0:5679 server

# java -cp ./target/edge-node-simulator-1.0-SNAPSHOT.jar org.example.NodeSimulator 127.0.0.1:5679 server
