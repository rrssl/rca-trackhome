"""
Pulling messages from Google Cloud Pub/Sub topics.
"""
import argparse
import json
import time
from concurrent import futures
from datetime import datetime, timedelta, timezone
from operator import itemgetter, methodcaller

import yaml
from google.cloud.pubsub_v1 import SubscriberClient
from google.cloud.pubsub_v1.subscriber.message import Message


def get_arg_parser():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=__doc__
    )
    parser.add_argument(
        "--config",
        metavar="FILE",
        required=True,
        help="Path to the YAML config file."
    )
    parser.add_argument(
        "--timeout",
        default=3,
        type=int,
        help="Timeout for requests.",
    )

    return parser


def get_config():
    aconf = get_arg_parser().parse_args()
    with open(aconf.config, 'r') as stream:
        fconf = yaml.safe_load(stream)
    return vars(aconf) | fconf


class CloudIOTCollector:
    """Periodically collects all the logs published on the cloud"""

    def __init__(
        self,
        subscriptions: list[str],
        dtypes: list[str],
        project_id: str,
        service_account_json: str,
        timeout: int
    ):
        self._subscriptions = subscriptions
        self._dtypes = dtypes
        self.project_id = project_id
        self.service_account_json = service_account_json
        self.timeout = timeout
        self._sub_buffers = {sub: [] for sub in subscriptions}

    def _get_subscription_cb(self, dtype: str):
        if dtype == 'json':
            decode = json.loads
        else:
            decode = methodcaller('decode', 'utf-8')

        def callback(message: Message):
            data = decode(message.data)
            sub = message.attributes['subFolder']
            device = message.attributes['deviceId']
            pubtime = message.publish_time
            self._sub_buffers[sub].append((data, device, pubtime))
            # message.ack()

        return callback

    def collect(self):
        subscriber = SubscriberClient.from_service_account_json(
            self.service_account_json
        )
        # The `subscription_path` method creates a fully qualified identifier
        # in the form `projects/{project_id}/subscriptions/{subscription_id}`
        pull_futures = [
            subscriber.subscribe(
                subscription=subscriber.subscription_path(
                    self.project_id, sub
                ),
                callback=self._get_subscription_cb(dtype)
            )
            for sub, dtype in zip(self._subscriptions, self._dtypes)
        ]
        # Wrap subscriber in a 'with' to automatically call close() when done.
        with subscriber:
            for future in pull_futures:
                try:
                    # When `timeout` is not set, result() will block
                    # indefinitely, unless an exception is encountered first.
                    future.result(timeout=self.timeout)
                except futures.TimeoutError:
                    future.cancel()  # Trigger the shutdown.
                    future.result()  # Block until shutdown is complete.
        # Process the collected logs.
        for sub, buffer in self._sub_buffers.items():
            buffer.sort(key=itemgetter(2))  # sort by pubtime, in place

    def flush(self, older_than: datetime = None):
        for sub, buffer in self._sub_buffers.items():
            if older_than is not None:
                buffer = [row for row in buffer if row[2] <= older_than]
            for data, device, pubtime in buffer:
                if isinstance(data, dict):
                    data = data.copy()
                    data['t'] = datetime.fromtimestamp(
                        data['t'] / 1000, timezone.utc
                    ).strftime('%Y-%m-%d %H:%M:%S %Z')
                    data = json.dumps(data, indent=2)
                pubtime = pubtime.strftime('%Y-%m-%d %H:%M:%S %Z')
                print(
                    f"Received '{data}' in '{sub}' "
                    f"sent from {device} @ {pubtime}"
                )


def main():
    """Entry point."""
    conf = get_config()
    subscriptions = ['location', 'debug']
    types = ['json', 'str']
    collector = CloudIOTCollector(
        subscriptions,
        types,
        project_id=conf['pull']['project_id'],
        service_account_json=conf['pull']['service_account_json'],
        timeout=conf['timeout']
    )
    delta = timedelta(minutes=5)
    for _ in range(1):
        collector.collect()
        collector.flush(older_than=datetime.now(timezone.utc)-delta)
        time.sleep(3)


if __name__ == "__main__":
    main()
