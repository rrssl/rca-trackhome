"""MQTT clients for Google Cloud and AWS."""
import datetime
import logging
import ssl
import time
from pathlib import Path

import jwt
import paho.mqtt.client as mqtt
from paho.mqtt.packettypes import PacketTypes

logger = logging.getLogger(__name__)


class CloudClient:
    """MQTT client wrapper to publish and receive location data and logs."""

    def __init__(
        self,
        client_id: str,
        host: str,
        port: int,
        ca_certs: Path,
        publisher: bool = True
    ):
        self.connected = False
        self.client_id = client_id
        self._client = mqtt.Client(client_id, protocol=mqtt.MQTTv5)
        self._setup_callbacks()
        # Connect.
        self.ca_certs = ca_certs
        self._setup_auth()
        self.host = host  # kept for reinitialise()
        self.port = port
        self.publisher = publisher
        self._client.connect(host, port)

    def _get_topic_path(self, topic: str) -> str:
        """To be reimplemented for providers with specific topic paths."""
        return topic

    def _setup_auth(self):
        """To be implemented for each provider."""
        raise NotImplementedError

    def _setup_callbacks(self):
        """Connect the various MQTT client callbacks."""
        self._client.on_connect = self.on_connect
        self._client.on_disconnect = self.on_disconnect
        self._client.on_message = self.on_message
        self._client.on_publish = self.on_publish
        self._client.on_subscribe = self.on_subscribe

    def _update_auth(self):
        """To be reimplemented for providers with specific auth updates."""
        return

    def disconnect(self):
        self._client.disconnect()
        self._client.loop_stop()

    def on_connect(
        self,
        unused_client,
        unused_userdata,
        unused_flags,
        reasonCode,
        properties
    ):
        """Callback for when a device connects."""
        logger.debug(f"Connection outcome: {reasonCode}")
        self.connected = True
        if self.publisher:
            self._client.subscribe(self._get_topic_path("commands"), qos=0)
            # QoS = 1 because we want to be sure it is received.
            self._client.subscribe(self._get_topic_path("config"), qos=1)
        else:
            self._client.subscribe(self._get_topic_path("debug"), qos=1)
            self._client.subscribe(self._get_topic_path("error"), qos=1)
            self._client.subscribe(self._get_topic_path("location"), qos=1)

    def on_disconnect(
        self,
        unused_client,
        unused_userdata,
        reasonCode,
        properties
    ):
        """Callback for when a device disconnects."""
        # There is a bug in paho.mqtt where the reasonCode passed to
        # on_disconnect is an internal error code, even when using MQTTv5.
        # See https://github.com/eclipse/paho.mqtt.python/issues/659
        if not isinstance(reasonCode, mqtt.ReasonCodes):
            reasonCode = mqtt.error_string(reasonCode)
        logger.debug(f"Disconnection outcome: {reasonCode}")
        self.connected = False

    def on_message(self, unused_client, unused_userdata, message):
        """Callback when the device receives a message on a subscription."""
        payload = str(message.payload.decode('utf-8'))
        logger.debug(
            f"Received message '{payload}' "
            f"on topic '{message.topic}' with Qos {message.qos}"
        )

    def on_publish(self, unused_client, unused_userdata, unused_mid):
        """Callback when a message is sent to the broker."""
        logger.debug("Successfully published.")

    def on_subscribe(
        self,
        unused_client,
        unused_userdata,
        unused_mid,
        reasonCodes,
        properties
    ):
        """Callback when the client subscribes to a topic."""
        logger.debug(f"Subscription outcome: {reasonCodes[0]}.")

    def publish(self, topic, msg):
        """Publish to the MQTT topic (QoS=1)."""
        self._update_auth()
        props = mqtt.Properties(PacketTypes.PUBLISH)
        now_str = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        props.UserProperty = [
            ('client_id', self.client_id),
            ('timestamp', now_str)
        ]
        self._client.publish(
            self._get_topic_path(topic),
            msg,
            qos=1,
            properties=props
        )

    def reinitialise(self):
        self.connected = False
        self._client.reinitialise(client_id=self.client_id)
        self._setup_callbacks()
        # Connect.
        self._setup_auth()
        return self._client.connect(self.host, self.port)

    def start(self):
        self._client.loop_start()


class AWSClient(CloudClient):
    def __init__(
        self,
        client_id: str,
        host: str,
        port: int,
        ca_certs: Path,
        device_cert: Path,
        device_private_key: Path,
        publisher: bool = True
    ):
        # Attributes used for authentication.
        self.device_cert = device_cert
        self.device_private_key = device_private_key
        super().__init__(client_id, host, port, ca_certs, publisher)

    def _get_topic_path(self, topic: str) -> str:
        if topic in ("commands", "config"):
            return f"{topic}/{self.client_id}"
        return topic

    def _setup_auth(self):
        self._client.tls_set(
            ca_certs=self.ca_certs,
            certfile=self.device_cert,
            keyfile=self.device_private_key,
            tls_version=ssl.PROTOCOL_TLSv1_2
        )


def create_jwt(
    project_id: str,
    private_key_file: Path,
    algorithm: str,
    expiration_min: int
):
    """Creates a JWT (https://jwt.io) to establish an MQTT connection.

    Parameters
    ----------
    project_id : str
      The cloud project ID this device belongs to
    private_key_file : Path or str
      A path to a file containing either an RSA256 or ES256 private key.
    algorithm : ('RS256', 'ES256')
      The encryption algorithm to use.
    expiration_min : int
      After how many minutes the JWT expires.

    Returns
    -------
    A JWT generated from the given project_id and private key, which
    expires after X minutes. After X minutes, your client will be
    disconnected, and a new JWT will have to be generated.

    Raises
    ------
    ValueError
      If the private_key_file does not contain a known key.
    """
    token = {
        # The time that the token was issued at.
        'iat': datetime.datetime.now(tz=datetime.timezone.utc),
        # The time the token expires.
        'exp': (
            datetime.datetime.now(tz=datetime.timezone.utc)
            + datetime.timedelta(minutes=expiration_min)
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


class GoogleClient(CloudClient):
    def __init__(
        self,
        project_id: str,
        cloud_region: str,
        registry_id: str,
        device_id: str,
        host: str,
        port: int,
        ca_certs: Path,
        device_private_key: Path,
        algorithm,
        jwt_expires_minutes: int,
        publisher: bool = True
    ):
        # Attributes used for authentication.
        self.project_id = project_id
        self.device_private_key = device_private_key
        self.algorithm = algorithm
        self.jwt_iat = time.time()
        self.jwt_expires_mins = jwt_expires_minutes
        # Attribute used for topic paths.
        self._paths = {
            'commands': f"/devices/{device_id}/commands/#",
            'config': f"/devices/{device_id}/config",
        }
        for topic in ("debug", "default", "error", "location"):
            self._paths[topic] = f"/devices/{device_id}/events/{topic}"
        # The client_id is a unique string that identifies this device. For
        # Google Cloud IoT, it must be in the format below.
        self.client_id = (
            f"projects/{project_id}/locations/{cloud_region}/"
            f"registries/{registry_id}/devices/{device_id}"
        )
        super().__init__(self.client_id, host, port, ca_certs, publisher)

    def _get_topic_path(self, topic: str) -> str:
        return self._paths[topic]

    def _setup_auth(self):
        # With Google Cloud IoT, the username field is ignored, and the
        # password field is used to transmit a JWT to authorize the device.
        self._client.username_pw_set(
            username="unused",
            password=create_jwt(
                self.project_id,
                self.device_private_key,
                self.algorithm,
                self.jwt_expires_mins
            )
        )
        # Enable SSL/TLS support.
        self._client.tls_set(
            ca_certs=self.ca_certs,
            tls_version=ssl.PROTOCOL_TLSv1_2
        )

    def _update_auth(self):
        """To be reimplemented for providers with specific auth updates."""
        # Refresh the JWT if it is too old.
        seconds_since_issue = time.time() - self.jwt_iat
        if seconds_since_issue > 60 * self.jwt_expires_mins:
            logger.debug(
                f"Refreshing token after {seconds_since_issue/60} min"
            )
            self.disconnect()
            self.jwt_iat = time.time()
            self.reinitialise()
            self.start()
