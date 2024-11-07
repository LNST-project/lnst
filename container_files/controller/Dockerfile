# syntax=docker/dockerfile:1
FROM fedora:41

RUN dnf install -y initscripts \
    iputils \
    python3.9 \
    python-pip \
    gcc \
    python-devel \
    libxml2-devel \
    libxslt-devel \
    libnl3 \
    lksctp-tools-devel \
    git \
    libnl3-devel &&  \
    curl -sSL https://install.python-poetry.org |  \
    python3 - --version 1.8.3

RUN mkdir -p /root/.lnst
COPY . /lnst
COPY container_files/controller/pool /root/.lnst/pool

RUN cd /lnst && \
    /root/.local/bin/poetry config virtualenvs.path /root/lnst_venv && \
    /root/.local/bin/poetry config virtualenvs.in-project false && \
    /root/.local/bin/poetry install
# setting in-project to false to prevent poetry from
# using in-project .venv which might be present if
# user has mounted host-machine's lnst dir to /lnst

WORKDIR /lnst
CMD ["/lnst/container_files/controller/entrypoint.sh"]
