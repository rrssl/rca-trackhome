"""
Collect and save telemetry from Google Cloud Pub/Sub topics.
"""
import argparse
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from trkpy.collect import CloudIOTCollector


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
        "--collect_every",
        default=60,
        type=int,
        help="Collection interval (in seconds). Default: 60",
    )
    parser.add_argument(
        "--write_after",
        default=300,
        type=int,
        help="Flush logs older than this amount (in seconds). Default: 300",
    )
    parser.add_argument(
        "--timeout",
        default=3,
        type=int,
        help="Timeout for requests (in seconds). Default: 3",
    )

    return parser


def get_config():
    aconf = get_arg_parser().parse_args()
    with open(aconf.config, 'r') as stream:
        fconf = yaml.safe_load(stream)
    return vars(aconf) | fconf


def main():
    """Entry point."""
    conf = get_config()
    auth_dir = Path(conf['global']['auth_dir'])
    conf['pull']['service_account_json'] = (
        auth_dir / conf['pull']['service_account_json']
    )
    out_dir = Path(conf['global']['out_dir'])
    subscriptions = ['location', 'error', 'debug']
    types = ['json', 'str', 'str']
    collector = CloudIOTCollector(
        subscriptions,
        types,
        flush_dir=out_dir,
        project_id=conf['cloud']['project_id'],
        service_account_json=conf['pull']['service_account_json'],
        timeout=conf['timeout']
    )
    collect_every = conf['collect_every']
    write_after = timedelta(seconds=conf['write_after'])
    try:
        while True:
            collector.collect()
            write_time = datetime.now(timezone.utc) - write_after
            collector.flush(older_than=write_time)
            time.sleep(collect_every)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
