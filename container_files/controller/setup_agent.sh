#!/bin/bash
set -euo pipefail

LNST_SRC="${1:-git+https://github.com/LNST-project/lnst.git@25cd5e9bdb80ca562c0d9ba5d40f124ba28ca77d}"

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
    python3-pip \
    git \
    gcc \
    libnl3-devel \
    iproute-tc \
    tcpdump \
    iperf3 \

# --- Install lnst via pip ---

echo "Installing lnst package..."
# --break-system-packages: required on Python 3.12+ (PEP 668) for system-wide
# install. Needed because lnst-agent.service hardcodes /usr/local/bin/lnst-agent.
# Older pip (RHEL9) doesn't have this flag, so only use it when supported.
PIP_FLAGS=()
if pip3 install --help 2>&1 | grep -q break-system-packages; then
    PIP_FLAGS=(--break-system-packages)
fi
pip3 install "${PIP_FLAGS[@]}" "$LNST_SRC"

# --- Verify lnst-agent binary ---

if ! command -v lnst-agent &>/dev/null; then
    echo "Error: lnst-agent not found after installation."
    exit 1
fi

echo "lnst-agent installed at: $(command -v lnst-agent)"

# --- Set up systemd service ---

SITE_PACKAGES=$(pip3 show lnst | awk '/^Location:/ {print $2}')
cp "$SITE_PACKAGES/install/lnst-agent.service" /usr/lib/systemd/system/
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
