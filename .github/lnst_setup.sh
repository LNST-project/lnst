#!/bin/bash

echo Set up system requirements

sudo apt-get update
sudo apt-get install podman -y
sudo systemctl enable --now podman.socket
curl -sSL https://install.python-poetry.org | python3 - --version 1.3.1

echo Set up Podman network requirements

sudo sysctl -w net.ipv4.ip_forward=1
sudo sysctl net.ipv4.conf.all.forwarding=1
sudo iptables -P FORWARD ACCEPT
sudo sysctl -p

echo Install LNST

sudo apt-get install -y iputils-* \
ethtool \
gcc \
python-dev \
libxml2-dev \
libxslt-dev \
qemu-kvm \
libvirt-daemon-system \
libvirt-clients \
bridge-utils \
libvirt-dev \
libnl-3-200 \
libnl-route-3-dev \
git \
libnl-3-dev
export PATH="/root/.local/bin:$PATH"
poetry install -E "containers"

echo Build LNST agents image
sudo -E XDG_RUNTIME_DIR= podman build . -t lnst -f container_files/agent/Dockerfile
