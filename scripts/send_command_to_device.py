"""Send a string command to a device."""
import argparse
from pathlib import Path

import yaml
from google.cloud.iot_v1 import DeviceManagerClient


def get_arg_parser():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=__doc__
    )
    parser.add_argument(
        "--config",
        metavar="FILE",
        required=True,
        help="Path to the YAML config file."
    )
    parser.add_argument(
        "--device",
        required=True,
        help="Name of the device",
    )
    parser.add_argument(
        "--command",
        required=True,
        help="Command to send to the device.",
    )

    return parser


def get_config():
    aconf = get_arg_parser().parse_args()
    with open(aconf.config, 'r') as stream:
        fconf = yaml.safe_load(stream)
    return vars(aconf) | fconf


def main():
    """Entry point."""
    conf = get_config()
    auth_dir = Path(conf['global']['auth_dir'])
    conf['pull']['service_account_json'] = (
        auth_dir / conf['pull']['service_account_json']
    )
    client = DeviceManagerClient.from_service_account_json(
        conf['pull']['service_account_json']
    )
    device_path = client.device_path(
        conf['publish']['project_id'],
        conf['publish']['cloud_region'],
        conf['publish']['registry_id'],
        conf['device']
    )
    command = conf['command'].encode('utf-8')
    resp = client.send_command_to_device(name=device_path, binary_data=command)
    print(resp)


if __name__ == "__main__":
    main()
