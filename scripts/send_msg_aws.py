"""
Utility to send messages to a device (config, commands) via AWS MQTT.
"""
import argparse
import json
import logging
import time

import track_publish
from trkpy.cloud import AWSClient


def get_arg_parser():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
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
        help="Command to send to the device.",
    )
    parser.add_argument(
        "--profile",
        help="Path to the JSON config to send to the device.",
    )
    return parser


def main():
    """Entry point."""
    track_publish.get_arg_parser = get_arg_parser
    conf = track_publish.get_config()
    logging.basicConfig(level=logging.DEBUG)
    client = AWSClient(**conf['cloud']['aws'])
    client.start()
    while not client.connected:
        logging.debug("Waiting to connect...")
        time.sleep(1)
    if conf.get('command') is not None:
        client.publish(f"commands/{conf['device']}", conf['command'])
    elif conf.get('profile') is not None:
        with open(conf['profile'], 'r') as handle:
            profile = json.load(handle)
        client.publish(f"config/{conf['device']}", json.dumps(profile))
    client.disconnect()


if __name__ == "__main__":
    main()
