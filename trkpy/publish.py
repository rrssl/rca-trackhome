"""Cloud IoT publishing client."""
import datetime
import logging
import ssl
import time

import jwt
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


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

    logger.debug(
        f"Creating JWT using {algorithm} "
        f"from private key file {private_key_file}"
    )

    return jwt.encode(token, private_key, algorithm=algorithm)


class CloudIOTClient(mqtt.Client):
    """MQTT client adapted for use with Cloud IoT."""
    # pylint: disable=arguments-differ,invalid-overridden-method

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
        self.project_id = project_id
        self.device_id = device_id
        self.private_key_file = private_key_file
        self.algorithm = algorithm
        self.ca_certs = ca_certs
        self.mqtt_bridge_hostname = mqtt_bridge_hostname
        self.mqtt_bridge_port = mqtt_bridge_port
        # The client_id is a unique string that identifies this device. For
        # Cloud IoT, it must be in the format below.
        self.client_id = (
            f"projects/{project_id}/locations/{cloud_region}/"
            f"registries/{registry_id}/devices/{device_id}"
        )

        super().__init__(client_id=self.client_id)
        self.connected = False
        self._setup()

    def reinitialise(self):
        # Can't call super().reinitialise because it ignores custom __init__
        # so this mimicks super().reinitialise
        self._reset_sockets()

        super().__init__(client_id=self.client_id)
        self.connected = False
        self._setup()

    def _setup(self):
        """Set up authentication, connection and subscriptions."""
        # With Google Cloud IoT Core, the username field is ignored, and the
        # password field is used to transmit a JWT to authorize the device.
        self.username_pw_set(
            username="unused",
            password=create_jwt(
                self.project_id, self.private_key_file, self.algorithm
            )
        )
        # Enable SSL/TLS support.
        self.tls_set(ca_certs=self.ca_certs, tls_version=ssl.PROTOCOL_TLSv1_2)
        # Connect to the Google MQTT bridge.
        self.connect(self.mqtt_bridge_hostname, self.mqtt_bridge_port)
        # This is the topic that the device will receive configuration updates
        # on.
        mqtt_config_topic = f"/devices/{self.device_id}/config"
        # Subscribe to the config topic.
        self.subscribe(mqtt_config_topic, qos=1)
        # The topic that the device will receive commands on.
        mqtt_command_topic = f"/devices/{self.device_id}/commands/#"
        # Subscribe to the commands topic, QoS 1 enables message
        # acknowledgement.
        self.subscribe(mqtt_command_topic, qos=0)

    def on_connect(self, unused_client, unused_userdata, unused_flags, rc):
        """Callback for when a device connects."""
        logger.debug(mqtt.connack_string(rc))
        self.connected = True

    def on_disconnect(self, unused_client, unused_userdata, rc):
        """Paho callback for when a device disconnects."""
        logger.debug(mqtt.error_string(rc))
        self.connected = False

    def on_publish(self, unused_client, unused_userdata, unused_mid):
        """Paho callback when a message is sent to the broker."""
        logger.debug("Successfully published.")

    def on_message(self, unused_client, unused_userdata, message):
        """Callback when the device receives a message on a subscription."""
        payload = str(message.payload.decode('utf-8'))
        logger.debug(
            f"Received message '{payload}' "
            f"on topic '{message.topic}' with Qos {message.qos}"
        )


class CloudHandler(logging.Handler):
    """Publishes logs to the cloud."""

    def __init__(
        self,
        project_id: str,
        cloud_region: str,
        registry_id: str,
        device_id: str,
        private_key_file: str,
        algorithm: str,
        ca_certs: str,
        mqtt_bridge_hostname: str,
        mqtt_bridge_port: int,
        jwt_expires_minutes: int,
        level=logging.NOTSET
    ):
        super().__init__(level)
        self.jwt_iat = time.time()
        self.jwt_expires_mins = jwt_expires_minutes
        # Topic where location events are published.
        # Cloud IoT client.
        self.client = CloudIOTClient(
            project_id,
            cloud_region,
            registry_id,
            device_id,
            private_key_file,
            algorithm,
            ca_certs,
            mqtt_bridge_hostname,
            mqtt_bridge_port,
        )
        logger.debug("Cloud logger initialized.")
        self.client.loop()

    def emit(self, record: logging.LogRecord):
        client = self.client
        # Process network events.
        client.loop()
        # Reconnect if needed.
        if not client.connected:
            client.reconnect()
            client.loop()
        # Refresh JWT if it is too old.
        seconds_since_issue = time.time() - self.jwt_iat
        if seconds_since_issue > 60 * self.jwt_expires_mins:
            logger.debug(
                f"Refreshing token after {seconds_since_issue/60} min"
            )
            # self.client.loop()
            client.disconnect()
            self.jwt_iat = time.time()
            client.reinitialise()
            client.loop()
        # Publish record to the MQTT topic. qos=1 means at least once delivery.
        # Cloud IoT Core also supports qos=0 for at most once delivery.
        if record.levelno == logging.INFO:
            topic = "location"
        elif record.levelno == logging.DEBUG:
            topic = "debug"
        else:
            topic = "default"
        mqtt_topic = f"/devices/{client.device_id}/events/{topic}"
        client.publish(mqtt_topic, record.getMessage(), qos=1)
