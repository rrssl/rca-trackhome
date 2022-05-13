"""
Pulling messages from Google Cloud Pub/Sub topics.
"""
import argparse
import json
from datetime import datetime

from google.cloud import pubsub_v1


def parse_command_line_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=__doc__
    )
    parser.add_argument(
        "--service_account_json",
        required=True,
        help="Path to the service account JSON file",
    )
    parser.add_argument(
        "--project_id",
        required=True,
        help="Google Cloud Platform project name",
    )
    parser.add_argument(
        "--subscription_topic",
        required=True,
        help="Pub/Sub topic to pull messages from.",
    )
    parser.add_argument(
        "--timeout",
        default=5,
        type=int,
        help="Timeout for requests.",
    )
    parser.add_argument(
        "--cloud_region", default="us-central1", help="GCP cloud region"
    )

    return parser.parse_args()


def main():
    """Entry point."""
    args = parse_command_line_args()
    subscriber = pubsub_v1.SubscriberClient.from_service_account_json(
        args.service_account_json
    )
    # The `subscription_path` method creates a fully qualified identifier
    # in the form `projects/{project_id}/subscriptions/{subscription_id}`
    subscription_path = subscriber.subscription_path(
        args.project_id,
        args.subscription_topic
    )

    def callback(message: pubsub_v1.subscriber.message.Message) -> None:
        data = json.loads(message.data)
        data['t'] = datetime.utcfromtimestamp(
            data['t'] / 1000
        ).strftime('%Y-%m-%d %H:%M:%S')
        print(f"Received {json.dumps(data, indent=2)}.")
        # message.ack()

    streaming_pull_future = subscriber.subscribe(
        subscription_path,
        callback=callback
    )
    print(f"Listening for messages on {subscription_path}...\n")

    # Wrap subscriber in a 'with' to automatically call close() when done.
    with subscriber:
        try:
            # When `timeout` is not set, result() will block indefinitely,
            # unless an exception is encountered first.
            streaming_pull_future.result(timeout=args.timeout)
        except TimeoutError:
            streaming_pull_future.cancel()  # Trigger the shutdown.
            streaming_pull_future.result()  # Block until shutdown is complete.


if __name__ == "__main__":
    main()
