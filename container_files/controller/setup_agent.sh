#!/bin/bash
set -euo pipefail

LNST_SRC="${1:-git+https://github.com/LNST-project/lnst.git}"

UV_VERSION="${UV_VERSION:-0.11.6}"
export UV_PROJECT_ENVIRONMENT="/opt/lnst"
export UV_PYTHON_INSTALL_DIR="/opt/uv/python"
export UV_PYTHON="3.13"

# --- Validation ---

if [[ $EUID -ne 0 ]]; then
    echo "Error: This script must be run as root (use sudo)."
    exit 1
fi

if systemctl is-active --quiet lnst-agent 2>/dev/null && ss -tlnp | grep -q ':9999 '; then
    echo "lnst-agent is already running and listening on port 9999."
    systemctl --no-pager status lnst-agent
    echo "To reinstall, run: systemctl stop lnst-agent && $0 $*"
    exit 0
fi

echo "Installing LNST agent from: $LNST_SRC"

# --- Install system packages ---

echo "Installing system packages..."
dnf install -y \
    python3-devel \
    git \
    gcc \
    libnl3-devel \
    iproute-tc \
    tcpdump \
    iperf3 \

# --- Install uv ---

echo "Installing uv..."
curl -LsSf "https://astral.sh/uv/${UV_VERSION}/install.sh" | sh
export PATH="/root/.local/bin:$PATH"

# --- Install lnst via uv ---

echo "Installing lnst package..."
uv venv --python "$UV_PYTHON" "$UV_PROJECT_ENVIRONMENT"
uv pip install --python "$UV_PROJECT_ENVIRONMENT/bin/python" "$LNST_SRC"

# --- Verify lnst-agent binary ---

if [[ ! -x "$UV_PROJECT_ENVIRONMENT/bin/lnst-agent" ]]; then
    echo "Error: lnst-agent not found after installation."
    exit 1
fi

echo "lnst-agent installed at: $UV_PROJECT_ENVIRONMENT/bin/lnst-agent"

# --- Set up systemd service ---

LNST_COMMIT=$(echo "$LNST_SRC" | sed 's/.*@//')
LNST_REPO=$(echo "$LNST_SRC" | sed 's/^git+//; s/@.*//')
curl -LsSf "${LNST_REPO%.git}/raw/${LNST_COMMIT}/install/lnst-agent.service" \
    -o /usr/lib/systemd/system/lnst-agent.service
systemctl daemon-reload
systemctl enable lnst-agent
systemctl start lnst-agent

# --- Verify agent is running ---

echo ""
echo "Waiting for lnst-agent to listen on port 9999..."
for i in $(seq 1 10); do
    if ss -tlnp | grep -q ':9999 '; then
        echo "LNST agent installed and listening on port 9999."
        systemctl --no-pager status lnst-agent
        exit 0
    fi
    sleep 1
done

echo "Error: lnst-agent is not listening on port 9999."
systemctl --no-pager status lnst-agent || true
exit 1
