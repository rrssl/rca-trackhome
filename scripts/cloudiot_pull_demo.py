"""
Pulling messages from Google Cloud Pub/Sub topics.
"""
import argparse
import json
import time
from concurrent import futures
from csv import DictWriter
from datetime import datetime, timedelta, timezone
from operator import itemgetter, methodcaller
from pathlib import Path

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
        flush_dir: Path,
        project_id: str,
        service_account_json: str,
        timeout: int
    ):
        self._subscriptions = subscriptions
        self._dtypes = dtypes
        self.flush_dir = flush_dir
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
            message.ack()

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
            # Split the buffer between what to keep and what to flush.
            if older_than is not None:
                try:
                    # Find the first element more recent than `older_than`.
                    split = next(
                        i for i, (_, _, pubtime) in enumerate(buffer)
                        if pubtime > older_than
                    )
                except StopIteration:
                    # Nothing in the buffer is more recent than `older_than`.
                    split = len(buffer)
            else:
                split = len(buffer)
            if split == 0:
                # Nothing in the buffer is older than `older_than`.
                continue
            to_flush = buffer[:split]
            self._sub_buffers[sub] = buffer[split:]
            # Format the data for flushing to CSV.
            rows = []
            for data, device, pubtime in to_flush:
                row = {'device': device, 'pubtime': pubtime.timestamp()}
                if isinstance(data, dict):
                    row.update(data)
                else:
                    row['message'] = data
                rows.append(row)
                # log = row.copy()
                # log['t'] = datetime.fromtimestamp(
                #     row['t'] / 1000, timezone.utc
                # ).strftime('%Y-%m-%d %H:%M:%S %Z')
                # log['pubtime'] = pubtime.strftime('%Y-%m-%d %H:%M:%S %Z')
                # print(json.dumps(log, indent=2))
            # Write the CSV file.
            flush_path = self.flush_dir / f"{sub}.csv"
            write_header = not flush_path.exists()
            with open(flush_path, 'a', newline='') as stream:
                writer = DictWriter(stream, fieldnames=row.keys())
                if write_header:
                    writer.writeheader()
                writer.writerows(rows)


def main():
    """Entry point."""
    conf = get_config()
    out_dir = Path(conf['global']['out_dir'])
    subscriptions = ['location', 'debug']
    types = ['json', 'str']
    collector = CloudIOTCollector(
        subscriptions,
        types,
        flush_dir=out_dir,
        project_id=conf['pull']['project_id'],
        service_account_json=conf['pull']['service_account_json'],
        timeout=conf['timeout']
    )
    delta = timedelta(minutes=5)
    for _ in range(2):
        collector.collect()
        collector.flush(older_than=datetime.now(timezone.utc)-delta)
        time.sleep(3)


if __name__ == "__main__":
    main()
