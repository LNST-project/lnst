#!/bin/bash
set -euo pipefail

PYTHON_PATH=$(/root/.local/bin/poetry env info -p)/bin/python
POOL_DIR="/root/.lnst/pool"
TED_FILE="/lnst/container_files/controller/pool/test_environment.json"
SETUP_AGENTS_SCRIPT="/lnst/container_files/controller/setup_agent.sh"

# ---------------------------------------------------------------------------
# Phase 1 -- Pool generation
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Phase 2 -- Remote agent setup
# ---------------------------------------------------------------------------

# Parses host entry $1 from $TED_FILE and populates the array named by $2
# with the ssh command tokens. Sets $hostname and $ssh_port in caller scope.
build_ssh_cmd() {
    local idx="$1"
    local -n _cmd="$2"

    hostname=$(jq -r ".[$idx].hostname"        "$TED_FILE" | xargs)
    ssh_port=$(jq -r ".[$idx].ssh_port"         "$TED_FILE" | xargs)
    local username=$(jq -r ".[$idx].username"          "$TED_FILE" | xargs)
    local password=$(jq -r ".[$idx].password // empty" "$TED_FILE" | xargs)

    _cmd=()
    if [[ -n "$password" ]]; then
        _cmd+=("sshpass" "-p" "$password")
    fi
    _cmd+=("ssh" "-o" "StrictHostKeyChecking=no" "-o" "UserKnownHostsFile=/dev/null"
           "-o" "ConnectTimeout=10" "-p" "$ssh_port" "${username}@${hostname}")
}

if [[ ! -f "$TED_FILE" ]]; then
    echo "WARNING: $TED_FILE not found -- skipping remote agent setup." >&2
else
    echo "Setting up agents on remote hosts defined in $TED_FILE..."
    host_count=$(jq 'length' "$TED_FILE")

    for ((i = 0; i < host_count; i++)); do
        build_ssh_cmd "$i" ssh_cmd

        echo "=== Setting up agent on $hostname (port $ssh_port) ==="
        echo "SSH command: ${ssh_cmd[*]}"

        # Run setup_agents.sh remotely (piped over stdin)
        if ! "${ssh_cmd[@]}" 'bash -s' < "$SETUP_AGENTS_SCRIPT"; then
            echo "ERROR: setup_agent.sh failed on $hostname" >&2
            exit 1
        fi

        # Verify expected NICs exist on the remote host
        mapfile -t expected_macs < <(jq -r ".[$i].test_nic_hw_addrs[]" "$TED_FILE")

        remote_macs=$("${ssh_cmd[@]}" 'cat /sys/class/net/*/address' 2>/dev/null || true)

        for mac in "${expected_macs[@]}"; do
            mac_lower=$(echo "$mac" | tr '[:upper:]' '[:lower:]')

            if ! echo "$remote_macs" | tr '[:upper:]' '[:lower:]' | grep -qF "$mac_lower"; then
                available=$(echo "$remote_macs" | sort -u | paste -sd ', ' -)
                echo "ERROR: NIC with MAC $mac not found on $hostname" >&2
                echo "       Available MACs: $available" >&2
                exit 1
            fi
        done

        echo "=== Agent setup complete on $hostname ==="
    done
fi

# ---------------------------------------------------------------------------
# Phase 3 -- Run controller
# ---------------------------------------------------------------------------
exec "$PYTHON_PATH" /lnst/container_files/controller/container_runner.py
