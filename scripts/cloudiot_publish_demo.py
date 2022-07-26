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

from trkpy.publish import CloudHandler

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
    aconf = get_arg_parser().parse_args()
    with open(aconf.config, 'r') as stream:
        fconf = yaml.safe_load(stream)
    return vars(aconf) | fconf


def main():
    """Entry point."""
    conf = get_config()
    auth_dir = Path(conf['global']['auth_dir'])
    conf['publish']['ca_certs'] = auth_dir / conf['publish']['ca_certs']
    conf['publish']['private_key_file'] = (
        auth_dir / conf['publish']['private_key_file'])
    out_dir = Path(conf['global']['out_dir'])
    name = Path(__file__).with_suffix("").name
    log_path = out_dir / f"{name}.log"

    # Create loggers.
    # - root logger: logs to a local file.
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    file_handler = logging.FileHandler(log_path, encoding='ascii')
    file_formatter = logging.Formatter(
        fmt='|{asctime}|{levelname}|{name}|{funcName}|{message}',
        datefmt='%Y-%m-%d %H:%M:%S',
        style='{'
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    # - cloud logger.
    cloud_logger = logging.getLogger("cloud")
    cloud_handler = CloudHandler(**conf['publish'])
    cloud_logger.addHandler(cloud_handler)
    # Publish num_messages messages to the MQTT bridge once per second.
    cloud_logger.debug("Starting.")
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
        cloud_logger.info(payload)
        # Send events every second.
        time.sleep(1)
    cloud_logger.debug("Finished.")
    cloud_handler.client.disconnect()


if __name__ == "__main__":
    main()
