#!/bin/sh
PYTHON_PATH=$(/root/.local/bin/poetry env info -p)/bin/python
exec "$PYTHON_PATH" /lnst/container_files/controller/container_runner.py
