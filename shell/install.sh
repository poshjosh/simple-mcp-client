#!/usr/bin/env bash

set -euo pipefail

VIRTUAL_ENV_DIR=".venv"

cd ..

if [ ! -d "$VIRTUAL_ENV_DIR" ]; then
  printf "\nCreating virtual environment: %s\n" "$VIRTUAL_ENV_DIR"
  python3 -m venv "$VIRTUAL_ENV_DIR"
fi

printf "\nActivating virtual environment: %s\n" "$VIRTUAL_ENV_DIR"

source "${VIRTUAL_ENV_DIR}/bin/activate"

python3 -m pip install --upgrade pip

python3 -m pip install pip-tools

cd "src/mcx"

printf "\nCompiling dependencies to requirements.txt\n"
pip-compile requirements.in > requirements.txt

printf "\nInstalling dependencies from requirements.txt\n"
python3 -m pip install -r requirements.txt
