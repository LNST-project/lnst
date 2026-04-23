#!/bin/python

import json
import yaml
import argparse
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom

def main():
    parser = argparse.ArgumentParser(description="Generate an LNST Machine pool from test environment description")

    parser.add_argument(
        '--test-environment-description',
        type=load_TED,
        required=True,
        help="Path to the JSON or YAML test environment description file"
    )
    parser.add_argument(
        '-o', '--output',
        type=Path,
        required=True,
        help="Directory where to output Machine pool files",
    )

    args = parser.parse_args()

    pool_path = create_machine_pool(args.test_environment_description, args.output)
    print(pool_path)


def create_machine_pool(test_environment_description, pool_path):
    # create a clean pool directory
    pool_path.mkdir(parents=True, exist_ok=True)
    for item in pool_path.iterdir():
        if item.is_file():
            item.unlink()

    for machine in test_environment_description:
        test_system_name = machine['test_system_name']
        root = ET.Element("agentmachine")

        params_node = ET.SubElement(root, "params")
        add_param(params_node, "hostname", machine['hostname'])
        add_param(params_node, "rpc_port", "9999")

        interfaces_node = ET.SubElement(root, "interfaces")

        for i, mac_address in enumerate(machine['test_nic_hw_addrs']):
            eth_node = ET.SubElement(interfaces_node, "eth", {
                "label": "net1",
                "id": f"eth{i}",
            })

            # Nested <params><param name="hwaddr" .../></params>
            eth_params = ET.SubElement(eth_node, "params")
            add_param(eth_params, "hwaddr", mac_address)
            add_param(eth_params, "driver", "any")
            add_param(eth_params, "nic_speed", "1")
            add_param(eth_params, "nic_model", "1")

        # Prettify the XML string
        xml_str = ET.tostring(root, encoding='utf-8')
        pretty_xml = minidom.parseString(xml_str).toprettyxml(indent="    ")

        # Save to file
        save_path = Path(pool_path) / f"{test_system_name}_agent.xml"
        save_path.write_text(pretty_xml)
        print(f"Generated XML at: {save_path}")

    return pool_path

def add_param(parent, name, value):
    """Helper to create <param name="X" value="Y"/> nodes."""
    ET.SubElement(parent, "param", {"name": name, "value": str(value)})

def load_TED(file_path):
    """Reads a JSON or YAML file and returns a Python dict."""
    path = Path(file_path)
    if not path.exists():
        raise argparse.ArgumentTypeError(f"File {file_path} does not exist.")

    ext = path.suffix.lower()

    with open(file_path, 'r') as f:
        if ext in ['.yaml', '.yml']:
            return yaml.safe_load(f)
        elif ext == '.json':
            return json.load(f)
        else:
            raise argparse.ArgumentTypeError("File must be .json, .yaml, or .yml")

if __name__ == "__main__":
    main()
