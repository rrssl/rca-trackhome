"""
Python sample for connecting to Google Cloud IoT Core via MQTT, using JWT.
Sends dummy location/time data every second.
"""
import argparse
import datetime
import json
import logging
import random
import time

from trkpy.publish import CloudIOTClient

logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.CRITICAL)


def parse_command_line_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Example Google Cloud IoT Core MQTT device connection code."
        )
    )
    parser.add_argument(
        "--algorithm",
        choices=("RS256", "ES256"),
        required=True,
        help="Which encryption algorithm to use to generate the JWT.",
    )
    parser.add_argument(
        "--ca_certs",
        default="roots.pem",
        help="CA root from https://pki.google.com/roots.pem",
    )
    parser.add_argument(
        "--cloud_region", default="us-central1", help="GCP cloud region"
    )
    parser.add_argument(
        "--device_id",
        required=True,
        help="Cloud IoT Core device id"
    )
    parser.add_argument(
        "--jwt_expires_minutes",
        default=20,
        type=int,
        help="Expiration time, in minutes, for JWT tokens.",
    )
    parser.add_argument(
        "--mqtt_bridge_hostname",
        default="mqtt.googleapis.com",
        help="MQTT bridge hostname.",
    )
    parser.add_argument(
        "--mqtt_bridge_port",
        choices=(8883, 443),
        default=8883,
        type=int,
        help="MQTT bridge port.",
    )
    parser.add_argument(
        "--num_messages",
        type=int,
        default=100,
        help="Number of messages to publish."
    )
    parser.add_argument(
        "--private_key_file",
        required=True,
        help="Path to private key file."
    )
    parser.add_argument(
        "--project_id",
        required=True,
        help="Google Cloud Platform project name",
    )
    parser.add_argument(
        "--registry_id",
        required=True,
        help="Cloud IoT Core registry id"
    )

    return parser.parse_args()


def main():
    """Entry point."""
    args = parse_command_line_args()

    # Topic where location events are published.
    mqtt_topic = f"/devices/{args.device_id}/events/location"
    # Parameters for JWT refresh.
    jwt_iat = datetime.datetime.now(tz=datetime.timezone.utc)
    jwt_exp_mins = args.jwt_expires_minutes
    # Cloud IoT client.
    client = CloudIOTClient(
        args.project_id,
        args.cloud_region,
        args.registry_id,
        args.device_id,
        args.private_key_file,
        args.algorithm,
        args.ca_certs,
        args.mqtt_bridge_hostname,
        args.mqtt_bridge_port,
    )
    # Publish num_messages messages to the MQTT bridge once per second.
    for i in range(1, args.num_messages + 1):
        # Process network events.
        client.loop()
        # Wait if backoff is required.
        if client.should_backoff:
            # If backoff time is too large, give up.
            if client.minimum_backoff_time > client.maximum_backoff_time:
                print("Exceeded maximum backoff time. Giving up.")
                break

            # Otherwise, wait and connect again.
            delay = (
                client.minimum_backoff_time + random.randint(0, 1000) / 1000.0
            )
            print(f"Waiting for {delay} before reconnecting.")
            time.sleep(delay)
            client.minimum_backoff_time *= 2
            client.connect(args.mqtt_bridge_hostname, args.mqtt_bridge_port)

        # Create location record.
        location = {
            'x': random.random(),
            'y': random.random(),
            'z': random.random(),
            't': int(time.time()*1000)
        }
        payload = json.dumps(location)
        print(f"Publishing message {i}/{args.num_messages}: '{payload}'")
        # Refresh JWT if it is too old.
        seconds_since_issue = (
            datetime.datetime.now(tz=datetime.timezone.utc) - jwt_iat
        ).seconds
        if seconds_since_issue > 60 * jwt_exp_mins:
            print(f"Refreshing token after {seconds_since_issue}s")
            jwt_iat = datetime.datetime.now(tz=datetime.timezone.utc)
            client.loop()
            client.disconnect()
            client = CloudIOTClient(
                args.project_id,
                args.cloud_region,
                args.registry_id,
                args.device_id,
                args.private_key_file,
                args.algorithm,
                args.ca_certs,
                args.mqtt_bridge_hostname,
                args.mqtt_bridge_port,
            )
        # Publish "payload" to the MQTT topic. qos=1 means at least once
        # delivery. Cloud IoT Core also supports qos=0 for at most once
        # delivery.
        client.publish(mqtt_topic, payload, qos=1)
        # Send events every second.
        time.sleep(1)

    print("Finished.")


if __name__ == "__main__":
    main()
