#!/usr/bin/env bash
URL="http://localhost:8080/version"
N=${1:-50}
for i in $(seq 1 $N); do
  hdrs=$(curl -sI --max-time 5 "$URL")
  status=$(echo "$hdrs" | head -n1 | awk '{print $2}')
  pool=$(echo "$hdrs" | grep -i '^X-App-Pool:' | awk '{print $2}' | tr -d '\r')
  rid=$(echo "$hdrs" | grep -i '^X-Release-Id:' | awk '{print $2}' | tr -d '\r')
  echo "$i: status=$status pool=${pool:-N/A} release=${rid:-N/A}"
  sleep 0.1
done