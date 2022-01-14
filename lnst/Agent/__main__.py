#! /usr/bin/env python3
"""
LNST Agent

This module defines the main entry point for running an LNST Agent.
Running the `main` method will start the agent and wait for connections from
LNST Controller(s)
"""
import os
import logging
import argparse
from pathlib import Path
from lnst.Common.Logs import LoggingCtl
from lnst.Common.Colours import load_presets_from_config
from .Config import AgentConfig
from .NetTestSlave import NetTestSlave as Agent

DEFAULT_USER_CFG = Path.home() / ".lnst" / "lnst-agent.conf"


def main():
    parser = argparse.ArgumentParser(description="LNST Agent")
    parser.add_argument("-d", "--debug", action='store_true', help="emit debugging messages")
    parser.add_argument("-m", "--no-colours", action='store_true', help="disable coloured terminal output")
    parser.add_argument("-p", "--port", type=int, default=None, help="LNST RPC port to listen on")
    parser.add_argument("-c", "--config", default=DEFAULT_USER_CFG, help="Config file")
    args = parser.parse_args()

    agent_config = AgentConfig()

    if os.path.isfile(args.config):
        agent_config.load_config(args.config)
    #else:
    #    agent_config.load_config("/dev/null") #TODO Do we need this? Is there some other way to handle it

    load_presets_from_config(agent_config)
    coloured_output = not (agent_config.get_option("colours", "disable_colours") or args.no_colours)
    log_ctl = LoggingCtl(args.debug,
                     log_dir=agent_config.get_option('environment', 'log_dir'),
                     colours=coloured_output)
    logging.info("Started")

    if args.port != None:
        agent_config.set_option("environment", "rpcport", args.port)

    agent = Agent(log_ctl, agent_config)
    agent.run()


if __name__ == "__main__":
    main()
