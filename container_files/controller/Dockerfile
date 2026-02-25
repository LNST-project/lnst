# syntax=docker/dockerfile:1
FROM fedora:41

COPY --from=ghcr.io/astral-sh/uv:0.11.6 /uv /uvx /bin/

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
    libnl3-devel \
    jq \
    sshpass \
    openssh-clients

RUN mkdir -p /root/.lnst
ARG LNST_SRC=https://github.com/LNST-project/lnst.git
RUN repo="$LNST_SRC" && \
    ref="" && \
    case "$repo" in *@*) ref="${repo##*@}"; repo="${repo%@*}" ;; esac && \
    git clone "$repo" /lnst && \
    if [ -n "$ref" ]; then cd /lnst && git checkout "$ref"; fi
ENV LNST_SRC=${LNST_SRC}

ENV UV_PROJECT_ENVIRONMENT=/root/lnst_venv
RUN cd /lnst && uv sync --extra trex
# UV_PROJECT_ENVIRONMENT places the venv outside /lnst
# to prevent conflicts when user mounts host-machine's
# lnst dir to /lnst

WORKDIR /lnst
CMD ["/lnst/container_files/controller/entrypoint.sh"]
