"""
Python sample for connecting to Google Cloud IoT Core via MQTT, using JWT.
Sends dummy location/time data every second.
"""
import argparse
import json
import logging
import random
import time
from pathlib import Path

import yaml

import track_publish

logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.CRITICAL)


def get_arg_parser():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Example Google Cloud IoT Core MQTT device connection code."
        )
    )
    parser.add_argument(
        "--config",
        metavar="FILE",
        required=True,
        help="Path to the YAML config file."
    )
    parser.add_argument(
        "--num_messages",
        type=int,
        default=100,
        help="Number of messages to publish."
    )

    return parser


def get_config():
    # Load the configuration.
    aconf, fconf_override = get_arg_parser().parse_known_args()
    with open(aconf.config, 'r') as handle:
        fconf = yaml.safe_load(handle)
    # Override file config with "--section.option val" command line arguments.
    args = iter(fconf_override)
    for name, val in zip(args, args):
        section, option = name[2:].split('.')
        fconf[section][option] = val
    # Preprocess paths to make life easier.
    for section in fconf.values():
        for key, value in section.items():
            if not isinstance(value, str):
                continue
            if "/" in value or value in (".", "..", "~"):  # UNIX path
                section[key] = Path(value)
    # Merge configs.
    conf = vars(aconf) | fconf
    # Process some specific paths.
    auth_dir = conf['global']['auth_dir']
    conf['cloud']['ca_certs'] = auth_dir / conf['cloud']['ca_certs']
    conf['cloud']['private_key_file'] = (
        auth_dir / conf['cloud']['private_key_file']
    )
    return conf


def on_message(unused_client, unused_userdata, message):
    """Method to demonstrate that on_message can be overriden dynamically
    (e.g. to receive commands)."""
    payload = str(message.payload.decode('utf-8'))
    print(f"I just received {payload}")


def main():
    """Entry point."""
    conf = get_config()
    client = track_publish.CloudIOTClient(**conf['cloud'])
    logger = track_publish.init_logger(client, conf)
    client.on_message = on_message
    # Publish num_messages messages to the MQTT bridge once per second.
    logger.debug("Starting.")
    for _ in range(conf['num_messages']):
        # Create location record.
        location = {
            'x': random.random(),
            'y': random.random(),
            'z': random.random(),
            'i': f"0x000{random.randint(0, 3)}",
            't': int(time.time()*1000)
        }
        payload = json.dumps(location)
        logger.info(payload)
        # Send events every second.
        time.sleep(1)
    logger.debug("Finished.")
    client.disconnect()


if __name__ == "__main__":
    main()
