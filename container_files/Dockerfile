# syntax=docker/dockerfile:1
FROM fedora:34

RUN dnf install -y initscripts \
    iputils \
    ethtool \
    python3.6 \
    python-pip \
    gcc \
    python-devel \
    libxml2-devel \
    libxslt-devel \
    libvirt \
    libvirt-devel \
    libnl3 \
    git \
    libnl3-devel && pip install 'poetry==1.1.7'

COPY . /lnst
RUN cd /lnst/container_files && chmod +x install.sh && sh install.sh

CMD cd /lnst/.bin && ./lnst-slave
