#!/bin/bash
export PATH="/root/.local/bin:$PATH"
poetry install -E "containers"

venv_path=$(poetry env info -p)
echo "$venv_path"
ln -s $venv_path/bin /lnst/.bin

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

