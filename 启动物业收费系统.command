#!/bin/zsh
cd "$(dirname "$0")"
export PM_PORT=5001
python3 server.py
