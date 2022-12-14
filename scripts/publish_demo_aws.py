"""
Python sample for publishing to AWS IoT via MQTT.
"""
import argparse
import json
# import logging
import random
import time

import track_publish
from trkpy.cloud import AWSClient

# logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.CRITICAL)


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
        default=10,
        help="Number of messages to publish."
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=1,
        help="Publishing interval in seconds."
    )
    return parser


def on_message(unused_client, unused_userdata, message):
    """Method to demonstrate that on_message can be overriden dynamically
    (e.g. to receive commands)."""
    payload = str(message.payload.decode('utf-8'))
    if payload[0] == '{':
        payload = json.loads(payload)
    print(f"I just received {payload}")


def main():
    """Entry point."""
    track_publish.get_arg_parser = get_arg_parser
    conf = track_publish.get_config()
    client = AWSClient(**conf['cloud']['aws'])
    client._client.on_message = on_message
    logger = track_publish.init_logger(client, conf, term_out=True)
    while not client.connected:
        time.sleep(1)
    # Publish num_messages messages to the MQTT server every interval second.
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
        time.sleep(conf['interval'])
    logger.debug("Finished.")
    client.disconnect()


if __name__ == "__main__":
    main()
