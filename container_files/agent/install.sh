#!/bin/bash
cd /lnst
uv sync --extra containers

ln -s /lnst/.venv/bin /lnst/.bin

echo "================== Installing iperf  ======================"
cd /
git clone https://github.com/LNST-project/iperf.git
cd iperf
git checkout mptcp_udp_retry_cherrypick
./configure && make && make install
echo "================== Successfully installed iperf  ======================"

echo "================== Installing neper  ======================"
git clone -b lnst-production https://github.com/LNST-project/neper.git /root/neper
cd /root/neper
git --no-pager show --summary HEAD
make -s
echo "================== Successfully installed neper  ======================"
echo "================== Successfully installed LNST  ======================"

