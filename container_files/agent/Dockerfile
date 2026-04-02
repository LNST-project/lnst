# syntax=docker/dockerfile:1
FROM fedora:41

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN dnf install -y initscripts \
    iputils \
    ethtool \
    python3 \
    gcc \
    python3-devel \
    libxml2-devel \
    libxslt-devel \
    libvirt \
    libvirt-devel \
    libnl3 \
    lksctp-tools-devel \
    git \
    perf \
    perftest \
    tcpdump \
    libnl3-devel \
    nftables \
    openvswitch \
    teamd \
    kernel-tools

COPY . /lnst
RUN cd /lnst/container_files/agent && chmod +x install.sh && sh install.sh

CMD cd /lnst/.bin && ./lnst-agent
