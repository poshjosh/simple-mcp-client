#!/usr/bin/env bash

source ./pre_run.sh

#printf "\nStarting app directly\n\n"
#python3 src/mcx/cli.py --verbose call "list_tools"

printf "\nStarting app from cli\n\n"
#mcx --verbose use aideas --cmd=node \
#  --arg='/Users/chinomso/dev_ai/automate-idea-to-social-mcp/build/index.js' \
#  --env='AIDEAS_ENV_FILE=/Users/chinomso/.aideas/content/run.env'

mcx use aideas --cmd=docker \
  --arg="run" --arg="-u" --arg="0" --arg="-i" --arg="--rm" \
  --arg="-v" --arg="/var/run/docker.sock:/var/run/docker.sock" \
  --arg="-e" --arg="APP_PROFILES=docker" \
  --arg="-e" --arg="USER_HOME=/Users/chinomso" \
  --arg="poshjosh/aideas-mcp:0.0.1"

mcx list --fmt='tools[*].name'

mcx call list_agents --fmt='content[0].text'

mcx call get_agent_config --arg='agent_name=test-agent'  --fmt='content[0].text'

mcx call create_automation_task \
  --arg='agents=test-agent' \
  --arg='agents=test-log' \
  --fmt='content[0].text'

#mcx call create_automation_task \
#  --arg='agents=test-log' \
#  --arg='agents=twitter' \
#  --arg='text-content=Rest is for the assured' \
#  --fmt='content[0].text'

#mcx call get_task_status \
#  --arg='task_id=634a346b921442dcaa85b93c5fcb1cde' \
#  --fmt='content[0].text'

mcx quit
