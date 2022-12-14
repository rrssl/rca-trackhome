"""Cloud IoT publishing client."""
import logging

from trkpy.cloud import CloudClient

logger = logging.getLogger(__name__)


class CloudHandler(logging.Handler):
    """Publishes logs to the cloud."""

    def __init__(
        self,
        client: CloudClient,
        level=logging.NOTSET
    ):
        super().__init__(level)
        self.client = client
        self.client.start()
        logger.debug("Cloud logger initialized.")

    def emit(self, record: logging.LogRecord):
        # Publish record to the MQTT topic.
        if record.levelno == logging.INFO:
            topic = "location"
        elif record.levelno == logging.DEBUG:
            topic = "debug"
        elif record.levelno == logging.ERROR:
            topic = "error"
        else:
            topic = "default"
        self.client.publish(topic, record.getMessage())
