#!/usr/bin/env bash
# Kullanim: ./run.sh   -> http://localhost:8000
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate && pip install -q -r requirements.txt
exec uvicorn "trader.api:get_app" --factory --host 127.0.0.1 --port 8000
