# syntax=docker/dockerfile:1
FROM fedora:41

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN dnf install -y initscripts \
    iputils \
    python3 \
    gcc \
    python3-devel \
    libxml2-devel \
    libxslt-devel \
    libnl3 \
    lksctp-tools-devel \
    git \
    libnl3-devel

RUN mkdir -p /root/.lnst
COPY . /lnst
COPY container_files/controller/pool /root/.lnst/pool

ENV UV_PROJECT_ENVIRONMENT=/root/lnst_venv
RUN cd /lnst && uv sync --frozen
# UV_PROJECT_ENVIRONMENT places the venv outside /lnst
# to prevent conflicts when user mounts host-machine's
# lnst dir to /lnst

WORKDIR /lnst
CMD ["/lnst/container_files/controller/entrypoint.sh"]
