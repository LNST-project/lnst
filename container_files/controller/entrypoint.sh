#!/bin/sh
PYTHON_PATH=$(/root/.local/bin/poetry env info -p)/bin/python
POOL_DIR="/root/.lnst/pool"
TED_FILE="/lnst/container_files/controller/pool/test_environment.json"

mkdir -p "$POOL_DIR"

if ls "$POOL_DIR"/*.xml >/dev/null 2>&1; then
    echo "Pool XML files already present in $POOL_DIR, skipping pool generation."
elif [ -f "$TED_FILE" ]; then
    echo "No pool XML files found in $POOL_DIR, generating from $TED_FILE..."
    "$PYTHON_PATH" /lnst/container_files/controller/create_pool.py \
        --test-environment-description "$TED_FILE" \
        -o "$POOL_DIR"
else
    echo "ERROR: No .xml files found in $POOL_DIR and no test environment description found at $TED_FILE" >&2
    exit 1
fi

/lnst/container_files/controller/setup_agents.sh
exec "$PYTHON_PATH" /lnst/container_files/controller/container_runner.py
