"""
Python sample for connecting to Google Cloud IoT Core via MQTT, using JWT.
Sends dummy location/time data every second.
"""
import argparse
import json
import logging
import random
import time

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

    logging.basicConfig(level=logging.DEBUG)
    # Create logger.
    logger = logging.getLogger("cloud")
    logger.setLevel(logging.DEBUG)
    cloud_handler = CloudHandler(**conf['cloud'])
    logger.addHandler(cloud_handler)
    # Publish num_messages messages to the MQTT bridge once per second.
    logger.debug("Starting")
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
    cloud_handler.client.disconnect()


if __name__ == "__main__":
    main()
