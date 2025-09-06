#!/usr/bin/env bash

source ./pre_run.sh

printf "\nStarting app directly\n\n"
mcx --verbose use aideas --cmd=node \
  --arg='/Users/chinomso/dev_ai/automate-idea-to-social-mcp/build/index.js' \
  --env='AIDEAS_ENV_FILE=/Users/chinomso/.aideas/content/run.env'