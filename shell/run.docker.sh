#!/usr/bin/env bash

source ./pre_run.sh

printf "\nStarting app from cli\n\n"

mcx use aideas --cmd=docker \
  --arg="run" --arg="-u" --arg="0" --arg="-i" --arg="--rm" \
  --arg="-v" --arg="/var/run/docker.sock:/var/run/docker.sock" \
  --arg="-e" --arg="APP_PROFILES=docker" \
  --arg="-e" --arg="USER_HOME=/Users/chinomso" \
  --arg="poshjosh/aideas-mcp:0.0.1"

mcx list --fmt='tools[*].name'

mcx call list_agents | tr -d '\n' | jq '.content[0].text' | jq 'fromjson.agents'

mcx call get_agent_config --arg='agent_name=test-agent' \
  --fmt='content[0].text' | tr -d '\n' | jq "fromjson"

task_creation_response=$(mcx call create_automation_task \
  --arg='agents=test-log' \
  --arg='agents=twitter' \
  --arg='text-content=Rest is for the assured')

task_id=$(echo "$task_creation_response" | tr -d '\n' | jq '.content[0].text' | jq --raw-output 'fromjson.task_id')

printf "\nGetting status of task with ID: %s\n" "$task_id"

mcx call get_task_status \
  --arg="task_id=$task_id" \
  --fmt='content[0].text' | tr -d '\n' | jq "fromjson"

mcx --verbose quit
