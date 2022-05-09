#!/usr/bin/env python

# Copyright 2017 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Python sample for connecting to Google Cloud IoT Core via MQTT, using JWT.
This example connects to Google Cloud IoT Core via MQTT, using a JWT for device
authentication. After connecting, by default the device publishes 100 messages
to the device's MQTT topic at a rate of one per second, and then exits.
Before you run the sample, you must follow the instructions in the README
for this sample.
"""

# [START iot_mqtt_includes]
import argparse
import datetime
import logging
import random
import ssl
import time

import jwt
import paho.mqtt.client as mqtt

# [END iot_mqtt_includes]

logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.CRITICAL)

# The initial backoff time after a disconnection occurs, in seconds.
minimum_backoff_time = 1

# The maximum backoff time before giving up, in seconds.
MAXIMUM_BACKOFF_TIME = 32

# Whether to wait with exponential backoff before publishing.
should_backoff = False


def create_jwt(project_id, private_key_file, algorithm):
    """Creates a JWT (https://jwt.io) to establish an MQTT connection.
    Args:
     project_id: The cloud project ID this device belongs to
     private_key_file: A path to a file containing either an RSA256 or
             ES256 private key.
     algorithm: The encryption algorithm to use. Either 'RS256' or 'ES256'
    Returns:
        A JWT generated from the given project_id and private key, which
        expires in 20 minutes. After 20 minutes, your client will be
        disconnected, and a new JWT will have to be generated.
    Raises:
        ValueError: If the private_key_file does not contain a known key.
    """

    token = {
        # The time that the token was issued at.
        'iat': datetime.datetime.now(tz=datetime.timezone.utc),
        # The time the token expires.
        'exp': (
            datetime.datetime.now(tz=datetime.timezone.utc)
            + datetime.timedelta(minutes=20)
        ),
        # The audience field should always be set to the GCP project id.
        'aud': project_id,
    }

    # Read the private key file.
    with open(private_key_file, 'r') as handle:
        private_key = handle.read()

    print(
        f"Creating JWT using {algorithm} "
        f"from private key file {private_key_file}"
    )

    return jwt.encode(token, private_key, algorithm=algorithm)


def error_str(rc):
    """Convert a Paho error to a human readable string."""
    return f"{rc}: {mqtt.error_string(rc)}"


def on_connect(unused_client, unused_userdata, unused_flags, rc):
    """Callback for when a device connects."""
    print("on_connect", mqtt.connack_string(rc))

    # After a successful connect, reset backoff time and stop backing off.
    global should_backoff
    global minimum_backoff_time
    should_backoff = False
    minimum_backoff_time = 1


def on_disconnect(unused_client, unused_userdata, rc):
    """Paho callback for when a device disconnects."""
    print("on_disconnect", error_str(rc))

    # Since a disconnect occurred, the next loop iteration will wait with
    # exponential backoff.
    global should_backoff
    should_backoff = True


def on_publish(unused_client, unused_userdata, unused_mid):
    """Paho callback when a message is sent to the broker."""
    print("on_publish")


def on_message(unused_client, unused_userdata, message):
    """Callback when the device receives a message on a subscription."""
    payload = str(message.payload.decode('utf-8'))
    print(
        f"Received message '{payload}' "
        f"on topic '{message.topic}' with Qos {message.qos}"
    )


def get_client(
    project_id,
    cloud_region,
    registry_id,
    device_id,
    private_key_file,
    algorithm,
    ca_certs,
    mqtt_bridge_hostname,
    mqtt_bridge_port,
):
    """Create our MQTT client."""
    # The client_id is a unique string that identifies this device.
    # For Google Cloud IoT Core, it must be in the format below.
    client_id = (
        f"projects/{project_id}/locations/{cloud_region}/"
        f"registries/{registry_id}/devices/{device_id}"
    )
    print(f"Device client_id is '{client_id}'")

    client = mqtt.Client(client_id=client_id)

    # With Google Cloud IoT Core, the username field is ignored, and the
    # password field is used to transmit a JWT to authorize the device.
    client.username_pw_set(
        username="unused",
        password=create_jwt(project_id, private_key_file, algorithm)
    )

    # Enable SSL/TLS support.
    client.tls_set(ca_certs=ca_certs, tls_version=ssl.PROTOCOL_TLSv1_2)

    # Register message callbacks. https://eclipse.org/paho/clients/python/docs/
    # describes additional callbacks that Paho supports. In this example, the
    # callbacks just print to standard out.
    client.on_connect = on_connect
    client.on_publish = on_publish
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    # Connect to the Google MQTT bridge.
    client.connect(mqtt_bridge_hostname, mqtt_bridge_port)

    # This is the topic that the device will receive configuration updates on.
    mqtt_config_topic = f"/devices/{device_id}/config"

    # Subscribe to the config topic.
    client.subscribe(mqtt_config_topic, qos=1)

    # The topic that the device will receive commands on.
    mqtt_command_topic = f"/devices/{device_id}/commands/#"

    # Subscribe to the commands topic, QoS 1 enables message acknowledgement.
    print(f"Subscribing to {mqtt_command_topic}")
    client.subscribe(mqtt_command_topic, qos=0)

    return client


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
        "--data",
        default="Hello there",
        help="The telemetry data sent on behalf of a device",
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
        "--listen_dur",
        default=60,
        type=int,
        help="Duration (seconds) to listen for configuration messages",
    )
    parser.add_argument(
        "--message_type",
        choices=("event", "state"),
        default="event",
        help=(
            "Indicates whether the message to be published is a "
            "telemetry event or a device state message."
        ),
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


def mqtt_device_demo(args):
    """Connects a device, sends data, and receives data."""
    # [START iot_mqtt_run]
    global minimum_backoff_time
    global MAXIMUM_BACKOFF_TIME

    # Publish to the events or state topic based on the flag.
    sub_topic = "events" if args.message_type == "event" else "state"

    mqtt_topic = f"/devices/{args.device_id}/{sub_topic}"

    jwt_iat = datetime.datetime.now(tz=datetime.timezone.utc)
    jwt_exp_mins = args.jwt_expires_minutes
    client = get_client(
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
        if should_backoff:
            # If backoff time is too large, give up.
            if minimum_backoff_time > MAXIMUM_BACKOFF_TIME:
                print("Exceeded maximum backoff time. Giving up.")
                break

            # Otherwise, wait and connect again.
            delay = minimum_backoff_time + random.randint(0, 1000) / 1000.0
            print(f"Waiting for {delay} before reconnecting.")
            time.sleep(delay)
            minimum_backoff_time *= 2
            client.connect(args.mqtt_bridge_hostname, args.mqtt_bridge_port)

        payload = f"{args.registry_id}/{args.device_id}-payload-{i}"
        print(f"Publishing message {i}/{args.num_messages}: '{payload}'")

        seconds_since_issue = (
            datetime.datetime.now(tz=datetime.timezone.utc) - jwt_iat
        ).seconds
        if seconds_since_issue > 60 * jwt_exp_mins:
            print("Refreshing token after {}s".format(seconds_since_issue))
            jwt_iat = datetime.datetime.now(tz=datetime.timezone.utc)
            client.loop()
            client.disconnect()
            client = get_client(
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

        # Send events every second. State should not be updated as often
        for _ in range(0, 60):
            time.sleep(1)
            client.loop()
    # [END iot_mqtt_run]


def main():
    args = parse_command_line_args()
    mqtt_device_demo(args)
    print("Finished.")


if __name__ == "__main__":
    main()
