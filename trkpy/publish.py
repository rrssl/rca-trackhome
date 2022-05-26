"""Cloud IoT publishing client."""
import datetime
import ssl

import jwt
import paho.mqtt.client as mqtt


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
    with open(private_key_file, 'r', encoding='ascii') as handle:
        private_key = handle.read()

    print(
        f"Creating JWT using {algorithm} "
        f"from private key file {private_key_file}"
    )

    return jwt.encode(token, private_key, algorithm=algorithm)


def error_str(rc):  # pylint: disable=invalid-name
    """Convert a Paho error to a human readable string."""
    return f"{rc}: {mqtt.error_string(rc)}"


class CloudIOTClient(mqtt.Client):
    """MQTT client adapted for use with Cloud IoT."""
    # pylint: disable=arguments-differ,invalid-overridden-method
    # The maximum backoff time before giving up, in seconds.
    maximum_backoff_time = 32

    def __init__(
        self,
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
        # The client_id is a unique string that identifies this device. For
        # Cloud IoT, it must be in the format below.
        client_id = (
            f"projects/{project_id}/locations/{cloud_region}/"
            f"registries/{registry_id}/devices/{device_id}"
        )
        print(f"Device client_id is '{client_id}'")
        super().__init__(client_id=client_id)
        # With Google Cloud IoT Core, the username field is ignored, and the
        # password field is used to transmit a JWT to authorize the device.
        self.username_pw_set(
            username="unused",
            password=create_jwt(project_id, private_key_file, algorithm)
        )
        # Enable SSL/TLS support.
        self.tls_set(ca_certs=ca_certs, tls_version=ssl.PROTOCOL_TLSv1_2)
        # Connect to the Google MQTT bridge.
        self.connect(mqtt_bridge_hostname, mqtt_bridge_port)
        # This is the topic that the device will receive configuration updates
        # on.
        mqtt_config_topic = f"/devices/{device_id}/config"
        # Subscribe to the config topic.
        self.subscribe(mqtt_config_topic, qos=1)
        # The topic that the device will receive commands on.
        mqtt_command_topic = f"/devices/{device_id}/commands/#"
        # Subscribe to the commands topic, QoS 1 enables message
        # acknowledgement.
        print(f"Subscribing to {mqtt_command_topic}")
        self.subscribe(mqtt_command_topic, qos=0)
        # Whether to wait with exponential backoff before publishing.
        self.should_backoff = False
        # The initial backoff time after a disconnection occurs, in seconds.
        self.minimum_backoff_time = 1

    def on_connect(self, unused_client, unused_userdata, unused_flags, rc):
        """Callback for when a device connects."""
        print("on_connect", mqtt.connack_string(rc))
        # After a successful connect, reset backoff time and stop backing off.
        self.should_backoff = False
        self.minimum_backoff_time = 1

    def on_disconnect(self, unused_client, unused_userdata, rc):
        """Paho callback for when a device disconnects."""
        print("on_disconnect", error_str(rc))
        # Since a disconnect occurred, the next loop iteration will wait with
        # exponential backoff.
        self.should_backoff = True

    def on_publish(self, unused_client, unused_userdata, unused_mid):
        """Paho callback when a message is sent to the broker."""
        print("on_publish")

    def on_message(self, unused_client, unused_userdata, message):
        """Callback when the device receives a message on a subscription."""
        payload = str(message.payload.decode('utf-8'))
        print(
            f"Received message '{payload}' "
            f"on topic '{message.topic}' with Qos {message.qos}"
        )
